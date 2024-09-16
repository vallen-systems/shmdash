# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.6.0] - 2024-09-16

### Added

- `Setup` class
- `HTTPSession` interface to wrap and inject http libraries (#3)
- `Client.upload_annotation` (#11)

### Changed

- `Attribute.description`, `Attribute.format`, `Attribute.soft_limits` is optional
- `VirtualChannel.name` is optional
- Simplify exception types (#2)
- Remove setup-related functions from `Client` (#4).
  The following `Client` methods always fetch the setup from the server. Instead, the setup should only be fetched once and queries done on this object.

  - Remove `Client.has_setup()`, use `Client.get_setup()` and `Setup.is_empty()` instead
  - Remove `Client.get_attributes()` and `Client.get_attribute(id)`, use `Client.get_setup` and `Setup.attributes` instead
  - Remove `Client.get_virtual_channels()` and `Client.get_virtual_channel(id)`, use `Client.get_setup` and `Setup.virtual_channels` instead
- Remove existence check in Client.add_attribute and Client.add_virtual_channel (#6)
- Rename `Attribute.desc` -> `Attribute.description`, `VirtualChannel.desc` -> `VirtualChannel.description` (#12)
- Enable SSL verification by default, remove `verify_ssl` flag (#14, #16)
- Migrate to HTTPX (#15)
- Rename `UploadData` -> `Data`, `Data.data` -> `Data.values` (#17)

### Fixed

- Remove `None` values from JSON objects
- Check response in `Client.get_setup` (#5)
- Halve upload batch size while payload too large (#8)

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

[Unreleased]: https://github.com/vallen-systems/pySHMdash/compare/0.6.0...HEAD
[0.6.0]: https://github.com/vallen-systems/pySHMdash/compare/0.5.0...0.6.0
[0.5.0]: https://github.com/vallen-systems/pySHMdash/compare/0.4.0...0.5.0
[0.4.0]: https://github.com/vallen-systems/pySHMdash/releases/tag/0.4.0
