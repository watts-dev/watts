# SPDX-FileCopyrightText: 2026 UChicago Argonne, LLC
# SPDX-License-Identifier: MIT

"""Tests for the simulator-neutral fuel-cycle contract.

These tests intentionally build plain arrays and common fuel receipts.  A
failure here therefore identifies a WATTS calculation problem, not a missing
Cyclus installation, a DYMOND license, or a change in either output format.
"""

from pathlib import Path

import dill
import numpy as np
import pytest

from watts.enrichment_utils import enrichment_cascade
from watts.fuel_cycle_utils import (
    CASCADE_SPLITS,
    FuelReceipt,
    NATURAL_ASSAY,
    ResultFileReader,
    SECONDS_PER_YEAR,
    TAILS_ASSAY,
    aggregate_calendar_years,
    calculate_fuel_resources,
    format_fuel_resource_results,
    format_reactor_results,
    find_single_output,
    mass_to_kg,
    select_reactors,
    power_to_gw,
    sum_reactor_series,
)


def test_find_single_output_selects_one_native_artifact_case_insensitively():
    outputs = [Path("run.log"), Path("fuel-cycle.H5")]

    assert find_single_output(outputs, (".h5", ".hdf5"), "HDF5") == (
        Path("fuel-cycle.H5")
    )


@pytest.mark.parametrize(
    "outputs, match",
    [
        ([Path("run.log")], "found 0"),
        ([Path("one.sqlite"), Path("two.sqlite")], "found 2"),
    ],
)
def test_find_single_output_rejects_missing_or_ambiguous_artifacts(
    outputs, match
):
    with pytest.raises(ValueError, match=match):
        find_single_output(outputs, ("sqlite",), "Cyclus SQLite")


@pytest.mark.parametrize(
    "unit, value, expected",
    [
        ("W", 1.0e9, 1.0),
        ("kW", 1.0e6, 1.0),
        ("kWe", 1.0e6, 1.0),
        ("MW", 1.0e3, 1.0),
        ("MWe", 1.0e3, 1.0),
        ("GW", 1.0, 1.0),
        ("GWe", 1.0, 1.0),
        ("EJ / yr", SECONDS_PER_YEAR * 1.0e-9, 1.0),
        ("TWh/yr", 8.766, 1.0),
    ],
)
def test_power_to_gw_uses_one_shared_unit_contract(unit, value, expected):
    # Case and the optional whitespace around '/' come from simulator input;
    # neither should alter the standard GW result.
    assert power_to_gw(value, unit) == pytest.approx(expected)


def test_power_to_gw_preserves_array_shape_and_rejects_unknown_units():
    values = power_to_gw([[1000, 2000]], "MW")
    np.testing.assert_allclose(values, [[1.0, 2.0]])
    assert values.shape == (1, 2)

    with pytest.raises(ValueError, match="Unsupported power unit"):
        power_to_gw(1, "horsepower")


@pytest.mark.parametrize(
    "unit, value, expected",
    [
        ("g", 1000.0, 1.0),
        ("grams", 1000.0, 1.0),
        ("kg", 1.0, 1.0),
        ("kilograms", 1.0, 1.0),
        ("t", 0.001, 1.0),
        ("tonnes", 0.001, 1.0),
        ("metric tons", 0.001, 1.0),
    ],
)
def test_mass_to_kg_uses_one_shared_unit_contract(unit, value, expected):
    assert mass_to_kg(value, unit) == pytest.approx(expected)


def test_mass_to_kg_rejects_unknown_units():
    with pytest.raises(ValueError, match="Unsupported mass unit"):
        mass_to_kg(1, "pounds")


def test_select_reactors_defines_selection_consistently():
    available = ["LWR", "SFR"]

    assert select_reactors(None, available) == ("LWR", "SFR")
    assert select_reactors("SFR", available) == ("SFR",)
    # Repeated names must not double-count capacity or material flows.
    assert select_reactors(["SFR", "LWR", "SFR"], available) == (
        "SFR",
        "LWR",
    )
    assert select_reactors([], available) == ()


def test_select_reactors_reports_unknown_names():
    with pytest.raises(ValueError, match="Unknown reactor.*HTGR"):
        select_reactors(["LWR", "HTGR"], ["LWR", "SFR"])


def test_sum_reactor_series_preserves_time_shape_for_empty_selection():
    result = sum_reactor_series({}, (), length=4)
    np.testing.assert_array_equal(result, np.zeros(4))
    assert result.shape == (4,)


