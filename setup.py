from setuptools import find_packages
from setuptools import setup


setup(
    name="dundercode",
    packages=find_packages(),
    python_requires=">=3.9",
    install_requires=[
        "asgiref==3.6.0",
        "cryptography==3.*",
        "uvicorn[standard]==0.27.1",
        "openai>=1.0",
        "ddkypy@git+https://github.com/Kyle-Verhoog/datadog-python.git@c7b8a40#egg=ddkypy",
    ],
)
