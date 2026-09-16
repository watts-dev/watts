# SPDX-FileCopyrightText: 2022-2025 UChicago Argonne, LLC
# SPDX-License-Identifier: MIT

import math
from pathlib import Path
import re
import sys
from typing import List, Optional

import pandas as pd

from .fileutils import PathLike
from .plugin import PluginGeneric, _find_executable
from .results import Results


class PluginACCERT(PluginGeneric):
    """Plugin for running ACCERT

    Parameters
    ----------
    template_file
        Templated ACCERT input
    executable
        Path to ACCERT Main.py script
    extra_inputs
        List of extra (non-templated) input files that are needed
    extra_template_inputs
        Extra templated input files
    show_stdout
        Whether to display output from stdout when ACCERT is run
    show_stderr
        Whether to display output from stderr when ACCERT is run

    Attributes
    ----------
    executable
        Path to ACCERT executable

    """

    def __init__(self, template_file: str,
                 executable: PathLike = 'Main.py',
                 extra_inputs: Optional[List[str]] = None,
                 extra_template_inputs: Optional[List[PathLike]] = None,
                 show_stdout: bool = False, show_stderr: bool = False):
        executable = _find_executable(executable, 'ACCERT_DIR')
        execute_command = [sys.executable, '{self.executable}', '-i', '{self.input_name}']
        super().__init__(executable, execute_command, template_file, extra_inputs,
                         extra_template_inputs, "ACCERT", show_stdout, show_stderr)
        self.input_name = "ACCERT_input.son"

    @PluginGeneric.executable.setter
    def executable(self, exe: PathLike):
        if not exe.is_file():
            raise RuntimeError(
                f"{self.plugin_name} module '{exe}' does not exist. The "
                "ACCERT_DIR environment variable needs to be set to a directory "
                "containing the Main.py module."
            )
        self._executable = Path(exe)


