import os

from cryptography.fernet import Fernet


_key = os.getenv("KEY")
assert _key, "Specify $KEY to decrypt"
_fernet = Fernet(_key.encode("utf-8"))


def encrypt(fname: str) -> bytes:
    with open(fname, "rb") as f:
        data = f.read()
    return _fernet.encrypt(data)


def decrypt(fname: str) -> bytes:
    with open(fname, "rb") as f:
        data = f.read()
    return _fernet.decrypt(data)
