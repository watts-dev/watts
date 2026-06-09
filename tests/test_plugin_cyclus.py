# SPDX-FileCopyrightText: 2026 UChicago Argonne, LLC
# SPDX-License-Identifier: MIT

import sqlite3

import numpy as np
import pytest

from watts.enrichment_utils import enrichment_cascade
from watts.plugin_cyclus import CyclusOutput, PluginCyclus


MONTH_SECONDS = 365.25 / 12 * 24 * 3600


def _create_cyclus_output(
    path,
    *,
    initial_month=1,
    duration=24,
    resources=None,
    transactions=None,
):
    """Create a small Cyclus-like SQLite file with only the used tables."""
    con = sqlite3.connect(path)
    cur = con.cursor()

    cur.execute("CREATE TABLE InputFiles (Data BLOB)")
    cur.execute(
        "INSERT INTO InputFiles VALUES (?)",
        (sqlite3.Binary(b"<simulation><control /></simulation>"),),
    )
    cur.execute(
        "CREATE TABLE Info "
        "(InitialYear INTEGER, InitialMonth INTEGER, Duration INTEGER)"
    )
    cur.execute("INSERT INTO Info VALUES (?, ?, ?)", (2020, initial_month, duration))
    cur.execute("CREATE TABLE TimeStepDur (DurationSecs REAL)")
    cur.execute("INSERT INTO TimeStepDur VALUES (?)", (MONTH_SECONDS,))

    cur.execute(
        "CREATE TABLE agententry "
        "(agentid INTEGER, prototype TEXT, kind TEXT, spec TEXT, "
        "entertime INTEGER, lifetime INTEGER, parentid INTEGER)"
    )
    cur.executemany(
        "INSERT INTO agententry VALUES (?, ?, ?, ?, ?, ?, ?)",
        [
            (1, "LWR", "Facility", ":cycamore:Reactor", 0, 24, 0),
            (2, "HTGR", "Facility", ":cycamore:Reactor", 6, 12, 0),
        ],
    )

    cur.execute(
        "CREATE TABLE timeseriespower "
        "(agentid INTEGER, time INTEGER, value REAL)"
    )
    cur.executemany(
        "INSERT INTO timeseriespower VALUES (?, ?, ?)",
        [(1, t, 1000.0 if t < 12 else 500.0) for t in range(duration)]
        + [(2, t, 600.0) for t in range(6, 18)],
    )

    cur.execute(
        "CREATE TABLE Prototypes (AgentId INTEGER, Prototype TEXT)"
    )
    cur.execute(
        "CREATE TABLE AgentState_cycamore_ReactorInfo "
        "(AgentId INTEGER, cycle_time REAL, refuel_time REAL)"
    )
    cur.executemany(
        "INSERT INTO Prototypes VALUES (?, ?)",
        [(1, "LWR"), (2, "HTGR")],
    )
    cur.executemany(
        "INSERT INTO AgentState_cycamore_ReactorInfo VALUES (?, ?, ?)",
        [(1, 18.0, 6.0), (2, 9.0, 3.0)],
    )

    cur.execute(
        "CREATE TABLE transactions "
        "(resourceid INTEGER, receiverid INTEGER, senderid INTEGER, "
        "commodity TEXT, time INTEGER)"
    )
    cur.execute(
        "CREATE TABLE resources "
        "(resourceid INTEGER, qualid INTEGER, quantity REAL)"
    )
    cur.execute(
        "CREATE TABLE compositions "
        "(qualid INTEGER, nucid INTEGER, massfrac REAL)"
    )
    if resources is None:
        resources = [
            (100, 10, 10.0),
            (101, 10, 20.0),
            (102, 10, 30.0),
            (200, 10, 7.0),
        ]
    cur.executemany("INSERT INTO resources VALUES (?, ?, ?)", resources)
    cur.executemany(
        "INSERT INTO compositions VALUES (?, ?, ?)",
        [
            (10, 922350000, 0.05),
            (10, 922380000, 0.95),
        ],
    )
    if transactions is None:
        transactions = [
            # Only the first calendar year appears in the annual result; the
            # first output slot is the historical zero placeholder.
            (100, 1, 99, "fresh_fuel", 0),
            (101, 1, 99, "fresh_fuel", 11),
            (102, 1, 99, "fresh_fuel", 12),
            (200, 99, 1, "spent_fuel", 3),
        ]
    cur.executemany("INSERT INTO transactions VALUES (?, ?, ?, ?, ?)", transactions)

    con.commit()
    con.close()
    return CyclusOutput(path)


