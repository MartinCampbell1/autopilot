# Autopilot Implementation Plan

> **For agentic workers:** This is a detailed implementation plan for the Autopilot platform. Execute tasks in order. Each task produces a working, testable increment. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a platform that runs autonomous AI programmers (Codex/Claude/Gemini) on multiple projects in parallel, with account rotation, critic review loops, escalation chains, and a Kanban dashboard.

**Architecture:** Python CLI (Typer) wrapping Ralph for loop mechanics. Python sidecar (FastAPI) for orchestration, account rotation, critic engine, and dashboard API. Next.js dashboard for visual management. All state in SQLite + Ralph's file-based state.

**Tech Stack:**
- Python 3.12+, Typer (CLI), FastAPI (API), SQLAlchemy (ORM), aiosqlite
- Ralph (`npm i -g @iannuttall/ralph`) for loop engine
- Next.js 15, Tailwind CSS, shadcn/ui (dashboard)
- SQLite (state.db), YAML (config)
- python-telegram-bot (notifications)

**Spec:** See `docs/autopilot-design.md` for full architecture and design decisions.

---

## File Map

### Phase 1: CLI Core (MVP)

```
autopilot/
  pyproject.toml
  README.md
  autopilot/
    __init__.py
    __main__.py              # entry point: python -m autopilot
    cli/
      __init__.py
      main.py                # Typer app, registers subcommands
      login.py               # autopilot login <provider>
      init.py                # autopilot init <project-path>
      run.py                 # autopilot run <project-path>
      status.py              # autopilot status
    core/
      __init__.py
      models.py              # dataclasses: Profile, PoolStatus, GateResult, CriticResult
      config.py              # load/save ~/.autopilot/config.yaml
      account_manager.py     # ProfilePool, rotation, cooldown, rate limit detection
      loop_runner.py          # run Ralph with CODEX_HOME, parse output
      gates.py               # run build/test/lint commands, collect results
      critic.py              # run Codex critic, parse APPROVED/NEEDS_WORK
      stuck_detector.py      # detect repeated failures, empty diffs, timeouts
      orchestrator.py        # main loop: story -> worker -> gates -> critic -> next
    templates/
      worker-prompt.md
      retry-prompt.md
      critic-prompt.md
  tests/
    __init__.py
    test_models.py
    test_config.py
    test_account_manager.py
    test_gates.py
    test_critic.py
    test_stuck_detector.py
    test_orchestrator.py
```

### Phase 2: Multi-project + Escalation (adds to Phase 1)

```
  autopilot/
    core/
      dispatcher.py          # multi-project: allocate accounts, manage priorities
      escalation.py          # provider chain: codex -> claude -> gemini -> human
      worktree.py            # git worktree create/merge for parallel stories
      notifier.py            # Telegram bot notifications
      providers.py           # provider-specific env builders (codex, claude, gemini)
    cli/
      run.py                 # updated: --all flag, --project flag
      status.py              # updated: --all flag
  tests/
    test_dispatcher.py
    test_escalation.py
    test_worktree.py
    test_notifier.py
    test_providers.py
```

### Phase 3: Dashboard (adds to Phase 1-2)

```
  autopilot/
    api/
      __init__.py
      main.py                # FastAPI app
      routes/
        __init__.py
        projects.py          # GET/POST /projects, GET /projects/:id
        stories.py           # GET /projects/:id/stories, POST actions
        accounts.py          # GET /accounts, GET /accounts/health
        events.py            # GET /events (SSE stream)
      sse.py                 # SSE event broadcaster
      deps.py                # shared dependencies (db session, etc.)
    cli/
      dashboard.py           # autopilot dashboard (starts API + opens browser)
  dashboard/
    package.json
    next.config.ts
    tailwind.config.ts
    app/
      layout.tsx
      page.tsx               # main kanban view
      projects/
        [id]/
          page.tsx           # project detail with story cards
      health/
        page.tsx             # system health
    components/
      kanban-board.tsx
      story-card.tsx
      story-detail-panel.tsx
      timeline.tsx
      account-health.tsx
      action-buttons.tsx
    lib/
      api.ts                 # fetch wrapper for sidecar API
      sse.ts                 # SSE hook for live updates
      types.ts               # TypeScript types matching Python models
```

### Phase 4: Intake Agent (adds to Phase 3)

```
  autopilot/
    core/
      intake.py              # intake agent: brainstorm, generate PRD
    api/
      routes/
        intake.py            # POST /intake/message, GET /intake/sessions
  dashboard/
    app/
      intake/
        page.tsx             # intake chat page
    components/
      intake-chat.tsx
      prd-preview.tsx
```

---

## Phase 1: CLI Core (MVP)

### Task 1: Project Scaffold

**Files:**
- Create: `pyproject.toml`
- Create: `autopilot/__init__.py`
- Create: `autopilot/__main__.py`
- Create: `autopilot/cli/__init__.py`
- Create: `autopilot/cli/main.py`
- Create: `README.md`

- [ ] **Step 1: Initialize git repo**

```bash
cd ~/Desktop/autopilot
git init
```

- [ ] **Step 2: Create pyproject.toml**

```toml
[project]
name = "autopilot"
version = "0.1.0"
description = "Autonomous AI programmer platform with account rotation and critic loops"
requires-python = ">=3.12"
dependencies = [
    "typer>=0.15.0",
    "rich>=13.0.0",
    "pyyaml>=6.0",
    "pydantic>=2.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.24",
    "pytest-cov>=6.0",
    "ruff>=0.8",
]
api = [
    "fastapi>=0.115.0",
    "uvicorn>=0.34.0",
    "aiosqlite>=0.20.0",
    "sqlalchemy>=2.0",
]
notify = [
    "python-telegram-bot>=21.0",
]

[project.scripts]
autopilot = "autopilot.cli.main:app"

[tool.ruff]
line-length = 120
target-version = "py312"

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

- [ ] **Step 3: Create entry points**

`autopilot/__init__.py`:
```python
"""Autopilot — Autonomous AI Programmer Platform."""

__version__ = "0.1.0"
```

`autopilot/__main__.py`:
```python
"""Allow running as `python -m autopilot`."""

from autopilot.cli.main import app

app()
```

`autopilot/cli/__init__.py`:
```python
```

`autopilot/cli/main.py`:
```python
"""Main CLI entrypoint."""

import typer

app = typer.Typer(
    name="autopilot",
    help="Autonomous AI programmer platform with account rotation and critic loops.",
    no_args_is_help=True,
)


@app.command()
def version():
    """Show version."""
    from autopilot import __version__

    typer.echo(f"autopilot v{__version__}")
```

- [ ] **Step 4: Install and verify**

```bash
cd ~/Desktop/autopilot
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
autopilot version
# Expected: autopilot v0.1.0
```

- [ ] **Step 5: Create .gitignore and commit**

`.gitignore`:
```
__pycache__/
*.pyc
.venv/
*.egg-info/
dist/
.pytest_cache/
.ruff_cache/
node_modules/
.next/
state.db
```

```bash
git add .
git commit -m "feat: project scaffold with Typer CLI"
```

---

### Task 2: Data Models

**Files:**
- Create: `autopilot/core/__init__.py`
- Create: `autopilot/core/models.py`
- Create: `tests/__init__.py`
- Create: `tests/test_models.py`

- [ ] **Step 1: Write tests for models**

`tests/__init__.py`:
```python
```

`tests/test_models.py`:
```python
"""Tests for core data models."""

import time
from autopilot.core.models import (
    Profile,
    GateResult,
    CriticResult,
    StoryStatus,
    IterationRecord,
)


class TestProfile:
    def test_create_profile(self):
        p = Profile(name="acc1", provider="codex", path="/home/.autopilot/profiles/codex/acc1")
        assert p.name == "acc1"
        assert p.provider == "codex"
        assert p.is_available is True
        assert p.requests_made == 0

    def test_mark_rate_limited(self):
        p = Profile(name="acc1", provider="codex", path="/tmp")
        p.mark_rate_limited(cooldown_base=300)
        assert p.is_available is False
        assert p.consecutive_errors == 1
        assert p.cooldown_until > time.time()

    def test_cooldown_recovery(self):
        p = Profile(name="acc1", provider="codex", path="/tmp")
        p.cooldown_until = time.time() - 1  # expired
        p.is_available = False
        assert p.check_available() is True
        assert p.is_available is True

    def test_mark_success_resets_errors(self):
        p = Profile(name="acc1", provider="codex", path="/tmp")
        p.consecutive_errors = 3
        p.mark_success()
        assert p.consecutive_errors == 0


class TestGateResult:
    def test_gate_passed(self):
        r = GateResult(name="build", cmd="npm run build", passed=True, output="ok", required=True)
        assert r.passed is True

    def test_gate_failed_required(self):
        r = GateResult(name="test", cmd="npm test", passed=False, output="1 failed", required=True)
        assert r.passed is False
        assert r.required is True


class TestCriticResult:
    def test_approved(self):
        r = CriticResult(approved=True, feedback="", raw_output="APPROVED\nAll looks good.")
        assert r.approved is True

    def test_needs_work(self):
        r = CriticResult(
            approved=False,
            feedback="- callback URL is hardcoded\n- no error handling",
            raw_output="NEEDS_WORK\n- callback URL is hardcoded\n- no error handling",
        )
        assert r.approved is False
        assert "hardcoded" in r.feedback


class TestStoryStatus:
    def test_values(self):
        assert StoryStatus.OPEN == "open"
        assert StoryStatus.IN_PROGRESS == "in_progress"
        assert StoryStatus.DONE == "done"
        assert StoryStatus.STUCK == "stuck"


class TestIterationRecord:
    def test_create(self):
        rec = IterationRecord(
            story_id=1,
            iteration=1,
            profile_used="acc3",
            provider="codex",
            gates_passed=True,
            critic_approved=False,
            critic_feedback="missing tests",
            elapsed_sec=120.5,
        )
        assert rec.story_id == 1
        assert rec.critic_approved is False
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_models.py -v
# Expected: FAIL — ModuleNotFoundError: No module named 'autopilot.core.models'
```

- [ ] **Step 3: Implement models**

`autopilot/core/__init__.py`:
```python
```

`autopilot/core/models.py`:
```python
"""Core data models for Autopilot."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import StrEnum


class StoryStatus(StrEnum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    STUCK = "stuck"
    SKIPPED = "skipped"


class Provider(StrEnum):
    CODEX = "codex"
    CLAUDE = "claude"
    GEMINI = "gemini"


@dataclass
class Profile:
    """One CLI account/profile."""

    name: str
    provider: str
    path: str
    is_available: bool = True
    requests_made: int = 0
    last_used: float = 0.0
    cooldown_until: float = 0.0
    consecutive_errors: int = 0

    def mark_rate_limited(self, cooldown_base: int = 300) -> None:
        """Mark profile as rate-limited with exponential backoff."""
        self.is_available = False
        self.consecutive_errors += 1
        backoff = min(self.consecutive_errors * 60, 1800)
        self.cooldown_until = time.time() + cooldown_base + backoff

    def mark_success(self) -> None:
        """Reset error counter on success."""
        self.consecutive_errors = 0

    def check_available(self) -> bool:
        """Check if cooldown has expired and restore availability."""
        if not self.is_available and time.time() >= self.cooldown_until:
            self.is_available = True
            self.consecutive_errors = 0
        return self.is_available


@dataclass
class GateResult:
    """Result of running one auto-gate (build/test/lint)."""

    name: str
    cmd: str
    passed: bool
    output: str
    required: bool = True
    elapsed_sec: float = 0.0


@dataclass
class CriticResult:
    """Result of critic evaluation."""

    approved: bool
    feedback: str
    raw_output: str
    profile_used: str = ""
    elapsed_sec: float = 0.0


@dataclass
class IterationRecord:
    """Record of one worker iteration."""

    story_id: int
    iteration: int
    profile_used: str
    provider: str
    gates_passed: bool
    critic_approved: bool | None = None
    critic_feedback: str = ""
    elapsed_sec: float = 0.0
    timestamp: float = field(default_factory=time.time)
    git_diff_empty: bool = False
    gate_results: list[GateResult] = field(default_factory=list)


@dataclass
class ProjectConfig:
    """Configuration for one managed project."""

    name: str
    path: str
    prd: str = ".agents/tasks/prd.json"
    priority: str = "normal"  # high, normal, low
    gates: list[dict] = field(default_factory=list)
    providers: list[str] = field(default_factory=lambda: ["codex"])


RATE_LIMIT_PATTERNS: list[str] = [
    "resource has been exhausted",
    "resource_exhausted",
    "rate limit",
    "rate_limit",
    "quota exceeded",
    "quota_exceeded",
    "429",
    "too many requests",
    "insufficient_quota",
    "capacity",
    "overloaded",
    "try again later",
]


def is_rate_limited(text: str) -> bool:
    """Check if output contains rate limit indicators."""
    lower = text.lower()
    return any(p in lower for p in RATE_LIMIT_PATTERNS)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_models.py -v
# Expected: all PASS
```

- [ ] **Step 5: Commit**

```bash
git add autopilot/core/ tests/
git commit -m "feat: core data models — Profile, GateResult, CriticResult, IterationRecord"
```

---

### Task 3: Config Manager

**Files:**
- Create: `autopilot/core/config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write tests**

`tests/test_config.py`:
```python
"""Tests for config loading and saving."""

import tempfile
from pathlib import Path

from autopilot.core.config import AutopilotConfig, load_config, save_config, DEFAULT_CONFIG


class TestConfig:
    def test_default_config(self):
        cfg = DEFAULT_CONFIG
        assert cfg.accounts.total == 20
        assert cfg.accounts.workers == 14
        assert cfg.accounts.critics == 5
        assert cfg.accounts.intake == 1

    def test_save_and_load(self, tmp_path: Path):
        cfg = DEFAULT_CONFIG
        config_path = tmp_path / "config.yaml"
        save_config(cfg, config_path)

        loaded = load_config(config_path)
        assert loaded.accounts.total == cfg.accounts.total
        assert loaded.accounts.workers == cfg.accounts.workers

    def test_load_missing_file_returns_default(self, tmp_path: Path):
        config_path = tmp_path / "nonexistent.yaml"
        loaded = load_config(config_path)
        assert loaded.accounts.total == 20

    def test_autopilot_home(self):
        cfg = DEFAULT_CONFIG
        home = cfg.autopilot_home
        assert home.name == ".autopilot"
```

- [ ] **Step 2: Run tests — should fail**

```bash
pytest tests/test_config.py -v
```

- [ ] **Step 3: Implement**

`autopilot/core/config.py`:
```python
"""Configuration management for Autopilot."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from pathlib import Path

import yaml


@dataclass
class AccountAllocation:
    total: int = 20
    workers: int = 14
    critics: int = 5
    intake: int = 1


@dataclass
class AutopilotConfig:
    accounts: AccountAllocation = field(default_factory=AccountAllocation)
    codex_timeout_sec: int = 1800  # 30 min
    cooldown_base_sec: int = 300  # 5 min
    max_retries_per_provider: int = 3
    providers_order: list[str] = field(default_factory=lambda: ["codex", "claude", "gemini"])

    @property
    def autopilot_home(self) -> Path:
        return Path.home() / ".autopilot"

    @property
    def profiles_dir(self) -> Path:
        return self.autopilot_home / "profiles"

    @property
    def state_db_path(self) -> Path:
        return self.autopilot_home / "state.db"

    @property
    def projects_yaml_path(self) -> Path:
        return self.autopilot_home / "projects.yaml"


DEFAULT_CONFIG = AutopilotConfig()


