# Dashboard

Frontend for the Autopilot dashboard.

## Development

From this directory:

```bash
npm run dev
```

That single command starts:

- Next.js on `http://localhost:3020`
- FastAPI backend on `http://localhost:8420`

You can also start the full stack from the repository root:

```bash
.venv/bin/python -m autopilot dashboard
```

## Notes

- The frontend expects the backend API at `http://localhost:8420/api` by default.
- The default frontend dev port is `3020` so it does not collide with other apps using `3000`.
- Webpack is forced for local dev and build; Turbopack is not used by default.
- SSE updates are consumed from `/api/events/`.
- Intake chat uses `/api/intake/message` and `/api/intake/sessions`.
