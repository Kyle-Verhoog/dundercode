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
        "ddkypy@git+https://github.com/Kyle-Verhoog/datadog-python.git@7d101f6e559ef723331ada8f31a661a306524b99#egg=ddkypy",
    ],
)