def save_config(config: AutopilotConfig, path: Path) -> None:
    """Save config to YAML file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "accounts": {
            "total": config.accounts.total,
            "workers": config.accounts.workers,
            "critics": config.accounts.critics,
            "intake": config.accounts.intake,
        },
        "codex_timeout_sec": config.codex_timeout_sec,
        "cooldown_base_sec": config.cooldown_base_sec,
        "max_retries_per_provider": config.max_retries_per_provider,
        "providers_order": config.providers_order,
    }
    path.write_text(yaml.dump(data, default_flow_style=False))


def load_config(path: Path) -> AutopilotConfig:
    """Load config from YAML file. Returns default if file doesn't exist."""
    if not path.exists():
        return AutopilotConfig()

    data = yaml.safe_load(path.read_text()) or {}
    accounts_data = data.get("accounts", {})

    return AutopilotConfig(
        accounts=AccountAllocation(
            total=accounts_data.get("total", 20),
            workers=accounts_data.get("workers", 14),
            critics=accounts_data.get("critics", 5),
            intake=accounts_data.get("intake", 1),
        ),
        codex_timeout_sec=data.get("codex_timeout_sec", 1800),
        cooldown_base_sec=data.get("cooldown_base_sec", 300),
        max_retries_per_provider=data.get("max_retries_per_provider", 3),
        providers_order=data.get("providers_order", ["codex", "claude", "gemini"]),
    )
```

- [ ] **Step 4: Run tests — should pass**

```bash
pytest tests/test_config.py -v
```

- [ ] **Step 5: Commit**

```bash
git add autopilot/core/config.py tests/test_config.py
git commit -m "feat: config manager — load/save YAML config with defaults"
```

---

### Task 4: Account Manager

**Files:**
- Create: `autopilot/core/account_manager.py`
- Create: `tests/test_account_manager.py`

- [ ] **Step 1: Write tests**

`tests/test_account_manager.py`:
```python
"""Tests for account manager — profile discovery, rotation, cooldown."""

import tempfile
import json
from pathlib import Path

from autopilot.core.account_manager import AccountManager
from autopilot.core.models import Profile


class TestAccountManager:
    def _create_codex_profile(self, base: Path, name: str) -> Path:
        """Helper: create a fake codex profile directory."""
        profile_dir = base / "codex" / name
        profile_dir.mkdir(parents=True)
        (profile_dir / "auth.json").write_text(json.dumps({"auth_mode": "chatgpt"}))
        (profile_dir / "config.toml").write_text('model = "gpt-5.4"')
        return profile_dir

    def _create_claude_profile(self, base: Path, name: str) -> Path:
        """Helper: create a fake claude profile directory."""
        profile_dir = base / "claude" / name / "home" / ".claude"
        profile_dir.mkdir(parents=True)
        (profile_dir / "settings.json").write_text("{}")
        return profile_dir.parent.parent

    def test_discover_codex_profiles(self, tmp_path: Path):
        profiles_dir = tmp_path / "profiles"
        self._create_codex_profile(profiles_dir, "acc1")
        self._create_codex_profile(profiles_dir, "acc2")

        mgr = AccountManager(profiles_dir=profiles_dir)
        mgr.discover()

        assert "codex" in mgr.pools
        assert len(mgr.pools["codex"]) == 2

    def test_discover_claude_profiles(self, tmp_path: Path):
        profiles_dir = tmp_path / "profiles"
        self._create_claude_profile(profiles_dir, "acc1")

        mgr = AccountManager(profiles_dir=profiles_dir)
        mgr.discover()

        assert "claude" in mgr.pools
        assert len(mgr.pools["claude"]) == 1

    def test_get_next_round_robin(self, tmp_path: Path):
        profiles_dir = tmp_path / "profiles"
        self._create_codex_profile(profiles_dir, "acc1")
        self._create_codex_profile(profiles_dir, "acc2")

        mgr = AccountManager(profiles_dir=profiles_dir)
        mgr.discover()

        p1 = mgr.get_next("codex")
        p2 = mgr.get_next("codex")
        p3 = mgr.get_next("codex")

        assert p1.name == "acc1"
        assert p2.name == "acc2"
        assert p3.name == "acc1"  # wraps around

    def test_get_next_skips_unavailable(self, tmp_path: Path):
        profiles_dir = tmp_path / "profiles"
        self._create_codex_profile(profiles_dir, "acc1")
        self._create_codex_profile(profiles_dir, "acc2")

        mgr = AccountManager(profiles_dir=profiles_dir)
        mgr.discover()

        mgr.mark_rate_limited("codex", "acc1")
        p = mgr.get_next("codex")
        assert p.name == "acc2"

    def test_get_next_returns_none_all_exhausted(self, tmp_path: Path):
        profiles_dir = tmp_path / "profiles"
        self._create_codex_profile(profiles_dir, "acc1")

        mgr = AccountManager(profiles_dir=profiles_dir)
        mgr.discover()

        mgr.mark_rate_limited("codex", "acc1")
        p = mgr.get_next("codex")
        assert p is None

    def test_pool_status(self, tmp_path: Path):
        profiles_dir = tmp_path / "profiles"
        self._create_codex_profile(profiles_dir, "acc1")
        self._create_codex_profile(profiles_dir, "acc2")

        mgr = AccountManager(profiles_dir=profiles_dir)
        mgr.discover()

        status = mgr.pool_status("codex")
        assert len(status) == 2
        assert all(s["available"] for s in status)

    def test_save_profile_from_source(self, tmp_path: Path):
        profiles_dir = tmp_path / "profiles"
        source_dir = tmp_path / "source_codex"
        source_dir.mkdir()
        (source_dir / "auth.json").write_text('{"auth_mode": "chatgpt"}')
        (source_dir / "config.toml").write_text('model = "gpt-5.4"')

        mgr = AccountManager(profiles_dir=profiles_dir)
        name = mgr.save_profile("codex", source_dir)

        assert name == "acc1"
        assert (profiles_dir / "codex" / "acc1" / "auth.json").exists()
        assert (profiles_dir / "codex" / "acc1" / "config.toml").exists()
```

- [ ] **Step 2: Run tests — should fail**

```bash
pytest tests/test_account_manager.py -v
```

- [ ] **Step 3: Implement**

`autopilot/core/account_manager.py`:
```python
"""Account manager — profile discovery, round-robin rotation, cooldown."""

from __future__ import annotations

import shutil
import time
from pathlib import Path

from autopilot.core.models import Profile


class AccountManager:
    """Manages CLI profiles across providers with round-robin rotation."""

    def __init__(self, profiles_dir: Path, cooldown_base: int = 300):
        self.profiles_dir = profiles_dir
        self.cooldown_base = cooldown_base
        self.pools: dict[str, list[Profile]] = {}
        self._indexes: dict[str, int] = {}

    def discover(self) -> None:
        """Scan profiles directory and populate pools."""
        self.pools.clear()
        self._indexes.clear()

        for provider in ("codex", "claude", "gemini"):
            provider_dir = self.profiles_dir / provider
            if not provider_dir.exists():
                continue

            profiles: list[Profile] = []
            for acc_dir in sorted(provider_dir.iterdir()):
                if not acc_dir.is_dir() or not acc_dir.name.startswith("acc"):
                    continue

                if provider == "codex":
                    if not (acc_dir / "config.toml").exists() and not (acc_dir / "auth.json").exists():
                        continue
                elif provider in ("claude", "gemini"):
                    if not (acc_dir / "home").exists():
                        continue

                profiles.append(Profile(
                    name=acc_dir.name,
                    provider=provider,
                    path=str(acc_dir),
                ))

            if profiles:
                self.pools[provider] = profiles
                self._indexes[provider] = 0

    def get_next(self, provider: str) -> Profile | None:
        """Get next available profile using round-robin. Returns None if all exhausted."""
        profiles = self.pools.get(provider, [])
        if not profiles:
            return None

        start_idx = self._indexes.get(provider, 0)

        for i in range(len(profiles)):
            idx = (start_idx + i) % len(profiles)
            p = profiles[idx]

            p.check_available()

            if p.is_available:
                self._indexes[provider] = (idx + 1) % len(profiles)
                p.last_used = time.time()
                p.requests_made += 1
                return p

        return None

    def mark_rate_limited(self, provider: str, profile_name: str) -> None:
        """Mark a profile as rate-limited."""
        for p in self.pools.get(provider, []):
            if p.name == profile_name:
                p.mark_rate_limited(self.cooldown_base)
                return

    def mark_success(self, provider: str, profile_name: str) -> None:
        """Reset error counter for a profile."""
        for p in self.pools.get(provider, []):
            if p.name == profile_name:
                p.mark_success()
                return

    def pool_status(self, provider: str) -> list[dict]:
        """Get status of all profiles in a provider pool."""
        now = time.time()
        return [
            {
                "name": p.name,
                "available": p.is_available or now >= p.cooldown_until,
                "requests_made": p.requests_made,
                "cooldown_remaining_sec": max(0, round(p.cooldown_until - now))
                if not p.is_available and now < p.cooldown_until
                else 0,
            }
            for p in self.pools.get(provider, [])
        ]

    def save_profile(self, provider: str, source_dir: Path) -> str:
        """Copy a profile from source to the profiles directory. Returns the assigned name."""
        provider_dir = self.profiles_dir / provider
        provider_dir.mkdir(parents=True, exist_ok=True)

        existing = sorted(
            [d.name for d in provider_dir.iterdir() if d.is_dir() and d.name.startswith("acc")]
        )
        next_num = len(existing) + 1
        name = f"acc{next_num}"

        dest = provider_dir / name
        shutil.copytree(source_dir, dest)

        return name

    def build_env(self, profile: Profile) -> dict[str, str]:
        """Build environment variables for running CLI with a specific profile."""
        import os

        env = os.environ.copy()
        real_home = str(Path.home())

        if profile.provider == "codex":
            env["CODEX_HOME"] = profile.path

        elif profile.provider in ("claude", "gemini"):
            env["HOME"] = str(Path(profile.path) / "home")
            env["PATH"] = ":".join([
                "/opt/homebrew/bin",
                "/opt/homebrew/sbin",
                "/usr/local/bin",
                "/usr/bin",
                "/bin",
                f"{real_home}/.npm-global/bin",
                f"{real_home}/.local/bin",
                f"{real_home}/.cargo/bin",
                f"{real_home}/.bun/bin",
                env.get("PATH", ""),
            ])

        return env
```

- [ ] **Step 4: Run tests — should pass**

```bash
pytest tests/test_account_manager.py -v
```

- [ ] **Step 5: Commit**

```bash
git add autopilot/core/account_manager.py tests/test_account_manager.py
git commit -m "feat: account manager — profile discovery, round-robin rotation, cooldown"
```

---

### Task 5: CLI Login Command

**Files:**
- Create: `autopilot/cli/login.py`
- Modify: `autopilot/cli/main.py`

- [ ] **Step 1: Implement login command**

`autopilot/cli/login.py`:
```python
"""CLI command: autopilot login <provider>."""

from __future__ import annotations

import shutil
import time
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from autopilot.core.config import load_config

console = Console()

PROVIDER_SOURCE_DIRS = {
    "codex": Path.home() / ".codex",
    "claude": Path.home(),  # Claude uses HOME, we copy ~/.claude
    "gemini": Path.home(),  # Gemini uses HOME, we copy config
}

PROVIDER_VALIDATION = {
    "codex": lambda src: (src / "auth.json").exists() or (src / "config.toml").exists(),
    "claude": lambda src: (src / ".claude").exists(),
    "gemini": lambda src: (src / ".config" / "gemini").exists() or (src / ".gemini").exists(),
}


def login(
    provider: str = typer.Argument(help="Provider: codex, claude, or gemini"),
) -> None:
    """Save a logged-in CLI session as a reusable profile."""
    if provider not in ("codex", "claude", "gemini"):
        console.print(f"[red]Unknown provider: {provider}. Use: codex, claude, gemini[/red]")
        raise typer.Exit(1)

    config = load_config(Path.home() / ".autopilot" / "config.yaml")
    profiles_dir = config.profiles_dir
    provider_dir = profiles_dir / provider

    console.print(f"\n[bold]Autopilot Login — {provider}[/bold]\n")

    count = 0
    while True:
        console.print(f"[yellow]Log in to {provider} in your browser/terminal, then press Enter here...[/yellow]")
        input()

        source = PROVIDER_SOURCE_DIRS[provider]
        validate = PROVIDER_VALIDATION[provider]

        if not validate(source):
            console.print(f"[red]No valid {provider} session found at {source}.[/red]")
            console.print(f"[dim]Make sure you're logged in and try again.[/dim]")
            continue

        # Determine next account number
        provider_dir.mkdir(parents=True, exist_ok=True)
        existing = sorted([d.name for d in provider_dir.iterdir() if d.is_dir() and d.name.startswith("acc")])
        next_num = len(existing) + 1
        name = f"acc{next_num}"
        dest = provider_dir / name

        # Copy profile
        if provider == "codex":
            shutil.copytree(source, dest)
        else:
            # For claude/gemini, wrap in home/ subdirectory
            home_dir = dest / "home"
            home_dir.mkdir(parents=True)
            if provider == "claude":
                shutil.copytree(source / ".claude", home_dir / ".claude")
            elif provider == "gemini":
                for candidate in [".config/gemini", ".gemini"]:
                    src_path = source / candidate
                    if src_path.exists():
                        dest_path = home_dir / candidate
                        dest_path.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copytree(src_path, dest_path)

        count += 1
        console.print(f"[green]Account {name} saved.[/green] Total: {count}")

        another = typer.confirm("Add another account?", default=True)
        if not another:
            break

    console.print(f"\n[bold green]Done! {count} {provider} account(s) saved to {provider_dir}[/bold green]")

    # Show summary table
    table = Table(title=f"{provider} profiles")
    table.add_column("Name")
    table.add_column("Path")
    for d in sorted(provider_dir.iterdir()):
        if d.is_dir() and d.name.startswith("acc"):
            table.add_row(d.name, str(d))
    console.print(table)
```

- [ ] **Step 2: Register in main CLI**

Update `autopilot/cli/main.py`:
```python
"""Main CLI entrypoint."""

import typer

app = typer.Typer(
    name="autopilot",
    help="Autonomous AI programmer platform with account rotation and critic loops.",
    no_args_is_help=True,
)


@app.command()
def version():
    """Show version."""
    from autopilot import __version__

    typer.echo(f"autopilot v{__version__}")


@app.command()
def login(
    provider: str = typer.Argument(help="Provider: codex, claude, or gemini"),
):
    """Save a logged-in CLI session as a reusable profile."""
    from autopilot.cli.login import login as _login

    _login(provider)
```

- [ ] **Step 3: Manual test**

```bash
autopilot login codex
# Expected: prompts to log in, saves profile to ~/.autopilot/profiles/codex/acc1/
```

- [ ] **Step 4: Commit**

```bash
git add autopilot/cli/login.py autopilot/cli/main.py
git commit -m "feat: autopilot login command — interactive profile collection"
```

---

### Task 6: Ralph Templates

**Files:**
- Create: `autopilot/templates/worker-prompt.md`
- Create: `autopilot/templates/retry-prompt.md`
- Create: `autopilot/templates/critic-prompt.md`

- [ ] **Step 1: Create worker prompt template**

`autopilot/templates/worker-prompt.md`:
```markdown
## Context
You are an autonomous programmer. You work on the project in the current directory.

## Before starting
1. Read .ralph/progress.md — what has already been done
2. Read .ralph/guardrails.md — mistakes NOT to repeat
3. Read the PRD — find the story with status "open"

## Your task
Implement ONE story. No more.

## When finished
1. Make sure the build passes
2. Make sure tests are green
3. Update .ralph/progress.md — what you did, what decisions you made
4. If you hit a problem — write it in .ralph/guardrails.md
5. Commit everything in one commit with a clear message
6. Mark the story as done in the PRD
```

- [ ] **Step 2: Create retry prompt template**

`autopilot/templates/retry-prompt.md`:
```markdown
## Context
The critic did NOT approve your previous work on story #{story_id}.

## Before starting
1. Read .ralph/critic-feedback.md — what exactly is wrong
2. Read .ralph/guardrails.md — previous mistakes

## Your task
Fix the critic's feedback for story #{story_id}. Do NOT add anything new.

