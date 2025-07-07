import pytest
import numpy as np
from ..enr_utils import (
    feed_to_product_ratio,
    tails_to_product_ratio,
    _value_function,
    swu_to_product_ratio,
    enrichment_cascade,
    multistage_enr,
)


ENR_NATL = 0.0071
ENR_LEU = 0.0495
ENR_HALEU = 0.165
ENR_TAILS = 0.0025
EXP_SWU = 7.818


# ---------------------------
# feed_to_product_ratio tests
# ---------------------------

def test_feed_to_product_single_value():
    assert np.isclose(feed_to_product_ratio(
        ENR_NATL, ENR_LEU, ENR_TAILS), (ENR_LEU - ENR_TAILS) / (ENR_NATL - ENR_TAILS))


def test_feed_to_product_array():
    result = feed_to_product_ratio([0.02, 0.03], [0.05, 0.06], [0.005, 0.01])
    expected = (np.array([0.05, 0.06]) - np.array([0.005, 0.01])) / \
        (np.array([0.02, 0.03]) - np.array([0.005, 0.01]))
    np.testing.assert_allclose(result, expected)

# ---------------------------
# tails_to_product_ratio tests
# ---------------------------


def test_tails_to_product_single_value():
    assert np.isclose(tails_to_product_ratio(
        ENR_NATL, ENR_LEU, ENR_TAILS), (ENR_LEU - ENR_NATL) / (ENR_NATL - ENR_TAILS))


def test_evens_out():
    assert np.isclose(feed_to_product_ratio(ENR_NATL, ENR_LEU, ENR_TAILS) -
                      tails_to_product_ratio(ENR_NATL, ENR_LEU, ENR_TAILS), 1)


def test_tails_to_product_array():
    result = tails_to_product_ratio([0.02, 0.03], [0.05, 0.06], [0.005, 0.01])
    expected = (np.array([0.05, 0.06]) - np.array([0.02, 0.03])) / \
        (np.array([0.02, 0.03]) - np.array([0.005, 0.01]))
    np.testing.assert_allclose(result, expected)

# ---------------------------
# _value_function tests
# ---------------------------


def test_value_function_typical():
    result = _value_function(0.05)
    expected = (2 * 0.05 - 1) * np.log(0.05 / 0.95)
    assert np.isclose(result, expected)


def test_value_function_array():
    input_values = np.array([0.01, 0.99])
    result = _value_function(input_values)
    expected = (2 * input_values - 1) * \
        np.log(input_values / (1 - input_values))
    np.testing.assert_allclose(result, expected)

# ---------------------------
# swu_to_product_ratio tests
# ---------------------------


def test_swu_to_product_typical():
    result = swu_to_product_ratio(ENR_NATL, ENR_LEU, ENR_TAILS)
    assert np.isclose(result, EXP_SWU, rtol=1e-2)


def test_swu_to_product_array():
    feed = [ENR_NATL, ENR_NATL*1.1]
    prod = [ENR_LEU, ENR_LEU*1.1]
    tail = [ENR_TAILS, ENR_TAILS*0.9]
    result = swu_to_product_ratio(feed, prod, tail)
    assert isinstance(result, np.ndarray)
    np.testing.assert_allclose(result, [EXP_SWU, 8.6656], rtol=1e-2)

# ---------------------------
# enrichment_cascade tests
# ---------------------------


def test_enrichment_cascade_leu():
    result = enrichment_cascade(ENR_NATL, ENR_LEU, ENR_TAILS)['swu']
    assert isinstance(result, list)
    assert len(result) == 3  # default cascade splits: [0.1, 0.2] → 3 stages
    assert result[1] == 0
    assert np.isclose(result[0], EXP_SWU, rtol=1e-2)


def test_enrichment_cascade_haleu():
    result = enrichment_cascade(ENR_NATL, ENR_HALEU, ENR_TAILS)['swu']
    assert isinstance(result, list)
    print(result)
    assert len(result) == 3  # default cascade splits: [0.1, 0.2] → 3 stages
    assert np.isclose(result[0], 32.07823497, rtol=1e-3)
    assert np.isclose(result[1], 1.5064309, rtol=1e-3)


