# SHMdash

Python client library for Vallen Systeme Dashboard (SHM Dash).

## Installation

Install the latest version from Git:

```
pip install 'shmdash @ git+https://github.com/vallen-systems/pySHMdash'
```

## Development setup

```sh
# Clone repository
git clone https://github.com/vallen-systems/pySHMdash
cd pySHMdash

# Install package and development tools
pip install -e .[dev]

# Install the git hook scripts
pre-commit install

# Run checks & tests with tox
tox
```
