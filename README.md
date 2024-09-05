[![CI](https://github.com/vallen-systems/pySHMdash/workflows/CI/badge.svg)](https://github.com/vallen-systems/pySHMdash/actions)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/charliermarsh/ruff/main/assets/badge/v2.json)](https://github.com/charliermarsh/ruff)

# SHMdash

Python client library for Vallen Systeme Dashboard (SHM Dash).

Please have a look at the [basic example](examples/basic.py) for usage.
Further descriptions of the client functions can be found in the docstrings.

## Installation

Install the latest version from Git:

```sh
$ pip install 'shmdash @ git+https://github.com/vallen-systems/pySHMdash'
```

## Development setup

```sh
# Clone repository
$ git clone https://github.com/vallen-systems/pySHMdash
$ cd pySHMdash

# Install package and development tools
$ pip install -e .[dev]

# Run checks
$ ruff check .
$ mypy .

# Run tests
$ pytest
```
