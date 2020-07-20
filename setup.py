from setuptools import setup, find_packages

INSTALL_REQUIRES = [
    "aiohttp",
]

EXTRAS_REQUIRE = {
    "tests": [
        "pytest",
        "coverage<5.0",
    ],
    "tools": [
        "tox",
        "pylint>=2.5",  # pyproject.toml support
        "mypy",
        "black",
        "isort",
    ],
}

EXTRAS_REQUIRE["dev"] = EXTRAS_REQUIRE["tests"] + EXTRAS_REQUIRE["tools"]

setup(
    name="daqmon",
    version="0.2.0",
    description="DaqMon (Data Acquisition and Monitoring) interface for Vallen Systeme dashboards",
    author="Lukas Berbuer (Vallen Systeme GmbH)",
    author_email="software@vallen.de",
    packages=find_packages("src"),
    package_dir={"": "src"},
    python_requires=">=3.6",
    install_requires=INSTALL_REQUIRES,
    extras_require=EXTRAS_REQUIRE,
)