def test_enrichment_cascade_custom():
    # drops unnecssary stages
    result = enrichment_cascade(
        ENR_NATL, ENR_LEU, ENR_TAILS, cascade_splits=[0.1, 0.3, 0.7])['swu']
    assert (sum(result[1:]) == 0)
    assert len(result) == 4


def test_enrichment_cascade_cascade_down():
    feed_enrs = [ENR_NATL, 0.1]
    prod_enrs = [0.1, ENR_HALEU]
    tail_enrs = [ENR_TAILS, ENR_NATL]
    result = multistage_enr(feed_enrs, prod_enrs, tail_enrs, printing=False)

    for i in range(2, 7):  # try all weird cascade options
        splits = [0.1] + list(np.linspace(0.1, 0.2, i))[1:]
        d = enrichment_cascade(
            ENR_NATL, ENR_HALEU, ENR_TAILS, cascade_splits=splits, printing=False)

        for k in ['swu', 'tailing']:
            assert (np.isclose(sum(result[k]), sum(d[k]), rtol=1e-3))
        # feed has to be the same
        assert (np.isclose(result['feed'][0], d['feed'][0], rtol=1e-3))


def test_enrichmnent_cascade_one_cascade():

    result = enrichment_cascade(ENR_NATL, ENR_HALEU, ENR_TAILS, cascade_splits=[
                                np.inf], printing=False)['swu']

    assert (len(result) == 1)
    assert np.isclose(result[0], 32.07823497 + 1.5064309, rtol=1e-3)


# ---------------------------
# multistage_enr tests
# ---------------------------

def test_multistage_enr_reuse_tails():
    feed_enrs = [ENR_NATL, 0.1]
    prod_enrs = [0.1, ENR_HALEU]
    tail_enrs = [ENR_TAILS, ENR_NATL]
    result = multistage_enr(feed_enrs, prod_enrs, tail_enrs, printing=False)
    assert 'swu' in result and 'feed' in result and 'tailing' in result
    assert all(isinstance(x, list) for x in result.values())
    np.testing.assert_allclose(
        result['swu'], [32.07823497, 1.5064309], rtol=1e-2)
    np.testing.assert_allclose(
        result['feed'], [35.3260869, 1.699677], rtol=1e-2)
    np.testing.assert_allclose(result['tailing'], [34.3260869, 0.0], rtol=1e-2)


# this will have higher cat2 fraction than cat3 than the reuse tails scenario
def test_multistage_enr_with_alltails():
    feed_enrs = [ENR_NATL, 0.1]
    prod_enrs = [0.1, ENR_HALEU]
    tail_enrs = [ENR_TAILS, ENR_TAILS]
    result = multistage_enr(feed_enrs, prod_enrs, tail_enrs, printing=False)
    assert 'swu' in result and 'feed' in result and 'tailing' in result
    assert all(isinstance(x, list) for x in result.values())
    np.testing.assert_allclose(
        result['swu'], [31.45522513, 2.129440], rtol=1e-2)
    np.testing.assert_allclose(
        result['feed'], [35.3260869, 1.66666], rtol=1e-2)
    np.testing.assert_allclose(
        result['tailing'], [33.659420, 0.6666], rtol=1e-2)


def test_multistage_tot_is_the_same():
    feed_enrs = [ENR_NATL, 0.1]
    prod_enrs = [0.1, ENR_HALEU]
    tail_enrs = [ENR_TAILS, ENR_TAILS]
    result1 = multistage_enr(feed_enrs, prod_enrs, tail_enrs, printing=False)
    tail_enrs2 = [ENR_TAILS, ENR_NATL]
    result2 = multistage_enr(feed_enrs, prod_enrs, tail_enrs2, printing=False)

    for k in ['swu', 'tailing']:
        # total tailing and swu should be the same
        assert (np.isclose(sum(result1[k]), sum(result2[k]), rtol=1e-3))

    # frontend feed (natlu) should be the same
    assert (np.isclose(result1['feed'][0], result2['feed'][0], rtol=1e-3))
