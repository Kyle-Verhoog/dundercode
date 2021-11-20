
if __name__ == "__main__":
    import os
    import uvicorn

    port = int(os.getenv("PORT", 8000))
    uvicorn.run("dundercode.app:app", host="0.0.0.0", port=port, reload=True)
