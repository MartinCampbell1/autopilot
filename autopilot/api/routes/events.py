"""SSE event stream route backed by the filesystem event log."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi import APIRouter, Header, Query
from fastapi.responses import StreamingResponse

from autopilot.api.deps import get_config
from autopilot.core.audit_chain import build_audit_bundle, read_jsonl_records, verify_audit_chain
from autopilot.core.control_messages import (
    BoundedMessageIdSet,
    build_structured_event_envelope,
    format_sse_frame,
    parse_control_message,
    parse_sse_replay_sequence,
    resolve_control_event_id,
)

router = APIRouter()


def _load_event_record(line: str) -> dict | None:
    try:
        payload = json.loads(line)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _render_sse_event(payload: dict, *, sequence: int, structured: bool) -> str:
    parsed_control = parse_control_message(payload)
    event_name = str(payload.get("event") or getattr(parsed_control, "type", "project_event"))
    event_id = resolve_control_event_id(payload, sequence)
    if structured:
        data = (
            {
                **parsed_control.model_dump(exclude_none=True),
                "event_id": event_id,
                "sequence": sequence,
                "source": "events_log",
                "timestamp": str(payload.get("timestamp") or "").strip() or None,
            }
            if parsed_control is not None
            else build_structured_event_envelope(payload, sequence=sequence).model_dump(exclude_none=True)
        )
    else:
        data = payload
    return format_sse_frame(event_name, data, event_id=event_id)


def _resolve_replay_sequence(path: Path, *, from_sequence: int | None = None, last_event_id: str | None = None) -> int | None:
    if from_sequence is not None:
        return from_sequence
    parsed_replay_sequence = parse_sse_replay_sequence(last_event_id)
    if parsed_replay_sequence is not None:
        return parsed_replay_sequence
    normalized_event_id = str(last_event_id or "").strip()
    if not normalized_event_id:
        return None
    sequence = 0
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            sequence += 1
            payload = _load_event_record(line)
            if payload is None:
                continue
            if resolve_control_event_id(payload, sequence) == normalized_event_id:
                return sequence
    # Bias toward replaying from the beginning instead of risking state loss after reconnect.
    return 0


async def _event_generator(
    path: Path,
    *,
    structured: bool = False,
    from_sequence: int | None = None,
    last_event_id: str | None = None,
):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch(exist_ok=True)

    replay_from_sequence = _resolve_replay_sequence(
        path,
        from_sequence=from_sequence,
        last_event_id=last_event_id,
    )
    seen_event_ids = BoundedMessageIdSet(4096)

    with path.open("r", encoding="utf-8") as handle:
        sequence = 0
        if replay_from_sequence is None:
            handle.seek(0, 2)
        else:
            for line in handle:
                sequence += 1
                if sequence <= replay_from_sequence:
                    continue
                payload = _load_event_record(line)
                if payload is None:
                    continue
                event_id = resolve_control_event_id(payload, sequence)
                if seen_event_ids.has(event_id):
                    continue
                seen_event_ids.add(event_id)
                yield _render_sse_event(payload, sequence=sequence, structured=structured)
        while True:
            line = handle.readline()
            if not line:
                yield ": ping\n\n"
                await asyncio.sleep(1)
                continue

            sequence += 1
            payload = _load_event_record(line)
            if payload is None:
                continue
            event_id = resolve_control_event_id(payload, sequence)
            if seen_event_ids.has(event_id):
                continue
            seen_event_ids.add(event_id)
            yield _render_sse_event(payload, sequence=sequence, structured=structured)


@router.get("/")
async def event_stream(
    structured: bool = Query(default=False),
    from_sequence: int | None = Query(default=None, ge=0),
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
) -> StreamingResponse:
    config = get_config()
    return StreamingResponse(
        _event_generator(
            config.events_log_path,
            structured=structured,
            from_sequence=from_sequence,
            last_event_id=last_event_id,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@router.get("/audit")
async def event_stream_audit(
    limit: int = Query(default=200, ge=1, le=5000),
    include_entries: bool = Query(default=True),
) -> dict[str, object]:
    config = get_config()
    entries = read_jsonl_records(config.events_log_path)
    selected_entries = entries[-limit:] if limit > 0 else entries
    return {
        "audit": build_audit_bundle(
            selected_entries,
            chain_kind="events",
            include_entries=include_entries,
            config=config,
            source_verification=verify_audit_chain(entries, chain_kind="events", config=config),
            source_entry_count=len(entries),
        )
    }