def test_sum_and_format_reactor_results_have_stable_copy_behavior():
    source = {
        "LWR": np.array([1.0, 2.0]),
        "SFR": np.array([10.0, 20.0]),
    }

    np.testing.assert_array_equal(
        sum_reactor_series(source, ("SFR", "LWR"), 2),
        [11.0, 22.0],
    )
    separated = format_reactor_results(
        source, ("LWR",), length=2, return_sum=False
    )
    separated["LWR"][0] = 99.0
    # Public output may be mutated without corrupting a cached native result.
    assert source["LWR"][0] == 1.0


@pytest.mark.parametrize(
    "series, reactors, message",
    [
        ({"LWR": np.ones(3)}, ("LWR",), "shape"),
        ({"LWR": np.ones(2)}, ("SFR",), "No series"),
    ],
)
def test_sum_reactor_series_validates_the_shared_shape(
    series, reactors, message
):
    with pytest.raises(ValueError, match=message):
        sum_reactor_series(series, reactors, length=2)


def test_calendar_aggregation_keeps_complete_years():
    years, totals = aggregate_calendar_years(
        np.ones(12), init_year=2030, init_month=1, how="sum"
    )

    np.testing.assert_array_equal(years, [2030])
    np.testing.assert_array_equal(totals, [12.0])


def test_calendar_aggregation_keeps_both_partial_boundary_years():
    # July through the following June is six represented months in each
    # calendar year.  Neither boundary block should be discarded or padded.
    years, totals = aggregate_calendar_years(
        np.ones(12), init_year=2030, init_month=7, how="sum"
    )

    np.testing.assert_array_equal(years, [2030, 2031])
    np.testing.assert_array_equal(totals, [6.0, 6.0])


def test_calendar_aggregation_supports_multidimensional_values_and_methods():
    values = np.arange(28, dtype=float).reshape(14, 2)

    years, maximum = aggregate_calendar_years(values, 2030, 12, "max")
    _, ending = aggregate_calendar_years(values, 2030, 12, "end")
    _, average = aggregate_calendar_years(values, 2030, 12, "mean")

    np.testing.assert_array_equal(years, [2030, 2031, 2032])
    np.testing.assert_array_equal(maximum[0], values[0])
    np.testing.assert_array_equal(maximum[1], values[12])
    np.testing.assert_array_equal(ending[1], values[12])
    np.testing.assert_allclose(average[1], values[1:13].mean(axis=0))
    assert maximum.shape == (3, 2)


def test_calendar_aggregation_handles_empty_multidimensional_input():
    years, values = aggregate_calendar_years(
        np.zeros((0, 3)), init_year=2030, init_month=1, how="sum"
    )

    assert years.shape == (0,)
    assert values.shape == (0, 3)


@pytest.mark.parametrize(
    "values, month, how, message",
    [
        (1.0, 1, "sum", "time dimension"),
        ([1.0], 0, "sum", "init_month"),
        ([1.0], 13, "sum", "init_month"),
        ([1.0], 1, "median", "Unknown yearly aggregation"),
    ],
)
def test_calendar_aggregation_rejects_ambiguous_requests(
    values, month, how, message
):
    with pytest.raises(ValueError, match=message):
        aggregate_calendar_years(values, 2030, month, how)


def _receipt(
    assay,
    uranium_mass=100.0,
    material_mass=120.0,
    reactor="LWR",
    time_index=0,
):
    """Build one fuel receipt for calculation tests."""

    return FuelReceipt(
        reactor=reactor,
        time_index=time_index,
        material_mass=material_mass,
        uranium_mass=uranium_mass,
        u235_mass=assay * uranium_mass,
    )


def test_resource_calculation_uses_shared_enrichment_defaults():
    resources = calculate_fuel_resources(
        [_receipt(0.04, uranium_mass=80.0, material_mass=120.0)],
        reactors=("LWR",),
        n_times=1,
    )
    cascade = enrichment_cascade(
        NATURAL_ASSAY,
        0.04,
        TAILS_ASSAY,
        CASCADE_SPLITS,
    )

    assert resources["natu"]["LWR"][0] == pytest.approx(
        cascade["feed"][0] * 80.0
    )
    np.testing.assert_allclose(
        resources["tails"]["LWR"][:, 0],
        np.asarray(cascade["tails"]) * 80.0,
    )
    np.testing.assert_allclose(
        resources["swu"]["LWR"][:, 0],
        np.asarray(cascade["swu"]) * 80.0,
    )


