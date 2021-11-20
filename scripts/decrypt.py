from dundercode.crypt import decrypt


if __name__ == "__main__":
    """
    Usage:
        KEY=... python -m scripts.decrypt > transcript.csv
    """
    data = decrypt("transcript")
    print(data.decode("utf-8"))
