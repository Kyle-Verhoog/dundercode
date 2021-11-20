from dundercode.crypt import encrypt


if __name__ == "__main__":
    """
    Usage:
        KEY=... python -m scripts.encrypt
    """
    data = encrypt("transcript.csv")
    with open("transcript", "wb") as f:
        f.write(data)
