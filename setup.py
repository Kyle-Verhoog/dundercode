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
        "ddkypy@git+https://github.com/Kyle-Verhoog/datadog-python.git@c4ed172a03c08d7769e079ae0792c2661398d46d#egg=ddkypy",
    ],
)
