from setuptools import find_packages
from setuptools import setup


setup(
    name="dundercode",
    packages=find_packages(),
    python_requires=">=3.9",
    install_requires=[
        "cryptography==3.*",
        "fastapi==0.70.*",
        "uvicorn[standard]",
        "yattag",
    ],
)