@pytest.fixture
def cyclus_output(tmp_path):
    """Build a January-start Cyclus output for lifecycle and cache tests."""
    return _create_cyclus_output(tmp_path / "cyclus.sqlite")


@pytest.fixture
def shifted_cyclus_output(tmp_path):
    """Build a July-start output to make calendar-year binning nontrivial."""
    resources = [
        (300, 10, 10.0),
        (301, 10, 20.0),
        (302, 10, 30.0),
        (303, 10, 40.0),
        (304, 10, 50.0),
    ]
    transactions = [
        (300, 1, 99, "fresh_fuel", 0),
        (301, 1, 99, "fresh_fuel", 5),
        (302, 1, 99, "fresh_fuel", 6),
        (303, 1, 99, "fresh_fuel", 17),
        (304, 1, 99, "fresh_fuel", 18),
    ]
    return _create_cyclus_output(
        tmp_path / "shifted_cyclus.sqlite",
        initial_month=7,
        resources=resources,
        transactions=transactions,
    )


def test_cyclus_generated_power_cache_keeps_monthly_data(cyclus_output):
    """Yearly public calls must not shrink the shared monthly power cache."""
    yearly = cyclus_output.get_generated_power(
        "LWR", return_sum=False, yearly=True
    )
    np.testing.assert_allclose(yearly["LWR"], [0.0, 1.0])

    # Mutating the returned value simulates caller-side post-processing. The
    # cached result inside CyclusOutput should remain unchanged.
    yearly["LWR"][1] = 99.0

    monthly = cyclus_output.get_generated_power(
        "LWR", return_sum=False, yearly=False
    )
    assert monthly["LWR"].shape == (24,)
    np.testing.assert_allclose(monthly["LWR"][:12], np.ones(12))
    np.testing.assert_allclose(monthly["LWR"][12:], np.full(12, 0.5))

    yearly_again = cyclus_output.get_generated_power(
        "LWR", return_sum=False, yearly=True
    )
    np.testing.assert_allclose(yearly_again["LWR"], [0.0, 1.0])


def test_cyclus_generated_power_cache_is_order_independent(cyclus_output):
    """Monthly and yearly calls should not contaminate each other's cache."""
    monthly = cyclus_output.get_generated_power(
        "LWR", return_sum=False, yearly=False
    )
    np.testing.assert_allclose(monthly["LWR"][:12], np.ones(12))

    # Mutate the first public result before asking for the yearly view. A cache
    # that returns internal arrays would carry this bad value into the average.
    monthly["LWR"][0] = 12.0

    yearly = cyclus_output.get_generated_power(
        "LWR", return_sum=False, yearly=True
    )
    np.testing.assert_allclose(yearly["LWR"], [0.0, 1.0])

    monthly_again = cyclus_output.get_generated_power(
        "LWR", return_sum=False, yearly=False
    )
    np.testing.assert_allclose(monthly_again["LWR"][0], 1.0)


def test_cyclus_generated_power_capacity_factor_override(cyclus_output):
    """Capacity-factor mode should use deployed capacity, not power history."""
    generated = cyclus_output.get_generated_power(
        ["LWR", "HTGR"],
        return_sum=False,
        yearly=False,
        capacity_factors={"LWR": 0.25},
        default_capacity_factor=0.5,
    )

    expected_lwr = np.full(24, 0.25)
    expected_htgr = np.zeros(24)
    expected_htgr[6:18] = 0.6 * 0.5
    np.testing.assert_allclose(generated["LWR"], expected_lwr)
    np.testing.assert_allclose(generated["HTGR"], expected_htgr)

    generated["HTGR"][7] = 99.0
    generated_again = cyclus_output.get_generated_power(
        ["LWR", "HTGR"],
        return_sum=False,
        yearly=False,
        capacity_factors={"LWR": 0.25},
        default_capacity_factor=0.5,
    )
    np.testing.assert_allclose(generated_again["HTGR"], expected_htgr)


