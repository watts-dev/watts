# SPDX-FileCopyrightText: 2026 UChicago Argonne, LLC
# SPDX-License-Identifier: MIT

"""Focused integration tests for the two fuel-cycle plugin boundaries.

The native readers are replaced with tiny closeable objects where the test is
about WATTS result lifecycle.  This keeps the tests fast and makes relocation
or serialization failures independent of either simulator's output schema.
"""

import inspect
import json
import os
from pathlib import Path

import h5py
import numpy as np
import pytest

from watts.enrichment_utils import enrichment_cascade
from watts.fuel_cycle_utils import SECONDS_PER_YEAR
from watts.parameters import Parameters
from watts.plugin import _find_executable
from watts.plugin_cyclus import CyclusOutput, ResultsCyclus
from watts.plugin_dymond import (
    DYMONDOutput,
    PluginDYMOND,
    ResultsDYMOND,
    _default_dymond_executable,
)
from watts.results import ExecInfo, Results


class _Reader:
    """Record the path and whether WATTS closed a native reader."""

    def __init__(self, path):
        self.path = Path(path)
        self.closed = False

    def close(self):
        self.closed = True


def _exec_info(plugin):
    """Make stable execution metadata for result-wrapper tests."""

    return ExecInfo(1, plugin, "fuel-cycle-test", 0)


@pytest.mark.parametrize(
    "result_class, module_name, reader_name, suffix, plugin_name",
    [
        (
            ResultsCyclus,
            "watts.plugin_cyclus",
            "CyclusOutput",
            ".sqlite",
            "Cyclus",
        ),
        (
            ResultsDYMOND,
            "watts.plugin_dymond",
            "DYMONDOutput",
            ".h5",
            "DYMOND",
        ),
    ],
)
def test_fuel_cycle_result_reader_follows_file_relocation(
    tmp_path,
    monkeypatch,
    result_class,
    module_name,
    reader_name,
    suffix,
    plugin_name,
):
    output = tmp_path / f"result{suffix}"
    output.touch()
    readers = []

    def make_reader(path):
        reader = _Reader(path)
        readers.append(reader)
        return reader

    monkeypatch.setattr(f"{module_name}.{reader_name}", make_reader)
    result = result_class(
        Parameters(), _exec_info(plugin_name), inputs=[], outputs=[output]
    )

    # Construction happens before Plugin moves output artifacts.  It must not
    # bind a reader to that temporary path.
    assert result._reader is None
    assert result.obj.path == output.resolve()

    destination = tmp_path / "database-result"
    destination.mkdir()
    first_reader = result.obj
    result.move_files(destination)

    assert first_reader.closed
    assert result._reader is None
    assert result.outputs == [destination / output.name]
    assert result.obj.path == (destination / output.name).resolve()
    assert len(readers) == 2


@pytest.mark.parametrize(
    "result_class, module_name, reader_name, suffix, plugin_name",
    [
        (
            ResultsCyclus,
            "watts.plugin_cyclus",
            "CyclusOutput",
            ".sqlite",
            "Cyclus",
        ),
        (
            ResultsDYMOND,
            "watts.plugin_dymond",
            "DYMONDOutput",
            ".h5",
            "DYMOND",
        ),
    ],
)
def test_fuel_cycle_result_pickle_contains_metadata_not_native_reader(
    tmp_path,
    monkeypatch,
    result_class,
    module_name,
    reader_name,
    suffix,
    plugin_name,
):
    output = tmp_path / f"result{suffix}"
    output.touch()
    readers = []

    def make_reader(path):
        reader = _Reader(path)
        readers.append(reader)
        return reader

    monkeypatch.setattr(f"{module_name}.{reader_name}", make_reader)
    result = result_class(
        Parameters(), _exec_info(plugin_name), inputs=[], outputs=[output]
    )
    live_reader = result.obj
    pickle_path = tmp_path / "result.pkl"

    result.save(pickle_path)
    restored = Results.from_pickle(pickle_path)

    # Saving does not unexpectedly close an object still in use, while the
    # restored result starts without stale SQLite/HDF5 state.
    assert not live_reader.closed
    assert restored._reader is None
    assert restored.obj.path == output.resolve()
    assert len(readers) == 2


