from setuptools import find_packages
from setuptools import setup


setup(
    name="dundercode",
    packages=find_packages(),
    python_requires=">=3.9",
    install_requires=[
        "asgiref==3.6.0",
        "cryptography==3.*",
        "uvicorn[standard]==0.20.0",
        "ddkypy@git+https://github.com/Kyle-Verhoog/datadog-python.git@ea41659a572b1476a95e4d91b9f313796a8efb87#egg=ddkypy",
    ],
)
