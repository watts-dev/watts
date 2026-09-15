# SPDX-FileCopyrightText: 2026 UChicago Argonne, LLC
# SPDX-License-Identifier: MIT

import json

import h5py
import numpy as np
import pytest

from watts.enrichment_utils import enrichment_cascade
from watts.fuel_cycle_utils import SECONDS_PER_YEAR
from watts.plugin_dymond import DYMONDOutput


@pytest.fixture
def dymond_output(tmp_path):
    """Create a compact but representative DYMOND HDF5 output.

    No DYMOND installation is needed for reader tests: the public adapter only
    needs the documented HDF5 structures.  This synthetic file deliberately
    covers all three portable data paths:

    * ``operations`` supplies generated power for one reactor;
    * ``flows`` supplies aggregate fuel demand and discharge; and
    * raw per-instance ``process`` records supply compositions for enrichment
      and nonlinear fuel-resource calculations.

    Keeping those paths in one small fixture makes their units and physical
    relationship visible to a future maintainer, while avoiding a large,
    opaque simulator-generated binary in the repository.
    """
    path = tmp_path / "dymond.h5"
    input_data = {
        "Model": {
            "units": {
                "time": "YEARS",
                "power": "TWH/YR",
                # DYMOND stores the fixture's material quantities in tonnes,
                # whereas the portable WATTS fuel API promises kilograms.
                # Non-unity units make an omitted conversion easy to detect.
                "mass": "TONNES",
            },
        },
        "Simulation": {
            "start year": 2020,
            "duration": 3,
        },
        "Types": {
            "reactor": [
                {
                    "name": "LWR",
                    "power": 8.766,
                    "capacity factor": 0.5,
                    "lifetime": 3,
                },
                {
                    "name": "NoOps",
                    "power": 17.532,
                    "capacity factor": 0.25,
                    "lifetime": 3,
                },
                {
                    "name": "DefaultCF",
                    "power": 8.766,
                    "lifetime": 3,
                },
            ],
        },
        "Deployments": {
            "fleet_lwr": {
                "type name": "LWR",
                "deployment time": [0],
                "deployment quantity": [1],
            },
            "fleet_no_ops": {
                "type name": "NoOps",
                "deployment time": [0],
                "deployment quantity": [1],
            },
            "fleet_default_cf": {
                "type name": "DefaultCF",
                "deployment time": [0],
                "deployment quantity": [1],
            },
        },
    }

    with h5py.File(path, "w") as h5:
        output = h5.create_group("OUTPUT")
        output.create_dataset(
            "input", data=json.dumps(input_data).encode("utf-8")
        )
        operations = output.create_group("operations")
        operations.create_dataset("times", data=np.array([0.0, 1.0, 2.0]))
        reactor = operations.create_group("reactor")
        lwr = reactor.create_group("LWR")
        lwr.create_dataset(
            "Operating", data=np.array([8.766, 17.532, 0.0])
        )

        # A present reactor group with no Operating dataset is subtly
        # different from a wholly absent reactor group.  Both are incomplete
        # operation records and must use the deployed-capacity fallback.
        reactor.create_group("DefaultCF")

        # Portable mass methods read aggregate process flows.  The extra
        # material proves that the adapter sums every material at the selected
        # location rather than returning only the first HDF5 child.
        flows = output.create_group("flows")
        flow_config = flows.create_group("reactor")
        flow_config.create_dataset("times", data=np.array([0.0, 1.0, 2.0]))
        flow_reactors = flow_config.create_group("reactor")
        flow_lwr = flow_reactors.create_group("LWR")
        process_flows = flow_lwr.create_group("process")
        uox = process_flows.create_group("uox")
        uox.create_dataset("incoming", data=np.array([0.10, 0.08, 0.0]))
        uox.create_dataset("outgoing", data=np.array([0.0, 0.06, 0.04]))
        additives = process_flows.create_group("additives")
        additives.create_dataset(
            "incoming", data=np.array([0.02, 0.02, 0.0])
        )
        additives.create_dataset(
            "outgoing", data=np.array([0.0, 0.02, 0.01])
        )

        # Raw process records retain each batch's composition.  The first
        # batch is 120 kg of 5%-enriched uranium oxide (96 kg uranium); the
        # second is 100 kg of 10%-enriched material (80 kg uranium).  Having
        # two assays is essential because enrichment work is nonlinear: the
        # correct result is the sum of two cascades, not one cascade evaluated
        # at their mass-weighted average assay.
        output.create_dataset(
            "nuclide_ids",
            data=np.array([b"u235", b"u238", b"o16"]),
        )
        raw_reactors = h5.create_group("Reactor")
        raw_lwr = raw_reactors.create_group("LWR")
        instance = raw_lwr.create_group("lwr-1")
        process = instance.create_group("process")
        process.create_dataset(
            "times", data=np.array([0.0, SECONDS_PER_YEAR])
        )
        process.create_dataset("masses", data=np.array([0.12, 0.10]))
        process.create_dataset(
            "compositions",
            data=np.array(
                [
                    [0.04, 0.76, 0.20],
                    [0.08, 0.72, 0.20],
                ]
            ),
        )

    return DYMONDOutput(path)


