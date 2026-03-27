"""SSE event stream route."""

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from autopilot.api.sse import broadcaster

router = APIRouter()


@router.get("/")
async def event_stream() -> StreamingResponse:
    return StreamingResponse(
        broadcaster.subscribe(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
