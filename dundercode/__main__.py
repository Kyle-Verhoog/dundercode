if __name__ == "__main__":
    import os
    import uvicorn

    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "0.0.0.0")
    uvicorn.run("dundercode.app:app", host=host, port=port, log_config={
        "version": 1,
        "disable_existing_loggers": False,
    }, reload=True)
