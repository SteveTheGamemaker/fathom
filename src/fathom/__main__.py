from __future__ import annotations

import uvicorn

from fathom.config import settings


def main() -> None:
    uvicorn.run(
        "fathom.app:create_app",
        factory=True,
        host=settings.server.host,
        port=settings.server.port,
        reload=False,
    )


if __name__ == "__main__":
    main()
