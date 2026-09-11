import uvicorn

from app.config import settings

if __name__ == "__main__":
    kwargs = {}
    if getattr(settings, "ssl_enabled", False):
        kwargs["ssl_certfile"] = settings.ssl_certfile
        kwargs["ssl_keyfile"] = settings.ssl_keyfile
    uvicorn.run(
        "app.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=True,
        **kwargs,
    )
