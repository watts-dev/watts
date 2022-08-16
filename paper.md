---
title: 'WATTS: Workflow and template toolkit for simulation'
tags:
  - Python
  - nuclear engineering
  - simulation
  - Jinja
authors:
  - name: Paul K. Romano
    orcid: 0000-0002-1147-045X
    corresponding: true
    affiliation: 1
  - name: Nicolas E. Stauff
    orcid: 0000-0001-6167-9326
    affiliation: 1
  - name: Zhiee Jhia Ooi
    orcid: 0000-0003-3027-8516
    affiliation: 1
  - name: Yinbin Miao
    orcid: 0000-0002-3128-4275
    affiliation: 1
  - name: Amanda Lund
    orcid: 0000-0002-8316-0709
    affiliation: 1
  - name: Ling Zou
    orcid: 0000-0003-0664-0474
    affiliation: 1
affiliations:
 - name: Argonne National Laboratory, USA
   index: 1
date: 10 August 2022
bibliography: paper.bib
---

# Summary

Modeling and simulation in many science and engineering domains often involves
the execution and/or iteration of a sequence of applications, with data transfer
between applications typically required. These applications often do not have a
formal application programming interface (API). Instead, executing an
application requires first writing a text-based input file, the format of which
is typically defined in a user's manual. While text-based input files are
suitable for simple one-off calculations, they can become cumbersome if a user
wants to execute the applications multiple times and systematically vary input
parameters, especially when a complex workflow is involved. In this case, they
must resort to either manually making changes in the input file or developing
their own script that modifies the input file and executes the application.
Depending on the format of the input file, writing such a script can be a
non-trivial and error-prone task.

``watts`` (Workflow and Template Toolkit for Simulation) is a Python package
that consists of a set of classes that can manage the execution of one or more
applications. Most importantly, it provides an ability to use placeholder values
in text-based input files that are filled in programmatically from Python,
thereby giving users of scientific applications a means of performing parameter
and sensitivity studies, optimization, and other scientific workflows using
common third-party Python packages. When running multiple applications in
sequence, this capability also provides a means of using the outputs of one
application as the inputs (parameters) in a subsequent application. ``watts``
relies on the Jinja [@jinja] templating engine for handling templated variables
and expressions in input files. In a Jinja template, an identifier surrounded by
a pair of ``{{`` and ``}}`` braces denotes a variable; the variable can then be
specified using the ``Parameters`` class from ``watts``. When an application is
executed via ``watts``, it will first _render_ the template using the specified
parameters.

One of the challenges of managing scientific computing workflows that involve
multiple applications is dealing with differing unit systems. Some applications
may use the [SI](https://en.wikipedia.org/wiki/International_System_of_Units)
system of units whereas others may use some variant of the
[CGS](https://en.wikipedia.org/wiki/Centimetre%E2%80%93gram%E2%80%93second_system_of_units)
system or even [imperial](https://en.wikipedia.org/wiki/Imperial_units) units.
When a single parameter is used by multiple applications, it begs the question
of what units should be used when specifying the parameter. ``watts`` solves
this problem by optionally storing physical quantities using the ``Quantity``
class from Astropy [@astropy:2013; @astropy:2018], which enables the user to
specify a value along with its associated units. Each application that is linked
to ``watts`` has a unit system specified so that when a templated input file for
that application is rendered, any parameters stored as ``Quantity`` instances
are first converted to the appropriate units. For example, if an application
uses SI units and a parameter is stored in inches, it will first be converted to
meters.

In addition to the templating capabilities provided by ``watts``, there are a
number of other useful capabilities for scientific simulation workflows. Each
time an application is executed through ``watts``, an isolated execution
environment is used so that input and output files are not overwritten from
multiple invocations. Additionally, ``watts`` keeps a local database of
application input and output files along with the parameters that are associated
with them for later retrieval. Plugin classes, which are discussed further
below, encapsulate the execution logic for particular applications and provide
extra postprocessing capabilities for interpreting application results.

# Statement of need

The motivation for the development of ``watts`` originated from research and
development activities in nuclear science and engineering (NSE), which rely on a
wide array of modeling and simulation applications covering areas such as
reactor physics, thermal hydraulics, fuel performance, and more. Many of these
applications have been developed over decades, and although some---particularly
those written in C++ and Python---have a formal API by which external software
can interface with, most legacy software packages in NSE typically rely on
simple text-based input files and do not have an API. Thus, ``watts`` is meant
to aid scientists and engineers in working with these applications, enabling
integration with other off-the-shelf and open source software packages, and
providing a means of data transfer between applications.

There have been prior efforts to develop software that enables parameterization
of input files. In particular, the Funz package [@funz] allows input files to be
templated in a similar manner to ``watts``. However, it differs in several key
respects. First, Funz appears to have a broader scope in terms of how
applications are executed; it allows simulations to be performed from a
command-line interface, Excel, R, Python, bash, Java, and others. ``watts``, on
the other hand, solely focuses on enabling Python-based parameterized workflows.
Another key difference is that Funz defines its own syntax for template
parameters and expressions. In contrast, ``watts`` relies on the Jinja
templating engine and its associated syntax. We believe this is advantageous for
a number of reasons. Relying on Jinja significantly simplifies the
implementation in ``watts`` by delegating all the logic associated with template
rendering. It is also beneficial to users because learning Jinja and its
associated syntax gives them a transferrable skill that is useful in any other
context where Jinja is used (e.g., web development). Finally, Funz does not
provide any functionality for handling unit conversions whereas ``watts`` does.

``watts`` provides a set of "plugin" classes for specific simulation
applications. These plugin classes define how the application is executed
(location of executable and command-line arguments, if any), what input files
are necessary, the system of units to use, and what output files are produced
and collected at the end of a simulation. At present, the collection of plugin
classes consists of common applications used in NSE, including MOOSE [@moose]
and MOOSE-based applications, SAS [@sas], OpenMC [@openmc; @openmc_zenodo], MCNP
[@mcnp], Serpent [@serpent], RELAP5 [@relap5], Dakota [@dakota], and PyARC
[@pyarc]. However, the core capabilities of ``watts`` are not specific to the
NSE field and could be applied to any science or engineering application.

At Argonne National Laboratory, ``watts`` is currently being used in a variety
of research projects focused on nuclear reactor design that rely on the
aforementioned set of applications. Ongoing work at Argonne also seeks to tie
traditional nuclear reactor design tools with techno-economic and energy market
modeling applications.

# Acknowledgments

This material is based upon work supported by Laboratory Directed Research and
Development (LDRD) funding from Argonne National Laboratory, provided by the
Director, Office of Science, of the U.S. Department of Energy under Contract
No. DE-AC02-06CH1135.

# References
