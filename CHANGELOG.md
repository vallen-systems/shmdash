# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.5.0] - 2024-08-26

### Added

- `to_identifier` helper function
- Log request body on error
- `AttributeType` and `DiagramScale` enum
- Use logging in example

### Changed

- Make `Attribute.format_` optional
- Rename `Attribute` fields
  - `type_` -> `type`
  - `format_` -> `format`
- Migrate to hatch build system

### Fixed

- Type hints

## [0.4.0] - 2023-01-04

First public release

[Unreleased]: https://github.com/vallen-systems/pySHMdash/compare/0.5.0...HEAD
[0.5.0]: https://github.com/vallen-systems/pySHMdash/compare/0.4.0...0.5.0
[0.4.0]: https://github.com/vallen-systems/pySHMdash/releases/tag/0.4.0
