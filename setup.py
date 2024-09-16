from setuptools import setup, find_packages

setup(
    name="archetypeai",
    version="24.09.16",
    author="Archetype AI",
    url="https://github.com/archetypeai/python-client",
    description="The official python client for the Archetype AI API.",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    python_requires=">=3.8",
    install_requires=[
        "wheel",
        "argparse>=1.4.0",
        "typing-extensions>=4.8.0",
        "requests>=2.31.0",
        "requests-toolbelt>=1.0.0",
        "websockets>=12.0",
        "websocket-client>=1.8.0",
    ],
    include_package_data=True,
)