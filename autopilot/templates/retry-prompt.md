## Context
You are continuing story #{story_id}: {story_title}

Story details:
{story_description}

The previous attempt was rejected or incomplete.

## Before starting
1. Read .ralph/critic-feedback.md - what exactly is wrong
2. Read .ralph/progress.md - what has already been tried
3. Read .ralph/guardrails.md - previous mistakes
4. Read .ralph/team-context.json and .ralph/team-messages.json if they exist.
5. Treat .ralph/team-messages.json as the explicit teammate channel; do not assume arbitrary notes files are shared.
6. Read AGENTS.md if it exists
7. Read any file from disk before editing it; do not patch from memory or stale snippets.

## Your task
Fix only the outstanding issues from the previous attempt for story #{story_id}.

Non-negotiable:
- Do not widen scope beyond the current story.
- Treat every bullet in .ralph/critic-feedback.md as a checklist item to resolve.
- If the critic says a required file is missing, create it.
- If the critic says verification is missing, add and run the minimum meaningful verification.
- For non-documentation stories, a README-only or docs-only change is incomplete.
- If the required existing codebase or file is missing, record the blocker in .ralph/errors.log and .ralph/guardrails.md and stop without claiming success.
- Keep edits grounded in the exact text you just read, and prefer the smallest precise fix that closes the critic gap.
- If you launch or delegate background work, report it as launched/running until you have the real result.
- Do not peek at unfinished sub-work or invent a fork result just to close the loop.

## When finished
1. Make sure the build passes
2. Make sure tests are green
3. Update .ralph/progress.md - what you fixed
4. Commit with a message like "fix: address critic feedback for story #{story_id}"