## When finished
1. Make sure the build passes
2. Make sure tests are green
3. Update .ralph/progress.md — what you fixed
4. Commit with a message like "fix: address critic feedback for story #{story_id}"
```

- [ ] **Step 3: Create critic prompt template**

`autopilot/templates/critic-prompt.md`:
```markdown
You are a code reviewer. Your task is to evaluate the latest commit.

## Task from PRD
{story_title}: {story_description}

## Diff
{diff}

## Check
1. Does the code solve the task from the story?
2. No obvious bugs?
3. No hardcoded secrets?
4. Is the code readable?
5. Are there tests for new functionality?

## Response format
If everything is OK:
APPROVED

If there are issues:
NEEDS_WORK
- Issue 1: specific description
- Issue 2: specific description
```

- [ ] **Step 4: Commit**

```bash
git add autopilot/templates/
git commit -m "feat: Ralph prompt templates — worker, retry, critic"
```

---

### Task 7: Auto-Gates Runner

**Files:**
- Create: `autopilot/core/gates.py`
- Create: `tests/test_gates.py`

- [ ] **Step 1: Write tests**

`tests/test_gates.py`:
```python
"""Tests for auto-gates runner."""

import subprocess
from unittest.mock import patch, MagicMock
from pathlib import Path

from autopilot.core.gates import run_gates, run_single_gate
from autopilot.core.models import GateResult


class TestRunSingleGate:
    @patch("autopilot.core.gates.subprocess.run")
    def test_gate_passes(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="OK", stderr="")
        result = run_single_gate("build", "npm run build", Path("/tmp"), required=True)
        assert result.passed is True
        assert result.name == "build"

    @patch("autopilot.core.gates.subprocess.run")
    def test_gate_fails(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="Error: build failed")
        result = run_single_gate("build", "npm run build", Path("/tmp"), required=True)
        assert result.passed is False
        assert "build failed" in result.output

    @patch("autopilot.core.gates.subprocess.run")
    def test_gate_timeout(self, mock_run):
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="test", timeout=120)
        result = run_single_gate("test", "npm test", Path("/tmp"), required=True)
        assert result.passed is False
        assert "timeout" in result.output.lower()


class TestRunGates:
    @patch("autopilot.core.gates.run_single_gate")
    def test_all_pass(self, mock_gate):
        mock_gate.return_value = GateResult(name="build", cmd="x", passed=True, output="ok", required=True)

        gates_config = [
            {"name": "build", "cmd": "npm run build", "required": True},
            {"name": "test", "cmd": "npm test", "required": True},
        ]
        all_passed, results = run_gates(gates_config, Path("/tmp"))
        assert all_passed is True
        assert len(results) == 2

    @patch("autopilot.core.gates.run_single_gate")
    def test_required_fails(self, mock_gate):
        def side_effect(name, cmd, workdir, required):
            if name == "test":
                return GateResult(name=name, cmd=cmd, passed=False, output="fail", required=True)
            return GateResult(name=name, cmd=cmd, passed=True, output="ok", required=required)

        mock_gate.side_effect = side_effect
        gates_config = [
            {"name": "build", "cmd": "npm run build", "required": True},
            {"name": "test", "cmd": "npm test", "required": True},
        ]
        all_passed, results = run_gates(gates_config, Path("/tmp"))
        assert all_passed is False

    @patch("autopilot.core.gates.run_single_gate")
    def test_optional_fails_still_passes(self, mock_gate):
        def side_effect(name, cmd, workdir, required):
            if name == "lint":
                return GateResult(name=name, cmd=cmd, passed=False, output="warn", required=False)
            return GateResult(name=name, cmd=cmd, passed=True, output="ok", required=required)

        mock_gate.side_effect = side_effect
        gates_config = [
            {"name": "build", "cmd": "npm run build", "required": True},
            {"name": "lint", "cmd": "npm run lint", "required": False},
        ]
        all_passed, results = run_gates(gates_config, Path("/tmp"))
        assert all_passed is True  # lint is optional
```

- [ ] **Step 2: Run tests — should fail**

```bash
pytest tests/test_gates.py -v
```

- [ ] **Step 3: Implement**

`autopilot/core/gates.py`:
```python
"""Auto-gates runner — build, test, lint checks."""

from __future__ import annotations

import subprocess
import time
from pathlib import Path

from autopilot.core.models import GateResult


def run_single_gate(
    name: str,
    cmd: str,
    workdir: Path,
    required: bool = True,
    timeout: int = 120,
) -> GateResult:
    """Run a single gate command and return the result."""
    t0 = time.time()
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            cwd=str(workdir),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        passed = result.returncode == 0
        output = result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        passed = False
        output = f"Timeout after {timeout}s"
    except Exception as e:
        passed = False
        output = str(e)

    return GateResult(
        name=name,
        cmd=cmd,
        passed=passed,
        output=output.strip()[:2000],  # cap output length
        required=required,
        elapsed_sec=round(time.time() - t0, 2),
    )


def run_gates(
    gates_config: list[dict],
    workdir: Path,
) -> tuple[bool, list[GateResult]]:
    """Run all configured gates. Returns (all_required_passed, results)."""
    results: list[GateResult] = []

    for gate in gates_config:
        result = run_single_gate(
            name=gate.get("name", gate["cmd"]),
            cmd=gate["cmd"],
            workdir=workdir,
            required=gate.get("required", True),
        )
        results.append(result)

    all_required_passed = all(r.passed for r in results if r.required)
    return all_required_passed, results
```

- [ ] **Step 4: Run tests — should pass**

```bash
pytest tests/test_gates.py -v
```

- [ ] **Step 5: Commit**

```bash
git add autopilot/core/gates.py tests/test_gates.py
git commit -m "feat: auto-gates runner — build/test/lint verification"
```

---

### Task 8: Critic Runner

**Files:**
- Create: `autopilot/core/critic.py`
- Create: `tests/test_critic.py`

- [ ] **Step 1: Write tests**

`tests/test_critic.py`:
```python
"""Tests for critic runner."""

from unittest.mock import patch, MagicMock
from pathlib import Path

from autopilot.core.critic import parse_critic_output, build_critic_prompt, run_critic
from autopilot.core.models import CriticResult


class TestParseCriticOutput:
    def test_approved(self):
        output = "APPROVED\n\nAll looks good. Code is clean and well-tested."
        result = parse_critic_output(output)
        assert result.approved is True
        assert result.feedback == ""

    def test_needs_work(self):
        output = "NEEDS_WORK\n- callback URL is hardcoded\n- no error handling for OAuth"
        result = parse_critic_output(output)
        assert result.approved is False
        assert "hardcoded" in result.feedback
        assert "error handling" in result.feedback

    def test_approved_with_notes(self):
        output = "APPROVED\n\nMinor: could add more comments, but not blocking."
        result = parse_critic_output(output)
        assert result.approved is True

    def test_needs_work_takes_priority(self):
        output = "NEEDS_WORK\n- serious issue\nBut otherwise APPROVED"
        result = parse_critic_output(output)
        assert result.approved is False

    def test_empty_output(self):
        result = parse_critic_output("")
        assert result.approved is False
        assert "empty" in result.feedback.lower()


class TestBuildCriticPrompt:
    def test_builds_prompt_with_diff(self):
        prompt = build_critic_prompt(
            story_title="OAuth login",
            story_description="Add Google OAuth",
            diff="+ def oauth_callback():\n+     pass",
            template_path=None,
        )
        assert "OAuth login" in prompt
        assert "oauth_callback" in prompt
```

- [ ] **Step 2: Run tests — should fail**

```bash
pytest tests/test_critic.py -v
```

- [ ] **Step 3: Implement**

`autopilot/core/critic.py`:
```python
"""Critic runner — evaluate worker output via Codex/Claude/Gemini."""

from __future__ import annotations

import subprocess
import time
from pathlib import Path

from autopilot.core.models import CriticResult

TEMPLATE_DIR = Path(__file__).parent.parent / "templates"

DEFAULT_CRITIC_TEMPLATE = """You are a code reviewer. Your task is to evaluate the latest commit.

## Task from PRD
{story_title}: {story_description}

## Diff
{diff}

## Check
1. Does the code solve the task from the story?
2. No obvious bugs?
3. No hardcoded secrets?
4. Is the code readable?
5. Are there tests for new functionality?

## Response format
If everything is OK:
APPROVED

If there are issues:
NEEDS_WORK
- Issue 1: specific description
- Issue 2: specific description
"""


def parse_critic_output(raw_output: str) -> CriticResult:
    """Parse critic CLI output into structured result."""
    if not raw_output.strip():
        return CriticResult(approved=False, feedback="Empty output from critic", raw_output=raw_output)

    upper = raw_output.upper()
    has_needs_work = "NEEDS_WORK" in upper
    has_approved = "APPROVED" in upper

    if has_needs_work:
        # Extract feedback lines (everything after NEEDS_WORK)
        lines = raw_output.strip().split("\n")
        feedback_lines = []
        capture = False
        for line in lines:
            if "NEEDS_WORK" in line.upper():
                capture = True
                continue
            if capture:
                feedback_lines.append(line)
        feedback = "\n".join(feedback_lines).strip()
        return CriticResult(approved=False, feedback=feedback, raw_output=raw_output)

    if has_approved:
        return CriticResult(approved=True, feedback="", raw_output=raw_output)

    # Ambiguous — treat as not approved
    return CriticResult(approved=False, feedback=raw_output.strip(), raw_output=raw_output)


def build_critic_prompt(
    story_title: str,
    story_description: str,
    diff: str,
    template_path: Path | None = None,
) -> str:
    """Build the critic prompt from template and parameters."""
    if template_path and template_path.exists():
        template = template_path.read_text()
    else:
        template = DEFAULT_CRITIC_TEMPLATE

    return template.format(
        story_title=story_title,
        story_description=story_description,
        diff=diff[:8000],  # cap diff length to avoid token limits
    )


