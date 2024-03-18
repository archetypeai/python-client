from setuptools import setup, find_packages

setup(
    name="archetypeai",
    version="24.03.18",
    packages=find_packages(),
    install_requires=["wheel"],  # external packages as dependencies
    include_package_data=True,
)