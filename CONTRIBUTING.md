# Contributing

Autopilot is the execution plane for FounderOS. Contributions should improve the product as an operator-visible, local-first, deterministic system, not turn it into another opaque swarm runner.

## Ground Rules

- keep orchestration deterministic; do not move core coordination logic into an LLM
- preserve the local-first and operator-trust model
- prefer extending existing contracts over introducing parallel subsystems
- keep changes scoped; avoid mixing unrelated refactors with product work
- update public docs and tests when public behavior or contracts change

## Local Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,api]"
cd dashboard && npm install
cd ..
```

## Verification Baseline

Before opening a pull request, run the same baseline used for release verification:

```bash
./.venv/bin/python -m pytest -q
./.venv/bin/ruff check autopilot tests
(cd dashboard && npm run lint)
(cd dashboard && npm run build)
./.venv/bin/autopilot dashboard --no-browser
./.venv/bin/autopilot live --once
./.venv/bin/autopilot status
```

If you intentionally skip any step, explain why in the pull request.

## Pull Requests

- describe the user-visible change, not just the implementation detail
- call out any contract changes across CLI, API, dashboard, or docs
- include the verification commands you ran and their outcomes
- keep migration and compatibility notes explicit when changing persisted state

Use the pull request template in `.github/pull_request_template.md`.

## Issues And Roadmap

- use the issue templates for bugs and feature requests
- check [ROADMAP.md](ROADMAP.md) before proposing large new systems
- treat deferred items as out of scope unless there is a concrete failure mode

## License

By contributing, you agree that your contributions will be licensed under the MIT License in this repository.

## Conduct

Participation in this project is governed by [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
