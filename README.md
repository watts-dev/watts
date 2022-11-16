# <img valign="middle" src="https://raw.githubusercontent.com/watts-dev/watts/development/doc/source/_static/watts.svg" height="75" height="75" alt="WATTS logo"/> WATTS

[![License](https://img.shields.io/badge/license-MIT-green)](https://opensource.org/licenses/MIT)
[![PyPI](https://img.shields.io/pypi/v/watts?label=PyPI)](https://pypi.org/project/watts/)
[![GitHub Actions build status (Linux)](https://github.com/watts-dev/watts/workflows/CI/badge.svg?branch=development)](https://github.com/watts-dev/watts/actions?query=workflow%3ACI)
[![DOI](https://joss.theoj.org/papers/10.21105/joss.04735/status.svg)](https://doi.org/10.21105/joss.04735)

WATTS (Workflow and Template Toolkit for Simulation) consists of a set of Python
classes that can manage simulation workflows for one or multiple codes. It
provides the following capabilities:

- An isolated execution environment when running a code;
- The ability to use placeholder values in input files that are filled in
  programmatically;
- Seamless unit conversions when working with multiple codes;
- A managed database that simulation inputs and outputs are automatically saved
  to; and
- Python classes that provide extra post-processing and analysis capabilities
  for each code.

## Installation

To install `watts`, run:

    python -m pip install watts

## Documentation

Documentation for WATTS can be found
[__here__](https://watts.readthedocs.io/en/latest/index.html).

## Citing

If you use WATTS in your research, please consider giving proper attribution by
citing the following publication:

- Paul K. Romano, Nicolas E. Stauff, Zhiee Jhia Ooi, Yinbin Miao, Amanda Lund,
  and Ling Zou, "WATTS: Workflow and template toolkit for simulation," *Journal
  of Open Source Software*, **7** (79), 4735 (2022).
  [doi:10.21105/joss.04735](https://doi.org/10.21105/joss.04735)

## Sponsors

WATTS is being developed with support from Argonne National Laboratory. For any
questions, please contact [watts@anl.gov](mailto:watts@anl.gov).
