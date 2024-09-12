[![CI](https://github.com/vallen-systems/shmdash/workflows/CI/badge.svg)](https://github.com/vallen-systems/shmdash/actions)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/charliermarsh/ruff/main/assets/badge/v2.json)](https://github.com/charliermarsh/ruff)

# SHMdash

Python client library to upload data to a SHM Dashboard server.

Have a look at the [basic example](examples/basic.py) for usage.
Further descriptions of the client functions can be found in the docstrings.

> [!NOTE]
> The SHM Dashboard is a product from Vallen Systeme to upload data from different sources and locations and instantly access and visualize the data in a dashboard.
> If you are interested, please check out our [demo dashboard](https://demo.shmdash.de) and contact our sales department [sales@vallen.de](mailto:sales@vallen.de).

## Installation

Install the latest version from Git:

```sh
$ pip install 'shmdash @ git+https://github.com/vallen-systems/shmdash'
```

## Development setup

```sh
# Clone repository
$ git clone https://github.com/vallen-systems/shmdash
$ cd shmdash

# Install package and development tools
$ pip install -e .[dev]

# Run checks
$ ruff check .
$ mypy .

# Run tests
$ pytest
```
