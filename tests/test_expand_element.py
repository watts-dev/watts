import pytest

from watts.plugin_mcnp import expand_element

endf70_xsdir = """
directory
6000.70c 11.898000 endf70a
7014.70c 13.882780 endf70a
7015.70c 14.871000 endf70a
8016.70c 15.857510 endf70a
8017.70c 16.853100 endf70a
73181.70c 179.400000 endf70i
73182.70c 180.387000 endf70i
74182.70c 180.390000 endf70i
74183.70c 181.380000 endf70i
74184.70c 182.370000 endf70i
74186.70c 184.360000 endf70i
94239.70c 236.998600 endf70j
"""

endf80_xsdir = """
directory
6012.00c 11.89365 6012.800nc
6013.00c 12.89165 6013.800nc
7014.00c 13.88278 7014.800nc
7015.00c 14.871 7015.800nc
8016.00c 15.85751 8016.800nc
8017.00c 16.8531 8017.800nc
8018.00c 17.8445 8018.800nc
73180.00c 178.4016 73180.800nc
73181.00c 179.3936 73181.800nc
73182.00c 180.387 73182.800nc
74180.00c 178.401 74180.800nc
74181.00c 179.3938 74181.800nc
74182.00c 180.385 74182.800nc
74183.00c 181.379 74183.800nc
74184.00c 182.371 74184.800nc
74185.00c 183.3646 74185.800nc
74186.00c 184.357 74186.800nc
"""

jeff33_xsdir = """
directory
6000.03c 11.898000 6-C-0g-293.ace 0 1 1 110620 0 0 2.5300E-08
6013.03c 12.891650 6-C-13g-293.ace 0 1 1 201260 0 0 2.5300E-08
"""

xsdir = {
    '70c': endf70_xsdir,
    '00c': endf80_xsdir,
    '03c': jeff33_xsdir,
}


@pytest.mark.parametrize(
    "suffix,element,iso_right,iso_wrong",
    [
        ('70c', ('6000', 'C'), ['6000'], ['6012', '6013']),
        ('70c', ('8000', 'O'), ['8016', '8017'], ['8000', '8018']),
        ('70c', ('73000', 'Ta'), ['73181'], ['73180', '73182']),
        ('70c', ('74000', 'W'), ['74182', '74183', '74184', '74186'], ['74180']),
        ('00c', ('6000', 'C'), ['6012', '6013'], ['6000']),
        ('00c', ('8000', 'O'), ['8016', '8017', '8018'], ['8000']),
        ('00c', ('73000', 'Ta'), ['73180', '73181'], ['73182']),
        ('00c', ('74000', 'W'), ['74180', '74182', '74183', '74184', '74186'], []),
        ('03c', ('6000', 'C'), ['6000'], ['6012', '6013']),
    ]
)
def test_expand_element(run_in_tmpdir, suffix, element, iso_right, iso_wrong):
    # Write xsdir file
    with open('xsdir', 'w') as fh:
        fh.write(xsdir[suffix])

    # Generate expand function for this xsdir
    expand = expand_element('xsdir')

    for elem in element:
        # Expand element in material definition
        mat = expand(f"{elem}.{suffix} 1.0")

        # Ensure isotopes that should be there actually are
        for iso in iso_right:
            assert f'{iso}.{suffix}' in mat

        # Ensure isotopes that shouldn't be there are not
        for iso in iso_wrong:
            assert f'{iso}.{suffix}' not in mat

        # fraction should add up to 1.0
        total = sum(float(x) for x in mat.split()[1::2])
        assert total == pytest.approx(1.0)


@pytest.fixture
def temporary_xsdir(run_in_tmpdir):
    with open('xsdir', 'w') as fh:
        fh.write(xsdir['70c'])
    yield


def test_expand_material(temporary_xsdir):
    expand = expand_element('xsdir')

    # Expanding N should give N14 and N!5
    mat = expand("7000.70c 1.0").split()
    assert len(mat) == 4
    assert mat[0] == '7014.70c'
    assert mat[2] == '7015.70c'

    # Check that material card is handled correctly
    mat = expand('m10   7000.70c 1.0').split()
    assert len(mat) == 5
    assert mat[1] == '7014.70c'
    assert mat[3] == '7015.70c'


def test_expand_mix(temporary_xsdir):
    expand = expand_element('xsdir')

    # Expanding regular nuclide should do nothing
    mat = expand('92235.70c 1.0').split()
    assert mat == ['92235.70c', '1.0']

    # Expanding one isotope and one element should only expand element
    mat = expand('92235.70c 1.0 7000.70c 1.0').split()
    assert len(mat) == 6
    assert mat[0] == '92235.70c'
    assert mat[2] == '7014.70c'
    assert mat[4] == '7015.70c'

    # Also check when material card is present
    mat = expand('m5   92235.70c 1.0 7000.70c 1.0').split()
    assert len(mat) == 7
    assert mat[1] == '92235.70c'
    assert mat[3] == '7014.70c'
    assert mat[5] == '7015.70c'


def test_not_naturally_occurring(temporary_xsdir):
    expand = expand_element('xsdir')

    with pytest.raises(ValueError):
        expand('94000.70c 1.0')


def test_default_suffix(temporary_xsdir):
    expand = expand_element('xsdir')

    for original in ('7000 1.0', '7000. 1.0', 'N. 1.0', 'N 1.0'):
        mat = expand(original, '70c').split()
        assert len(mat) == 4
        assert mat[0] == '7014.70c'
        assert mat[2] == '7015.70c'

    # Default suffix shouldn't override existing
    mat = expand('7000.70c 1.0', '80c').split()
    assert mat[0] == '7014.70c'
    assert mat[2] == '7015.70c'
