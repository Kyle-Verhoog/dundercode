from dundercode.crypt import encrypt


if __name__ == "__main__":
    """
    Usage:
        # have transcript.csv in root of repository
        KEY=... python -m scripts.encrypt
    """
    data = encrypt("transcript.csv")
    with open("transcript", "wb") as f:
        f.write(data)
