"""Programmatic API server entrypoint for local development."""

from __future__ import annotations

import os

import uvicorn

from autopilot.api.main import app


def main() -> None:
    host = os.getenv("AUTOPILOT_API_HOST", "0.0.0.0")
    port = int(os.getenv("AUTOPILOT_API_PORT", "8420"))
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
