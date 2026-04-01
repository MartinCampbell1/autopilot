# Autopilot Service Install

These sample files run `autopilot` in headless mode so the service manager can restart failed runs and keep JSON summaries in the log stream.

## Linux (`systemd`)

1. Copy `deploy/systemd/autopilot.service` to `~/.config/systemd/user/autopilot.service` or `/etc/systemd/system/autopilot.service`.
2. Replace these placeholders:
   - `__PYTHON__`
   - `__AUTOPILOT_HOME__`
   - `__AUTOPILOT_PROJECT_PATH__`
   - `__AUTOPILOT_PROJECT_ID__`
   - `__AUTOPILOT_PRD__`
   - `__WORKDIR__`
   - `__LOG_PATH__`
3. Run `systemctl --user daemon-reload`.
4. Run `systemctl --user enable --now autopilot.service`.
5. Inspect logs with `journalctl --user -u autopilot.service -f` or tail `__LOG_PATH__`.

## macOS (`launchd`)

1. Copy `deploy/launchd/com.autopilot.plist` to `~/Library/LaunchAgents/com.autopilot.plist`.
2. Replace the same placeholders in the plist.
3. Run `launchctl unload ~/Library/LaunchAgents/com.autopilot.plist 2>/dev/null || true`.
4. Run `launchctl load ~/Library/LaunchAgents/com.autopilot.plist`.
5. Inspect logs with `tail -f __LOG_PATH__`.

## Notes

- The service command uses `autopilot run --headless`, so stdout/stderr are JSON-friendly.
- `Restart=on-failure` and `KeepAlive` restart the process when the run exits non-zero.
- Use the registered project id when possible so the service resumes the same runtime state after a crash.