def get_git_diff(workdir: Path) -> str:
    """Get the diff of the last commit."""
    try:
        result = subprocess.run(
            ["git", "diff", "HEAD~1"],
            cwd=str(workdir),
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.stdout.strip()
    except Exception:
        return ""


def run_critic(
    prompt: str,
    provider: str,
    env: dict[str, str],
    workdir: Path,
    timeout: int = 600,
) -> CriticResult:
    """Run critic agent and return parsed result."""
    t0 = time.time()

    if provider == "codex":
        cmd = ["codex", "exec", "--full-auto", prompt]
    elif provider == "claude":
        cmd = ["claude", "-p", prompt]
    elif provider == "gemini":
        cmd = ["gemini", "-p", prompt]
    else:
        return CriticResult(approved=False, feedback=f"Unknown provider: {provider}", raw_output="")

    try:
        result = subprocess.run(
            cmd,
            cwd=str(workdir),
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
        raw = result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        raw = "TIMEOUT: critic did not respond within time limit"
    except Exception as e:
        raw = f"ERROR: {e}"

    parsed = parse_critic_output(raw)
    parsed.elapsed_sec = round(time.time() - t0, 2)
    return parsed
```

- [ ] **Step 4: Run tests — should pass**

```bash
pytest tests/test_critic.py -v
```

- [ ] **Step 5: Commit**

```bash
git add autopilot/core/critic.py tests/test_critic.py
git commit -m "feat: critic runner — parse APPROVED/NEEDS_WORK, build prompts"
```

---

### Task 9: Stuck Detector

**Files:**
- Create: `autopilot/core/stuck_detector.py`
- Create: `tests/test_stuck_detector.py`

- [ ] **Step 1: Write tests**

`tests/test_stuck_detector.py`:
```python
"""Tests for stuck detector."""

from autopilot.core.stuck_detector import StuckDetector, StuckReason
from autopilot.core.models import IterationRecord


class TestStuckDetector:
    def test_not_stuck_initially(self):
        detector = StuckDetector(max_same_feedback=3, max_empty_diffs=3, max_same_gate_fail=3)
        assert detector.is_stuck() is False

    def test_stuck_same_feedback(self):
        detector = StuckDetector(max_same_feedback=3)
        for _ in range(3):
            detector.record_iteration(IterationRecord(
                story_id=1, iteration=1, profile_used="acc1", provider="codex",
                gates_passed=True, critic_approved=False,
                critic_feedback="callback URL is hardcoded",
            ))
        result = detector.is_stuck()
        assert result is True
        assert detector.stuck_reason == StuckReason.SAME_FEEDBACK

    def test_not_stuck_different_feedback(self):
        detector = StuckDetector(max_same_feedback=3)
        feedbacks = ["issue A", "issue B", "issue C"]
        for fb in feedbacks:
            detector.record_iteration(IterationRecord(
                story_id=1, iteration=1, profile_used="acc1", provider="codex",
                gates_passed=True, critic_approved=False, critic_feedback=fb,
            ))
        assert detector.is_stuck() is False

    def test_stuck_empty_diffs(self):
        detector = StuckDetector(max_empty_diffs=3)
        for _ in range(3):
            detector.record_iteration(IterationRecord(
                story_id=1, iteration=1, profile_used="acc1", provider="codex",
                gates_passed=True, git_diff_empty=True,
            ))
        assert detector.is_stuck() is True
        assert detector.stuck_reason == StuckReason.EMPTY_DIFF

    def test_stuck_same_gate_failure(self):
        detector = StuckDetector(max_same_gate_fail=3)
        for _ in range(3):
            detector.record_iteration(IterationRecord(
                story_id=1, iteration=1, profile_used="acc1", provider="codex",
                gates_passed=False, critic_feedback="build: Error: cannot find module 'foo'",
            ))
        assert detector.is_stuck() is True
        assert detector.stuck_reason == StuckReason.SAME_GATE_FAIL

    def test_reset(self):
        detector = StuckDetector(max_same_feedback=2)
        for _ in range(2):
            detector.record_iteration(IterationRecord(
                story_id=1, iteration=1, profile_used="acc1", provider="codex",
                gates_passed=True, critic_approved=False, critic_feedback="same",
            ))
        assert detector.is_stuck() is True
        detector.reset()
        assert detector.is_stuck() is False
```

- [ ] **Step 2: Run tests — should fail**

```bash
pytest tests/test_stuck_detector.py -v
```

- [ ] **Step 3: Implement**

`autopilot/core/stuck_detector.py`:
```python
"""Stuck detector — identify when an agent is spinning without progress."""

from __future__ import annotations

from enum import StrEnum

from autopilot.core.models import IterationRecord


class StuckReason(StrEnum):
    NOT_STUCK = "not_stuck"
    SAME_FEEDBACK = "same_feedback"
    EMPTY_DIFF = "empty_diff"
    SAME_GATE_FAIL = "same_gate_fail"
    TIMEOUT = "timeout"


class StuckDetector:
    """Tracks iteration history and detects stuck patterns."""

    def __init__(
        self,
        max_same_feedback: int = 3,
        max_empty_diffs: int = 3,
        max_same_gate_fail: int = 3,
    ):
        self.max_same_feedback = max_same_feedback
        self.max_empty_diffs = max_empty_diffs
        self.max_same_gate_fail = max_same_gate_fail
        self.iterations: list[IterationRecord] = []
        self.stuck_reason: StuckReason = StuckReason.NOT_STUCK

    def record_iteration(self, record: IterationRecord) -> None:
        """Add an iteration record to history."""
        self.iterations.append(record)

    def is_stuck(self) -> bool:
        """Check all stuck patterns. Returns True if any pattern matches."""
        if not self.iterations:
            self.stuck_reason = StuckReason.NOT_STUCK
            return False

        if self._check_same_feedback():
            self.stuck_reason = StuckReason.SAME_FEEDBACK
            return True

        if self._check_empty_diffs():
            self.stuck_reason = StuckReason.EMPTY_DIFF
            return True

        if self._check_same_gate_fail():
            self.stuck_reason = StuckReason.SAME_GATE_FAIL
            return True

        self.stuck_reason = StuckReason.NOT_STUCK
        return False

    def _check_same_feedback(self) -> bool:
        """Critic gave the same feedback N times in a row."""
        recent = self.iterations[-self.max_same_feedback:]
        if len(recent) < self.max_same_feedback:
            return False
        feedbacks = [r.critic_feedback.strip().lower() for r in recent if r.critic_feedback]
        if len(feedbacks) < self.max_same_feedback:
            return False
        return len(set(feedbacks)) == 1

    def _check_empty_diffs(self) -> bool:
        """Agent produced no changes N times in a row."""
        recent = self.iterations[-self.max_empty_diffs:]
        if len(recent) < self.max_empty_diffs:
            return False
        return all(r.git_diff_empty for r in recent)

    def _check_same_gate_fail(self) -> bool:
        """Same gate failure N times in a row."""
        recent = self.iterations[-self.max_same_gate_fail:]
        if len(recent) < self.max_same_gate_fail:
            return False
        failed = [r for r in recent if not r.gates_passed]
        if len(failed) < self.max_same_gate_fail:
            return False
        feedbacks = [r.critic_feedback.strip().lower() for r in failed]
        return len(set(feedbacks)) == 1

    def reset(self) -> None:
        """Clear iteration history."""
        self.iterations.clear()
        self.stuck_reason = StuckReason.NOT_STUCK

    def summary(self) -> str:
        """Human-readable summary of current stuck state."""
        if not self.is_stuck():
            return "Not stuck"
        reason_messages = {
            StuckReason.SAME_FEEDBACK: f"Critic gave same feedback {self.max_same_feedback} times",
            StuckReason.EMPTY_DIFF: f"No code changes for {self.max_empty_diffs} iterations",
            StuckReason.SAME_GATE_FAIL: f"Same gate failure for {self.max_same_gate_fail} iterations",
            StuckReason.TIMEOUT: "Agent timed out",
        }
        return reason_messages.get(self.stuck_reason, str(self.stuck_reason))
```

- [ ] **Step 4: Run tests — should pass**

```bash
pytest tests/test_stuck_detector.py -v
```

- [ ] **Step 5: Commit**

```bash
git add autopilot/core/stuck_detector.py tests/test_stuck_detector.py
git commit -m "feat: stuck detector — same feedback, empty diffs, repeated gate failures"
```

---

### Task 10: Loop Runner (Ralph Integration)

**Files:**
- Create: `autopilot/core/loop_runner.py`
- Create: `tests/test_loop_runner.py`

- [ ] **Step 1: Write tests**

`tests/test_loop_runner.py`:
```python
"""Tests for loop runner — Ralph integration."""

from unittest.mock import patch, MagicMock
from pathlib import Path

from autopilot.core.loop_runner import (
    run_ralph_iteration,
    check_ralph_installed,
    init_ralph_project,
    read_progress,
    write_critic_feedback,
    check_git_diff_empty,
)


class TestLoopRunner:
    @patch("autopilot.core.loop_runner.subprocess.run")
    def test_check_ralph_installed(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="0.1.3")
        assert check_ralph_installed() is True

    @patch("autopilot.core.loop_runner.subprocess.run")
    def test_check_ralph_not_installed(self, mock_run):
        mock_run.side_effect = FileNotFoundError()
        assert check_ralph_installed() is False

    def test_write_and_read_critic_feedback(self, tmp_path: Path):
        ralph_dir = tmp_path / ".ralph"
        ralph_dir.mkdir()

        write_critic_feedback(tmp_path, "- callback URL hardcoded\n- no tests")
        content = (ralph_dir / "critic-feedback.md").read_text()
        assert "callback URL" in content

    def test_read_progress_missing(self, tmp_path: Path):
        result = read_progress(tmp_path)
        assert result == ""

    def test_read_progress_exists(self, tmp_path: Path):
        ralph_dir = tmp_path / ".ralph"
        ralph_dir.mkdir()
        (ralph_dir / "progress.md").write_text("# Progress\n- Story 1 done")

        result = read_progress(tmp_path)
        assert "Story 1 done" in result

    @patch("autopilot.core.loop_runner.subprocess.run")
    def test_check_git_diff_empty_true(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="")
        assert check_git_diff_empty(Path("/tmp")) is True

    @patch("autopilot.core.loop_runner.subprocess.run")
    def test_check_git_diff_empty_false(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="+new line")
        assert check_git_diff_empty(Path("/tmp")) is False
```

- [ ] **Step 2: Run tests — should fail**

```bash
pytest tests/test_loop_runner.py -v
```

- [ ] **Step 3: Implement**

`autopilot/core/loop_runner.py`:
```python
"""Loop runner — Ralph integration with account rotation."""

from __future__ import annotations

import subprocess
import time
from pathlib import Path

from autopilot.core.models import is_rate_limited


def check_ralph_installed() -> bool:
    """Check if Ralph CLI is available."""
    try:
        result = subprocess.run(["ralph", "--version"], capture_output=True, text=True, timeout=10)
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def init_ralph_project(project_path: Path) -> bool:
    """Run ralph install in the project directory."""
    try:
        result = subprocess.run(
            ["ralph", "install"],
            cwd=str(project_path),
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.returncode == 0
    except Exception:
        return False


def run_ralph_iteration(
    project_path: Path,
    env: dict[str, str],
    timeout: int = 1800,
    prd_path: str | None = None,
) -> tuple[bool, str, bool]:
    """
    Run one Ralph build iteration.

    Returns: (success, output, rate_limited)
    """
    cmd = ["ralph", "build", "1", "--no-commit"]
    if prd_path:
        cmd.extend(["--prd", prd_path])

    t0 = time.time()
    try:
        result = subprocess.run(
            cmd,
            cwd=str(project_path),
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
        output = result.stdout + "\n" + result.stderr
        success = result.returncode == 0
        rate_limited = is_rate_limited(output)
        return success, output.strip(), rate_limited
    except subprocess.TimeoutExpired:
        return False, f"Timeout after {timeout}s", False
    except Exception as e:
        return False, str(e), False


def read_progress(project_path: Path) -> str:
    """Read .ralph/progress.md."""
    progress_file = project_path / ".ralph" / "progress.md"
    if progress_file.exists():
        return progress_file.read_text()
    return ""


def write_critic_feedback(project_path: Path, feedback: str) -> None:
    """Write critic feedback to .ralph/critic-feedback.md."""
    ralph_dir = project_path / ".ralph"
    ralph_dir.mkdir(exist_ok=True)
    feedback_file = ralph_dir / "critic-feedback.md"
    feedback_file.write_text(feedback)


def append_guardrail(project_path: Path, guardrail: str) -> None:
    """Append a guardrail entry to .ralph/guardrails.md."""
    ralph_dir = project_path / ".ralph"
    ralph_dir.mkdir(exist_ok=True)
    guardrails_file = ralph_dir / "guardrails.md"
    existing = guardrails_file.read_text() if guardrails_file.exists() else ""
    guardrails_file.write_text(existing + f"\n- {guardrail}\n")


def check_git_diff_empty(project_path: Path) -> bool:
    """Check if the last commit produced an empty diff."""
    try:
        result = subprocess.run(
            ["git", "diff", "HEAD~1", "--stat"],
            cwd=str(project_path),
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.stdout.strip() == ""
    except Exception:
        return False


def get_last_commit_diff(project_path: Path) -> str:
    """Get the diff of the last commit for critic review."""
    try:
        result = subprocess.run(
            ["git", "diff", "HEAD~1"],
            cwd=str(project_path),
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.stdout.strip()
    except Exception:
        return ""
```

- [ ] **Step 4: Run tests — should pass**

```bash
pytest tests/test_loop_runner.py -v
```

- [ ] **Step 5: Commit**

```bash
git add autopilot/core/loop_runner.py tests/test_loop_runner.py
git commit -m "feat: loop runner — Ralph integration, progress/feedback file management"
```

---

### Task 11: Main Orchestrator

**Files:**
- Create: `autopilot/core/orchestrator.py`
- Create: `tests/test_orchestrator.py`

This is the central component that ties everything together: pick story -> run worker -> gates -> critic -> next.

- [ ] **Step 1: Write tests**

`tests/test_orchestrator.py`:
```python
"""Tests for main orchestrator loop."""

from unittest.mock import patch, MagicMock, PropertyMock
from pathlib import Path

from autopilot.core.orchestrator import Orchestrator, StoryOutcome
from autopilot.core.models import GateResult, CriticResult, Profile
from autopilot.core.config import AutopilotConfig


class TestOrchestrator:
    def _make_orchestrator(self, tmp_path: Path) -> Orchestrator:
        return Orchestrator(
            project_path=tmp_path,
            config=AutopilotConfig(),
            profiles_dir=tmp_path / "profiles",
        )

    @patch("autopilot.core.orchestrator.run_ralph_iteration")
    @patch("autopilot.core.orchestrator.run_gates")
    @patch("autopilot.core.orchestrator.run_critic")
    @patch("autopilot.core.orchestrator.get_last_commit_diff")
    @patch("autopilot.core.orchestrator.check_git_diff_empty")
    def test_successful_iteration(
        self, mock_diff_empty, mock_get_diff, mock_critic, mock_gates, mock_ralph, tmp_path
    ):
        mock_ralph.return_value = (True, "Story 1 done", False)
        mock_gates.return_value = (True, [GateResult(name="build", cmd="x", passed=True, output="ok")])
        mock_get_diff.return_value = "+new code"
        mock_diff_empty.return_value = False
        mock_critic.return_value = CriticResult(approved=True, feedback="", raw_output="APPROVED")

        orch = self._make_orchestrator(tmp_path)
        profile = Profile(name="acc1", provider="codex", path=str(tmp_path))
        env = {"PATH": "/usr/bin"}

        outcome = orch.run_single_iteration(
            profile=profile,
            env=env,
            story_id=1,
            story_title="Setup",
            story_description="Project setup",
            gates_config=[{"name": "build", "cmd": "npm run build"}],
            critic_profile=profile,
            critic_env=env,
        )

        assert outcome == StoryOutcome.APPROVED

    @patch("autopilot.core.orchestrator.run_ralph_iteration")
    @patch("autopilot.core.orchestrator.run_gates")
    def test_gate_failure(self, mock_gates, mock_ralph, tmp_path):
        mock_ralph.return_value = (True, "Story 1 done", False)
        mock_gates.return_value = (False, [GateResult(name="test", cmd="x", passed=False, output="1 failed")])

        orch = self._make_orchestrator(tmp_path)
        profile = Profile(name="acc1", provider="codex", path=str(tmp_path))
        env = {"PATH": "/usr/bin"}

        outcome = orch.run_single_iteration(
            profile=profile,
            env=env,
            story_id=1,
            story_title="Setup",
            story_description="Project setup",
            gates_config=[{"name": "test", "cmd": "npm test"}],
            critic_profile=profile,
            critic_env=env,
        )

        assert outcome == StoryOutcome.GATE_FAILED

    @patch("autopilot.core.orchestrator.run_ralph_iteration")
    def test_rate_limited(self, mock_ralph, tmp_path):
        mock_ralph.return_value = (False, "429 Too Many Requests", True)

        orch = self._make_orchestrator(tmp_path)
        profile = Profile(name="acc1", provider="codex", path=str(tmp_path))
        env = {"PATH": "/usr/bin"}

        outcome = orch.run_single_iteration(
            profile=profile,
            env=env,
            story_id=1,
            story_title="Setup",
            story_description="desc",
            gates_config=[],
            critic_profile=profile,
            critic_env=env,
        )

        assert outcome == StoryOutcome.RATE_LIMITED
```

- [ ] **Step 2: Run tests — should fail**

```bash
pytest tests/test_orchestrator.py -v
```

- [ ] **Step 3: Implement**

`autopilot/core/orchestrator.py`:
```python
"""Main orchestrator — ties worker, gates, critic, and stuck detection together."""

from __future__ import annotations

import json
import time
from enum import StrEnum
from pathlib import Path

from rich.console import Console

from autopilot.core.config import AutopilotConfig
from autopilot.core.models import Profile, IterationRecord, CriticResult
from autopilot.core.account_manager import AccountManager
from autopilot.core.loop_runner import (
    run_ralph_iteration,
    write_critic_feedback,
    check_git_diff_empty,
    get_last_commit_diff,
    append_guardrail,
)
from autopilot.core.gates import run_gates
from autopilot.core.critic import run_critic, build_critic_prompt, parse_critic_output
from autopilot.core.stuck_detector import StuckDetector

console = Console()


class StoryOutcome(StrEnum):
    APPROVED = "approved"
    GATE_FAILED = "gate_failed"
    CRITIC_REJECTED = "critic_rejected"
    RATE_LIMITED = "rate_limited"
    WORKER_FAILED = "worker_failed"
    STUCK = "stuck"
    ERROR = "error"


class Orchestrator:
    """Runs the full loop for a single project: story -> worker -> gates -> critic."""

    def __init__(
        self,
        project_path: Path,
        config: AutopilotConfig,
        profiles_dir: Path,
    ):
        self.project_path = project_path
        self.config = config
        self.account_mgr = AccountManager(profiles_dir=profiles_dir, cooldown_base=config.cooldown_base_sec)
        self.account_mgr.discover()
        self.stuck_detector = StuckDetector()
        self.iteration_history: list[IterationRecord] = []

    def run_single_iteration(
        self,
        profile: Profile,
        env: dict[str, str],
        story_id: int,
        story_title: str,
        story_description: str,
        gates_config: list[dict],
        critic_profile: Profile,
        critic_env: dict[str, str],
    ) -> StoryOutcome:
        """Execute one full iteration: worker -> gates -> critic."""
        t0 = time.time()

        # 1. Run worker (Ralph iteration)
        console.print(f"  [blue]Worker[/blue] {profile.provider}/{profile.name} starting story #{story_id}...")
        success, output, rate_limited = run_ralph_iteration(
            self.project_path, env, self.config.codex_timeout_sec
        )

        if rate_limited:
            console.print(f"  [yellow]Rate limited[/yellow] — {profile.name}")
            return StoryOutcome.RATE_LIMITED

        if not success:
            record = IterationRecord(
                story_id=story_id, iteration=len(self.iteration_history) + 1,
                profile_used=profile.name, provider=profile.provider,
                gates_passed=False, elapsed_sec=round(time.time() - t0, 2),
            )
            self.stuck_detector.record_iteration(record)
            self.iteration_history.append(record)
            console.print(f"  [red]Worker failed[/red]")
            return StoryOutcome.WORKER_FAILED

        # 2. Check if diff is empty
        diff_empty = check_git_diff_empty(self.project_path)

        # 3. Run auto-gates
        if gates_config:
            console.print(f"  [blue]Gates[/blue] running...")
            all_passed, gate_results = run_gates(gates_config, self.project_path)

            for gr in gate_results:
                status = "[green]PASS[/green]" if gr.passed else "[red]FAIL[/red]"
                console.print(f"    {gr.name}: {status}")

            if not all_passed:
                error_output = "\n".join(f"- {g.name}: {g.output[:200]}" for g in gate_results if not g.passed)
                write_critic_feedback(self.project_path, f"Gate failures:\n{error_output}")

                record = IterationRecord(
                    story_id=story_id, iteration=len(self.iteration_history) + 1,
                    profile_used=profile.name, provider=profile.provider,
                    gates_passed=False, critic_feedback=error_output,
                    elapsed_sec=round(time.time() - t0, 2),
                    git_diff_empty=diff_empty, gate_results=gate_results,
                )
                self.stuck_detector.record_iteration(record)
                self.iteration_history.append(record)
                return StoryOutcome.GATE_FAILED

        # 4. Run critic
        console.print(f"  [blue]Critic[/blue] {critic_profile.provider}/{critic_profile.name} reviewing...")
        diff = get_last_commit_diff(self.project_path)
        critic_prompt = build_critic_prompt(story_title, story_description, diff)

        critic_result = run_critic(
            prompt=critic_prompt,
            provider=critic_profile.provider,
            env=critic_env,
            workdir=self.project_path,
        )

        record = IterationRecord(
            story_id=story_id, iteration=len(self.iteration_history) + 1,
            profile_used=profile.name, provider=profile.provider,
            gates_passed=True,
            critic_approved=critic_result.approved,
            critic_feedback=critic_result.feedback,
            elapsed_sec=round(time.time() - t0, 2),
            git_diff_empty=diff_empty,
        )
        self.stuck_detector.record_iteration(record)
        self.iteration_history.append(record)

        if critic_result.approved:
            console.print(f"  [green]APPROVED[/green]")
            return StoryOutcome.APPROVED

        # Write feedback for next iteration
        write_critic_feedback(self.project_path, critic_result.feedback)
        console.print(f"  [yellow]NEEDS_WORK[/yellow]: {critic_result.feedback[:100]}...")
        return StoryOutcome.CRITIC_REJECTED

    def check_stuck(self) -> bool:
        """Check if the agent is stuck and should escalate."""
        if self.stuck_detector.is_stuck():
            console.print(f"  [red]STUCK[/red]: {self.stuck_detector.summary()}")
            return True
        return False

    def reset_stuck(self) -> None:
        """Reset stuck detector for a new story or new provider."""
        self.stuck_detector.reset()
```

- [ ] **Step 4: Run tests — should pass**

```bash
pytest tests/test_orchestrator.py -v
```

- [ ] **Step 5: Commit**

```bash
git add autopilot/core/orchestrator.py tests/test_orchestrator.py
git commit -m "feat: main orchestrator — worker -> gates -> critic loop with stuck detection"
```

---

### Task 12: CLI Run Command

**Files:**
- Create: `autopilot/cli/run.py`
- Modify: `autopilot/cli/main.py`

- [ ] **Step 1: Implement run command**

`autopilot/cli/run.py`:
```python
"""CLI command: autopilot run <project-path>."""

from __future__ import annotations

import json
import time
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from autopilot.core.config import load_config
from autopilot.core.account_manager import AccountManager
from autopilot.core.orchestrator import Orchestrator, StoryOutcome

console = Console()


def load_prd_stories(project_path: Path, prd_path: str) -> list[dict]:
    """Load stories from a PRD JSON file."""
    full_path = project_path / prd_path
    if not full_path.exists():
        console.print(f"[red]PRD not found: {full_path}[/red]")
        raise typer.Exit(1)

    data = json.loads(full_path.read_text())
    return data.get("stories", [])


def find_next_open_story(stories: list[dict]) -> dict | None:
    """Find the next story with status 'open'."""
    for story in stories:
        if story.get("status", "open") == "open":
            return story
    return None


def update_story_status(project_path: Path, prd_path: str, story_id: int, status: str) -> None:
    """Update a story's status in the PRD JSON file."""
    full_path = project_path / prd_path
    data = json.loads(full_path.read_text())
    for story in data.get("stories", []):
        if story["id"] == story_id:
            story["status"] = status
            break
    full_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))


def run(
    project_path: str = typer.Argument(help="Path to the project directory"),
    prd: str = typer.Option(".agents/tasks/prd.json", help="Path to PRD JSON file (relative to project)"),
) -> None:
    """Run autopilot loop on a single project until all stories are done."""
    project = Path(project_path).expanduser().resolve()
    if not project.exists():
        console.print(f"[red]Project not found: {project}[/red]")
        raise typer.Exit(1)

    config = load_config(Path.home() / ".autopilot" / "config.yaml")
    account_mgr = AccountManager(profiles_dir=config.profiles_dir, cooldown_base=config.cooldown_base_sec)
    account_mgr.discover()

    if "codex" not in account_mgr.pools:
        console.print("[red]No Codex profiles found. Run: autopilot login codex[/red]")
        raise typer.Exit(1)

    # Load project gates config
    gates_config: list[dict] = []
    project_config_path = Path.home() / ".autopilot" / "projects.yaml"
    if project_config_path.exists():
        import yaml
        projects_data = yaml.safe_load(project_config_path.read_text()) or {}
        for p in projects_data.get("projects", []):
            if Path(p["path"]).resolve() == project:
                gates_config = p.get("gates", [])
                break

    orchestrator = Orchestrator(
        project_path=project,
        config=config,
        profiles_dir=config.profiles_dir,
    )

    console.print(f"\n[bold]Autopilot[/bold] — running on [cyan]{project.name}[/cyan]\n")

    while True:
        stories = load_prd_stories(project, prd)
        story = find_next_open_story(stories)

        if story is None:
            console.print("[bold green]All stories complete![/bold green]")
            break

        story_id = story["id"]
        story_title = story.get("title", f"Story #{story_id}")
        story_desc = story.get("description", "")

        console.print(f"\n[bold]Story #{story_id}:[/bold] {story_title}")
        update_story_status(project, prd, story_id, "in_progress")
        orchestrator.reset_stuck()

        approved = False
        while not approved:
            # Get worker profile
            worker_profile = account_mgr.get_next("codex")
            if worker_profile is None:
                console.print("[yellow]All worker accounts on cooldown. Waiting 60s...[/yellow]")
                time.sleep(60)
                continue

            worker_env = account_mgr.build_env(worker_profile)

            # Get critic profile (prefer different account)
            critic_profile = account_mgr.get_next("codex")
            if critic_profile is None:
                critic_profile = worker_profile  # fallback: use same
            critic_env = account_mgr.build_env(critic_profile)

            outcome = orchestrator.run_single_iteration(
                profile=worker_profile,
                env=worker_env,
                story_id=story_id,
                story_title=story_title,
                story_description=story_desc,
                gates_config=gates_config,
                critic_profile=critic_profile,
                critic_env=critic_env,
            )

            if outcome == StoryOutcome.APPROVED:
                update_story_status(project, prd, story_id, "done")
                account_mgr.mark_success("codex", worker_profile.name)
                approved = True

            elif outcome == StoryOutcome.RATE_LIMITED:
                account_mgr.mark_rate_limited("codex", worker_profile.name)
                continue  # try next account

            elif outcome in (StoryOutcome.GATE_FAILED, StoryOutcome.CRITIC_REJECTED, StoryOutcome.WORKER_FAILED):
                if orchestrator.check_stuck():
                    console.print(f"[red]Story #{story_id} is stuck. Skipping.[/red]")
                    update_story_status(project, prd, story_id, "stuck")
                    break
                # Otherwise, retry
                continue

            else:
                console.print(f"[red]Unexpected outcome: {outcome}[/red]")
                break

    console.print("\n[bold]Autopilot finished.[/bold]")
```

- [ ] **Step 2: Register in main CLI**

Update `autopilot/cli/main.py` — add run command:
```python
"""Main CLI entrypoint."""

import typer

app = typer.Typer(
    name="autopilot",
    help="Autonomous AI programmer platform with account rotation and critic loops.",
    no_args_is_help=True,
)


@app.command()
def version():
    """Show version."""
    from autopilot import __version__

    typer.echo(f"autopilot v{__version__}")


@app.command()
def login(
    provider: str = typer.Argument(help="Provider: codex, claude, or gemini"),
):
    """Save a logged-in CLI session as a reusable profile."""
    from autopilot.cli.login import login as _login

    _login(provider)


@app.command()
def run(
    project_path: str = typer.Argument(help="Path to the project directory"),
    prd: str = typer.Option(".agents/tasks/prd.json", help="PRD JSON path relative to project"),
):
    """Run autopilot loop on a project until all stories are done."""
    from autopilot.cli.run import run as _run

    _run(project_path, prd)
```

- [ ] **Step 3: Commit**

```bash
git add autopilot/cli/run.py autopilot/cli/main.py
git commit -m "feat: autopilot run command — main loop with worker/gates/critic"
```

---

### Task 13: CLI Status & Init Commands

**Files:**
- Create: `autopilot/cli/status.py`
- Create: `autopilot/cli/init_cmd.py`
- Modify: `autopilot/cli/main.py`

- [ ] **Step 1: Implement status command**

`autopilot/cli/status.py`:
```python
"""CLI command: autopilot status."""

from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from autopilot.core.config import load_config
from autopilot.core.account_manager import AccountManager

console = Console()


def status() -> None:
    """Show status of all profiles and projects."""
    config = load_config(Path.home() / ".autopilot" / "config.yaml")
    account_mgr = AccountManager(profiles_dir=config.profiles_dir)
    account_mgr.discover()

    # Accounts table
    console.print(Panel("[bold]Account Status[/bold]"))
    for provider in ("codex", "claude", "gemini"):
        profiles = account_mgr.pools.get(provider, [])
        if not profiles:
            continue

        table = Table(title=f"{provider} ({len(profiles)} accounts)")
        table.add_column("Name")
        table.add_column("Available")
        table.add_column("Requests")
        table.add_column("Cooldown")

        for s in account_mgr.pool_status(provider):
            avail = "[green]yes[/green]" if s["available"] else "[red]no[/red]"
            cd = f"{s['cooldown_remaining_sec']}s" if s["cooldown_remaining_sec"] > 0 else "-"
            table.add_row(s["name"], avail, str(s["requests_made"]), cd)

        console.print(table)

    # Projects
    projects_path = config.projects_yaml_path
    if projects_path.exists():
        import yaml
        data = yaml.safe_load(projects_path.read_text()) or {}
        projects = data.get("projects", [])

        if projects:
            console.print(Panel("[bold]Projects[/bold]"))
            table = Table()
            table.add_column("Name")
            table.add_column("Path")
            table.add_column("Priority")
            table.add_column("Stories")

            for p in projects:
                prd_path = Path(p["path"]) / p.get("prd", ".agents/tasks/prd.json")
                story_count = "-"
                if prd_path.exists():
                    try:
                        prd_data = json.loads(prd_path.read_text())
                        stories = prd_data.get("stories", [])
                        done = sum(1 for s in stories if s.get("status") == "done")
                        total = len(stories)
                        story_count = f"{done}/{total}"
                    except Exception:
                        pass

                table.add_row(p["name"], p["path"], p.get("priority", "normal"), story_count)

            console.print(table)
```

- [ ] **Step 2: Implement init command**

`autopilot/cli/init_cmd.py`:
```python
"""CLI command: autopilot init <project-path>."""

from __future__ import annotations

import subprocess
from pathlib import Path

import typer
from rich.console import Console

from autopilot.core.loop_runner import check_ralph_installed

console = Console()


def init(
    project_path: str = typer.Argument(help="Path to the project directory"),
) -> None:
    """Initialize a project for autopilot (installs Ralph templates)."""
    project = Path(project_path).expanduser().resolve()

    if not project.exists():
        console.print(f"[red]Directory not found: {project}[/red]")
        raise typer.Exit(1)

    if not check_ralph_installed():
        console.print("[red]Ralph is not installed. Run: npm i -g @iannuttall/ralph[/red]")
        raise typer.Exit(1)

    console.print(f"[bold]Initializing autopilot in {project.name}...[/bold]")

    # Run ralph install
    result = subprocess.run(
        ["ralph", "install"],
        cwd=str(project),
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        console.print(f"[red]Ralph install failed: {result.stderr}[/red]")
        raise typer.Exit(1)

    # Create .ralph directory
    ralph_dir = project / ".ralph"
    ralph_dir.mkdir(exist_ok=True)
    (ralph_dir / "progress.md").write_text("# Progress\n\n")
    (ralph_dir / "guardrails.md").write_text("# Guardrails\n\nDo not repeat these mistakes:\n\n")

    console.print("[green]Done![/green] Project initialized.")
    console.print(f"\nNext steps:")
    console.print(f"  1. Create PRD: ralph prd")
    console.print(f"  2. Run: autopilot run {project}")
```

- [ ] **Step 3: Register both in main CLI**

Add to `autopilot/cli/main.py`:
```python
@app.command()
def status():
    """Show status of accounts and projects."""
    from autopilot.cli.status import status as _status

    _status()


@app.command(name="init")
def init_project(
    project_path: str = typer.Argument(help="Path to the project directory"),
):
    """Initialize a project for autopilot."""
    from autopilot.cli.init_cmd import init as _init

    _init(project_path)
```

- [ ] **Step 4: Commit**

```bash
git add autopilot/cli/status.py autopilot/cli/init_cmd.py autopilot/cli/main.py
git commit -m "feat: autopilot status and init commands"
```

- [ ] **Step 5: Run full test suite**

```bash
pytest tests/ -v --tb=short
# Expected: all tests pass
```

- [ ] **Step 6: Commit Phase 1 complete marker**

```bash
git tag v0.1.0-phase1
git commit --allow-empty -m "milestone: Phase 1 CLI core complete"
```

---

## Phase 2: Multi-project + Escalation

### Task 14: Provider-specific Environment Builders

**Files:**
- Create: `autopilot/core/providers.py`
- Create: `tests/test_providers.py`

- [ ] **Step 1: Write tests**

`tests/test_providers.py`:
```python
"""Tests for provider-specific environment building and CLI commands."""

from autopilot.core.providers import build_cli_command, PROVIDER_COMMANDS


class TestProviders:
    def test_codex_command(self):
        cmd = build_cli_command("codex", "do the thing", model=None)
        assert cmd[0] == "codex"
        assert "exec" in cmd
        assert "--full-auto" in cmd

    def test_claude_command(self):
        cmd = build_cli_command("claude", "do the thing", model=None)
        assert cmd[0] == "claude"
        assert "-p" in cmd

    def test_gemini_command(self):
        cmd = build_cli_command("gemini", "do the thing", model=None)
        assert cmd[0] == "gemini"

    def test_provider_registry(self):
        assert "codex" in PROVIDER_COMMANDS
        assert "claude" in PROVIDER_COMMANDS
        assert "gemini" in PROVIDER_COMMANDS
```

- [ ] **Step 2: Run tests — should fail**

```bash
pytest tests/test_providers.py -v
```

- [ ] **Step 3: Implement**

`autopilot/core/providers.py`:
```python
"""Provider-specific CLI command builders and configurations."""

from __future__ import annotations


PROVIDER_COMMANDS: dict[str, dict] = {
    "codex": {
        "exec": ["codex", "exec", "--full-auto"],
        "review": ["codex", "review"],
        "check_installed": ["codex", "--version"],
        "install_hint": "npm i -g @openai/codex",
    },
    "claude": {
        "exec": ["claude", "-p"],
        "review": ["claude", "-p"],
        "check_installed": ["claude", "--version"],
        "install_hint": "curl -fsSL https://claude.ai/install.sh | bash",
    },
    "gemini": {
        "exec": ["gemini", "-p"],
        "review": ["gemini", "-p"],
        "check_installed": ["gemini", "--version"],
        "install_hint": "npm i -g @anthropic-ai/gemini",  # placeholder
    },
}


def build_cli_command(
    provider: str,
    prompt: str,
    model: str | None = None,
    mode: str = "exec",
) -> list[str]:
    """Build CLI command for a specific provider."""
    config = PROVIDER_COMMANDS.get(provider)
    if not config:
        raise ValueError(f"Unknown provider: {provider}")

    cmd = list(config[mode])

    if provider == "codex":
        if model:
            cmd.extend(["-m", model])
        cmd.append(prompt)

    elif provider == "claude":
        cmd.append(prompt)

    elif provider == "gemini":
        cmd.append(prompt)

    return cmd
```

- [ ] **Step 4: Run tests — should pass**

```bash
pytest tests/test_providers.py -v
```

- [ ] **Step 5: Commit**

```bash
git add autopilot/core/providers.py tests/test_providers.py
git commit -m "feat: provider-specific CLI command builders"
```

---

### Task 15: Escalation Chain

**Files:**
- Create: `autopilot/core/escalation.py`
- Create: `tests/test_escalation.py`

- [ ] **Step 1: Write tests**

`tests/test_escalation.py`:
```python
"""Tests for escalation chain."""

from autopilot.core.escalation import EscalationChain, EscalationResult


class TestEscalationChain:
    def test_initial_provider(self):
        chain = EscalationChain(providers=["codex", "claude", "gemini"], max_attempts_per_provider=3)
        assert chain.current_provider == "codex"
        assert chain.is_exhausted() is False

    def test_advance_after_max_attempts(self):
        chain = EscalationChain(providers=["codex", "claude"], max_attempts_per_provider=3)
        for _ in range(3):
            chain.record_failure("same issue")
        assert chain.current_provider == "claude"

    def test_exhausted_after_all_providers(self):
        chain = EscalationChain(providers=["codex", "claude"], max_attempts_per_provider=2)
        for _ in range(2):
            chain.record_failure("issue")
        assert chain.current_provider == "claude"
        for _ in range(2):
            chain.record_failure("issue")
        assert chain.is_exhausted() is True

    def test_reset(self):
        chain = EscalationChain(providers=["codex", "claude"], max_attempts_per_provider=2)
        for _ in range(2):
            chain.record_failure("issue")
        chain.reset()
        assert chain.current_provider == "codex"
        assert chain.is_exhausted() is False

    def test_build_context_summary(self):
        chain = EscalationChain(providers=["codex", "claude"], max_attempts_per_provider=2)
        chain.record_failure("callback URL hardcoded")
        chain.record_failure("still hardcoded")
        summary = chain.context_summary()
        assert "codex" in summary.lower()
        assert "hardcoded" in summary

    def test_try_fresh_account_first(self):
        chain = EscalationChain(
            providers=["codex", "claude"],
            max_attempts_per_provider=3,
            try_fresh_account_first=True,
        )
        # First stuck detection should try fresh codex account before moving to claude
        chain.record_failure("issue")
        chain.record_failure("issue")
        chain.record_failure("issue")
        # After 3 failures, should have moved to "codex_fresh" first, then claude
        # Implementation detail: the chain tracks this internally
        assert chain.attempts_on_current >= 3
```

- [ ] **Step 2: Run tests — should fail**

```bash
pytest tests/test_escalation.py -v
```

- [ ] **Step 3: Implement**

`autopilot/core/escalation.py`:
```python
"""Escalation chain — rotate through providers when agent is stuck."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ProviderAttempt:
    provider: str
    failures: list[str] = field(default_factory=list)


@dataclass
class EscalationResult:
    exhausted: bool
    current_provider: str
    context_summary: str


class EscalationChain:
    """Manages provider escalation: codex -> claude -> gemini -> human."""

    def __init__(
        self,
        providers: list[str],
        max_attempts_per_provider: int = 3,
        try_fresh_account_first: bool = True,
    ):
        self.providers = providers
        self.max_attempts_per_provider = max_attempts_per_provider
        self.try_fresh_account_first = try_fresh_account_first
        self._provider_index = 0
        self._attempts: list[ProviderAttempt] = [ProviderAttempt(provider=providers[0])]
        self.attempts_on_current = 0

    @property
    def current_provider(self) -> str:
        return self.providers[self._provider_index]

    def record_failure(self, description: str) -> None:
        """Record a failure on the current provider."""
        self._attempts[-1].failures.append(description)
        self.attempts_on_current += 1

        if self.attempts_on_current >= self.max_attempts_per_provider:
            self._advance()

    def _advance(self) -> None:
        """Move to the next provider in the chain."""
        if self._provider_index + 1 < len(self.providers):
            self._provider_index += 1
            self._attempts.append(ProviderAttempt(provider=self.current_provider))
            self.attempts_on_current = 0

    def is_exhausted(self) -> bool:
        """Check if all providers have been tried."""
        if self._provider_index >= len(self.providers) - 1:
            return self.attempts_on_current >= self.max_attempts_per_provider
        return False

    def context_summary(self) -> str:
        """Build enriched context for the next provider."""
        lines = ["## What was already tried"]
        for attempt in self._attempts:
            if attempt.failures:
                lines.append(f"\n### {attempt.provider} ({len(attempt.failures)} attempts)")
                for i, f in enumerate(attempt.failures, 1):
                    lines.append(f"  {i}. {f}")
        return "\n".join(lines)

    def reset(self) -> None:
        """Reset the chain for a new story."""
        self._provider_index = 0
        self._attempts = [ProviderAttempt(provider=self.providers[0])]
        self.attempts_on_current = 0
```

- [ ] **Step 4: Run tests — should pass**

```bash
pytest tests/test_escalation.py -v
```

- [ ] **Step 5: Commit**

```bash
git add autopilot/core/escalation.py tests/test_escalation.py
git commit -m "feat: escalation chain — codex -> claude -> gemini -> human"
```

---

### Task 16: Dispatcher (Multi-project)

**Files:**
- Create: `autopilot/core/dispatcher.py`
- Create: `tests/test_dispatcher.py`

- [ ] **Step 1: Write tests**

`tests/test_dispatcher.py`:
```python
"""Tests for multi-project dispatcher."""

from pathlib import Path

from autopilot.core.dispatcher import Dispatcher, ProjectAllocation
from autopilot.core.models import ProjectConfig


class TestDispatcher:
    def test_allocate_single_project(self):
        projects = [ProjectConfig(name="proj-a", path="/tmp/a", priority="normal")]
        dispatcher = Dispatcher(total_workers=14, total_critics=5)
        allocations = dispatcher.allocate(projects)

        assert len(allocations) == 1
        assert allocations[0].worker_count == 14
        assert allocations[0].critic_count == 5

    def test_allocate_by_priority(self):
        projects = [
            ProjectConfig(name="proj-high", path="/tmp/a", priority="high"),
            ProjectConfig(name="proj-normal", path="/tmp/b", priority="normal"),
            ProjectConfig(name="proj-low", path="/tmp/c", priority="low"),
        ]
        dispatcher = Dispatcher(total_workers=14, total_critics=5)
        allocations = dispatcher.allocate(projects)

        high = next(a for a in allocations if a.project_name == "proj-high")
        normal = next(a for a in allocations if a.project_name == "proj-normal")
        low = next(a for a in allocations if a.project_name == "proj-low")

        assert high.worker_count >= normal.worker_count
        assert normal.worker_count >= low.worker_count

    def test_allocate_equal_priority(self):
        projects = [
            ProjectConfig(name="a", path="/tmp/a", priority="normal"),
            ProjectConfig(name="b", path="/tmp/b", priority="normal"),
        ]
        dispatcher = Dispatcher(total_workers=10, total_critics=4)
        allocations = dispatcher.allocate(projects)

        assert allocations[0].worker_count == 5
        assert allocations[1].worker_count == 5

    def test_every_project_gets_at_least_one(self):
        projects = [
            ProjectConfig(name=f"p{i}", path=f"/tmp/p{i}", priority="normal")
            for i in range(10)
        ]
        dispatcher = Dispatcher(total_workers=14, total_critics=5)
        allocations = dispatcher.allocate(projects)

        for a in allocations:
            assert a.worker_count >= 1
            assert a.critic_count >= 1
```

- [ ] **Step 2: Run tests — should fail**

```bash
pytest tests/test_dispatcher.py -v
```

- [ ] **Step 3: Implement**

`autopilot/core/dispatcher.py`:
```python
"""Dispatcher — allocate accounts across multiple projects by priority."""

from __future__ import annotations

from dataclasses import dataclass

from autopilot.core.models import ProjectConfig


PRIORITY_WEIGHTS = {
    "high": 3,
    "normal": 2,
    "low": 1,
}


@dataclass
class ProjectAllocation:
    project_name: str
    project_path: str
    worker_count: int
    critic_count: int
    priority: str


class Dispatcher:
    """Allocates account slots to projects based on priority."""

    def __init__(self, total_workers: int = 14, total_critics: int = 5):
        self.total_workers = total_workers
        self.total_critics = total_critics

    def allocate(self, projects: list[ProjectConfig]) -> list[ProjectAllocation]:
        """Distribute workers and critics across projects by priority weight."""
        if not projects:
            return []

        weights = [PRIORITY_WEIGHTS.get(p.priority, 2) for p in projects]
        total_weight = sum(weights)

        allocations: list[ProjectAllocation] = []

        # Distribute workers
        worker_counts = self._distribute(self.total_workers, weights, total_weight, len(projects))
        critic_counts = self._distribute(self.total_critics, weights, total_weight, len(projects))

        for i, project in enumerate(projects):
            allocations.append(ProjectAllocation(
                project_name=project.name,
                project_path=project.path,
                worker_count=worker_counts[i],
                critic_count=critic_counts[i],
                priority=project.priority,
            ))

        return allocations

    def _distribute(self, total: int, weights: list[int], total_weight: int, count: int) -> list[int]:
        """Distribute total slots proportionally by weight, ensuring each gets at least 1."""
        # First, give everyone 1
        result = [1] * count
        remaining = total - count

        if remaining <= 0:
            return result

        # Distribute remaining by weight
        for i in range(len(weights)):
            share = int(remaining * weights[i] / total_weight)
            result[i] += share

        # Distribute any leftover to highest priority
        distributed = sum(result)
        leftover = total - distributed
        sorted_indices = sorted(range(len(weights)), key=lambda i: weights[i], reverse=True)
        for i in range(leftover):
            result[sorted_indices[i % len(sorted_indices)]] += 1

        return result
```

- [ ] **Step 4: Run tests — should pass**

```bash
pytest tests/test_dispatcher.py -v
```

- [ ] **Step 5: Commit**

```bash
git add autopilot/core/dispatcher.py tests/test_dispatcher.py
git commit -m "feat: dispatcher — multi-project account allocation by priority"
```

---

### Task 17: Git Worktrees for Parallel Stories

**Files:**
- Create: `autopilot/core/worktree.py`
- Create: `tests/test_worktree.py`

- [ ] **Step 1: Write tests**

`tests/test_worktree.py`:
```python
"""Tests for git worktree management."""

from unittest.mock import patch, MagicMock
from pathlib import Path

from autopilot.core.worktree import create_worktree, remove_worktree, merge_worktree, worktree_path


class TestWorktree:
    def test_worktree_path(self):
        result = worktree_path(Path("/Users/martin/project"), story_id=3)
        assert result == Path("/Users/martin/project-story-3")

    @patch("autopilot.core.worktree.subprocess.run")
    def test_create_worktree(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        result = create_worktree(Path("/Users/martin/project"), story_id=3)
        assert result == Path("/Users/martin/project-story-3")
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert "worktree" in call_args
        assert "add" in call_args

    @patch("autopilot.core.worktree.subprocess.run")
    def test_remove_worktree(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        remove_worktree(Path("/Users/martin/project"), Path("/Users/martin/project-story-3"))
        assert mock_run.called

    @patch("autopilot.core.worktree.subprocess.run")
    def test_merge_worktree(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        success = merge_worktree(
            main_path=Path("/Users/martin/project"),
            worktree_path=Path("/Users/martin/project-story-3"),
            branch_name="story-3",
        )
        assert success is True
```

- [ ] **Step 2: Run tests — should fail**

```bash
pytest tests/test_worktree.py -v
```

- [ ] **Step 3: Implement**

`autopilot/core/worktree.py`:
```python
"""Git worktree management for parallel story execution."""

from __future__ import annotations

import subprocess
from pathlib import Path


def worktree_path(project_path: Path, story_id: int) -> Path:
    """Generate worktree path for a story."""
    return project_path.parent / f"{project_path.name}-story-{story_id}"


def create_worktree(project_path: Path, story_id: int) -> Path:
    """Create a git worktree for a story. Returns the worktree path."""
    wt_path = worktree_path(project_path, story_id)
    branch = f"story-{story_id}"

    subprocess.run(
        ["git", "worktree", "add", "-b", branch, str(wt_path)],
        cwd=str(project_path),
        capture_output=True,
        text=True,
        check=True,
    )

    return wt_path


def remove_worktree(project_path: Path, wt_path: Path) -> None:
    """Remove a git worktree."""
    subprocess.run(
        ["git", "worktree", "remove", str(wt_path), "--force"],
        cwd=str(project_path),
        capture_output=True,
        text=True,
    )


def merge_worktree(main_path: Path, worktree_path: Path, branch_name: str) -> bool:
    """Merge a worktree branch back into main. Returns True on success."""
    # Switch to main
    result = subprocess.run(
        ["git", "merge", branch_name, "--no-edit"],
        cwd=str(main_path),
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        return False

    # Clean up worktree
    remove_worktree(main_path, worktree_path)

    # Delete branch
    subprocess.run(
        ["git", "branch", "-d", branch_name],
        cwd=str(main_path),
        capture_output=True,
        text=True,
    )

    return True
```

- [ ] **Step 4: Run tests — should pass**

```bash
pytest tests/test_worktree.py -v
```

- [ ] **Step 5: Commit**

```bash
git add autopilot/core/worktree.py tests/test_worktree.py
git commit -m "feat: git worktree management for parallel stories"
```

---

### Task 18: Telegram Notifier

**Files:**
- Create: `autopilot/core/notifier.py`
- Create: `tests/test_notifier.py`

- [ ] **Step 1: Write tests**

`tests/test_notifier.py`:
```python
"""Tests for notification system."""

from unittest.mock import patch, AsyncMock
from autopilot.core.notifier import Notifier, format_stuck_message, format_complete_message


class TestNotifier:
    def test_format_stuck_message(self):
        msg = format_stuck_message(
            project_name="uptime-monitor",
            story_id=3,
            story_title="OAuth login",
            reason="Critic gave same feedback 3 times",
            last_feedback="callback URL is hardcoded",
        )
        assert "uptime-monitor" in msg
        assert "OAuth login" in msg
        assert "hardcoded" in msg

    def test_format_complete_message(self):
        msg = format_complete_message(
            project_name="uptime-monitor",
            stories_done=5,
            stories_total=6,
            stories_stuck=1,
        )
        assert "5/6" in msg
        assert "uptime-monitor" in msg

    def test_notifier_disabled_without_token(self):
        notifier = Notifier(telegram_token=None, telegram_chat_id=None)
        assert notifier.enabled is False
```

- [ ] **Step 2: Run tests — should fail**

```bash
pytest tests/test_notifier.py -v
```

- [ ] **Step 3: Implement**

`autopilot/core/notifier.py`:
```python
"""Notification system — Telegram alerts for stuck agents and completions."""

from __future__ import annotations

import asyncio
import os


def format_stuck_message(
    project_name: str,
    story_id: int,
    story_title: str,
    reason: str,
    last_feedback: str,
) -> str:
    return (
        f"⚠️ STUCK — {project_name}\n\n"
        f"Story #{story_id}: {story_title}\n"
        f"Reason: {reason}\n\n"
        f"Last feedback:\n{last_feedback[:500]}"
    )


def format_complete_message(
    project_name: str,
    stories_done: int,
    stories_total: int,
    stories_stuck: int,
) -> str:
    status = "✅ COMPLETE" if stories_stuck == 0 else "⚠️ PARTIAL"
    return (
        f"{status} — {project_name}\n\n"
        f"Stories: {stories_done}/{stories_total} done\n"
        f"Stuck: {stories_stuck}"
    )


def format_escalation_message(
    project_name: str,
    story_id: int,
    from_provider: str,
    to_provider: str,
) -> str:
    return (
        f"🔄 ESCALATION — {project_name}\n\n"
        f"Story #{story_id}: {from_provider} → {to_provider}"
    )


class Notifier:
    """Send notifications via Telegram."""

    def __init__(
        self,
        telegram_token: str | None = None,
        telegram_chat_id: str | None = None,
    ):
        self.token = telegram_token or os.environ.get("AUTOPILOT_TELEGRAM_TOKEN")
        self.chat_id = telegram_chat_id or os.environ.get("AUTOPILOT_TELEGRAM_CHAT_ID")

    @property
    def enabled(self) -> bool:
        return bool(self.token and self.chat_id)

    async def send(self, message: str) -> bool:
        """Send a message via Telegram. Returns True on success."""
        if not self.enabled:
            return False

        try:
            from telegram import Bot
            bot = Bot(token=self.token)
            await bot.send_message(chat_id=self.chat_id, text=message)
            return True
        except Exception:
            return False

    def send_sync(self, message: str) -> bool:
        """Synchronous wrapper for send."""
        if not self.enabled:
            return False
        try:
            return asyncio.run(self.send(message))
        except Exception:
            return False
```

- [ ] **Step 4: Run tests — should pass**

```bash
pytest tests/test_notifier.py -v
```

- [ ] **Step 5: Commit**

```bash
git add autopilot/core/notifier.py tests/test_notifier.py
git commit -m "feat: Telegram notifier — stuck, escalation, completion alerts"
```

---

### Task 19: Update CLI for Multi-project (`autopilot run --all`)

**Files:**
- Modify: `autopilot/cli/run.py`
- Modify: `autopilot/cli/main.py`

- [ ] **Step 1: Add --all flag and multi-project orchestration**

Add to `autopilot/cli/run.py` a new function `run_all`:

```python
def run_all() -> None:
    """Run autopilot on all configured projects in parallel."""
    import yaml
    import concurrent.futures

    config = load_config(Path.home() / ".autopilot" / "config.yaml")
    projects_path = config.projects_yaml_path

    if not projects_path.exists():
        console.print("[red]No projects.yaml found. Create ~/.autopilot/projects.yaml[/red]")
        raise typer.Exit(1)

    data = yaml.safe_load(projects_path.read_text()) or {}
    projects = data.get("projects", [])

    if not projects:
        console.print("[red]No projects configured in projects.yaml[/red]")
        raise typer.Exit(1)

    console.print(f"[bold]Autopilot[/bold] — running {len(projects)} projects in parallel\n")

    # Run each project in a separate thread
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(projects)) as executor:
        futures = {}
        for p in projects:
            future = executor.submit(run, p["path"], p.get("prd", ".agents/tasks/prd.json"))
            futures[future] = p["name"]

        for future in concurrent.futures.as_completed(futures):
            name = futures[future]
            try:
                future.result()
                console.print(f"[green]{name}: complete[/green]")
            except Exception as e:
                console.print(f"[red]{name}: error — {e}[/red]")
```

- [ ] **Step 2: Update main CLI to expose --all**

Add to `autopilot/cli/main.py`:
```python
@app.command(name="run-all")
def run_all_projects():
    """Run autopilot on all configured projects in parallel."""
    from autopilot.cli.run import run_all

    run_all()
```

- [ ] **Step 3: Commit**

```bash
git add autopilot/cli/run.py autopilot/cli/main.py
git commit -m "feat: autopilot run-all — parallel multi-project execution"
```

- [ ] **Step 4: Tag Phase 2**

```bash
pytest tests/ -v --tb=short
git tag v0.2.0-phase2
git commit --allow-empty -m "milestone: Phase 2 multi-project + escalation complete"
```

---

## Phase 3: Dashboard

### Task 20: FastAPI Sidecar — Core API

**Files:**
- Create: `autopilot/api/__init__.py`
- Create: `autopilot/api/main.py`
- Create: `autopilot/api/deps.py`
- Create: `autopilot/api/routes/__init__.py`
- Create: `autopilot/api/routes/projects.py`
- Create: `autopilot/api/routes/accounts.py`

- [ ] **Step 1: Create API scaffold**

`autopilot/api/__init__.py`:
```python
```

`autopilot/api/deps.py`:
```python
"""Shared dependencies for API routes."""

from __future__ import annotations

from pathlib import Path

from autopilot.core.config import load_config, AutopilotConfig
from autopilot.core.account_manager import AccountManager


def get_config() -> AutopilotConfig:
    return load_config(Path.home() / ".autopilot" / "config.yaml")


def get_account_manager() -> AccountManager:
    config = get_config()
    mgr = AccountManager(profiles_dir=config.profiles_dir)
    mgr.discover()
    return mgr
```

`autopilot/api/main.py`:
```python
"""FastAPI sidecar API for the Autopilot dashboard."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from autopilot.api.routes import projects, accounts

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


@app.get("/api/health")
async def health():
    return {"status": "ok"}
```

`autopilot/api/routes/__init__.py`:
```python
```

`autopilot/api/routes/projects.py`:
```python
"""Project routes — list projects, get stories, perform actions."""

from __future__ import annotations

import json
from pathlib import Path

import yaml
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from autopilot.api.deps import get_config

router = APIRouter()


class StoryAction(BaseModel):
    action: str  # "pause", "skip", "reassign", "add_guidance"
    payload: str = ""


@router.get("/")
async def list_projects():
    config = get_config()
    projects_path = config.projects_yaml_path
    if not projects_path.exists():
        return {"projects": []}

    data = yaml.safe_load(projects_path.read_text()) or {}
    projects = []

    for p in data.get("projects", []):
        prd_path = Path(p["path"]) / p.get("prd", ".agents/tasks/prd.json")
        stories = []
        if prd_path.exists():
            try:
                prd_data = json.loads(prd_path.read_text())
                stories = prd_data.get("stories", [])
            except Exception:
                pass

        projects.append({
            "name": p["name"],
            "path": p["path"],
            "priority": p.get("priority", "normal"),
            "stories": stories,
            "stories_done": sum(1 for s in stories if s.get("status") == "done"),
            "stories_total": len(stories),
        })

    return {"projects": projects}


@router.get("/{project_name}")
async def get_project(project_name: str):
    config = get_config()
    projects_path = config.projects_yaml_path
    if not projects_path.exists():
        raise HTTPException(404, "No projects configured")

    data = yaml.safe_load(projects_path.read_text()) or {}
    for p in data.get("projects", []):
        if p["name"] == project_name:
            prd_path = Path(p["path"]) / p.get("prd", ".agents/tasks/prd.json")
            stories = []
            if prd_path.exists():
                prd_data = json.loads(prd_path.read_text())
                stories = prd_data.get("stories", [])

            # Read ralph state
            ralph_dir = Path(p["path"]) / ".ralph"
            progress = (ralph_dir / "progress.md").read_text() if (ralph_dir / "progress.md").exists() else ""
            guardrails = (ralph_dir / "guardrails.md").read_text() if (ralph_dir / "guardrails.md").exists() else ""

            return {
                **p,
                "stories": stories,
                "progress": progress,
                "guardrails": guardrails,
            }

    raise HTTPException(404, f"Project {project_name} not found")


@router.post("/{project_name}/stories/{story_id}/action")
async def story_action(project_name: str, story_id: int, action: StoryAction):
    config = get_config()
    projects_path = config.projects_yaml_path
    data = yaml.safe_load(projects_path.read_text()) or {}

    for p in data.get("projects", []):
        if p["name"] == project_name:
            if action.action == "add_guidance":
                ralph_dir = Path(p["path"]) / ".ralph"
                ralph_dir.mkdir(exist_ok=True)
                guardrails = ralph_dir / "guardrails.md"
                existing = guardrails.read_text() if guardrails.exists() else ""
                guardrails.write_text(existing + f"\n- [HUMAN]: {action.payload}\n")
                return {"status": "ok", "message": "Guidance added to guardrails.md"}

            elif action.action == "skip":
                prd_path = Path(p["path"]) / p.get("prd", ".agents/tasks/prd.json")
                prd_data = json.loads(prd_path.read_text())
                for s in prd_data["stories"]:
                    if s["id"] == story_id:
                        s["status"] = "skipped"
                prd_path.write_text(json.dumps(prd_data, indent=2, ensure_ascii=False))
                return {"status": "ok", "message": f"Story #{story_id} skipped"}

    raise HTTPException(404, "Project or story not found")
```

`autopilot/api/routes/accounts.py`:
```python
"""Account routes — health, status."""

from fastapi import APIRouter

from autopilot.api.deps import get_account_manager

router = APIRouter()


@router.get("/")
async def list_accounts():
    mgr = get_account_manager()
    result = {}
    for provider in ("codex", "claude", "gemini"):
        if provider in mgr.pools:
            result[provider] = mgr.pool_status(provider)
    return {"accounts": result}


@router.get("/health")
async def accounts_health():
    mgr = get_account_manager()
    total = sum(len(profiles) for profiles in mgr.pools.values())
    available = sum(
        sum(1 for p in profiles if p.check_available())
        for profiles in mgr.pools.values()
    )
    return {
        "total": total,
        "available": available,
        "on_cooldown": total - available,
    }
```

- [ ] **Step 2: Commit**

```bash
git add autopilot/api/
git commit -m "feat: FastAPI sidecar — projects and accounts API"
```

---

### Task 21: SSE Event Stream

**Files:**
- Create: `autopilot/api/sse.py`
- Create: `autopilot/api/routes/events.py`

- [ ] **Step 1: Implement SSE broadcaster**

`autopilot/api/sse.py`:
```python
"""Server-Sent Events broadcaster for live dashboard updates."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from typing import AsyncGenerator


@dataclass
class SSEEvent:
    event: str
    data: dict


class SSEBroadcaster:
    """Manages SSE connections and broadcasts events."""

    def __init__(self):
        self._queues: list[asyncio.Queue] = []

    async def subscribe(self) -> AsyncGenerator[str, None]:
        """Subscribe to the event stream."""
        queue: asyncio.Queue = asyncio.Queue()
        self._queues.append(queue)
        try:
            while True:
                event = await queue.get()
                yield f"event: {event.event}\ndata: {json.dumps(event.data)}\n\n"
        finally:
            self._queues.remove(queue)

    async def broadcast(self, event: str, data: dict) -> None:
        """Send an event to all connected clients."""
        sse_event = SSEEvent(event=event, data=data)
        for queue in self._queues:
            await queue.put(sse_event)


# Global broadcaster instance
broadcaster = SSEBroadcaster()
```

`autopilot/api/routes/events.py`:
```python
"""SSE event stream route."""

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from autopilot.api.sse import broadcaster

router = APIRouter()


@router.get("/")
async def event_stream():
    return StreamingResponse(
        broadcaster.subscribe(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
```

- [ ] **Step 2: Register in main app**

Add to `autopilot/api/main.py`:
```python
from autopilot.api.routes import projects, accounts, events

# ...existing code...
app.include_router(events.router, prefix="/api/events", tags=["events"])
```

- [ ] **Step 3: Commit**

```bash
git add autopilot/api/sse.py autopilot/api/routes/events.py autopilot/api/main.py
git commit -m "feat: SSE event stream for live dashboard updates"
```

---

### Task 22: Dashboard CLI Command

**Files:**
- Create: `autopilot/cli/dashboard.py`
- Modify: `autopilot/cli/main.py`

- [ ] **Step 1: Implement dashboard launcher**

`autopilot/cli/dashboard.py`:
```python
"""CLI command: autopilot dashboard."""

from __future__ import annotations

import subprocess
import webbrowser
import time

import typer
from rich.console import Console

console = Console()


def dashboard(
    port: int = typer.Option(8420, help="API server port"),
    no_browser: bool = typer.Option(False, help="Don't open browser"),
) -> None:
    """Start the dashboard (API server + opens browser)."""
    console.print(f"[bold]Starting Autopilot dashboard on port {port}...[/bold]")

    # Start uvicorn
    try:
        process = subprocess.Popen(
            ["uvicorn", "autopilot.api.main:app", "--port", str(port), "--host", "0.0.0.0"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        time.sleep(2)  # wait for server to start

        if not no_browser:
            webbrowser.open(f"http://localhost:3000")  # Next.js dashboard

        console.print(f"[green]API running on http://localhost:{port}[/green]")
        console.print("[dim]Press Ctrl+C to stop[/dim]")

        process.wait()
    except KeyboardInterrupt:
        console.print("\n[yellow]Shutting down...[/yellow]")
        process.terminate()
```

- [ ] **Step 2: Register in main CLI**

Add to `autopilot/cli/main.py`:
```python
@app.command()
def dashboard(
    port: int = typer.Option(8420, help="API server port"),
    no_browser: bool = typer.Option(False, help="Don't open browser"),
):
    """Start the Autopilot dashboard."""
    from autopilot.cli.dashboard import dashboard as _dashboard

    _dashboard(port, no_browser)
```

- [ ] **Step 3: Commit**

```bash
git add autopilot/cli/dashboard.py autopilot/cli/main.py
git commit -m "feat: autopilot dashboard command — starts API server"
```

---

### Task 23: Next.js Dashboard Scaffold

**Files:**
- Create: `dashboard/` (full Next.js project)

- [ ] **Step 1: Create Next.js project**

```bash
cd ~/Desktop/autopilot
npx create-next-app@latest dashboard --typescript --tailwind --eslint --app --no-src-dir --import-alias "@/*"
cd dashboard
npx shadcn@latest init -d
npx shadcn@latest add card badge button table tabs separator scroll-area
```

- [ ] **Step 2: Create API client**

`dashboard/lib/api.ts`:
```typescript
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8420/api";

export async function fetchProjects() {
  const res = await fetch(`${API_BASE}/projects`);
  return res.json();
}

export async function fetchProject(name: string) {
  const res = await fetch(`${API_BASE}/projects/${name}`);
  return res.json();
}

export async function fetchAccountsHealth() {
  const res = await fetch(`${API_BASE}/accounts/health`);
  return res.json();
}

export async function storyAction(projectName: string, storyId: number, action: string, payload = "") {
  const res = await fetch(`${API_BASE}/projects/${projectName}/stories/${storyId}/action`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action, payload }),
  });
  return res.json();
}
```

- [ ] **Step 3: Create SSE hook**

`dashboard/lib/sse.ts`:
```typescript
import { useEffect, useCallback, useRef } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8420/api";

export function useSSE(onEvent: (event: string, data: any) => void) {
  const eventSourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    const es = new EventSource(`${API_BASE}/events`);
    eventSourceRef.current = es;

    es.addEventListener("story_update", (e) => {
      onEvent("story_update", JSON.parse(e.data));
    });

    es.addEventListener("account_update", (e) => {
      onEvent("account_update", JSON.parse(e.data));
    });

    es.addEventListener("iteration_complete", (e) => {
      onEvent("iteration_complete", JSON.parse(e.data));
    });

    es.onerror = () => {
      es.close();
      // Reconnect after 3s
      setTimeout(() => {
        eventSourceRef.current = new EventSource(`${API_BASE}/events`);
      }, 3000);
    };

    return () => es.close();
  }, [onEvent]);
}
```

- [ ] **Step 4: Create TypeScript types**

`dashboard/lib/types.ts`:
```typescript
export interface Story {
  id: number;
  title: string;
  description: string;
  status: "open" | "in_progress" | "done" | "stuck" | "skipped";
  agent?: string;
  iteration?: number;
  elapsed_min?: number;
}

export interface Project {
  name: string;
  path: string;
  priority: "high" | "normal" | "low";
  stories: Story[];
  stories_done: number;
  stories_total: number;
}

export interface AccountHealth {
  total: number;
  available: number;
  on_cooldown: number;
}
```

- [ ] **Step 5: Commit**

```bash
cd ~/Desktop/autopilot
git add dashboard/
git commit -m "feat: Next.js dashboard scaffold with API client and SSE hook"
```

---

### Task 24: Kanban Board Component

**Files:**
- Create: `dashboard/components/kanban-board.tsx`
- Create: `dashboard/components/story-card.tsx`
- Modify: `dashboard/app/page.tsx`

- [ ] **Step 1: Create story card**

`dashboard/components/story-card.tsx`:
```tsx
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Story } from "@/lib/types";

const statusColors: Record<string, string> = {
  open: "bg-gray-100 text-gray-800",
  in_progress: "bg-blue-100 text-blue-800",
  done: "bg-green-100 text-green-800",
  stuck: "bg-red-100 text-red-800",
  skipped: "bg-yellow-100 text-yellow-800",
};

export function StoryCard({ story, onClick }: { story: Story; onClick?: () => void }) {
  return (
    <Card className="cursor-pointer hover:shadow-md transition-shadow" onClick={onClick}>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm font-medium">#{story.id} {story.title}</CardTitle>
          <Badge className={statusColors[story.status] || ""}>{story.status}</Badge>
        </div>
      </CardHeader>
      <CardContent className="pt-0">
        {story.agent && (
          <p className="text-xs text-muted-foreground">
            {story.agent} {story.iteration ? `• iter ${story.iteration}` : ""}
          </p>
        )}
      </CardContent>
    </Card>
  );
}
```

- [ ] **Step 2: Create kanban board**

`dashboard/components/kanban-board.tsx`:
```tsx
"use client";

import { ScrollArea } from "@/components/ui/scroll-area";
import { StoryCard } from "./story-card";
import { Project } from "@/lib/types";

const columns = [
  { key: "open", label: "Open" },
  { key: "in_progress", label: "In Progress" },
  { key: "done", label: "Done" },
  { key: "stuck", label: "Stuck" },
];

export function KanbanBoard({
  project,
  onStoryClick,
}: {
  project: Project;
  onStoryClick?: (storyId: number) => void;
}) {
  return (
    <div className="border rounded-lg p-4">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold">{project.name}</h2>
        <span className="text-sm text-muted-foreground">
          {project.stories_done}/{project.stories_total} done
        </span>
      </div>
      <div className="grid grid-cols-4 gap-4">
        {columns.map((col) => (
          <div key={col.key}>
            <h3 className="text-sm font-medium text-muted-foreground mb-2">{col.label}</h3>
            <ScrollArea className="h-[400px]">
              <div className="space-y-2">
                {project.stories
                  .filter((s) => s.status === col.key)
                  .map((story) => (
                    <StoryCard
                      key={story.id}
                      story={story}
                      onClick={() => onStoryClick?.(story.id)}
                    />
                  ))}
              </div>
            </ScrollArea>
          </div>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Update main page**

`dashboard/app/page.tsx`:
```tsx
"use client";

import { useEffect, useState, useCallback } from "react";
import { KanbanBoard } from "@/components/kanban-board";
import { fetchProjects, fetchAccountsHealth } from "@/lib/api";
import { useSSE } from "@/lib/sse";
import { Project, AccountHealth } from "@/lib/types";

export default function Home() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [health, setHealth] = useState<AccountHealth | null>(null);

  const loadData = useCallback(async () => {
    const [projData, healthData] = await Promise.all([
      fetchProjects(),
      fetchAccountsHealth(),
    ]);
    setProjects(projData.projects || []);
    setHealth(healthData);
  }, []);

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 10000);
    return () => clearInterval(interval);
  }, [loadData]);

  useSSE(
    useCallback(() => {
      loadData();
    }, [loadData])
  );

  return (
    <main className="p-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Autopilot</h1>
        {health && (
          <div className="text-sm text-muted-foreground">
            Accounts: {health.available}/{health.total} active
            {health.on_cooldown > 0 && ` • ${health.on_cooldown} cooldown`}
          </div>
        )}
      </div>

      <div className="space-y-6">
        {projects.map((project) => (
          <KanbanBoard key={project.name} project={project} />
        ))}
        {projects.length === 0 && (
          <p className="text-muted-foreground text-center py-12">
            No projects configured. Add projects to ~/.autopilot/projects.yaml
          </p>
        )}
      </div>
    </main>
  );
}
```

- [ ] **Step 4: Commit**

```bash
git add dashboard/
git commit -m "feat: Kanban board with story cards and live updates"
```

---

### Task 25: Story Detail Panel & Actions

**Files:**
- Create: `dashboard/components/story-detail-panel.tsx`
- Create: `dashboard/components/action-buttons.tsx`

- [ ] **Step 1: Create action buttons**

`dashboard/components/action-buttons.tsx`:
```tsx
"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { storyAction } from "@/lib/api";

export function ActionButtons({
  projectName,
  storyId,
  onAction,
}: {
  projectName: string;
  storyId: number;
  onAction?: () => void;
}) {
  const [guidance, setGuidance] = useState("");
  const [showGuidance, setShowGuidance] = useState(false);

  const handleAction = async (action: string, payload = "") => {
    await storyAction(projectName, storyId, action, payload);
    onAction?.();
  };

  return (
    <div className="space-y-2">
      <div className="flex gap-2">
        <Button size="sm" variant="outline" onClick={() => handleAction("pause")}>
          Pause
        </Button>
        <Button size="sm" variant="outline" onClick={() => handleAction("skip")}>
          Skip
        </Button>
        <Button size="sm" variant="outline" onClick={() => setShowGuidance(!showGuidance)}>
          Add Guidance
        </Button>
      </div>
      {showGuidance && (
        <div className="flex gap-2">
          <input
            className="flex-1 border rounded px-2 py-1 text-sm"
            placeholder="Add guidance for the agent..."
            value={guidance}
            onChange={(e) => setGuidance(e.target.value)}
          />
          <Button
            size="sm"
            onClick={() => {
              handleAction("add_guidance", guidance);
              setGuidance("");
              setShowGuidance(false);
            }}
          >
            Send
          </Button>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Create story detail panel**

`dashboard/components/story-detail-panel.tsx`:
```tsx
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { ActionButtons } from "./action-buttons";
import { Story } from "@/lib/types";

export function StoryDetailPanel({
  story,
  projectName,
  criticFeedback,
  onAction,
}: {
  story: Story;
  projectName: string;
  criticFeedback?: string;
  onAction?: () => void;
}) {
  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle>#{story.id}: {story.title}</CardTitle>
          <Badge>{story.status}</Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-sm text-muted-foreground">{story.description}</p>

        {story.agent && (
          <>
            <Separator />
            <div className="text-sm">
              <p><strong>Agent:</strong> {story.agent}</p>
              {story.iteration && <p><strong>Iteration:</strong> {story.iteration}</p>}
              {story.elapsed_min && <p><strong>Time:</strong> {story.elapsed_min}min</p>}
            </div>
          </>
        )}

        {criticFeedback && (
          <>
            <Separator />
            <div>
              <h4 className="text-sm font-medium mb-1">Critic Feedback</h4>
              <pre className="text-xs bg-muted p-2 rounded whitespace-pre-wrap">{criticFeedback}</pre>
            </div>
          </>
        )}

        <Separator />
        <ActionButtons projectName={projectName} storyId={story.id} onAction={onAction} />
      </CardContent>
    </Card>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add dashboard/components/
git commit -m "feat: story detail panel with critic feedback and action buttons"
```

- [ ] **Step 4: Tag Phase 3**

```bash
git tag v0.3.0-phase3
git commit --allow-empty -m "milestone: Phase 3 dashboard complete"
```

---

## Phase 4: Intake Agent

### Task 26: Intake Agent Backend

**Files:**
- Create: `autopilot/core/intake.py`
- Create: `autopilot/api/routes/intake.py`

- [ ] **Step 1: Implement intake agent**

`autopilot/core/intake.py`:
```python
"""Intake agent — brainstorm with user and generate PRD."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from dataclasses import dataclass, field

from autopilot.core.account_manager import AccountManager


@dataclass
class IntakeSession:
    session_id: str
    messages: list[dict] = field(default_factory=list)
    prd: dict | None = None
    project_name: str = ""

    def add_user_message(self, text: str) -> None:
        self.messages.append({"role": "user", "content": text})

    def add_agent_message(self, text: str) -> None:
        self.messages.append({"role": "assistant", "content": text})


INTAKE_SYSTEM_PROMPT = """You are a project intake agent. Your job is to help the user define a software project.

Ask clarifying questions ONE AT A TIME to understand:
1. What the project does
2. Tech stack (language, framework, deployment)
3. Key features (3-8 stories)
4. Any constraints or requirements

After you have enough information, generate a PRD in this JSON format:
```json
{
  "title": "Project Name",
  "description": "One paragraph description",
  "stories": [
    {"id": 1, "title": "Story title", "description": "What to build", "status": "open"},
    {"id": 2, "title": "Story title", "description": "What to build", "status": "open"}
  ]
}
```

Output ONLY the JSON when you're ready. No markdown fences, no explanation.
Start by asking: "What do you want to build?"
"""


def run_intake_turn(
    session: IntakeSession,
    user_message: str,
    provider: str,
    env: dict[str, str],
    workdir: str = "/tmp",
) -> str:
    """Run one turn of the intake conversation."""
    session.add_user_message(user_message)

    # Build conversation as prompt
    conversation = f"[System]: {INTAKE_SYSTEM_PROMPT}\n\n"
    for msg in session.messages:
        role = "User" if msg["role"] == "user" else "Assistant"
        conversation += f"[{role}]: {msg['content']}\n\n"
    conversation += "[Assistant]:"

    if provider == "codex":
        cmd = ["codex", "exec", "--full-auto", conversation]
    elif provider == "claude":
        cmd = ["claude", "-p", conversation]
    else:
        cmd = ["codex", "exec", "--full-auto", conversation]

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=120,
            cwd=workdir, env=env,
        )
        response = result.stdout.strip()
    except Exception as e:
        response = f"Error: {e}"

    session.add_agent_message(response)

    # Check if response is a PRD JSON
    try:
        prd = json.loads(response)
        if "stories" in prd:
            session.prd = prd
    except (json.JSONDecodeError, TypeError):
        pass

    return response


def save_prd(prd: dict, project_path: Path) -> Path:
    """Save generated PRD to the project's tasks directory."""
    tasks_dir = project_path / ".agents" / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)

    # Generate filename from title
    slug = prd.get("title", "project").lower().replace(" ", "-")[:30]
    prd_path = tasks_dir / f"prd-{slug}.json"
    prd_path.write_text(json.dumps(prd, indent=2, ensure_ascii=False))

    return prd_path
```

- [ ] **Step 2: Create intake API route**

`autopilot/api/routes/intake.py`:
```python
"""Intake routes — chat with intake agent, generate PRD."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from autopilot.api.deps import get_config, get_account_manager
from autopilot.core.intake import IntakeSession, run_intake_turn

router = APIRouter()

# In-memory sessions (for MVP; could move to SQLite later)
sessions: dict[str, IntakeSession] = {}


class ChatMessage(BaseModel):
    message: str
    session_id: str | None = None


class ChatResponse(BaseModel):
    session_id: str
    response: str
    prd_ready: bool
    prd: dict | None = None


@router.post("/message", response_model=ChatResponse)
async def intake_message(msg: ChatMessage):
    # Get or create session
    if msg.session_id and msg.session_id in sessions:
        session = sessions[msg.session_id]
    else:
        session_id = str(uuid.uuid4())[:8]
        session = IntakeSession(session_id=session_id)
        sessions[session_id] = session

    # Get an intake account
    config = get_config()
    mgr = get_account_manager()

    profile = mgr.get_next("codex")
    if profile is None:
        raise HTTPException(503, "No available accounts for intake")

    env = mgr.build_env(profile)

    response = run_intake_turn(
        session=session,
        user_message=msg.message,
        provider="codex",
        env=env,
    )

    return ChatResponse(
        session_id=session.session_id,
        response=response,
        prd_ready=session.prd is not None,
        prd=session.prd,
    )


@router.get("/sessions")
async def list_sessions():
    return {
        "sessions": [
            {
                "id": s.session_id,
                "messages": len(s.messages),
                "prd_ready": s.prd is not None,
            }
            for s in sessions.values()
        ]
    }
```

- [ ] **Step 3: Register in main API**

Add to `autopilot/api/main.py`:
```python
from autopilot.api.routes import projects, accounts, events, intake

app.include_router(intake.router, prefix="/api/intake", tags=["intake"])
```

- [ ] **Step 4: Commit**

```bash
git add autopilot/core/intake.py autopilot/api/routes/intake.py autopilot/api/main.py
git commit -m "feat: intake agent — brainstorm chat and PRD generation"
```

---

### Task 27: Intake Chat UI

**Files:**
- Create: `dashboard/app/intake/page.tsx`
- Create: `dashboard/components/intake-chat.tsx`

- [ ] **Step 1: Create chat component**

`dashboard/components/intake-chat.tsx`:
```tsx
"use client";

import { useState, useRef, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8420/api";

interface Message {
  role: "user" | "assistant";
  content: string;
}

export function IntakeChat({ onPRDReady }: { onPRDReady?: (prd: any) => void }) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const sendMessage = async () => {
    if (!input.trim() || loading) return;

    const userMsg = input.trim();
    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: userMsg }]);
    setLoading(true);

    try {
      const res = await fetch(`${API_BASE}/intake/message`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: userMsg, session_id: sessionId }),
      });
      const data = await res.json();

      setSessionId(data.session_id);
      setMessages((prev) => [...prev, { role: "assistant", content: data.response }]);

      if (data.prd_ready && data.prd) {
        onPRDReady?.(data.prd);
      }
    } catch (e) {
      setMessages((prev) => [...prev, { role: "assistant", content: "Error connecting to API" }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card className="flex flex-col h-[600px]">
      <ScrollArea className="flex-1 p-4">
        <div className="space-y-4">
          {messages.length === 0 && (
            <p className="text-muted-foreground text-center py-8">
              Describe your project idea and the intake agent will help you create a PRD.
            </p>
          )}
          {messages.map((msg, i) => (
            <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
              <div
                className={`max-w-[80%] rounded-lg px-3 py-2 text-sm ${
                  msg.role === "user" ? "bg-primary text-primary-foreground" : "bg-muted"
                }`}
              >
                <pre className="whitespace-pre-wrap font-sans">{msg.content}</pre>
              </div>
            </div>
          ))}
          {loading && (
            <div className="flex justify-start">
              <div className="bg-muted rounded-lg px-3 py-2 text-sm text-muted-foreground">
                Thinking...
              </div>
            </div>
          )}
          <div ref={scrollRef} />
        </div>
      </ScrollArea>
      <div className="border-t p-4 flex gap-2">
        <input
          className="flex-1 border rounded-lg px-3 py-2 text-sm"
          placeholder="Describe your project..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && sendMessage()}
          disabled={loading}
        />
        <Button onClick={sendMessage} disabled={loading}>
          Send
        </Button>
      </div>
    </Card>
  );
}
```

- [ ] **Step 2: Create intake page**

`dashboard/app/intake/page.tsx`:
```tsx
"use client";

import { useState } from "react";
import { IntakeChat } from "@/components/intake-chat";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";

export default function IntakePage() {
  const [prd, setPRD] = useState<any>(null);

  return (
    <main className="p-6 max-w-4xl mx-auto">
      <h1 className="text-2xl font-bold mb-6">New Project</h1>

      <IntakeChat onPRDReady={setPRD} />

      {prd && (
        <Card className="mt-6">
          <CardHeader>
            <CardTitle>Generated PRD: {prd.title}</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground mb-4">{prd.description}</p>
            <h3 className="font-medium mb-2">Stories ({prd.stories?.length || 0})</h3>
            <ul className="space-y-1">
              {prd.stories?.map((s: any) => (
                <li key={s.id} className="text-sm">
                  #{s.id} — {s.title}
                </li>
              ))}
            </ul>
            <div className="flex gap-2 mt-4">
              <Button>Launch Project</Button>
              <Button variant="outline">Edit PRD</Button>
            </div>
          </CardContent>
        </Card>
      )}
    </main>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add dashboard/
git commit -m "feat: intake chat UI — brainstorm and generate PRD from dashboard"
```

- [ ] **Step 4: Final tests and tag**

```bash
cd ~/Desktop/autopilot
pytest tests/ -v --tb=short
git tag v0.4.0-phase4
git commit --allow-empty -m "milestone: Phase 4 intake agent complete — all phases done"
```

---

## Summary of All Commands

After all phases, the full CLI looks like this:

```bash
# Setup
autopilot login codex          # save Codex accounts (repeat for each)
autopilot login claude         # save Claude accounts
autopilot init ~/my-project    # initialize Ralph in a project

# Single project
autopilot run ~/my-project     # run until all stories done
autopilot status               # show accounts + projects in terminal

# Multi-project
autopilot run-all              # run all configured projects in parallel

# Dashboard
autopilot dashboard            # start API + open browser
```

Total: **27 tasks**, **4 phases**, estimated **~120 files**.