def test_dymond_generated_power_converts_operating_units_to_gw(dymond_output):
    """Operating data should use the DYMOND power unit from the input file."""
    generated = dymond_output.get_generated_power(
        ["LWR", "NoOps"], return_sum=False
    )

    # 8.766 TWh/yr is equivalent to 1 GW over a 365.25-day year.
    np.testing.assert_allclose(generated["LWR"], [1.0, 2.0, 0.0])

    # Reactors without operations data still use deployed capacity times the
    # input capacity factor, in the same GW unit system.
    np.testing.assert_allclose(generated["NoOps"], [0.5, 0.5, 0.5])


def test_dymond_generated_electricity_forwards_capacity_factors(
    dymond_output,
):
    """Generated electricity should pass capacity-factor overrides through."""
    electricity = dymond_output.get_generated_electricity(
        "LWR",
        return_sum=True,
        capacity_factors={"LWR": 0.25},
        default_capacity_factor=0.9,
    )

    # If get_generated_electricity ignored the override, this would follow the
    # operations data [1.0, 2.0, 0.0] instead of the deployed-capacity result.
    np.testing.assert_allclose(electricity, [0.25, 0.25, 0.25])


def test_dymond_missing_capacity_factor_uses_default(dymond_output):
    """Reactors without operations or input CFs should use the default CF."""
    generated = dymond_output.get_generated_power(
        "DefaultCF",
        return_sum=True,
        default_capacity_factor=0.4,
    )

    # DefaultCF has no operations data and no input "capacity factor"; its
    # deployed capacity is 1 GW, so the default factor controls the result.
    np.testing.assert_allclose(generated, [0.4, 0.4, 0.4])


def test_dymond_metadata_exposes_input_times_types_and_nuclides(dymond_output):
    """Basic metadata should survive JSON and HDF5 decoding unchanged."""
    assert dymond_output.get_input_dict()["Simulation"]["start year"] == 2020
    assert dymond_output.get_times()["init_year"] == 2020
    np.testing.assert_allclose(
        dymond_output.get_times()["years"], [2020.0, 2021.0, 2022.0]
    )
    assert dymond_output.reactor_types == ["LWR", "NoOps", "DefaultCF"]
    assert dymond_output.get_nucids() == ["u235", "u238", "o16"]


def test_dymond_deployments_retirements_and_fleet_are_consistent(
    dymond_output,
):
    """Deployment-derived methods should share one time axis and selector."""
    deployments = dymond_output.get_new_deployments(
        ["LWR", "NoOps"], return_sum=False
    )
    retirements = dymond_output.get_retirements(
        ["LWR", "NoOps"], return_sum=False
    )
    fleet = dymond_output.get_fleet_size(
        ["LWR", "NoOps"], return_sum=False
    )

    # Each fleet deploys one unit at model time zero.  Its three-year lifetime
    # ends just beyond this three-sample reporting axis, so no retirement is
    # represented and each unit remains active throughout the returned data.
    for reactor_name in ("LWR", "NoOps"):
        np.testing.assert_allclose(deployments[reactor_name], [1.0, 0.0, 0.0])
        np.testing.assert_allclose(retirements[reactor_name], [0.0, 0.0, 0.0])
        np.testing.assert_allclose(fleet[reactor_name], [1.0, 1.0, 1.0])

    np.testing.assert_allclose(
        dymond_output.get_new_deployments(
            ["LWR", "NoOps"], return_sum=True
        ),
        [2.0, 0.0, 0.0],
    )

    # Python/NumPy normally reduce an empty collection to scalar zero.  The
    # portable API instead preserves its declared return shapes: an empty
    # mapping for per-reactor data and a zero time series for a requested sum.
    assert dymond_output.get_fleet_size([], return_sum=False) == {}
    np.testing.assert_array_equal(
        dymond_output.get_fleet_size([], return_sum=True), np.zeros(3)
    )


