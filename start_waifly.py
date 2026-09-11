import os

import uvicorn

from app.config import settings

if __name__ == "__main__":
    port = int(
        os.environ.get("PORT")
        or os.environ.get("SERVER_PORT")
        or settings.app_port
    )
    host = settings.app_host or "0.0.0.0"
    uvicorn.run("app.main:app", host=host, port=port, reload=False)