def test_deployed_capacity_has_the_same_default_in_both_adapters():
    cyclus_default = inspect.signature(
        CyclusOutput.get_deployed_capacity
    ).parameters["return_sum"].default
    dymond_default = inspect.signature(
        DYMONDOutput.get_deployed_capacity
    ).parameters["return_sum"].default

    assert cyclus_default is True
    assert dymond_default is True


def _bare_dymond_output():
    """Build an in-memory reader for methods that need no native HDF5 rows."""

    output = object.__new__(DYMONDOutput)
    output.reactor_types = ["LWR"]
    output.type_names = {"reactor": ["LWR"]}
    output.input_data = {
        "Model": {"units": {"power": "MW", "mass": "tonnes"}},
        "Types": {
            "reactor": [
                {
                    "name": "LWR",
                    "capacity factor": 0.8,
                    "power": 1000.0,
                }
            ]
        },
    }
    output.operations = {"times": np.asarray([0.0, 1.0])}
    output.stocks = {}
    output.flows = {}
    return output


def test_dymond_generated_power_empty_selection_is_a_time_series():
    output = _bare_dymond_output()

    result = output.get_generated_power(reactors=[], return_sum=True)

    np.testing.assert_array_equal(result, [0.0, 0.0])
    assert result.shape == (2,)


def test_dymond_generated_power_rejects_unknown_reactors():
    output = _bare_dymond_output()

    with pytest.raises(ValueError, match="Unknown reactor.*HTGR"):
        output.get_generated_power(reactors=["HTGR"])


def test_dymond_missing_operating_state_uses_documented_fallback(monkeypatch):
    output = _bare_dymond_output()
    # The reactor group exists, but the state itself does not.  That was once
    # interpreted as real zero production instead of missing report data.
    output.operations["reactor"] = {"LWR": {}}
    monkeypatch.setattr(
        output,
        "get_deployed_capacity",
        lambda facilities, facility_class, return_sum: np.asarray([1.0, 2.0]),
    )

    result = output.get_generated_power(reactors=["LWR"], return_sum=True)

    np.testing.assert_allclose(result, [0.8, 1.6])


def test_dymond_portable_fuel_demand_converts_model_mass_to_kg(monkeypatch):
    output = _bare_dymond_output()
    monkeypatch.setattr(
        output,
        "_get_flow",
        lambda reactor, facility_class, location, direction, config: (
            np.asarray([1.0, 2.0])
        ),
    )

    result = output.stock_fuel_demand(reactors=["LWR"], return_sum=True)

    np.testing.assert_array_equal(result, [1000.0, 2000.0])


def test_find_executable_uses_normal_path_when_hint_is_unset(
    tmp_path, monkeypatch
):
    executable = tmp_path / "DYMOND_linux.sh"
    executable.touch()
    monkeypatch.delenv("DYMOND_DIR", raising=False)
    monkeypatch.setattr(
        "watts.plugin.shutil.which", lambda name: str(executable)
    )

    assert _find_executable(executable.name, "DYMOND_DIR") == executable


def test_find_executable_uses_platform_path_separator(tmp_path, monkeypatch):
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    executable = second / "dymond-launcher"
    executable.touch()
    monkeypatch.setenv("DYMOND_DIR", os.pathsep.join((str(first), str(second))))

    assert _find_executable("dymond-launcher", "DYMOND_DIR") == (
        executable.resolve()
    )


def test_find_executable_accepts_an_absolute_path_without_environment(
    tmp_path, monkeypatch
):
    executable = (tmp_path / "explicit-launcher").resolve()
    monkeypatch.delenv("DYMOND_DIR", raising=False)

    assert _find_executable(executable, "DYMOND_DIR") == executable


def test_find_executable_reports_missing_and_ambiguous_hint_results(
    tmp_path, monkeypatch
):
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    monkeypatch.setenv("DYMOND_DIR", os.pathsep.join((str(first), str(second))))

    with pytest.raises(ValueError, match="was not found"):
        _find_executable("dymond-launcher", "DYMOND_DIR")

    (first / "dymond-launcher").touch()
    (second / "dymond-launcher").touch()
    with pytest.raises(ValueError, match="Found multiple copies"):
        _find_executable("dymond-launcher", "DYMOND_DIR")