def test_dymond_deployed_capacity_defaults_to_reactor_sum(dymond_output):
    """The default should match Cyclus: summed electrical capacity in GW."""
    per_reactor = dymond_output.get_deployed_capacity(return_sum=False)

    # The fixture's rated powers are expressed as TWh/year.  They correspond
    # to 1, 2, and 1 GW respectively, and each type has one active unit.
    np.testing.assert_allclose(per_reactor["LWR"], [1.0, 1.0, 1.0])
    np.testing.assert_allclose(per_reactor["NoOps"], [2.0, 2.0, 2.0])
    np.testing.assert_allclose(per_reactor["DefaultCF"], [1.0, 1.0, 1.0])
    np.testing.assert_allclose(
        dymond_output.get_deployed_capacity(), [4.0, 4.0, 4.0]
    )


def test_dymond_deployed_capacity_rejects_non_electrical_facilities(
    dymond_output,
):
    """Mass-throughput capacity must not masquerade as electrical GW."""
    with pytest.raises(ValueError, match="reactor electrical capacity only"):
        dymond_output.get_deployed_capacity(facility_class="fabrication")


def test_dymond_unknown_reactor_is_rejected_consistently(dymond_output):
    """Typos should fail rather than silently producing an all-zero series."""
    with pytest.raises(ValueError, match="Unknown reactor"):
        dymond_output.get_generated_power("Typo")

    with pytest.raises(ValueError, match="Unknown reactor"):
        dymond_output.get_deployed_capacity("Typo")

    with pytest.raises(ValueError, match="Unknown reactor"):
        dymond_output.stock_fuel_demand("Typo")


def test_dymond_stock_fuel_flows_are_summed_and_converted_to_kg(
    dymond_output,
):
    """Aggregate flows should sum materials and honor the model mass unit."""
    np.testing.assert_allclose(
        dymond_output.stock_fuel_demand("LWR"), [120.0, 100.0, 0.0]
    )
    np.testing.assert_allclose(
        dymond_output.stock_fuel_discharged("LWR"), [0.0, 80.0, 50.0]
    )

    # A known reactor without flow records represents zero activity, not a
    # malformed selector.  The shape must still match the simulation axis.
    demand = dymond_output.stock_fuel_demand("NoOps", return_sum=False)
    np.testing.assert_array_equal(demand["NoOps"], np.zeros(3))


def test_dymond_enrichments_use_uranium_fraction_not_total_material(
    dymond_output,
):
    """Oxygen in fuel must not dilute the reported U-235/U enrichment."""
    enrichment = dymond_output.get_enrichments("LWR")

    # In the first composition U-235 is 4% of total material but 5% of its
    # uranium (4 / (4 + 76)); the second is 10% uranium enrichment.
    np.testing.assert_allclose(enrichment["LWR"], [0.05, 0.10, 0.0])


def test_dymond_fuel_resources_sum_each_receipt_cascade(dymond_output):
    """Mixed-assay batches must be cascaded separately and binned by year."""
    resources = dymond_output.stock_fuel_resources(
        "LWR",
        natu_assay=0.00711,
        tails_assay=0.002,
        return_sum=True,
        split_cat=True,
        cascade_splits=[],
    )

    cascade_5 = enrichment_cascade(
        feed_enr=0.00711,
        prod_enr=0.05,
        tail_enr=0.002,
        cascade_splits=[np.inf],
    )
    cascade_10 = enrichment_cascade(
        feed_enr=0.00711,
        prod_enr=0.10,
        tail_enr=0.002,
        cascade_splits=[np.inf],
    )

    # Cascade ratios apply to uranium product mass, not to total oxide mass.
    # The fixture therefore contributes 96 kg uranium in year zero and 80 kg
    # in year one; its 20% oxygen contributes no natural-U, tails, or SWU.
    expected_natu = np.array(
        [cascade_5["feed"][0] * 96.0, cascade_10["feed"][0] * 80.0, 0.0]
    )
    expected_tails = np.array(
        [[cascade_5["tails"][0] * 96.0,
          cascade_10["tails"][0] * 80.0,
          0.0]]
    )
    expected_swu = np.array(
        [[cascade_5["swu"][0] * 96.0,
          cascade_10["swu"][0] * 80.0,
          0.0]]
    )

    np.testing.assert_allclose(resources["natu"], expected_natu)
    np.testing.assert_allclose(resources["tails"], expected_tails)
    np.testing.assert_allclose(resources["swu"], expected_swu)

    # This explicit negative assertion guards the old mathematical bug.  A
    # single cascade at the mass-weighted average assay produces a different
    # SWU requirement because separative work is nonlinear in product assay.
    average_assay = (0.05 * 96.0 + 0.10 * 80.0) / (96.0 + 80.0)
    averaged = enrichment_cascade(
        feed_enr=0.00711,
        prod_enr=average_assay,
        tail_enr=0.002,
        cascade_splits=[np.inf],
    )
    averaged_total_swu = averaged["swu"][0] * (96.0 + 80.0)
    assert resources["swu"].sum() != pytest.approx(averaged_total_swu)
