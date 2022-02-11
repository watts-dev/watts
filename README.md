# WATTS

[![License](https://img.shields.io/badge/license-MIT-green)](https://opensource.org/licenses/MIT)
[![GitHub Actions build status (Linux)](https://github.com/watts-dev/watts/workflows/CI/badge.svg?branch=development)](https://github.com/watts-dev/watts/actions?query=workflow%3ACI)


WATTS (Workflow and Template Toolkit for Simulation) provides a set of Python
classes that can manage simulation workflows for multiple codes where
information is exchanged at a coarse level. For each code, input files rely on
placeholder values that are filled in based on a set of user-defined parameters.

WATTS is being developed with support from Argonne National Laboratory. For any
questions, please contact [watts@anl.gov](mailto:watts@anl.gov).

## Installation

- git clone https://github.com/watts-dev/watts
- cd watts
- pip install -U pip
- pip install .

## Documentation

Here is the link to the online [__documentation__](https://watts.readthedocs.io/en/latest/user/index.html).

In case you want to build the documentation locally, you can run:

- cd doc
- pip install -r requirements.txt
- make html

Then you can view the documentation with:
- google-chrome build/html/index.html

or replace google-chrome with your favorite browser.

## Tutorial

Here is the link to a series of [__examples__](/examples/README.md).