def test_natural_uranium_receipt_needs_no_tails_or_swu():
    resources = calculate_fuel_resources(
        [_receipt(0.00711)],
        reactors=("LWR",),
        n_times=2,
        natu_assay=0.00711,
        tails_assay=0.002,
        cascade_splits=[],
    )

    np.testing.assert_array_equal(resources["natu"]["LWR"], [100.0, 0.0])
    np.testing.assert_array_equal(resources["tails"]["LWR"], [[0.0, 0.0]])
    np.testing.assert_array_equal(resources["swu"]["LWR"], [[0.0, 0.0]])


@pytest.mark.parametrize("assay", [0.002, 0.004])
def test_depleted_uranium_receipt_needs_no_enrichment_resources(assay):
    resources = calculate_fuel_resources(
        [_receipt(assay)],
        reactors=("LWR",),
        n_times=1,
        natu_assay=0.00711,
        tails_assay=0.002,
        cascade_splits=[],
    )

    np.testing.assert_array_equal(resources["natu"]["LWR"], [0.0])
    np.testing.assert_array_equal(resources["tails"]["LWR"], [[0.0]])
    np.testing.assert_array_equal(resources["swu"]["LWR"], [[0.0]])


def test_enrichment_uses_uranium_product_mass_not_total_material_mass():
    resources = calculate_fuel_resources(
        [_receipt(0.04, uranium_mass=80.0, material_mass=120.0)],
        reactors=("LWR",),
        n_times=1,
        natu_assay=0.00711,
        tails_assay=0.002,
        cascade_splits=[],
    )
    cascade = enrichment_cascade(0.00711, 0.04, 0.002, [np.inf])

    assert resources["natu"]["LWR"][0] == pytest.approx(
        cascade["feed"][0] * 80.0
    )
    assert resources["tails"]["LWR"][0, 0] == pytest.approx(
        cascade["tails"][0] * 80.0
    )


def test_enrichment_is_calculated_per_receipt_before_aggregation():
    receipts = [
        _receipt(0.03, uranium_mass=40.0),
        _receipt(0.10, uranium_mass=60.0),
    ]
    resources = calculate_fuel_resources(
        receipts,
        reactors=("LWR",),
        n_times=1,
        natu_assay=0.00711,
        tails_assay=0.002,
        cascade_splits=[],
    )
    low = enrichment_cascade(0.00711, 0.03, 0.002, [np.inf])
    high = enrichment_cascade(0.00711, 0.10, 0.002, [np.inf])
    expected_swu = low["swu"][0] * 40.0 + high["swu"][0] * 60.0

    assert resources["swu"]["LWR"][0, 0] == pytest.approx(expected_swu)
    # The weighted-average-assay shortcut is mathematically wrong for SWU's
    # nonlinear value function.  This assertion protects that exact bug.
    average_assay = (0.03 * 40.0 + 0.10 * 60.0) / 100.0
    averaged = enrichment_cascade(
        0.00711, average_assay, 0.002, [np.inf]
    )["swu"][0] * 100.0
    assert expected_swu != pytest.approx(averaged)


def test_resource_calculation_preserves_reactors_times_and_stage_shape():
    resources = calculate_fuel_resources(
        [
            _receipt(0.04, reactor="LWR", time_index=0),
            # This assay lies above both default split boundaries and exercises
            # every stage in the configured three-category cascade.
            _receipt(0.3, reactor="SFR", time_index=1),
        ],
        reactors=("LWR", "SFR"),
        n_times=3,
        natu_assay=0.00711,
        tails_assay=0.002,
        cascade_splits=None,
    )

    assert resources["natu"]["LWR"].shape == (3,)
    assert resources["tails"]["SFR"].shape == (3, 3)
    assert resources["swu"]["SFR"].shape == (3, 3)
    assert resources["natu"]["LWR"][1] == 0.0
    assert resources["natu"]["SFR"][0] == 0.0


def test_zero_fuel_keeps_the_configured_stage_shape():
    resources = calculate_fuel_resources(
        [],
        reactors=("LWR",),
        n_times=4,
        natu_assay=0.00711,
        tails_assay=0.002,
        cascade_splits=None,
    )

    # The output contract depends on requested categories, not on whether the
    # simulation happened to contain a fuel receipt.  This specifically
    # prevents the old two-versus-three-stage zero-data discrepancy.
    assert resources["natu"]["LWR"].shape == (4,)
    assert resources["tails"]["LWR"].shape == (3, 4)
    assert resources["swu"]["LWR"].shape == (3, 4)


