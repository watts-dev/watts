# SPDX-FileCopyrightText: 2022-2025 UChicago Argonne, LLC
# SPDX-License-Identifier: MIT

from pathlib import Path
import time

import pandas as pd
import pytest
import watts


ACCOUNT_TABLE = """\
code_of_account,account_description,total_cost,level,review_status
2,TOTAL DIRECT COST,1000000000.0,0,Updated
 21,Structures and improvements subtotal,400000000.0,1,Updated
 22,Reactor plant equipment subtotal,600000000.0,1,Updated
"""

# Overnight capital cost summary written by ACCERT for a reference model with a
# direct cost fraction of one, escalated with a factor of 1.25
OCC_TABLE = """\
metric,value_dollar,value_million_dollar,value_escalated_dollar,\
value_escalated_million_dollar,value_escalated_dollar_per_kw,escalated_dollar_year
total_calculated_direct_cost,1000000000.0,1000.0,1250000000.0,1250.0,1250.0,2025
total_direct_cost,1000000000.0,1000.0,1250000000.0,1250.0,1250.0,2025
total_indirect_costs,609000000.0,609.0,761250000.0,761.25,761.25,2025
total_cost_without_owner,1609000000.0,1609.0,2011250000.0,2011.25,2011.25,2025
owner_cost,321800000.0,321.8,402250000.0,402.25,402.25,2025
total_OCC,1930800000.0,1930.8,2413500000.0,2413.5,2413.5,2025
"""


def make_results(outputs) -> watts.ResultsACCERT:
    """Create a ResultsACCERT object from a mapping of filename to contents"""
    exec_info = watts.ExecInfo(123, 'ACCERT', 'test', time.time_ns())
    input_file = Path('ACCERT_input.son')
    input_file.touch()
    output_files = []
    for name, contents in outputs.items():
        path = Path(name)
        if isinstance(contents, pd.DataFrame):
            contents.to_excel(path, index=False)
        else:
            path.write_text(contents)
        output_files.append(path)
    params = watts.Parameters(thermal_power=3000.0, electric_power=1000.0)
    return watts.ResultsACCERT(params, exec_info, [input_file], output_files)


def test_results_accert(run_in_tmpdir):
    """OCC metrics should be read from the summary that ACCERT writes"""
    results = make_results({
        'pwr12-be_upd_acc_20250912_120000.csv': ACCOUNT_TABLE,
        'pwr12-be_post_20250912_120000.csv': OCC_TABLE,
    })

    assert results.ref_model == 'pwr12-be'
    assert len(results.account_table) == 3
    assert results.total_cost == pytest.approx(1e9)
    assert results.total_calculated_direct_cost == pytest.approx(1e9)
    assert results.total_direct_cost == pytest.approx(1e9)
    assert results.total_indirect_costs == pytest.approx(0.609e9)
    assert results.total_cost_without_owner == pytest.approx(1.609e9)
    assert results.owner_cost == pytest.approx(0.3218e9)
    assert results.total_OCC == pytest.approx(1.9308e9)
    assert results.escalated_dollar_year == 2025
    assert results.total_OCC_escalated == pytest.approx(2.4135e9)
    assert results.total_OCC_per_kW == pytest.approx(2413.5)


def test_results_accert_latest_output(run_in_tmpdir):
    """The most recent of several timestamped outputs should be used"""
    stale = ACCOUNT_TABLE.replace('1000000000.0', '999.0')
    results = make_results({
        'pwr12-be_upd_acc_20250912_120000.csv': stale,
        'pwr12-be_upd_acc_20250912_130000.csv': ACCOUNT_TABLE,
    })
    assert results.total_cost == pytest.approx(1e9)


def test_results_accert_without_summary(run_in_tmpdir):
    """Without an OCC summary, metrics are reconstructed from the accounts

    ACCERT calculates 83.4% of the direct cost of the ABR1000 explicitly, so
    the total direct cost is the calculated cost divided by that fraction.
    """
    results = make_results({'abr1000_upd_acc_20250912_120000.csv': ACCOUNT_TABLE})

    assert results.ref_model == 'abr1000'
    assert results.total_calculated_direct_cost == pytest.approx(1e9)
    assert results.total_direct_cost == pytest.approx(1e9 / 0.834)
    assert results.total_indirect_costs == pytest.approx(0.609e9 / 0.834)
    assert results.total_cost_without_owner == pytest.approx(1.609e9 / 0.834)
    assert results.owner_cost == pytest.approx(0.2 * 1.609e9 / 0.834)
    assert results.total_OCC == pytest.approx(1.2 * 1.609e9 / 0.834)

    with pytest.raises(FileNotFoundError):
        results.occ_table


def test_results_accert_legacy_output(run_in_tmpdir):
    """Cost element tables from ACCERT 1.x should still be found"""
    results = make_results({
        'pwr12-be_updated_account.xlsx': '',
        'pwr12-be_updated_cost_element.xlsx': '',
    })
    assert results.ref_model == 'pwr12-be'
    assert results._output_file(results._ACCOUNT_FILES).suffix == '.xlsx'
    assert results._output_file(results._COST_ELEMENT_FILES).suffix == '.xlsx'


def test_results_accert_lcoe(run_in_tmpdir):
    """The LCOE that ACCERT writes for fusion models should be read"""
    # ACCERT leaves the cost per kW empty for fusion models because they do
    # not define an electric power output
    occ_table = OCC_TABLE.replace(',1250.0,2025', ',,2025') \
        .replace(',761.25,2025', ',,2025').replace(',2011.25,2025', ',,2025') \
        .replace(',402.25,2025', ',,2025').replace(',2413.5,2025', ',,2025')
    lcoe_table = pd.DataFrame({
        'Variable': ['coecap', 'coeoam', 'coe'],
        'Description': ['Capital', 'O&M', 'Total cost of electricity ($/MWh)'],
        'Value': [480.7, 20.9, 515.9],
    })
    results = make_results({
        'large_tokamak_upd_acc_20250912_120000.csv': ACCOUNT_TABLE,
        'large_tokamak_post_20250912_120000.csv': occ_table,
        'large_tokamak_LCOE_results.xlsx': lcoe_table,
    })

    assert results.ref_model == 'large_tokamak'
    assert results.lcoe == pytest.approx(515.9)
    assert results.lcoe_table.at['coecap', 'Value'] == pytest.approx(480.7)
    assert results.total_OCC_escalated == pytest.approx(2.4135e9)
    with pytest.raises(ValueError, match='electric power'):
        results.total_OCC_per_kW


def test_results_accert_missing_output(run_in_tmpdir):
    results = make_results({})
    assert results.ref_model is None
    with pytest.raises(FileNotFoundError):
        results.account_table
    with pytest.raises(FileNotFoundError):
        results.cost_element_table
    with pytest.raises(FileNotFoundError):
        results.affected_cost_element_table
    with pytest.raises(FileNotFoundError):
        results.lcoe_table