def test_cyclus_generated_electricity_uses_power_time_basis(cyclus_output):
    """Electricity should be power integrated over the returned time period."""
    yearly = cyclus_output.get_generated_electricity(
        "LWR", return_sum=False, yearly=True
    )
    np.testing.assert_allclose(yearly["LWR"], [0.0, 1.0])

    monthly = cyclus_output.get_generated_electricity(
        "LWR", return_sum=True, yearly=False
    )
    expected_monthly = np.concatenate(
        (np.full(12, 1.0 / 12.0), np.full(12, 0.5 / 12.0))
    )
    np.testing.assert_allclose(monthly, expected_monthly)


def test_cyclus_lifecycle_helpers_use_positive_power_windows(cyclus_output):
    """Deployment, fleet, and capacity helpers should share one timeline."""
    deployments = cyclus_output.get_new_deployments(
        "LWR", return_sum=False, yearly=False, rest_key="other"
    )
    expected_lwr = np.zeros(24)
    expected_lwr[0] = 1.0
    expected_other = np.zeros(24)
    expected_other[6] = 1.0
    np.testing.assert_allclose(deployments["LWR"], expected_lwr)
    np.testing.assert_allclose(deployments["other"], expected_other)

    fleet = cyclus_output.get_fleet_size(
        "LWR", return_sum=False, yearly=False, rest_key="other"
    )
    expected_other_fleet = np.zeros(24)
    expected_other_fleet[6:18] = 1.0
    np.testing.assert_allclose(fleet["LWR"], np.ones(24))
    np.testing.assert_allclose(fleet["other"], expected_other_fleet)

    capacity = cyclus_output.get_deployed_capacity(
        "LWR", return_sum=True, yearly=False
    )
    np.testing.assert_allclose(capacity, np.ones(24))


def test_cyclus_fuel_helpers_share_cache_and_copy_public_results(cyclus_output):
    """Fuel demand, discharge, and enrichment use annual cached SQL results."""
    demand = cyclus_output.stock_fuel_demand("LWR", return_sum=False)
    np.testing.assert_allclose(demand["LWR"], [0.0, 30.0])

    enrichment = cyclus_output.get_enrichments("LWR")
    np.testing.assert_allclose(enrichment["LWR"], [0.0, 0.05])

    discharged = cyclus_output.stock_fuel_discharged(
        "LWR", return_sum=True
    )
    np.testing.assert_allclose(discharged, [0.0, 7.0])

    # Public cached values are returned as copies, so a caller cannot corrupt
    # the cached data used by later CyclusOutput calls.
    demand["LWR"][1] = 999.0
    demand_again = cyclus_output.stock_fuel_demand("LWR", return_sum=False)
    np.testing.assert_allclose(demand_again["LWR"], [0.0, 30.0])

    cache_names = {key[0] for key in cyclus_output._cache}
    assert "_received_fuel_yearly_arrays" in cache_names
    assert "_sent_fuel_yearly_arrays" in cache_names


def test_cyclus_shared_caches_avoid_repeated_sql(cyclus_output, monkeypatch):
    """Shared caches should serve related public calls after the first query."""
    original_sql_query = cyclus_output.sql_query
    queries = []

    def spy_sql_query(query):
        queries.append(query)
        return original_sql_query(query)

    monkeypatch.setattr(cyclus_output, "sql_query", spy_sql_query)

    # Fuel demand and enrichment are both backed by the same received-fuel
    # yearly query. Demand with a different return shape should also reuse it.
    cyclus_output.stock_fuel_demand("LWR", return_sum=False)
    cyclus_output.get_enrichments("LWR")
    cyclus_output.stock_fuel_demand("LWR", return_sum=True)

    # Discharged fuel has its own shared yearly query, then reuses it.
    cyclus_output.stock_fuel_discharged("LWR", return_sum=False)
    cyclus_output.stock_fuel_discharged("LWR", return_sum=True)

    # Lifecycle, fleet, and capacity helpers all use the same power-agent
    # summary query and shared lifecycle arrays.
    cyclus_output.get_new_deployments("LWR", yearly=False)
    cyclus_output.get_retirements("LWR", yearly=False)
    cyclus_output.get_fleet_size("LWR", yearly=False)
    cyclus_output.get_deployed_capacity("LWR", yearly=False)

    query_text = "\n".join(queries).lower()
    assert query_text.count("from transactions") == 2
    assert query_text.count("with power_history") == 1


