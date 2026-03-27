"""FastAPI sidecar API for the Autopilot dashboard."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from autopilot.api.routes import accounts, events, intake, projects

app = FastAPI(title="Autopilot API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(projects.router, prefix="/api/projects", tags=["projects"])
app.include_router(accounts.router, prefix="/api/accounts", tags=["accounts"])
app.include_router(events.router, prefix="/api/events", tags=["events"])
app.include_router(intake.router, prefix="/api/intake", tags=["intake"])


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
