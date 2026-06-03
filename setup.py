from setuptools import find_packages, setup


setup(
    name="echem-analyzer",
    version="0.1.1",
    packages=find_packages(),
    entry_points={"console_scripts": ["echem=echem_core.cli:main"]},
)
