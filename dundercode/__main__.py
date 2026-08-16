if __name__ == "__main__":
    import os
    import uvicorn

    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "0.0.0.0")
    # The reloader watches the source tree and respawns the worker on any
    # change. That is what you want locally and not in prod, where it doubles
    # the process count and re-parses the 6.5MB transcript on every respawn.
    reload = os.getenv("DD_ENV") != "prod"
    uvicorn.run("dundercode.app:app", host=host, port=port, log_config={
        "version": 1,
        "disable_existing_loggers": False,
    }, reload=reload)
