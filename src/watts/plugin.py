# SPDX-FileCopyrightText: 2022 UChicago Argonne, LLC
# SPDX-License-Identifier: MIT

from abc import ABC, abstractmethod
from contextlib import redirect_stdout, redirect_stderr
from datetime import datetime
import uuid
from pathlib import Path
import shutil
import time
from typing import Optional, List, Union

from .database import Database
from .fileutils import cd_tmpdir, PathLike, tee_stdout, tee_stderr, run as run_proc
from .parameters import Parameters
from .results import Results
from .template import TemplateRenderer
import watts


class Plugin(ABC):
    """Class defining the Plugin interface

    Parameters
    ----------
    extra_inputs
        Extra (non-templated) input files
    show_stdout
        Whether to display output from stdout when :math:`run` is called
    show_stderr
        Whether to display output from stderr when :meth:`run` is called
    unit_system : {'si', 'cgs'}
        Unit system to convert to when rendering input files

    Attributes
    ----------
    plugin_name : str
        Name of the plugin
    unit_system : {'si', 'cgs'}
        Desired system of units for rendering templates

    """

    def __init__(
        self,
        extra_inputs: Optional[List[PathLike]] = None,
        show_stdout: bool = False,
        show_stderr: bool = False,
        unit_system: str = 'si'
    ):
        self.extra_inputs = []
        if extra_inputs is not None:
            self.extra_inputs = [Path(f).resolve() for f in extra_inputs]
        self.show_stdout = show_stdout
        self.show_stderr = show_stderr
        self.unit_system = unit_system

    @abstractmethod
    def prerun(self, params):
        ...

    @abstractmethod
    def run(self):
        ...

    @abstractmethod
    def postrun(self, params, name) -> Results:
        ...

    @property
    def plugin_name(self):
        return type(self).__name__[6:]

    def __call__(self, params: Parameters = None, name: str = 'Workflow', **kwargs) -> Results:
        """Run the complete workflow for the plugin

        Parameters
        ----------
        params
            Parameters used in generating inputs
        name
            Name for workflow
        **kwargs
            Keyword arguments passed to the `run` method

        Returns
        -------
        Results from running workflow
        """
        db = Database()
        plugin_name = self.plugin_name

        # Generate empty Parameters object if none provided
        if params is None:
            params = Parameters()

        with cd_tmpdir():
            # Copy extra inputs to temporary directory
            cwd = Path.cwd()
            for path in self.extra_inputs:
                shutil.copy(str(path), str(cwd))  # Remove str() for Python 3.8+

            # Generate input files and perform any other prerun actions
            self._run_time = time.time_ns()
            print(f"[watts] Calling prerun() for {plugin_name} Plugin")
            self.prerun(params)

            # Execute the code, redirecting stdout/stderr if requested
            print(f"[watts] Calling run() for {plugin_name} Plugin")
            with open(f'{plugin_name}_log.txt', 'w') as outfile:
                func_stdout = tee_stdout if self.show_stdout else redirect_stdout
                func_stderr = tee_stderr if self.show_stderr else redirect_stderr
                with func_stdout(outfile), func_stderr(outfile):
                    self.run(**kwargs)

            # Collect results and perform any postrun actions
            print(f"[watts] Calling postrun() for {plugin_name} Plugin")
            result = self.postrun(params, name)

            # Create new directory for results and move files there
            workflow_path = db.path / uuid.uuid4().hex
            workflow_path.mkdir()
            try:
                result.move_files(workflow_path)
            except Exception:
                # If error occurred, make sure we remove results directory so it
                # doesn't pollute database
                shutil.rmtree(workflow_path)
                raise

        # Add result to database
        db.add_result(result)

        return result


