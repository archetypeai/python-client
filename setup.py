import re
import ast
from setuptools import setup, find_packages

# Dynamically extract the library version from the client.
_version_re = re.compile(r'_VERSION\s*=\s*(.*)')
with open("src/archetypeai/api_client.py", 'rb') as f:
    match = _version_re.search(f.read().decode('utf-8'))
    if match:
        version = str(ast.literal_eval(match.group(1)))
    else:
        raise RuntimeError("Unable to find version string.")

setup(
    name="archetypeai",
    version=version,
    author="Archetype AI",
    url="https://github.com/archetypeai/python-client",
    description="The official python client for the Archetype AI API.",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    python_requires=">=3.10",
    install_requires=[
        "typing-extensions>=4.15.0,<5",
        "requests>=2.31.0,<3",
        "requests-toolbelt==1.0.0",
        "websockets>=12.0,<16",
        "websocket-client>=1.8.0,<2",
        "kafka-python>=2.3.1,<3",
        "httpx>=0.28.1,<0.29",
        "httpx-sse>=0.4.3,<0.5",
        "pyyaml>=6.0.2,<7",
    ],
    include_package_data=True,
    extras_require={
        "test": [
            "pytest>=9.0.3,<10",
        ],
    },
)
