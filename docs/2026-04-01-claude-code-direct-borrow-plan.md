# Claude Code Deep Direct-Borrow Plan For FounderOS Autopilot

## Summary

This is the canonical deep donor-plan for the `claude-code` snapshot at:

- `/Users/martin/Downloads/claude-code-main.zip`
- upstream mirror reference: [instructkr/claude-code](https://github.com/instructkr/claude-code/tree/main)

This file supersedes the earlier shallow pass.

The review was done in two layers:

- direct local code inspection across `commands`, `tools`, `utils/plugins`, `utils/hooks`, `services/compact`, `services/tools`, `bridge`, and `entrypoints/sdk`
- five parallel subagent passes over:
  - tool/runtime/permissions/hooks
  - plugins/extensibility
  - command surface and GitHub flows
  - prompts / verification / subagenting / compaction
  - structured control protocol / bridge / cost telemetry

The main conclusion is stronger than before:

`claude-code` is not just a prompt donor. It is one of the best donor codebases we have found for turning `Autopilot` from a strong execution engine into a much more complete execution operating system.

What it does **not** replace:

- account rotation
- escalation chain
- execution plane
- multi-project dispatch
- approvals / control plane

What it **does** dramatically strengthen:

- executable tool runtime
- permission state machine
- hook and policy engine
- anti-hallucination verification
- subagent fork discipline
- plugin lifecycle and plugin-defined MCP
- product-grade onboarding and doctor flows
- GitHub bootstrap / review / ship loop
- structured headless control protocol
- session telemetry and compaction

## What Makes This Repo Exceptionally Valuable

Most donor repos give us one of these:

- orchestration ideas
- UI polish
- prompts
- plugin examples

`claude-code` gives us all of them at once, but the highest-value layer is this:

1. it has a **real runtime contract** for tools, permissions, hooks, and structured execution
2. it has a **real anti-hallucination layer** for verification, read-before-edit, and “don’t invent fork results”
3. it has a **real extensibility stack** for plugins, commands, agents, hooks, MCP, and later LSP
4. it has a **real product shell** for onboarding, doctor, GitHub setup, review, shipping, resume, and structured control I/O

That means the likely upside is not “the agent gets slightly smarter.”
The upside is closer to:

- much higher operator trust
- much cleaner extension surface
- much stronger autonomous verification
- much better headless / SDK / automation story
- much better OSS product feel

## Keep As Core Identity

Do not replace these with donor logic:

- `Autopilot` account pool and cooldown routing
- `Autopilot` escalation chain
- `Autopilot` execution-plane and approval concepts
- `FounderOS` idea -> brief -> execution thesis

The donor code should be grafted into these seams, not used to redefine the product.

## Layered Borrow Map

## P0 — Must Borrow First

These are the highest-value, lowest-regret direct ports.

| Priority | Layer | Donor file(s) | Exact donor pieces | Target in live Autopilot | Why it matters |
|---|---|---|---|---|---|
| P0 | Tool runtime | `src/Tool.ts` | `Tool`, `ToolDef`, `ToolResult`, `buildTool`, `toolMatchesName`, `findToolByName`, `ToolInputJSONSchema`, `ToolUseContext`, `ToolPermissionContext`, `getEmptyToolPermissionContext` | `autopilot/core/tool_contracts.py` (new), [capability_store.py](/Users/martin/Desktop/autopilot/autopilot/core/capability_store.py), [execution_plane.py](/Users/martin/Desktop/autopilot/autopilot/core/execution_plane.py) | This is the missing executable tool contract. Our current capability layer is metadata-heavy, not runtime-heavy. |
| P0 | Permissions | `src/types/permissions.ts`, `src/utils/permissions/PermissionUpdate.ts`, `src/utils/permissions/permissions.ts` | permission modes and decision unions, `applyPermissionUpdate`, `applyPermissionUpdates`, `persistPermissionUpdate`, `persistPermissionUpdates`, `checkRuleBasedPermissions`, `hasPermissionsToUseTool`, `createPermissionRequestMessage` | `autopilot/core/tool_permissions.py` (new), [approvals.py](/Users/martin/Desktop/autopilot/autopilot/core/approvals.py), [workspace_policy.py](/Users/martin/Desktop/autopilot/autopilot/core/workspace_policy.py) | Gives us a real allow/ask/deny state machine instead of scattered approval semantics. |
| P0 | Hooks | `src/types/hooks.ts`, `src/utils/hooks.ts`, `src/services/tools/toolHooks.ts` | `hookJSONOutputSchema`, hook event types, `executeHooks`, `executePreToolHooks`, `executePermissionRequestHooks`, `parseHookOutput`, `processHookJSONOutput`, `resolveHookPermissionDecision`, `runPreToolUseHooks` | `autopilot/core/hooks.py` (new), `autopilot/core/tool_hooks.py` (new), [execution_plane.py](/Users/martin/Desktop/autopilot/autopilot/core/execution_plane.py) | Creates a structured hook/policy engine that can intercept tool usage safely. |
| P0 | Tool execution lifecycle | `src/services/tools/toolExecution.ts` | `runToolUse` flow, permission-check -> pre-hooks -> execute -> post-hooks -> denial/failure handling, result envelopes, progress events | `autopilot/core/tool_runner.py` (new), [execution_plane.py](/Users/martin/Desktop/autopilot/autopilot/core/execution_plane.py) | This is one of the best runtime donors in the whole snapshot. |
| P0 | Verification / anti-hallucination | `src/tools/AgentTool/built-in/verificationAgent.ts` | `VERIFICATION_SYSTEM_PROMPT`, adversarial probe requirements, command/output evidence format, terminal `VERDICT: PASS|FAIL|PARTIAL` contract | [critic.py](/Users/martin/Desktop/autopilot/autopilot/core/critic.py), verifier layer, completion gates | One of the strongest anti-fake-completion donors in the repo. |
| P0 | Read-before-edit discipline | `src/tools/FileEditTool/prompt.ts` | `getPreReadInstruction()`, edit-fails-unless-read semantics, exact replacement discipline | worker prompts, future exact-edit tool, coding-agent guardrails | Prevents blind edits and cuts a lot of low-quality file mutations. |
| P0 | Subagent fork safety | `src/tools/AgentTool/prompt.ts`, `src/tools/AgentTool/forkSubagent.ts`, `src/tools/AgentTool/AgentTool.tsx` | fork semantics, `FORK_AGENT`, `buildForkedMessages()`, `FORK_PLACEHOLDER_RESULT`, “Don’t peek”, “Don’t race” rules | coordinator prompts, subtask launcher, background task notification flow | Strong donor for multi-agent autonomy without fabricated intermediate results. |
| P0 | Plugin loader core | `src/utils/plugins/pluginLoader.ts`, `src/utils/plugins/pluginDirectories.ts`, `src/utils/plugins/pluginIdentifier.ts`, `src/utils/plugins/schemas.ts` | `loadPluginManifest`, `createPluginFromPath`, `loadAllPlugins`, `clearPluginCache`, `getPluginsDirectory`, `getPluginDataDir`, `parsePluginIdentifier`, `buildPluginId`, `PluginManifestSchema` | [plugins.py](/Users/martin/Desktop/autopilot/autopilot/core/plugins.py), [capability_store.py](/Users/martin/Desktop/autopilot/autopilot/core/capability_store.py), `autopilot/core/plugin_loader.py` (new), `autopilot/core/plugin_models.py` (new) | Upgrades our minimal registry into a real plugin discovery and validation system. |
| P0 | Plugin config and substitution | `src/utils/plugins/pluginOptionsStorage.ts`, `src/utils/plugins/mcpbHandler.ts` | `getPluginStorageId`, `loadPluginOptions`, `savePluginOptions`, `getUnconfiguredOptions`, `substitutePluginVariables`, `substituteUserConfigVariables`, `substituteUserConfigInContent`, `validateUserConfig` | [config.py](/Users/martin/Desktop/autopilot/autopilot/core/config.py), [capabilities.py](/Users/martin/Desktop/autopilot/autopilot/api/routes/capabilities.py), [settings-capabilities.tsx](/Users/martin/Desktop/autopilot/dashboard/components/settings-capabilities.tsx), `autopilot/core/plugin_storage.py` (new) | Makes plugins configurable by users without editing core code. |
| P0 | Plugin commands and skills | `src/utils/plugins/loadPluginCommands.ts`, `src/utils/plugins/walkPluginMarkdown.ts` | `getPluginCommands`, `getPluginSkills`, `clearPluginCommandCache`, `clearPluginSkillsCache`, markdown command/skill discovery | [capability_store.py](/Users/martin/Desktop/autopilot/autopilot/core/capability_store.py), [intake.py](/Users/martin/Desktop/autopilot/autopilot/core/intake.py), [execution_plane.py](/Users/martin/Desktop/autopilot/autopilot/core/execution_plane.py), `autopilot/core/plugin_commands.py` (new) | Gives us real extensibility for commands and reusable skills. |
| P0 | Plugin-defined MCP | `src/utils/plugins/mcpPluginIntegration.ts` | `loadPluginMcpServers`, `getUnconfiguredChannels`, `addPluginScopeToServers`, `extractMcpServersFromPlugins`, `resolvePluginMcpEnvironment`, `getPluginMcpServers` | [capability_store.py](/Users/martin/Desktop/autopilot/autopilot/core/capability_store.py), [capabilities.py](/Users/martin/Desktop/autopilot/autopilot/api/routes/capabilities.py), [settings-capabilities.tsx](/Users/martin/Desktop/autopilot/dashboard/components/settings-capabilities.tsx), `autopilot/core/plugin_mcp.py` (new) | Turns MCP integration into a plugin-powered surface instead of a hand-curated list. |
| P0 | Cost telemetry | `src/cost-tracker.ts`, `src/commands/cost/cost.ts` | `getStoredSessionCosts`, `restoreCostStateForSession`, `saveCurrentSessionCosts`, `formatTotalCost`, `addToTotalSessionCost`, `call` | [cost_accounting.py](/Users/martin/Desktop/autopilot/autopilot/core/cost_accounting.py), [run.py](/Users/martin/Desktop/autopilot/autopilot/cli/run.py), `autopilot/cli/cost.py` (new), [runtime_budgets.py](/Users/martin/Desktop/autopilot/autopilot/core/runtime_budgets.py) | Gives a persistent session-usage layer, not just runtime budgets. |
| P0 | GitHub bootstrap | `src/commands/install-github-app/install-github-app.tsx`, `src/commands/install-github-app/setupGitHubActions.ts`, `src/constants/github-app.ts` | installer state machine, `createWorkflowFile`, `setupGitHubActions`, workflow templates, compare URL generation | [execution_plane.py](/Users/martin/Desktop/autopilot/autopilot/core/execution_plane.py), [execution_plane.py](/Users/martin/Desktop/autopilot/autopilot/api/routes/execution_plane.py), [page.tsx](/Users/martin/Desktop/autopilot/dashboard/app/control-plane/page.tsx), `autopilot/core/github_bootstrap.py` (new), `autopilot/cli/github.py` (new) | This is the fastest path to a polished GitHub connect-and-install flow. |
| P0 | Ship / PR creation | `src/commands/commit-push-pr.ts`, `src/utils/promptShellExecution.ts`, `src/utils/git.ts` | `ALLOWED_TOOLS`, `getPromptContent`, `getPromptForCommand`, `executeShellCommandsInPrompt`, `getDefaultBranch`, `getGithubRepo` | [execution_plane.py](/Users/martin/Desktop/autopilot/autopilot/core/execution_plane.py), [worktree.py](/Users/martin/Desktop/autopilot/autopilot/core/worktree.py), [run.py](/Users/martin/Desktop/autopilot/autopilot/cli/run.py), `autopilot/core/github_ship.py` (new), `autopilot/cli/ship.py` (new) | Closes the branch -> commit -> push -> PR loop with real safety rails. |

## P1 — Strong Second Wave

These are high-value after the P0 slice lands.

| Priority | Layer | Donor file(s) | Exact donor pieces | Target in live Autopilot | Why it matters |
|---|---|---|---|---|---|
| P1 | Structured control I/O | `src/cli/structuredIO.ts`, `src/entrypoints/sdk/coreSchemas.ts`, `src/entrypoints/sdk/controlSchemas.ts` | `StructuredIO`, `pendingRequests`, `sendRequest`, `injectControlResponse`, `setUnexpectedResponseCallback`, `setOnControlRequestSent`, `setOnControlRequestResolved`, NDJSON framing, session result/event schemas, control request/response schemas | `autopilot/core/structured_io.py` (new), `autopilot/core/control_messages.py` (new), [headless.py](/Users/martin/Desktop/autopilot/autopilot/core/headless.py), [run.py](/Users/martin/Desktop/autopilot/autopilot/cli/run.py), [dashboard/lib/types.ts](/Users/martin/Desktop/autopilot/dashboard/lib/types.ts) | This is the most important donor for a real headless/SDK/control-plane runtime. |
| P1 | Bridge protocol helpers | `src/bridge/bridgeMessaging.ts` | `isSDKMessage`, `isSDKControlResponse`, `isSDKControlRequest`, `handleIngressMessage`, `handleServerControlRequest`, `makeResultMessage`, `BoundedUUIDSet`, `extractTitleText` | `autopilot/core/control_messages.py` (new), [api/sse.py](/Users/martin/Desktop/autopilot/autopilot/api/sse.py), [api/routes/events.py](/Users/martin/Desktop/autopilot/autopilot/api/routes/events.py), [dashboard/lib/sse.ts](/Users/martin/Desktop/autopilot/dashboard/lib/sse.ts) | Gives safe parsing, control ACKs, dedup, and cleaner SSE/remote-runtime semantics. |
| P1 | Review surface | `src/commands/review.ts`, `src/commands/review/reviewRemote.ts`, `src/commands/review/ultrareviewCommand.tsx` | local review prompt shape, local/cloud split, remote review entry flow | [critic.py](/Users/martin/Desktop/autopilot/autopilot/core/critic.py), [execution_plane.py](/Users/martin/Desktop/autopilot/autopilot/core/execution_plane.py), [control_plane_issues.py](/Users/martin/Desktop/autopilot/autopilot/core/control_plane_issues.py), `autopilot/core/github_review.py` (new), `autopilot/cli/review.py` (new) | Turns criticing into a product-grade PR review surface. |
| P1 | Onboarding | `src/commands/init.ts`, `src/projectOnboardingState.ts`, `src/commands/init-verifiers.ts` | phased `NEW_INIT_PROMPT`, repo survey, minimal interview, proposal preview, onboarding complete marker, verifier generation | [init_cmd.py](/Users/martin/Desktop/autopilot/autopilot/cli/init_cmd.py), [intake.py](/Users/martin/Desktop/autopilot/autopilot/core/intake.py), [loop_runner.py](/Users/martin/Desktop/autopilot/autopilot/core/loop_runner.py), `autopilot/core/onboarding.py` (new), `autopilot/core/init_verifiers.py` (new) | Makes `autopilot init` far more useful and far less shallow. |
| P1 | Plugin agents | `src/utils/plugins/loadPluginAgents.ts` | `loadPluginAgents`, `clearPluginAgentCache`, markdown-defined agent discovery, frontmatter for tools/skills/model/background/memory/isolation/maxTurns | [capability_store.py](/Users/martin/Desktop/autopilot/autopilot/core/capability_store.py), [execution_plane.py](/Users/martin/Desktop/autopilot/autopilot/core/execution_plane.py), [intake.py](/Users/martin/Desktop/autopilot/autopilot/core/intake.py), `autopilot/core/plugin_agents.py` (new) | Enables plugin-defined specialists without editing core agent catalogs. |
| P1 | Plugin hooks lifecycle | `src/utils/plugins/loadPluginHooks.ts` | `loadPluginHooks`, `clearPluginHookCache`, `pruneRemovedPluginHooks`, `setupPluginHookHotReload`, `getPluginAffectingSettingsSnapshot` | [execution_plane.py](/Users/martin/Desktop/autopilot/autopilot/core/execution_plane.py), [project_store.py](/Users/martin/Desktop/autopilot/autopilot/core/project_store.py), `autopilot/core/plugin_hooks.py` (new) | Gives atomic hook swaps, reload safety, and removal semantics. |
| P1 | Plugin install state | `src/utils/plugins/installedPluginsManager.ts`, `src/utils/plugins/pluginStartupCheck.ts` | `loadInstalledPluginsV2`, `addPluginInstallation`, `removePluginInstallation`, `isPluginInstalled`, `isPluginGloballyInstalled`, `checkEnabledPlugins`, `findMissingPlugins`, `installSelectedPlugins` | [plugins.py](/Users/martin/Desktop/autopilot/autopilot/core/plugins.py), [doctor.py](/Users/martin/Desktop/autopilot/autopilot/cli/doctor.py), [main.py](/Users/martin/Desktop/autopilot/autopilot/cli/main.py), `autopilot/core/plugin_state.py` (new), `autopilot/cli/plugins.py` (new) | Separates install vs enable and creates a real lifecycle surface. |
| P1 | Plugin policy | `src/utils/plugins/pluginBlocklist.ts`, `src/utils/plugins/pluginFlagging.ts`, `src/utils/plugins/pluginPolicy.ts` | delisted detection/uninstall, flagged-plugin persistence, `isPluginBlockedByPolicy` | [doctor.py](/Users/martin/Desktop/autopilot/autopilot/cli/doctor.py), [capabilities.py](/Users/martin/Desktop/autopilot/autopilot/api/routes/capabilities.py), [settings-capabilities.tsx](/Users/martin/Desktop/autopilot/dashboard/components/settings-capabilities.tsx), `autopilot/core/plugin_policy.py` (new) | Gives safety and risk visibility before the plugin ecosystem grows. |
| P1 | Plugin CLI/API surface | `src/cli/handlers/plugins.ts` | `pluginValidateHandler`, `pluginListHandler`, `pluginInstallHandler`, `pluginUninstallHandler`, `pluginEnableHandler`, `pluginDisableHandler`, `pluginUpdateHandler` | [main.py](/Users/martin/Desktop/autopilot/autopilot/cli/main.py), [capabilities.py](/Users/martin/Desktop/autopilot/autopilot/api/routes/capabilities.py), [api.ts](/Users/martin/Desktop/autopilot/dashboard/lib/api.ts), [settings-capabilities.tsx](/Users/martin/Desktop/autopilot/dashboard/components/settings-capabilities.tsx), `autopilot/cli/plugins.py` (new) | Gives a proper product surface for extensions. |
| P1 | Resume / repo identity | `src/commands/resume/resume.tsx`, `src/utils/githubRepoPathMapping.ts`, `src/utils/git.ts` | cross-project resume, same-repo worktree detection, clipboard handoff, `updateGithubRepoPathMapping`, `getKnownPathsForRepo`, `findCanonicalGitRoot`, `getGithubRepo` | [worktree.py](/Users/martin/Desktop/autopilot/autopilot/core/worktree.py), [execution_plane.py](/Users/martin/Desktop/autopilot/autopilot/core/execution_plane.py), `autopilot/core/repo_registry.py` (new) | Important for multi-worktree and multi-clone Founder workflows. |

## P2 — High-Value Later

These are still good, but they should not delay the P0/P1 core.

| Priority | Layer | Donor file(s) | Exact donor pieces | Target in live Autopilot | Why it matters |
|---|---|---|---|---|---|
| P2 | Doctor / diagnostics | `src/screens/Doctor.tsx`, `src/utils/doctorDiagnostic.ts`, `src/utils/doctorContextWarnings.ts`, `src/components/sandbox/SandboxDoctorSection.tsx`, `src/commands/doctor/doctor.tsx` | consolidated diagnostics aggregation, multiple-install detection, config warnings, context warnings, sandbox section, dismiss/confirm flow | [adapters.py](/Users/martin/Desktop/autopilot/autopilot/core/adapters.py), [execution_plane.py](/Users/martin/Desktop/autopilot/autopilot/core/execution_plane.py), [page.tsx](/Users/martin/Desktop/autopilot/dashboard/app/control-plane/page.tsx), `autopilot/core/doctor.py` (new), `autopilot/cli/doctor.py` | Strong donor for turning raw health probes into a product-grade doctor surface. |
| P2 | Plugin startup / reload | `src/utils/plugins/refresh.ts`, `src/utils/plugins/performStartupChecks.tsx`, `src/hooks/useManagePlugins.ts` | `refreshActivePlugins`, `performStartupChecks`, initial load flow, `needsRefresh`, flagged/delist notifications | [doctor.py](/Users/martin/Desktop/autopilot/autopilot/cli/doctor.py), [capabilities.py](/Users/martin/Desktop/autopilot/autopilot/api/routes/capabilities.py), [api/main.py](/Users/martin/Desktop/autopilot/autopilot/api/main.py), [settings-capabilities.tsx](/Users/martin/Desktop/autopilot/dashboard/components/settings-capabilities.tsx), `autopilot/core/plugin_startup.py` (new) | Gives safer boot and cleaner “reload to activate” semantics. |
| P2 | Session state / requires-action UX | `src/utils/sessionState.ts` | `SessionState`, `RequiresActionDetails`, `notifySessionStateChanged`, `SessionExternalMetadata` | `autopilot/core/structured_io.py`, [orchestrator_sessions.py](/Users/martin/Desktop/autopilot/autopilot/core/orchestrator_sessions.py), [execution_plane.py](/Users/martin/Desktop/autopilot/autopilot/core/execution_plane.py) | Clean donor for `idle | running | requires_action` and pending-action surfaces. |
| P2 | Plugin output styles and hints | `src/utils/plugins/loadPluginOutputStyles.ts`, `src/utils/plugins/hintRecommendation.ts` | output-style discovery, `maybeRecordPluginHint`, `resolvePluginHint`, `markHintPluginShown`, `disableHintRecommendations` | [settings-capabilities.tsx](/Users/martin/Desktop/autopilot/dashboard/components/settings-capabilities.tsx), [live.py](/Users/martin/Desktop/autopilot/autopilot/cli/live.py), `autopilot/core/plugin_output_styles.py` (new) | Product polish once plugin basics exist. |
| P2 | Skill improvement | `src/utils/hooks/skillImprovement.ts` | `createSkillImprovementHook`, `initSkillImprovement`, `applySkillImprovement` | project skills system, dogfooding workflows, future memory/skills subsystem | Great donor for self-improving team workflows, but not first. |
| P2 | Plugin LSP | `src/utils/plugins/lspPluginIntegration.ts` | `loadPluginLspServers`, `resolvePluginLspEnvironment`, `addPluginScopeToLspServers`, `getPluginLspServers`, `extractLspServersFromPlugins` | [capability_store.py](/Users/martin/Desktop/autopilot/autopilot/core/capability_store.py), [dashboard/lib/types.ts](/Users/martin/Desktop/autopilot/dashboard/lib/types.ts), `autopilot/core/plugin_lsp.py` (new) | Valuable only once we have a serious IDE/LSP surface. |
| P2 | Compaction core | `src/commands/compact/compact.ts`, `src/services/compact/compact.ts`, `src/services/compact/sessionMemoryCompact.ts`, `src/services/compact/microCompact.ts`, `src/services/compact/prompt.ts` | `trySessionMemoryCompaction`, `calculateMessagesToKeepIndex`, `adjustIndexToPreserveAPIInvariants`, `annotateBoundaryWithPreservedSegment`, `createPostCompactFileAttachments`, `createPlanAttachmentIfNeeded`, `createSkillAttachmentIfNeeded`, `createPlanModeAttachmentIfNeeded`, `createAsyncAgentAttachmentsIfNeeded`, `cachedMicrocompactPath`, `evaluateTimeBasedTrigger`, `NO_TOOLS_PREAMBLE`, `createCompactCanUseTool` | long-session founder/operator sessions, future Quorum memory layer, later execution-session pressure manager | This is one of the best long-context donors, but it is still a second-wave port. |
| P2 | Background async agents | `src/tools/AgentTool/runAgent.ts`, `src/tools/AgentTool/resumeAgent.ts`, `src/tools/AgentTool/agentToolUtils.ts` | resumable async lifecycle, notification-on-complete, cleanup discipline, “do not poll” pattern | future task manager and background task subsystem | High value after the runtime contract is solid. |

## P3 — Valuable But Deferred

| Priority | Layer | Donor file(s) | Exact donor pieces | Why deferred |
|---|---|---|---|---|
| P3 | Plugin marketplace | `src/utils/plugins/marketplaceManager.ts`, `src/utils/plugins/officialMarketplace.ts`, `src/utils/plugins/marketplaceHelpers.ts`, `src/utils/plugins/parseMarketplaceInput.ts` | marketplace fetch/install/update semantics | Ecosystem-scale machinery, not first-wave FounderOS value |
| P3 | Plugin auto-update / cache | `src/utils/plugins/headlessPluginInstall.ts`, `src/utils/plugins/pluginAutoupdate.ts`, `src/utils/plugins/pluginVersioning.ts`, `src/utils/plugins/zipCache.ts` | update/cache/versioning/install flows | Mature only after plugin core is proven |
| P3 | Hosted-bridge blueprint only | `src/bridge/remoteBridgeCore.ts` | remote session / hosted bridge transport ideas | Too Anthropic-specific for immediate direct port |
| P3 | JWT refresh | `src/bridge/jwtUtils.ts` | `decodeJwtPayload`, `decodeJwtExpiry`, `createTokenRefreshScheduler` | Useful later if FounderOS adds hosted worker auth |

## Prompt Donors Worth Taking

These are not just “nice prompts.” Some of them directly improve reliability.

| Priority | Donor file | What to borrow | Target in our system | Why it matters |
|---|---|---|---|---|
| P0 | `src/tools/BashTool/prompt.ts` | git safety rules, commit/PR discipline, background command guidance, sandbox wording, shell safety | worker prompts, retry prompts, ship/review flows | One of the strongest prompt donors in the codebase |
| P0 | `src/tools/FileEditTool/prompt.ts` | read-before-edit rule, minimal unique context, exact string replacement discipline | coding-agent prompts, future edit tool layer | Reduces sloppy edits dramatically |
| P0 | `src/tools/AgentTool/prompt.ts` | fork vs fresh-agent guidance, “Don’t peek”, “Don’t race”, better delegation briefing | planner/coordinator prompts, subtask launcher | Very strong donor for multi-agent correctness |
| P0 | `src/tools/AgentTool/built-in/verificationAgent.ts` | adversarial verification prompt and evidence formatting | verifier agent, completion gate | High-value anti-hallucination donor |
| P1 | `src/tools/BriefTool/prompt.ts` | `ack -> work -> result` messaging discipline, `status: normal|proactive` | notifier summaries, intake UX, operator messaging | Makes autonomous work much more legible |
| P1 | `src/tools/AskUserQuestionTool/prompt.ts` | artifact previews, recommended options, clean clarification UX | onboarding interviews, approvals, guided choices | Strong donor for higher-signal question flows |
| P1 | `src/tools/EnterPlanModeTool/prompt.ts` | when to plan vs when to execute directly | intake / planner policy | Useful once interactive planning grows |

## Things We Explicitly Should Not Port As Core

- `src/bridge/remoteBridgeCore.ts`
  - too tied to Anthropic hosted sessions
  - not useful for our immediate moat
- frontend shell as donor foundation
  - our dashboard already exists
  - frontend is not the main gap right now
- Anthropic-specific billing, overage, subscriber, undercover, and hosted review policies
  - copy the mechanics, not their business logic

## What Changes Most If We Actually Implement This

If we do the full P0/P1 program, the product changes meaningfully:

- `Autopilot` stops being only an orchestrator and becomes much more of a real execution OS
- tool execution becomes safer and more inspectable
- autonomous work becomes less fake because verification and subagent semantics get stricter
- pluginability becomes real instead of aspirational
- GitHub delivery gets much smoother
- headless/runtime control gets a durable machine-readable protocol

This is a big productization win, not just polish.

## Recommended Implementation Order

1. `tool runtime + permissions + hooks + tool runner`
2. `verification prompt + read-before-edit + fork safety`
3. `plugin loader + plugin config + plugin commands + plugin MCP`
4. `cost telemetry + autopilot cost`
5. `github bootstrap + ship + review`
6. `structured IO + control messages + requires_action state`
7. `doctor + plugin startup/reload`
8. `onboarding + init-verifiers`
9. `resume/repo registry`
10. `compaction + skill improvement + plugin hints`

## Primary Landing Zones In The Live Repo

Core runtime:

- [capability_store.py](/Users/martin/Desktop/autopilot/autopilot/core/capability_store.py)
- [execution_plane.py](/Users/martin/Desktop/autopilot/autopilot/core/execution_plane.py)
- [approvals.py](/Users/martin/Desktop/autopilot/autopilot/core/approvals.py)
- [workspace_policy.py](/Users/martin/Desktop/autopilot/autopilot/core/workspace_policy.py)
- [plugins.py](/Users/martin/Desktop/autopilot/autopilot/core/plugins.py)
- [critic.py](/Users/martin/Desktop/autopilot/autopilot/core/critic.py)
- [cost_accounting.py](/Users/martin/Desktop/autopilot/autopilot/core/cost_accounting.py)
- [runtime_budgets.py](/Users/martin/Desktop/autopilot/autopilot/core/runtime_budgets.py)
- [worktree.py](/Users/martin/Desktop/autopilot/autopilot/core/worktree.py)
- [orchestrator_sessions.py](/Users/martin/Desktop/autopilot/autopilot/core/orchestrator_sessions.py)
- [intake.py](/Users/martin/Desktop/autopilot/autopilot/core/intake.py)
- [loop_runner.py](/Users/martin/Desktop/autopilot/autopilot/core/loop_runner.py)

CLI / API:

- [run.py](/Users/martin/Desktop/autopilot/autopilot/cli/run.py)
- [init_cmd.py](/Users/martin/Desktop/autopilot/autopilot/cli/init_cmd.py)
- [doctor.py](/Users/martin/Desktop/autopilot/autopilot/cli/doctor.py)
- [execution_plane.py](/Users/martin/Desktop/autopilot/autopilot/api/routes/execution_plane.py)
- [capabilities.py](/Users/martin/Desktop/autopilot/autopilot/api/routes/capabilities.py)
- [events.py](/Users/martin/Desktop/autopilot/autopilot/api/routes/events.py)
- [sse.py](/Users/martin/Desktop/autopilot/autopilot/api/sse.py)

Dashboard:

- [page.tsx](/Users/martin/Desktop/autopilot/dashboard/app/control-plane/page.tsx)
- [settings-capabilities.tsx](/Users/martin/Desktop/autopilot/dashboard/components/settings-capabilities.tsx)
- [api.ts](/Users/martin/Desktop/autopilot/dashboard/lib/api.ts)
- [types.ts](/Users/martin/Desktop/autopilot/dashboard/lib/types.ts)
- [sse.ts](/Users/martin/Desktop/autopilot/dashboard/lib/sse.ts)

Likely new files:

- `autopilot/core/tool_contracts.py`
- `autopilot/core/tool_permissions.py`
- `autopilot/core/tool_hooks.py`
- `autopilot/core/tool_runner.py`
- `autopilot/core/plugin_loader.py`
- `autopilot/core/plugin_models.py`
- `autopilot/core/plugin_storage.py`
- `autopilot/core/plugin_commands.py`
- `autopilot/core/plugin_agents.py`
- `autopilot/core/plugin_hooks.py`
- `autopilot/core/plugin_mcp.py`
- `autopilot/core/plugin_policy.py`
- `autopilot/core/plugin_state.py`
- `autopilot/core/plugin_startup.py`
- `autopilot/core/control_messages.py`
- `autopilot/core/structured_io.py`
- `autopilot/core/github_bootstrap.py`
- `autopilot/core/github_ship.py`
- `autopilot/core/github_review.py`
- `autopilot/core/onboarding.py`
- `autopilot/core/init_verifiers.py`
- `autopilot/core/repo_registry.py`
- `autopilot/cli/cost.py`
- `autopilot/cli/review.py`
- `autopilot/cli/ship.py`
- `autopilot/cli/github.py`
- `autopilot/cli/plugins.py`

## Test Plan

- tool runtime:
  - schema validation
  - permission evaluation
  - hook interception
  - destructive tool path
- verification:
  - PASS / FAIL / PARTIAL parsing
  - evidence-required completion gate
  - adversarial-probe presence
- subagenting:
  - fork result notification
  - no mid-flight fabricated result
  - async/resume path
- plugin system:
  - manifest validation
  - command/skill/agent discovery
  - MCP loading
  - plugin options and substitution
  - flagged/delisted handling
  - startup and reload semantics
- GitHub:
  - workflow install
  - secret creation
  - branch/PR flow
  - review flow
- structured I/O:
  - request/response correlation
  - duplicate response handling
  - `requires_action` state
  - NDJSON framing
- doctor:
  - multi-install detection
  - probe aggregation
  - plugin/runtime/tool warnings
- compaction later:
  - session-memory boundary preservation
  - microcompact
  - attachment rehydration

## Final Verdict

`claude-code` is now clearly in the top tier of donor repos for `FounderOS Autopilot`.

Not because it replaces our orchestration core.
Because it supplies the strongest missing product layers around that core:

- runtime contracts
- trust and anti-hallucination
- extension lifecycle
- command and GitHub surface
- structured control protocol

This file is now deep enough that the next agent should stop searching and start implementing.

## Tomography Appendix

This appendix expands the donor map from a prioritized plan into a slice-by-slice
backend inventory. It is intentionally repetitive: the point is to make it hard
to miss valuable donor code when implementation starts.

The appendix follows five backend slices:

1. permission and runtime safety
2. agent autonomy, verification, and compaction
3. operator flows and repository onboarding
4. live runtime protocol and headless control
5. plugin platform and extension lifecycle

The UI shell is deliberately excluded unless a file carries backend state
transitions that matter for correctness.

### Slice 1: Permission And Runtime Safety

This is the strongest donor seam for turning Autopilot from “approval-aware” into
“permission-engineered.”

| File | What it contributes | Port mode | Hidden dependencies | Land in Autopilot |
|---|---|---|---|---|
| `src/Tool.ts` | executable `Tool` contract, `ToolUseContext`, `ToolPermissionContext`, alias matching, runtime execution traits such as `isConcurrencySafe`, `interruptBehavior`, `preparePermissionMatcher`, `toAutoClassifierInput` | adapt | app state shape, message model, MCP tool naming | `autopilot/core/tool_contracts.py`, [execution_plane.py](/Users/martin/Desktop/autopilot/autopilot/core/execution_plane.py), [capability_store.py](/Users/martin/Desktop/autopilot/autopilot/core/capability_store.py) |
| `src/types/permissions.ts` | explicit decision model for `allow`, `ask`, `deny`, permission sources, classifier pending checks, explanation types, headless/coordinator flow | copy semantics closely | none major; mostly domain modeling | `autopilot/core/permission_models.py`, [approvals.py](/Users/martin/Desktop/autopilot/autopilot/core/approvals.py), [run_trace.py](/Users/martin/Desktop/autopilot/autopilot/core/run_trace.py) |
| `src/utils/permissions/permissions.ts` | rule evaluation spine, `checkRuleBasedPermissions`, `hasPermissionsToUseTool`, ask/deny matching, denial escalation, source-aware decision reasons | adapt closely | per-tool permission callbacks, denial tracker, hook runtime, classifier runtime | `autopilot/core/command_permissions.py`, [execution_plane.py](/Users/martin/Desktop/autopilot/autopilot/core/execution_plane.py) |
| `src/utils/permissions/filesystem.ts` | real path-aware permission engine, symlink-safe scope matching, internal-path protection, read/write suggestion generation, suspicious-path rejection | adapt closely | resolved-path helpers, Autopilot internal dirs, rule pattern normalization | `autopilot/core/path_permissions.py`, [workspace_policy.py](/Users/martin/Desktop/autopilot/autopilot/core/workspace_policy.py) |
| `src/utils/permissions/pathValidation.ts` | shell-facing path validation before the shell expands or mutates anything, dangerous removal blockers, tilde/env/path ambiguity blocking | copy semantics closely | sandbox allowlist if introduced, resolved path helpers | `autopilot/core/path_permissions.py`, command execution gate in [execution_plane.py](/Users/martin/Desktop/autopilot/autopilot/core/execution_plane.py) |
| `src/utils/permissions/permissionSetup.ts` | safe transitions into auto/plan mode, stripping dangerous rules in auto mode, restoring them on exit, transform-style gate verification | adapt closely | dynamic settings, mode state, rule persistence | `autopilot/core/command_permissions.py`, [runtime_control.py](/Users/martin/Desktop/autopilot/autopilot/core/runtime_control.py) |
| `src/utils/permissions/PermissionUpdate.ts` | explicit permission mutation state machine: add, replace, remove, persist, suggest | adapt | persistent config format | `autopilot/core/command_permissions.py`, [approvals.py](/Users/martin/Desktop/autopilot/autopilot/core/approvals.py) |
| `src/utils/permissions/permissionsLoader.ts` | multi-source rule loading and synchronization | adapt | config hierarchy | `autopilot/core/command_permissions.py`, config layer |
| `src/utils/permissions/permissionRuleParser.ts` | practical rule grammar and string normalization | copy semantics | rule naming conventions | `autopilot/core/command_permissions.py` |
| `src/utils/permissions/shellRuleMatching.ts` | fine-grained shell prefix matching and exact/prefix suggestion logic | copy semantics | shell wrapper normalization | `autopilot/core/command_permissions.py` |
| `src/utils/permissions/dangerousPatterns.ts` | curated dangerous shell/code-exec patterns | adapt | platform differences | `autopilot/core/command_permissions.py` |
| `src/utils/permissions/denialTracking.ts` | denial breaker / repeated-denial fallback to prompting | copy concept closely | storage for denial history | `autopilot/core/command_permissions.py`, [runtime_budgets.py](/Users/martin/Desktop/autopilot/autopilot/core/runtime_budgets.py) |
| `src/utils/permissions/yoloClassifier.ts` | transcript shaping for auto-mode classifier, only user text + tool-use projection, fails closed, prompt-too-long fallback | adapt | model runtime, tool registry, prompt source | `autopilot/core/action_classifier.py`, [execution_plane.py](/Users/martin/Desktop/autopilot/autopilot/core/execution_plane.py) |
| `src/types/hooks.ts` | structured hook protocol, blocking, continuation control, updated input, permission outcomes | copy semantics | hook event registry | `autopilot/core/hook_runtime.py` |
| `src/utils/hooks.ts` | hook discovery, trust gating, matching, dedup, timeouts, parallel execution, worktree/file/config/session hooks | adapt | trust model, subprocess/http hook runner, event registry | `autopilot/core/hook_runtime.py`, [worktree.py](/Users/martin/Desktop/autopilot/autopilot/core/worktree.py) |
| `src/services/tools/toolHooks.ts` | `resolveHookPermissionDecision`, pre/post hook flow, invariant that hook allow does not silently bypass deny/ask | copy/adapt with high fidelity | hook runtime, permission runtime | `autopilot/core/tool_hooks.py` |
| `src/services/tools/toolExecution.ts` | full execution spine: validate input, pre-hooks, permission resolution, execute, classify errors, post-success/failure hooks, progress/event envelopes | adapt closely | telemetry stripped down, MCP metadata, message envelopes | `autopilot/core/tool_runner.py` |
| `src/services/tools/StreamingToolExecutor.ts` | concurrency-safe orchestration and streaming result handling | adapt later | tool partitioning model | `autopilot/core/tool_runner.py` |
| `src/hooks/toolPermission/PermissionContext.ts` | resolve-once approval context, race-safe user/hook/classifier resolution, abort-aware settlement | copy semantics closely | approval queue/router, classifier callbacks, hook runtime | `autopilot/core/approval_runtime.py`, [approvals.py](/Users/martin/Desktop/autopilot/autopilot/core/approvals.py) |

#### Underemphasized donor inside this slice

The single most underemphasized file from the earlier pass is:

- `src/tools/BashTool/bashSecurity.ts`

This file is not “just shell validation.” It is a large catalog of ways an
autonomous agent can accidentally or adversarially turn a seemingly simple shell
command into something dangerous or misleading.

High-value sub-donors inside the Bash stack:

| File | Why it matters |
|---|---|
| `src/tools/BashTool/bashSecurity.ts` | catches command substitution tricks, heredoc abuse, token injection, newline tricks, unicode whitespace, zsh-specific dangers, obfuscated flags |
| `src/tools/BashTool/bashPermissions.ts` | wraps shell parsing into a practical permission engine, including speculative classifier checks and safe rule suggestions |
| `src/tools/BashTool/readOnlyValidation.ts` | distinguishes truly read-only shell from fake-safe shell, including git hook abuse and git-internal path tricks |
| `src/tools/BashTool/pathValidation.ts` | path extraction and path-level safety ordering for shell commands |

For Autopilot this matters because one of the fastest ways to improve autonomy
is not “better prompts,” but “better shell truth.” If the shell layer can say:

- this is definitely safe
- this is ambiguous, ask
- this is unsafe, deny
- this returned non-zero because there were no matches, not because the task failed

then the worker loop stops oscillating between false positives and risky
self-approval.

### Slice 2: Agent Autonomy, Verification, And Compaction

This slice contains the strongest donors for “finish the task honestly” rather
than “say plausible things while half-finished.”

| File | What it contributes | Port mode | Hidden dependencies | Land in Autopilot |
|---|---|---|---|---|
| `src/tools/AgentTool/prompt.ts` | fork-vs-fresh-agent law, “Don’t peek,” “Don’t race,” directive-style prompts, no fabricated intermediate results | copy prompt law closely | completion notifications, async task registry | worker/coordinator prompts, [loop_runner.py](/Users/martin/Desktop/autopilot/autopilot/core/loop_runner.py) |
| `src/tools/AgentTool/built-in/verificationAgent.ts` | explicit verifier role, anti-lazy verification rules, evidence format, adversarial probes, terminal `VERDICT` contract | copy prompt structure closely | read-only verifier execution, temp-script allowance | [critic.py](/Users/martin/Desktop/autopilot/autopilot/core/critic.py), [critic-prompt.md](/Users/martin/Desktop/autopilot/autopilot/templates/critic-prompt.md), new verifier template |
| `src/tools/FileEditTool/prompt.ts` | read-before-write law, exact replacement discipline, no blind edits | copy policy | read cache / exact edit helper | worker prompts, future edit tool |
| `src/tools/FileEditTool/FileEditTool.ts` | stale-write prevention, reject ambiguous old strings, preserve exactness | adapt | read snapshots, file-history context | future exact-edit helper under `autopilot/core` |
| `src/tools/AgentTool/forkSubagent.ts` | stable fork identity, cached prefix discipline, fork result placeholder handling | adapt | task registry, async result handling | new subagent launcher under `autopilot/core` |
| `src/tools/AgentTool/agentToolUtils.ts` | output-file handling, progress extraction, handoff classifier hooks, task metadata helpers | adapt | task outputs, notifications, transcripts | [run_trace.py](/Users/martin/Desktop/autopilot/autopilot/core/run_trace.py), runtime task helpers |
| `src/tools/AgentTool/runAgent.ts` | background lifecycle, transcript writing, resume hooks, per-agent metadata | adapt closely | transcript store, task registry, worktrees | [orchestrator_sessions.py](/Users/martin/Desktop/autopilot/autopilot/core/orchestrator_sessions.py), [project_store.py](/Users/martin/Desktop/autopilot/autopilot/core/project_store.py) |
| `src/tools/AgentTool/resumeAgent.ts` | reconstructing/resuming async agents from transcript and metadata | adapt closely | sidecar storage, transcript loader | resume layer in [orchestrator_sessions.py](/Users/martin/Desktop/autopilot/autopilot/core/orchestrator_sessions.py) |
| `src/tasks/LocalAgentTask/LocalAgentTask.tsx` | launched-now/complete-later lifecycle, progress tracker, background promotion, notification on completion | adapt closely | task registry, progress events, abort handoff | runtime-agent subsystem in `autopilot/core` |
| `src/tasks/RemoteAgentTask/RemoteAgentTask.tsx` | remote-review / remote-agent lifecycle, polling, persisted task state | adapt later unless remote execution becomes immediate | remote session API, polling loop | `autopilot/core/remote_sessions.py` |
| `src/utils/task/TaskOutput.ts` and `src/utils/task/diskOutput.ts` | durable output-file contract for async tasks | copy/adapt | GC policy, output directories | task-output helper in `autopilot/core` |
| `src/services/compact/compact.ts` | compact boundary preservation, rehydrating plans/skills/async agents after compaction | adapt | task registry, session memory, attachments | session compaction helper under `autopilot/core` |
| `src/services/compact/sessionMemoryCompact.ts` | session memory preservation | adapt | session-memory files | same |
| `src/services/compact/microCompact.ts` | cheap pre-API compaction | adapt later | prompt builder integration | later context manager |
| `src/services/compact/prompt.ts` | compact rules that preserve active work, not just summarize it away | copy policy | compact runtime | compaction prompts |

#### Strongest anti-hallucination mechanisms in this slice

The donor repo’s most valuable autonomy mechanisms are not subtle:

1. subagents are not allowed to “peek” or invent results mid-flight
2. verifier agents must produce command evidence, not prose confidence
3. edit tools are only trusted after a read and exact replacement match
4. background tasks produce durable outputs and notifications instead of forcing
   the parent to guess
5. compaction preserves active work and task identity instead of flattening
   everything into generic summaries

These five rules map directly onto Autopilot’s current weak spots:

- fabricated status updates
- overly soft criticing
- “probably fixed” edits
- long-run context drift
- poor recoverability after interrupted worker sessions

### Slice 3: Operator Flows, Onboarding, And Repo Semantics

This slice is less about autonomy and more about operator-grade backend product
flows: repo setup, review, GitHub wiring, doctor, context visibility, and
resumability.

| File | What it contributes | Port mode | Hidden dependencies | Land in Autopilot |
|---|---|---|---|---|
| `src/commands/init.ts` | staged onboarding interview, repo survey, proposal-before-apply, shared-vs-personal instructions | adapt flow | question tool, instruction store, repo scanning | [init_cmd.py](/Users/martin/Desktop/autopilot/autopilot/cli/init_cmd.py), `autopilot/core/onboarding.py` |
| `src/projectOnboardingState.ts` | onboarding-complete marker and state transitions | copy concept | config persistence | onboarding state file |
| `src/commands/init-verifiers.ts` | verifier bootstrap by subproject type, auth/tool detection, acceptance-check setup | adapt concept | skill system, tool detection | `autopilot/core/verification_bootstrap.py` |
| `src/utils/claudemd.ts` | instruction layering, memory file discovery, conditional rule loading, path-scoped instructions | adapt closely | frontmatter parser, include limits, cache invalidation | `autopilot/core/instructions_memory.py` |
| `src/utils/analyzeContext.ts` | context accounting by category, tool/memory/agent/skill/system prompt contributions | adapt | prompt builder, token estimator | `autopilot/core/context_visibility.py` |
| `src/commands/context/context-noninteractive.ts` | shared path for CLI + SDK context usage view based on the actual prompt view | adapt closely | microcompact and prompt-view transforms | CLI context command and API |
| `src/utils/doctorDiagnostic.ts` | deep config/runtime/plugin/path/memory diagnostics | adapt | config-source resolution, memory analyzer, permission linter | `autopilot/core/runtime_diagnostics.py`, [doctor.py](/Users/martin/Desktop/autopilot/autopilot/cli/doctor.py) |
| `src/utils/doctorContextWarnings.ts` | memory/context-specific warnings | adapt | context analyzer | same |
| `src/commands/review.ts` | local review command entrypoint | adapt | review prompt and repo state | `autopilot/cli/review.py` |
| `src/commands/review/reviewRemote.ts` | remote review lifecycle entrypoint | adapt heavily | remote sessions, quota/overage gates, storage | `autopilot/core/remote_sessions.py`, `autopilot/cli/review.py` |
| `src/commands/commit-push-pr.ts` | safe ship flow, one-shot branch->commit->push->PR policy | adapt flow | git/gh integration | `autopilot/core/shipping.py`, `autopilot/cli/ship.py` |
| `src/commands/install-github-app/install-github-app.tsx` | GitHub bootstrap wizard | adapt flow | gh auth, admin scopes, workflow templates | `autopilot/core/github_repo_setup.py`, `autopilot/cli/github_setup.py` |
| `src/commands/install-github-app/setupGitHubActions.ts` | create workflow file, branch/install/compare flow | adapt closely | gh CLI and repo permissions | same |
| `src/commands/resume/resume.tsx` | worktree-aware session browser, same-repo vs cross-project resume split | adapt closely | session history storage, worktree discovery | `autopilot/core/session_history.py`, `autopilot/cli/resume.py` |
| `src/utils/getWorktreePaths.ts` | worktree enumeration across same repo | copy/adapt | git helpers | [worktree.py](/Users/martin/Desktop/autopilot/autopilot/core/worktree.py) |
| `src/utils/crossProjectResume.ts` | `cd && resume` handoff for other project clones | adapt | clipboard or handoff UX | resume flow |

#### What is core backend value here

High-value backend donors:

- onboarding state machine
- instruction layering
- context analyzer
- doctor diagnostics
- worktree-aware resume
- GitHub repo bootstrap

Lower-value donors:

- literal prompt text in onboarding
- most UI wrappers around these flows
- product branding language

### Slice 4: Live Runtime Protocol, Headless Control, And Session Telemetry

This is the slice that most directly upgrades Autopilot’s control plane from
coarse events into a live runtime protocol.

| File | What it contributes | Port mode | Hidden dependencies | Land in Autopilot |
|---|---|---|---|---|
| `src/cli/structuredIO.ts` | correlated request/response control channel over stdin/stdout, pending request store, permission elicitation, cancellation | adapt closely | single-writer outbound queue, schema parser, child runtime | `autopilot/core/structured_io.py`, [headless.py](/Users/martin/Desktop/autopilot/autopilot/core/headless.py) |
| `src/entrypoints/sdk/coreSchemas.ts` | message/event/result schemas for runtime protocol | adapt | schema runtime, internal event model | `autopilot/core/control_messages.py` |
| `src/entrypoints/sdk/controlSchemas.ts` | control request/response schemas, `get_context_usage`, `can_use_tool`, model/permission updates | adapt closely | request correlation and runtime handlers | `autopilot/core/control_messages.py`, headless control plane |
| `src/utils/sessionState.ts` | explicit `idle | running | requires_action`, pending-action metadata, permission-mode state notifications | copy/adapt closely | single choke point for state changes | [orchestrator_sessions.py](/Users/martin/Desktop/autopilot/autopilot/core/orchestrator_sessions.py), [events.py](/Users/martin/Desktop/autopilot/autopilot/api/routes/events.py) |
| `src/bridge/bridgeMessaging.ts` | robust ingress parsing, dedup, explicit `control_response`, UUID rings | copy/adapt closely | stable event UUIDs and request ids | `autopilot/core/control_messages.py`, SSE/event layer |
| `src/bridge/flushGate.ts` | queue live writes during history replay/rebuild, then flush in order | copy concept closely | ordered event buffer | event replay / SSE reconnect layer |
| `src/bridge/replBridge.ts` and `src/bridge/replBridgeTransport.ts` | sequence/high-water replay semantics, ACK-based delivery | adapt concepts | stable sequence numbers, transport ack model | [events.py](/Users/martin/Desktop/autopilot/autopilot/api/routes/events.py), [dashboard/lib/sse.ts](/Users/martin/Desktop/autopilot/dashboard/lib/sse.ts) |
| `src/utils/sdkEventQueue.ts` | bounded event queue for task/session events | copy concept | internal event feed | event layer |
| `src/cost-tracker.ts` | session-resumable cost state and pretty summaries | adapt closely | provider usage capture and pricing data | [cost_accounting.py](/Users/martin/Desktop/autopilot/autopilot/core/cost_accounting.py) |
| `src/cli/transports/WorkerStateUploader.ts` | coalesced session-state uploader with merged pending patch and retry | adapt concept | patch semantics on storage side | session state sink in Autopilot |
| `src/bridge/sessionRunner.ts` | runtime child process runner with transcript capture and permission interception | adapt later | provider CLI runtime, transcript storage | headless runner |
| `src/bridge/bridgeApi.ts` | generic client hardening helpers such as safe ID validation and retry taxonomy | adapt only generic parts | remote runtime client | future remote execution |

#### Minimum transplant from this slice

If implementation bandwidth is tight, the minimum valuable transplant is:

1. request-id correlated control RPC
2. explicit `requires_action` session state with pending-action payload
3. deduped, resumable, sequence-aware event stream

That alone would materially upgrade Autopilot’s live control plane.

### Slice 5: Plugin Platform And Extension Lifecycle

This is the most structurally complete plugin donor we found. The critical idea
is that plugins are not just “a registry of things,” but a lifecycle with:

- declaration
- installation
- enablement
- activation
- refresh
- policy
- delisting

| File | What it contributes | Port mode | Hidden dependencies | Land in Autopilot |
|---|---|---|---|---|
| `src/utils/plugins/schemas.ts` | manifest schemas for commands, agents, MCP, LSP, hooks, skills, channels, output styles, installed state | adapt closely | plugin id normalization, config layering | `autopilot/core/plugin_manifest.py`, `plugin_types.py` |
| `src/types/plugin.ts` | loaded-plugin and plugin-error types | copy/adapt | none major | `autopilot/core/plugin_types.py` |
| `src/utils/plugins/pluginLoader.ts` | discovery, manifest load, source merge, cache discipline, enabled/disabled/error projection | adapt closely | cache dirs, marketplace data, policy layer | `autopilot/core/plugin_loader.py`, [plugins.py](/Users/martin/Desktop/autopilot/autopilot/core/plugins.py) |
| `src/utils/plugins/pluginIdentifier.ts` | scope-aware plugin IDs and parsing | copy semantics | none major | plugin id helper |
| `src/utils/plugins/pluginDirectories.ts` | standard plugin directory inference | copy/adapt | directory conventions | plugin loader |
| `src/utils/plugins/installedPluginsManager.ts` | install state ledger, migration, versioned installation persistence | adapt closely | install paths, scope model | `autopilot/core/plugin_installations.py` |
| `src/utils/plugins/pluginStartupCheck.ts` | compare enabled intent vs materialized installs | adapt | install ledger | `autopilot/core/plugin_startup.py` |
| `src/utils/plugins/dependencyResolver.ts` | dependency closure and demotion | copy/adapt closely | normalized plugin ids and scope rules | `autopilot/core/plugin_dependencies.py` |
| `src/utils/plugins/pluginOptionsStorage.ts` | plugin options, secret-safe config handling, missing-config detection | adapt closely | secure secret store | `autopilot/core/plugin_options.py`, `plugin_secrets.py` |
| `src/utils/plugins/mcpbHandler.ts` | MCP bundle ingestion and user-config substitution | adapt | MCP schema and options store | `autopilot/core/plugin_mcp.py` |
| `src/utils/plugins/loadPluginCommands.ts` | plugin-contributed commands and skills | adapt | markdown/frontmatter parser | `autopilot/core/plugin_commands.py`, `plugin_skillpacks.py` |
| `src/utils/plugins/loadPluginAgents.ts` | plugin-contributed agents/roles | adapt | agent file format | `autopilot/core/plugin_roles.py` |
| `src/utils/plugins/loadPluginHooks.ts` | hook registration, hot reload, cache clearing | adapt closely | hook runtime and settings snapshot | `autopilot/core/plugin_hooks.py` |
| `src/utils/plugins/mcpPluginIntegration.ts` | plugin-defined MCP connectors merged into runtime config | adapt aggressively | connector precedence, runtime reconnection | `autopilot/core/plugin_mcp.py`, [capability_store.py](/Users/martin/Desktop/autopilot/autopilot/core/capability_store.py) |
| `src/utils/plugins/lspPluginIntegration.ts` | plugin-defined LSP servers | adapt later | actual LSP host | `autopilot/core/plugin_lsp.py` |
| `src/utils/plugins/refresh.ts` | refresh/reload activation flow | adapt | cache invalidation and reconnect events | `autopilot/core/plugin_refresh.py` |
| `src/hooks/useManagePlugins.ts` | canonical initial-load and refresh mental model | reference for lifecycle semantics, not UI code | app state and notifications | used as behavioral spec |
| `src/utils/plugins/pluginPolicy.ts` | source and plugin blocking, managed-only policies | adapt closely | policy settings hierarchy | `autopilot/core/plugin_policy.py` |
| `src/utils/plugins/pluginBlocklist.ts` | delisted plugin detection and auto-uninstall | adapt | installed-state ledger | `autopilot/core/plugin_delisting.py` |
| `src/utils/plugins/pluginFlagging.ts` | flagged-plugin persistence and dismissal | adapt | operator notifications | `autopilot/core/plugin_flags.py` |
| `src/utils/plugins/performStartupChecks.tsx` | trust-gated startup reconciliation and background installation kickoff | adapt concept | trust model and background install worker | `autopilot/core/plugin_startup.py` |
| `src/services/plugins/PluginInstallationManager.ts` | background install/reconcile manager | adapt later | marketplace/install plane | `autopilot/core/plugin_background_tasks.py` |
| `src/utils/plugins/marketplaceManager.ts` | marketplace source model | adapt later | network/cache/policy | `autopilot/core/plugin_marketplaces.py` |
| `src/utils/plugins/reconciler.ts` | marketplace reconciliation | adapt later | marketplace cache | same |
| `src/cli/handlers/plugins.ts` | operator CLI lifecycle commands | adapt | plugin service layer | `autopilot/cli/plugins.py` |

#### Required vs optional parts of the plugin donor

Required for a real plugin platform:

- manifest and types
- loader
- install ledger
- dependency closure
- options/secrets
- activation/reload
- policy and delisting
- plugin-defined MCP

Optional or later:

- marketplace discovery
- autoupdate
- output styles
- LSP integration
- recommendation hints

### Cross-Slice Findings That Matter Most

Across all passes, the most important donor insights are:

1. autonomy quality is mostly a runtime problem, not a prompt problem
2. the best anti-hallucination gains come from:
   - verifier contract
   - fork no-peek/no-race rules
   - read-before-edit law
   - shell/permission engine
   - explicit `requires_action`
3. the plugin stack is valuable because it is lifecycle-complete, not because it
   has lots of plugin types
4. the runtime control plane donor is not the hosted Anthropic bridge itself,
   but the lower-level:
   - request correlation
   - pending-action metadata
   - resumable event streaming
   - coalesced session-state updates

### Revised “Most Valuable 15” Across The Whole Snapshot

If implementation starts tomorrow and we want the highest return donor bundle,
the best 15 backend donors are:

1. `src/Tool.ts`
2. `src/types/permissions.ts`
3. `src/utils/permissions/permissions.ts`
4. `src/utils/permissions/filesystem.ts`
5. `src/tools/BashTool/bashSecurity.ts`
6. `src/tools/BashTool/bashPermissions.ts`
7. `src/services/tools/toolExecution.ts`
8. `src/tools/AgentTool/built-in/verificationAgent.ts`
9. `src/tools/AgentTool/prompt.ts`
10. `src/tools/FileEditTool/prompt.ts`
11. `src/cli/structuredIO.ts`
12. `src/bridge/bridgeMessaging.ts`
13. `src/utils/sessionState.ts`
14. `src/utils/plugins/pluginLoader.ts`
15. `src/utils/plugins/mcpPluginIntegration.ts`

If we expand that to 25, the next ten are:

16. `src/utils/plugins/schemas.ts`
17. `src/utils/plugins/installedPluginsManager.ts`
18. `src/utils/plugins/dependencyResolver.ts`
19. `src/utils/plugins/loadPluginCommands.ts`
20. `src/utils/plugins/loadPluginHooks.ts`
21. `src/commands/init.ts`
22. `src/commands/install-github-app/setupGitHubActions.ts`
23. `src/commands/resume/resume.tsx`
24. `src/cost-tracker.ts`
25. `src/services/compact/compact.ts`

### Immediate Gap Statement Against The Live Autopilot Repo

After all current passes, the biggest donor gaps still missing in the live repo
are:

- no true executable tool contract
- no first-class permission decision model
- no path-accurate shell permission engine
- no verifier role with evidence contract
- no async task/output-file contract for subagents
- no explicit `requires_action` runtime state with structured details
- no resumable/deduped event stream
- no real plugin platform lifecycle

Those are the places where the donor repo is not just “nicer,” but materially
stronger than the current Autopilot baseline.