def test_format_fuel_resource_results_controls_sum_and_stage_splitting():
    resources = calculate_fuel_resources(
        [
            _receipt(0.04, reactor="LWR"),
            _receipt(0.20, reactor="SFR"),
        ],
        reactors=("LWR", "SFR"),
        n_times=1,
        natu_assay=0.00711,
        tails_assay=0.002,
        cascade_splits=[0.1],
    )

    separated = format_fuel_resource_results(
        resources,
        reactors=("LWR", "SFR"),
        n_times=1,
        return_sum=False,
        split_categories=True,
    )
    summed = format_fuel_resource_results(
        resources,
        reactors=("LWR", "SFR"),
        n_times=1,
        return_sum=True,
        split_categories=False,
    )

    assert separated["tails"]["LWR"].shape == (2, 1)
    np.testing.assert_allclose(
        summed["swu"],
        separated["swu"]["LWR"].sum(axis=0)
        + separated["swu"]["SFR"].sum(axis=0),
    )
    np.testing.assert_allclose(
        summed["natu"],
        separated["natu"]["LWR"] + separated["natu"]["SFR"],
    )


def test_format_fuel_resource_results_keeps_empty_split_output_dimensional():
    resources = calculate_fuel_resources(
        [],
        reactors=(),
        n_times=3,
        natu_assay=0.00711,
        tails_assay=0.002,
    )

    formatted = format_fuel_resource_results(
        resources,
        reactors=(),
        n_times=3,
        return_sum=True,
        split_categories=True,
    )

    assert formatted["natu"].shape == (3,)
    assert formatted["tails"].shape == (0, 3)
    assert formatted["swu"].shape == (0, 3)


@pytest.mark.parametrize(
    "resources, message",
    [
        ({"natu": {}, "tails": {}}, "missing metric"),
        (
            {
                "natu": {"LWR": np.zeros(2)},
                "tails": {"LWR": np.zeros((1, 3))},
                "swu": {"LWR": np.zeros((1, 2))},
            },
            r"expected \(stages, 2\)",
        ),
        (
            {
                "natu": {"LWR": np.zeros(2)},
                "tails": {"LWR": np.zeros((1, 2))},
                "swu": {},
            },
            "no data for reactor",
        ),
    ],
)
def test_format_fuel_resource_results_rejects_bad_shared_data(
    resources, message
):
    with pytest.raises(ValueError, match=message):
        format_fuel_resource_results(
            resources,
            reactors=("LWR",),
            n_times=2,
            return_sum=True,
            split_categories=True,
        )


def test_zero_uranium_receipt_is_valid_and_contributes_zero():
    resources = calculate_fuel_resources(
        [
            FuelReceipt(
                reactor="LWR",
                time_index=0,
                material_mass=100.0,
                uranium_mass=0.0,
                u235_mass=0.0,
            )
        ],
        reactors=("LWR",),
        n_times=1,
        natu_assay=0.00711,
        tails_assay=0.002,
    )
    assert all(
        np.all(values["LWR"] == 0.0) for values in resources.values()
    )


def test_receipt_mass_validation_allows_floating_point_roundoff():
    resources = calculate_fuel_resources(
        [
            FuelReceipt(
                reactor="LWR",
                time_index=0,
                material_mass=100_000.0,
                uranium_mass=100_000.0 + 3.0e-11,
                u235_mass=4_000.0,
            )
        ],
        reactors=("LWR",),
        n_times=1,
        natu_assay=0.00711,
        tails_assay=0.002,
        cascade_splits=[],
    )

    assert resources["natu"]["LWR"][0] > 0.0


