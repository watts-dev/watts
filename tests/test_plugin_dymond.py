# SPDX-FileCopyrightText: 2026 UChicago Argonne, LLC
# SPDX-License-Identifier: MIT

import json

import h5py
import numpy as np
import pytest

from watts.plugin_dymond import DYMONDOutput


@pytest.fixture
def dymond_output(tmp_path):
    """Create a minimal DYMOND HDF5 output for power-related tests.

    The fixture includes one reactor with explicit operating data and another
    reactor that must fall back to deployed capacity. That gives the tests a
    small but representative check of both generated-power paths.
    """
    path = tmp_path / "dymond.h5"
    input_data = {
        "Model": {
            "units": {
                "time": "YEARS",
                "power": "TWH/YR",
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