def test_cyclus_fuel_years_follow_initial_month(shifted_cyclus_output):
    """Annual fuel aggregation should honor non-January start months."""
    demand = shifted_cyclus_output.stock_fuel_demand("LWR", return_sum=False)
    enrichment = shifted_cyclus_output.get_enrichments("LWR")

    # The July-start case bins months 0-5 into the completed 2020 calendar
    # year and months 6-17 into 2021. Months 18-23 belong to the partial final
    # represented year, which the public yearly convention drops.
    np.testing.assert_allclose(demand["LWR"], [0.0, 30.0, 70.0])
    np.testing.assert_allclose(enrichment["LWR"], [0.0, 0.05, 0.05])


def test_cyclus_cache_clear_and_nucids_copy_cached_state(cyclus_output):
    """Cache reset should clear derived data without reopening the database."""
    nucids = cyclus_output.nucids
    nucids[0] = -1
    np.testing.assert_array_equal(
        cyclus_output.nucids, [922350000, 922380000]
    )

    cyclus_output.stock_fuel_demand("LWR")
    assert cyclus_output._cache

    cyclus_output.clear_cache()
    assert cyclus_output._cache == {}
    assert cyclus_output._nucids is None


def test_cyclus_stock_fuel_resources_requires_assays(cyclus_output):
    """Resource calculations need explicit feed and tails assays."""
    with pytest.raises(AssertionError, match="natu_assay"):
        cyclus_output.stock_fuel_resources("LWR", tails_assay=0.002)

    with pytest.raises(AssertionError, match="tails_assay"):
        cyclus_output.stock_fuel_resources("LWR", natu_assay=0.00711)


def test_cyclus_stock_fuel_resources_matches_cascade(cyclus_output):
    """Resource outputs should scale cascade ratios by annual fuel mass."""
    resources = cyclus_output.stock_fuel_resources(
        "LWR",
        natu_assay=0.00711,
        tails_assay=0.002,
        return_sum=False,
        split_cat=True,
        cascade_splits=[],
    )

    cascade = enrichment_cascade(
        feed_enr=0.00711,
        prod_enr=0.05,
        tail_enr=0.002,
        cascade_splits=[np.inf],
    )
    expected_natu = np.array([0.0, cascade["feed"][0] * 30.0])
    expected_tails = np.array([[0.0, cascade["tails"][0] * 30.0]])
    expected_swu = np.array([[0.0, cascade["swu"][0] * 30.0]])

    np.testing.assert_allclose(resources["natu"]["LWR"], expected_natu)
    np.testing.assert_allclose(resources["tails"]["LWR"], expected_tails)
    np.testing.assert_allclose(resources["swu"]["LWR"], expected_swu)


def test_cyclus_capacity_factor_helpers(cyclus_output):
    """Design and realized capacity factors are both exposed by prototype."""
    design = cyclus_output.get_capacity_factors("LWR")
    assert design == {"LWR": pytest.approx(0.75)}

    realized = cyclus_output.get_avg_capacity_factors("LWR")
    assert realized == {"LWR": pytest.approx(0.75)}
    assert cyclus_output.get_avg_capacity_factors("LWR", return_avg=True) \
        == pytest.approx(0.75)


def test_plugin_cyclus_uses_template_basename_for_sqlite_output(
    tmp_path,
    monkeypatch,
):
    """Cyclus output names should be derived from the template file name."""
    template = tmp_path / "scenario.case.xml"
    template.write_text("<simulation />")
    monkeypatch.setattr("watts.plugin.shutil.which", lambda exe: exe)

    plugin = PluginCyclus(template, executable="cyclus")

    assert plugin.input_name == "cyclus_input"
    assert plugin.execute_command == [
        "cyclus",
        "cyclus_input",
        "-o",
        "scenario.case.sqlite",
    ]
