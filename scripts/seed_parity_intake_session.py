#!/usr/bin/env python3
"""Create one synthetic Autopilot intake session for live parity seeding."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from autopilot.core.config import load_config
from autopilot.core.intake import IntakeSession
from autopilot.core.intake_sessions import intake_session_path, save_intake_session


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--summary", required=True)
    parser.add_argument("--user-message", required=True)
    parser.add_argument("--assistant-message", required=True)
    args = parser.parse_args()

    config = load_config(Path.home() / ".autopilot" / "config.yaml")
    session = IntakeSession(
        session_id=args.session_id,
        messages=[
            {"role": "user", "content": args.user_message},
            {"role": "assistant", "content": args.assistant_message},
        ],
        spec_bootstrap={
            "title": args.title,
            "summary": args.summary,
            "deliverables": [
                "Validate one fully linked discovery and execution chain.",
                "Keep parity surfaces consistent across dashboard, review, inbox, and portfolio.",
            ],
            "constraints": [
                "Use the unified shell browser contract only.",
                "Keep discovery and execution ids linked for parity audits.",
            ],
        },
        project_name=args.title,
    )
    save_intake_session(config, session)
    print(
        json.dumps(
            {
                "session_id": session.session_id,
                "autopilot_home": str(config.autopilot_home),
                "path": str(intake_session_path(config, session.session_id)),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
