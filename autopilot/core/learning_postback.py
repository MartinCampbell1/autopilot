"""Automatic outcome postback from Autopilot to Quorum.

Closes the learning loop: when an execution project reaches an outcome,
this worker posts the result back to Quorum's feedback ingest endpoint
so the discovery layer can learn from execution.

Idempotency keys are persisted to disk so duplicate postbacks are not sent
after process restarts.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import threading
from pathlib import Path
from typing import Callable

import httpx
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class PostbackConfig(BaseModel):
    """Configuration for the learning postback worker.

    quorum_feedback_base_url should include the orchestrate prefix, e.g.:
        http://127.0.0.1:8000/api/orchestrate
    The postback will append /discovery/ideas/{id}/execution-feedback.
    """

    quorum_feedback_base_url: str | None = None
    retry_max: int = 3
    retry_base_delay_sec: float = 1.0
    idempotency_enabled: bool = True
    idempotency_dir: str | None = None


class LearningPostback:
    """Posts execution outcomes back to Quorum's feedback ingest."""

    def __init__(self, config: PostbackConfig):
        self._config = config
        self._sent_keys: set[str] = set()
        self._idempotency_path: Path | None = None

        if config.idempotency_enabled:
            idem_dir = config.idempotency_dir or os.environ.get("AUTOPILOT_HOME", "")
            if idem_dir:
                self._idempotency_path = Path(idem_dir) / "learning-postback-sent.json"
                self._load_idempotency_keys()

    def _load_idempotency_keys(self) -> None:
        """Load persisted idempotency keys from disk."""
        if self._idempotency_path and self._idempotency_path.exists():
            try:
                data = json.loads(self._idempotency_path.read_text())
                self._sent_keys = set(data.get("sent_keys", []))
            except Exception:
                self._sent_keys = set()

    def _persist_idempotency_keys(self) -> None:
        """Persist idempotency keys to disk."""
        if self._idempotency_path:
            self._idempotency_path.parent.mkdir(parents=True, exist_ok=True)
            self._idempotency_path.write_text(
                json.dumps({"sent_keys": sorted(self._sent_keys)})
            )

    def _idempotency_key(self, idea_id: str, outcome: dict) -> str:
        outcome_id = outcome.get("outcome_id", "")
        raw = f"{idea_id}:{outcome_id}"
        return hashlib.sha256(raw.encode()).hexdigest()

    async def maybe_post_outcome(
        self,
        *,
        idea_id: str,
        outcome: dict,
        project_id: str,
        project_name: str,
    ) -> dict:
        if not self._config.quorum_feedback_base_url:
            return {"sent": False, "reason": "no_quorum_url"}

        key = ""
        if self._config.idempotency_enabled:
            key = self._idempotency_key(idea_id, outcome)
            if key in self._sent_keys:
                return {"sent": False, "reason": "already_sent", "idempotency_key": key}

        base = self._config.quorum_feedback_base_url.rstrip("/")
        url = f"{base}/discovery/ideas/{idea_id}/execution-feedback"

        payload = {
            "outcome": outcome,
            "autopilot_project_id": project_id,
            "autopilot_project_name": project_name,
            "actor": "autopilot",
        }

        last_error: Exception | None = None
        for attempt in range(self._config.retry_max):
            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    response = await client.post(url, json=payload)
                    response.raise_for_status()

                if self._config.idempotency_enabled and key:
                    self._sent_keys.add(key)
                    self._persist_idempotency_keys()

                return {"sent": True, "url": url}
            except (httpx.HTTPError, httpx.TimeoutException) as exc:
                last_error = exc
                delay = self._config.retry_base_delay_sec * (2 ** attempt)
                logger.warning(
                    "Postback attempt %d/%d failed for idea %s: %s. Retrying in %.1fs",
                    attempt + 1, self._config.retry_max, idea_id, exc, delay,
                )
                if attempt < self._config.retry_max - 1:
                    await asyncio.sleep(delay)

        logger.error(
            "Postback failed after %d attempts for idea %s: %s",
            self._config.retry_max, idea_id, last_error,
        )
        return {"sent": False, "reason": "delivery_failed", "error": str(last_error)}


# ---------------------------------------------------------------------------
# Module-level singleton for auto-wiring
# ---------------------------------------------------------------------------

_POSTBACK_INSTANCE: LearningPostback | None = None


def get_learning_postback() -> LearningPostback:
    """Return a module-level singleton postback worker.

    Reads QUORUM_FEEDBACK_BASE_URL and AUTOPILOT_HOME from environment.
    """
    global _POSTBACK_INSTANCE
    if _POSTBACK_INSTANCE is None:
        _POSTBACK_INSTANCE = LearningPostback(
            PostbackConfig(
                quorum_feedback_base_url=os.environ.get("QUORUM_FEEDBACK_BASE_URL"),
                idempotency_dir=os.environ.get("AUTOPILOT_HOME", ""),
            )
        )
    return _POSTBACK_INSTANCE


async def auto_post_learning_outcome(
    *,
    idea_id: str,
    outcome: dict,
    project_id: str,
    project_name: str,
) -> dict:
    """Convenience wrapper: post outcome via the module singleton.

    Call this from ``maybe_refresh_execution_outcome_bundle_for_event``
    or any other point where an outcome is finalized.
    """
    postback = get_learning_postback()
    return await postback.maybe_post_outcome(
        idea_id=idea_id,
        outcome=outcome,
        project_id=project_id,
        project_name=project_name,
    )


def dispatch_learning_postback(
    *,
    idea_id: str,
    outcome: dict,
    project_id: str,
    project_name: str,
    on_success: Callable[[], None] | None = None,
) -> None:
    """Safely schedule one background postback from sync or async contexts."""

    async def _runner() -> None:
        try:
            result = await auto_post_learning_outcome(
                idea_id=idea_id,
                outcome=outcome,
                project_id=project_id,
                project_name=project_name,
            )
            if result.get("sent") and on_success is not None:
                on_success()
        except Exception as exc:
            logger.warning("Learning postback trigger failed: %s", exc)

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        threading.Thread(
            target=lambda: asyncio.run(_runner()),
            name="learning-postback",
            daemon=True,
        ).start()
        return

    loop.create_task(_runner())
