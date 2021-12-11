from setuptools import find_packages
from setuptools import setup


setup(
    name="dundercode",
    packages=find_packages(),
    python_requires=">=3.9",
    install_requires=[
        "asgiref",
        "cryptography==3.*",
        "uvicorn[standard]",
    ],
)