@pytest.mark.parametrize(
    "receipts, reactors, n_times, natural, tails, message",
    [
        ([], ("LWR",), 1, None, 0.002, "natu_assay is required"),
        ([], ("LWR",), 1, 0.0, 0.0, "strictly between"),
        ([], ("LWR",), 1, 0.00711, 0.0, "0 < tails"),
        ([], ("LWR",), 1, 0.00711, 0.008, "0 < tails"),
        ([], ("LWR",), -1, 0.00711, 0.002, "non-negative integer"),
        ([], ("LWR",), 1.5, 0.00711, 0.002, "non-negative integer"),
        ([_receipt(1.0)], ("LWR",), 1, 0.00711, 0.002, r"in \[0, 1\)"),
        ([_receipt(0.04, reactor="SFR")], ("LWR",), 1,
         0.00711, 0.002, "unknown reactor"),
        ([_receipt(0.04, time_index=2)], ("LWR",), 1,
         0.00711, 0.002, "outside"),
        ([_receipt(0.04, time_index=0.5)], ("LWR",), 1,
         0.00711, 0.002, "noninteger time index"),
    ],
)
def test_resource_calculation_rejects_invalid_model_inputs(
    receipts, reactors, n_times, natural, tails, message
):
    with pytest.raises(ValueError, match=message):
        calculate_fuel_resources(
            receipts,
            reactors,
            n_times,
            natural,
            tails,
            cascade_splits=[],
        )


@pytest.mark.parametrize(
    "receipt, message",
    [
        (_receipt(0.04, material_mass=-1.0), "cannot be negative"),
        (_receipt(0.04, uranium_mass=121.0), "cannot exceed total"),
        (FuelReceipt("LWR", 0, 100.0, 80.0, 81.0),
         "cannot exceed uranium"),
        (FuelReceipt("LWR", 0, 100.0, np.nan, 1.0), "non-finite"),
    ],
)
def test_resource_calculation_rejects_inconsistent_receipt_mass(
    receipt, message
):
    with pytest.raises(ValueError, match=message):
        calculate_fuel_resources(
            [receipt],
            reactors=("LWR",),
            n_times=1,
            natu_assay=0.00711,
            tails_assay=0.002,
            cascade_splits=[],
        )


@pytest.mark.parametrize(
    "splits, message",
    [
        ([0.2, 0.1], "strictly increasing"),
        ([0.00711], "above the natural assay"),
        ([1.0], "below one"),
        ([0.1, np.inf], "must be finite"),
    ],
)
def test_resource_calculation_validates_cascade_stage_boundaries(
    splits, message
):
    with pytest.raises(ValueError, match=message):
        calculate_fuel_resources(
            [_receipt(0.2)],
            reactors=("LWR",),
            n_times=1,
            natu_assay=0.00711,
            tails_assay=0.002,
            cascade_splits=splits,
        )


class _Reader:
    """Tiny closeable stand-in for SQLite/HDF5 native result readers."""

    def __init__(self, path):
        self.path = Path(path)
        self.closed = False

    def close(self):
        self.closed = True


class _MovableMetadata:
    """Small Results-like base used to test result-file movement."""

    def __init__(self, path):
        self.path = Path(path)
        self.move_calls = []

    def move_files(self, destination):
        self.move_calls.append(Path(destination))
        self.path = Path(destination) / self.path.name


class _ResultWithFileReader(ResultFileReader, _MovableMetadata):
    """Concrete test result that exposes reader-construction history."""

    def __init__(self, path):
        super().__init__(path)
        self.created_paths = []
        self._initialize_result_reader()

    def _result_file_path(self):
        return self.path

    def _open_result_file(self, path):
        self.created_paths.append(path)
        return _Reader(path)


def test_result_reader_opens_on_request_and_follows_path_changes(tmp_path):
    result = _ResultWithFileReader(tmp_path / "initial.db")

    assert result._reader is None
    first_reader = result.obj
    assert first_reader.path == (tmp_path / "initial.db").resolve()
    assert result.obj is first_reader

    result.path = tmp_path / "relocated.db"
    second_reader = result.obj
    assert first_reader.closed
    assert second_reader is not first_reader
    assert second_reader.path == (tmp_path / "relocated.db").resolve()


def test_result_move_closes_an_open_reader_before_delegating(tmp_path):
    result = _ResultWithFileReader(tmp_path / "initial.db")
    reader = result.obj

    result.move_files(tmp_path / "database")

    assert reader.closed
    assert result._reader is None
    assert result.move_calls == [tmp_path / "database"]
    assert result.path == tmp_path / "database" / "initial.db"


def test_saved_result_excludes_open_reader_and_reopens_on_request(tmp_path):
    result = _ResultWithFileReader(tmp_path / "result.h5")
    original_reader = result.obj

    restored = dill.loads(dill.dumps(result))

    # Serialization must not close the live result owned by the caller, but it
    # must omit that reader from the durable metadata representation.
    assert not original_reader.closed
    assert restored._reader is None
    restored_reader = restored.obj
    assert restored_reader is not original_reader
    assert restored_reader.path == (tmp_path / "result.h5").resolve()
