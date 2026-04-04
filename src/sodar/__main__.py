from __future__ import annotations

import uvicorn

from sodar.config import settings


def main() -> None:
    uvicorn.run(
        "sodar.app:create_app",
        factory=True,
        host=settings.server.host,
        port=settings.server.port,
        reload=False,
    )


if __name__ == "__main__":
    main()