def test_plugin_dymond_default_constructor_uses_path_fallback(
    tmp_path, monkeypatch
):
    launcher = tmp_path / _default_dymond_executable()
    launcher.touch()
    template = tmp_path / "input.json"
    template.write_text("{}")
    monkeypatch.delenv("DYMOND_DIR", raising=False)
    monkeypatch.setattr(
        "watts.plugin.shutil.which", lambda name: str(launcher)
    )

    plugin = PluginDYMOND(template)

    assert plugin.executable == launcher


def _minimal_dymond_input():
    """Return enough embedded input metadata to initialize a DYMOND reader."""

    return {
        "Model": {"units": {"time": "YEARS", "power": "MW"}},
        "Simulation": {"start year": 2030, "duration": 1},
        "Types": {},
    }


def test_dymond_reader_decodes_one_element_byte_array_input(tmp_path):
    output = tmp_path / "output.h5"
    encoded = json.dumps(_minimal_dymond_input()).encode("utf-8")
    with h5py.File(output, "w") as hdf5:
        group = hdf5.create_group("OUTPUT")
        # Some DYMOND/HDF5 versions write input as a one-element byte array
        # instead of a scalar byte string.  Both are valid representations.
        group.create_dataset("input", data=np.asarray([encoded]))
        operations = group.create_group("operations")
        operations.create_dataset("times", data=[0.0, 1.0])

    result = DYMONDOutput(output)

    assert result.get_input_dict() == _minimal_dymond_input()
    np.testing.assert_array_equal(result.years, [2030.0, 2031.0])


def test_dymond_reader_prepares_receipts_before_shared_calculation(
    tmp_path,
):
    output = tmp_path / "fuel-output.h5"
    input_data = _minimal_dymond_input()
    input_data["Model"]["units"]["mass"] = "tonnes"
    input_data["Types"] = {
        "reactor": [{"name": "LWR", "power": 1000.0}]
    }
    with h5py.File(output, "w") as hdf5:
        output_group = hdf5.create_group("OUTPUT")
        output_group.create_dataset(
            "input", data=json.dumps(input_data).encode("utf-8")
        )
        output_group.create_dataset(
            "nuclide_ids", data=np.asarray([b"u235", b"u238", b"o16"])
        )
        operations = output_group.create_group("operations")
        operations.create_dataset("times", data=[0.0, 1.0])

        # Raw process receipts live under reactor instances rather than
        # the aggregate OUTPUT reports.  This one 0.12-tonne receipt contains
        # 80% uranium at a 5% U-235 assay, so the cascade product basis must be
        # 96 kg uranium—not 120 kg total compound.
        process = (
            hdf5.create_group("Reactor")
            .create_group("LWR")
            .create_group("instance-1")
            .create_group("process")
        )
        process.create_dataset("times", data=[0.0 * SECONDS_PER_YEAR])
        process.create_dataset("masses", data=[0.12])
        process.create_dataset("compositions", data=[[0.04, 0.76, 0.20]])

    result = DYMONDOutput(output).stock_fuel_resources(
        reactors=["LWR"],
        natu_assay=0.00711,
        tails_assay=0.002,
        cascade_splits=[],
    )
    cascade = enrichment_cascade(0.00711, 0.05, 0.002, [np.inf])

    assert result["natu"][0] == pytest.approx(cascade["feed"][0] * 96.0)
    assert result["tails"][0] == pytest.approx(cascade["tails"][0] * 96.0)
    assert result["swu"][0] == pytest.approx(cascade["swu"][0] * 96.0)
    np.testing.assert_array_equal(result["natu"][1:], [0.0])


def test_dymond_reader_uses_typed_errors_for_invalid_output(tmp_path):
    missing = tmp_path / "missing.h5"
    with pytest.raises(FileNotFoundError, match="does not exist"):
        DYMONDOutput(missing)

    invalid = tmp_path / "invalid.h5"
    with h5py.File(invalid, "w"):
        pass
    with pytest.raises(ValueError, match="does not contain an OUTPUT group"):
        DYMONDOutput(invalid)
