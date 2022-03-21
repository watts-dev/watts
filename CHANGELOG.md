# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/en/1.0.0/)
and this project adheres to [Semantic Versioning](http://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

* SAS4A/SASSY-1 Plugin

### Changes

* Serialization/deserialization handled through dill instead of h5py
* Calling a plugin is called via the `__call__` method instead of `workflow`

## [0.1.0]

### Added

* WATTS infrastructure
* OpenMC Plugin
* MOOSE Plugin
* PyARC Plugin
* initial documentation