class PluginGeneric(Plugin):
    """Plugin that relies on generating a template file

    This class can be used to control the execution of an arbitrary executable,
    first rendering one or more templated input files.

    Parameters
    ----------
    executable
        Path to executable
    execute_command
        List of command-line arguments, where each is formatted using the
        instance of the class as ``self``. The first string normally indicates
        the executable, i.e. "{self.executable}". The rendered input file can be
        accessed as "{self.input_name}". A single string of command-line
        arguments is also accepted.
    template_file
        Path to template file
    extra_inputs
        Extra (non-templated) input files
    extra_template_inputs
        Extra templated input files
    show_stdout
        Whether to display output from stdout when :math:`run` is called
    show_stderr
        Whether to display output from stderr when :meth:`run` is called
    unit_system : {'si', 'cgs'}
        Unit system to convert to when rendering input files

    Attributes
    ----------
    executable
        Path to plugin executable
    execute_command
        List of command-line arguments used to call the executable

    """
    def __init__(self,
        executable: PathLike,
        execute_command: Union[List[str], str],
        template_file: PathLike,
        extra_inputs: Optional[List[PathLike]] = None,
        extra_template_inputs: Optional[List[PathLike]] = None,
        show_stdout: bool = False,
        show_stderr: bool = False,
        unit_system: str = 'si'
    ):
        super().__init__(extra_inputs, show_stdout, show_stderr, unit_system)
        self.render_template = TemplateRenderer(template_file)
        self.extra_render_templates = []
        self.input_name = 'input_rendered'
        if extra_template_inputs is not None:
            self.extra_render_templates = [TemplateRenderer(f, '') for f in extra_template_inputs]

        self.executable = executable
        if isinstance(execute_command, str):
            self._execute_command = execute_command.split()
        else:
            self._execute_command = execute_command

    @property
    def executable(self) -> Path:
        return self._executable

    @executable.setter
    def executable(self, exe: PathLike):
        if shutil.which(exe) is None:
            raise RuntimeError(f"{self.plugin_name} executable '{exe}' is missing.")
        self._executable = Path(exe)

    @property
    def execute_command(self) -> List[str]:
        return [item.format(self=self) for item in self._execute_command]

    def prerun(self, params: Parameters, filename: Optional[str] = None):
        """Render the template based on model parameters

        Parameters
        ----------
        params
            Parameters used to render template
        filename
            Filename for rendered template
        """
        # If the 'input_name' attribute is set, use that as default when
        # filename is not explicitly passed
        if filename is None and self.input_name is not None:
            filename = self.input_name

        # Make a copy of params and convert units if necessary -- the original
        # params remains unchanged
        params_copy = params.convert_units(system=self.unit_system)

        # Render the template
        self.render_template(params_copy, filename=filename)
        for render_template in self.extra_render_templates:
            render_template(params_copy)

    def postrun(self, params: Parameters, name: str, **kwargs) -> Results:
        """Read simulation results and create results object

        Parameters
        ----------
        params
            Parameters used to generate input files
        name
            Name of the plugin
        **kwargs
            Keyword arguments for Results subclasses

        Returns
        -------
        Results object
        """

        # Determine time, inputs and outputs
        time = datetime.fromtimestamp(self._run_time * 1e-9)
        inputs = [self.input_name] + [p.name for p in self.extra_inputs]
        for renderer in self.extra_render_templates:
            inputs.append(renderer.template_file.name)
        outputs = [p for p in Path.cwd().iterdir() if p.name not in inputs]

        # Get correct Results subclass and return instance
        results_cls = getattr(watts, f'Results{self.plugin_name}', Results)
        return results_cls(params, name, time, inputs, outputs, **kwargs)

    def run(self, mpi_args: Optional[List[str]] = None,
            extra_args: Optional[List[str]] = None):
        """Run plugin

        Parameters
        ----------
        mpi_args
            MPI execute command and any additional MPI arguments to pass,
            e.g. ['mpiexec', '-n', '8'].
        extra_args
            Additional command-line arguments to append after the main command

        """
        if mpi_args is None:
            mpi_args = []
        if extra_args is None:
            extra_args = []
        run_proc(mpi_args + self.execute_command + extra_args)
