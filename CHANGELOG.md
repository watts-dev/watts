# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/en/1.0.0/)
and this project adheres to [Semantic Versioning](http://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changes

* The `Plugin.__call__` method now allows arbitrary keyword arguments to be
  passed on to the `Plugin.run` method
* The `Database` class now acts like a sequence

## [0.2.0]

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