class ResultsACCERT(Results):
    """ACCERT simulation results

    Parameters
    ----------
    params
        Parameters used to generate inputs
    exec_info
        Execution information (job ID, plugin name, time, etc.)
    inputs
        List of input files
    outputs
        List of output files

    Attributes
    ----------
    ref_model
        Name of the ACCERT reference model that was run
    account_table
        ACCERT results of account table
    cost_element_table
        ACCERT results of updated cost elements
    affected_cost_element_table
        ACCERT results of cost elements affected by user-defined variables
    occ_table
        ACCERT overnight capital cost (OCC) summary
    lcoe_table
        ACCERT breakdown of the levelized cost of electricity
    lcoe
        Levelized cost of electricity in $/MWh
    total_cost
        ACCERT results of total cost
    total_calculated_direct_cost
        Direct cost calculated from the accounts in the input
    total_direct_cost
        Total direct cost of the plant
    total_indirect_costs
        Total indirect services cost
    total_cost_without_owner
        Sum of direct and indirect costs
    owner_cost
        Owner's cost
    total_OCC
        Total overnight capital cost
    escalated_dollar_year
        Dollar year that escalated costs are reported in
    total_OCC_escalated
        Total overnight capital cost, escalated to :attr:`escalated_dollar_year`
    total_OCC_per_kW
        Escalated total overnight capital cost per kW of electric capacity

    """

    # Fraction of the total direct cost that ACCERT calculates explicitly for
    # each reference model. Used only when the OCC summary written by ACCERT
    # 2.0 and later is unavailable, in which case the OCC is reconstructed from
    # the account table the same way ACCERT does it internally.
    _DIRECT_COST_FRACTIONS = {
        'abr1000': 0.834,
        'heatpipe': 0.834,
        'lfr': 0.834,
    }
    _DEFAULT_DIRECT_COST_FRACTION = 1.0
    _INDIRECT_COST_FACTOR = 0.609
    _OWNER_COST_FRACTION = 0.2

    # Output file written by ACCERT 2.0 and later, followed by the equivalent
    # file written by earlier versions
    _ACCOUNT_FILES = ('*_upd_acc_*.csv', '*_updated_account.xlsx')
    _COST_ELEMENT_FILES = ('*_upd_ce_*.csv', '*_updated_cost_element.xlsx')
    _AFFECTED_COST_ELEMENT_FILES = (
        '*_aff_ce_*.csv', '*_variable_affected_cost_elements.xlsx')
    _OCC_FILES = ('*_post_*.csv',)
    _LCOE_FILES = ('*_LCOE_results.xlsx',)

    def _output_file(self, patterns) -> Optional[Path]:
        """Return most recent output file matching the first pattern that hits

        ACCERT names its output files with a ``%Y%m%d_%H%M%S`` timestamp, so
        sorting the matches alphabetically puts the most recent one last.

        Parameters
        ----------
        patterns
            Glob patterns to look for, in order of preference

        Returns
        -------
        Matching path, or None if no pattern matched

        """
        for pattern in patterns:
            matches = sorted(self.base_path.glob(pattern))
            if matches:
                return matches[-1]
        return None

    def _read_table(self, patterns, description: str) -> pd.DataFrame:
        """Read an ACCERT output table into a dataframe

        Parameters
        ----------
        patterns
            Glob patterns to look for, in order of preference
        description
            Human-readable name of the table, used in the error message

        Returns
        -------
        Dataframe with the contents of the table

        """
        path = self._output_file(patterns)
        if path is None:
            raise FileNotFoundError(f'ACCERT {description} not found')
        if path.suffix == '.xlsx':
            return pd.read_excel(path)
        return pd.read_csv(path)

    @property
    def ref_model(self) -> Optional[str]:
        path = self._output_file(self._ACCOUNT_FILES)
        if path is None:
            return None
        match = re.fullmatch(
            r'(?P<model>.+?)_(?:upd_acc_\d{8}_\d{6}|updated_account)',
            path.stem)
        return match['model'] if match is not None else None

    @property
    def account_table(self) -> pd.DataFrame:
        return self._read_table(self._ACCOUNT_FILES, 'account table')

    @property
    def cost_element_table(self) -> pd.DataFrame:
        return self._read_table(self._COST_ELEMENT_FILES, 'cost element table')

    @property
    def affected_cost_element_table(self) -> pd.DataFrame:
        return self._read_table(self._AFFECTED_COST_ELEMENT_FILES,
                                'affected cost element table')

    @property
    def occ_table(self) -> pd.DataFrame:
        """Overnight capital cost summary, indexed by metric

        The summary is written by ACCERT 2.0 and later when the input file
        requests it with ``post_process { occ = true }``.
        """
        if self._output_file(self._OCC_FILES) is None:
            raise FileNotFoundError(
                'ACCERT overnight capital cost summary not found. It is '
                'written by ACCERT 2.0 and later when the input file contains '
                '"post_process { occ = true }".')
        return self._read_table(
            self._OCC_FILES, 'overnight capital cost summary').set_index('metric')

    @property
    def lcoe_table(self) -> pd.DataFrame:
        """Levelized cost of electricity breakdown, indexed by variable

        ACCERT calculates the levelized cost of electricity for its fusion
        reference models only.
        """
        return self._read_table(
            self._LCOE_FILES, 'levelized cost of electricity breakdown'
        ).set_index('Variable')

    @property
    def lcoe(self) -> float:
        """Levelized cost of electricity in $/MWh"""
        return float(self.lcoe_table.at['coe', 'Value'])

    @property
    def total_cost(self) -> float:
        """Total direct cost of the accounts calculated by ACCERT"""
        table = self.account_table
        # Account 2 holds the total direct cost. ACCERT pads the code of
        # account with leading spaces to indicate its level in the hierarchy.
        direct = table[table['code_of_account'].astype(str).str.strip() == '2']
        if not direct.empty:
            return float(direct['total_cost'].values[0])
        return float(table['total_cost'].values[0])

    def _occ(self, metric: str) -> float:
        """Return an overnight capital cost metric in reference-year dollars

        Parameters
        ----------
        metric
            Name of the metric as reported by ACCERT

        Returns
        -------
        Value of the metric in dollars

        """
        if self._output_file(self._OCC_FILES) is not None:
            return float(self.occ_table.at[metric, 'value_dollar'])

        # ACCERT versions before 2.0 don't write an OCC summary, so
        # reconstruct it from the account table
        fraction = self._DIRECT_COST_FRACTIONS.get(
            self.ref_model, self._DEFAULT_DIRECT_COST_FRACTION)
        calculated_direct_cost = self.total_cost
        direct_cost = calculated_direct_cost / fraction
        indirect_costs = direct_cost * self._INDIRECT_COST_FACTOR
        cost_without_owner = direct_cost + indirect_costs
        owner_cost = cost_without_owner * self._OWNER_COST_FRACTION
        return {
            'total_calculated_direct_cost': calculated_direct_cost,
            'total_direct_cost': direct_cost,
            'total_indirect_costs': indirect_costs,
            'total_cost_without_owner': cost_without_owner,
            'owner_cost': owner_cost,
            'total_OCC': cost_without_owner + owner_cost,
        }[metric]

    @property
    def total_calculated_direct_cost(self) -> float:
        return self._occ('total_calculated_direct_cost')

    @property
    def total_direct_cost(self) -> float:
        return self._occ('total_direct_cost')

    @property
    def total_indirect_costs(self) -> float:
        return self._occ('total_indirect_costs')

    @property
    def total_cost_without_owner(self) -> float:
        """Direct cost + indirect costs"""
        return self._occ('total_cost_without_owner')

    @property
    def owner_cost(self) -> float:
        return self._occ('owner_cost')

    @property
    def total_OCC(self) -> float:
        """Total OCC = total cost without owner + owner cost"""
        return self._occ('total_OCC')

    def _escalated_column(self, table: pd.DataFrame, quantity: str) -> str:
        """Return the name of an escalated column in the OCC summary

        ACCERT 2.0 reports escalated costs in columns named after the target
        dollar year, e.g. ``value_2024_dollar``; later versions use a generic
        ``value_escalated_dollar``.

        Parameters
        ----------
        table
            Overnight capital cost summary
        quantity
            Suffix of the column, e.g. 'dollar' or 'dollar_per_kw'

        Returns
        -------
        Name of the matching column

        """
        column = f'value_escalated_{quantity}'
        if column in table.columns:
            return column
        pattern = re.compile(rf'value_\d{{4}}_{re.escape(quantity)}')
        for candidate in table.columns:
            if pattern.fullmatch(candidate):
                return candidate
        raise KeyError(
            f"No escalated '{quantity}' column in ACCERT overnight capital "
            "cost summary")

    @property
    def escalated_dollar_year(self) -> int:
        table = self.occ_table
        if 'escalated_dollar_year' in table.columns:
            return int(table['escalated_dollar_year'].values[0])
        column = self._escalated_column(table, 'dollar')
        return int(re.search(r'\d{4}', column).group())

    @property
    def total_OCC_escalated(self) -> float:
        table = self.occ_table
        return float(table.at['total_OCC', self._escalated_column(table, 'dollar')])

    @property
    def total_OCC_per_kW(self) -> float:
        table = self.occ_table
        column = self._escalated_column(table, 'dollar_per_kw')
        value = float(table.at['total_OCC', column])
        if math.isnan(value):
            # ACCERT leaves this column empty when the reference model does not
            # define an electric power, which is the case for its fusion models
            raise ValueError(
                f'ACCERT did not report a cost per kW for the {self.ref_model} '
                'reference model because the model does not define an electric '
                'power output'
            )
        return value
