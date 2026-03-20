# DEV Notes

This document tracks development notes for `agent-claw`, including PR references,
architecture decisions, testing strategy, and release-readiness checkpoints.

## Project Snapshot

- Name: `agent-claw`
- Language: Python
- Core runtime: ReAct-based execution flow
- Current direction:
  - use `skills` as capability packaging
  - use `tools` as executable actions
  - use `runtime` to drive the ReAct loop
  - use `agents` as the business-facing composition layer

## PR Log

Use this section to record each PR in a lightweight format.

### Current

- PR: 6
- Title: Agent Application Layer
- Branch: current working branch
- Status: in progress
- Summary:
  - added reusable `RuntimeAgent` and immutable `AgentRunConfig`
  - bound agent-owned skills alongside tools, with a repo-tracked `file-summary` skill
  - added `read_skill` so the runtime can load a skill on demand before using other tools
  - upgraded runtime state to track candidate skills, loaded skills, and the current active skill
  - upgraded prompt building so the model sees tool descriptions, skill summaries, and explicit `read_skill` guidance
  - added an async `AsyncOpenAI`-backed ReAct adapter for real model integration
  - added runtime-backed agent coverage and a runnable OpenAI runtime example
- Tests:
  - `./.venv/bin/pytest -q tests/unit/llm/test_openai_react.py tests/unit/runtime tests/unit/agents tests/integration/test_weather_skill_flow.py`
  - `./.venv/bin/pytest -q`
  - `PYTHONPATH=src ./.venv/bin/python examples/openai_runtime.py`
- Notes:
  - `tools` remain runtime-owned
  - `scripts` remain the hard boundary for `exec_script`
  - runtime now accepts `workspace_dir` directly instead of relying on test-only executor monkeypatching
  - FastAPI stays outside `agents` and is planned separately as the future API layer
  - agents now bind candidate skills and let the loop decide when to load one through `read_skill`
  - a single run can now load more than one skill over time; `active_skill` follows the latest loaded skill
  - real-model support now uses the native async OpenAI client instead of thread-wrapping a sync client

### Template

- PR:
- Title:
- Branch:
- Status:
- Summary:
- Tests:
- Notes:

## Architecture Notes

### Target module plan

- `common`
  - loguru-based logging
  - tracing
  - event bus
  - config loading
  - runtime context
  - shared types and helpers
  - `clawcore`
  - `skilling`
    - skill loading
    - skill metadata
    - skills prompt rendering
    - document-skill metadata for tools and scripts
  - `tooling`
    - tool base protocol
    - tool registry
    - tool policy
    - tool execution
    - tool result modeling
  - `runtime`
    - session
    - system prompt builder
    - ReAct loop
    - history and state
    - runtime hooks and event subscription
  - `llm`
    - abstract LLM client
    - mock/test backend
- `agents`
  - domain agents
  - prompts and policies
  - app-specific skills and tools
  - app-level wiring built on `clawcore`

### Core execution flow

```text
prepare_run()
-> load_skills()
-> build_skills_prompt()
-> build_tools()
-> apply_tool_policy()
-> build_system_prompt()
-> create_or_restore_session()
-> run_react_loop()
-> collect_result()
```

### Design rules for V1

- Do not add a separate planner-only LLM call in V1.
- Skills tell the model what capability packages exist.
- Tools give the model executable actions.
- Runtime owns the ReAct loop and session state.
- Agents only define business behavior and composition.
- Prefer deterministic behavior and testability over framework cleverness.
- Treat skills primarily as document-skills:
  - a skill is documentation plus constrained metadata
  - a skill may recommend tools and allowed scripts
  - a skill should not directly execute code by itself

### Runtime state mental model

- `available_skills`
  - candidate skills exposed to the run as summaries before any full skill is loaded
- `loaded_skills`
  - skills that have already been loaded through the loop and can be inspected later
- `active_skill`
  - the currently selected skill, usually the most recently loaded one
- `scratchpad`
  - text observations fed back into the ReAct loop for later reasoning
- `tool_results`
  - structured tool outputs kept for programmatic access and assertions
- `events`
  - runtime lifecycle events used for hooks, tracing, and debugging
- `trace`
  - ordered timeline of the run across thought, action, observation, and final answer

## PR Roadmap

### PR 1 - Common Foundation

- Goal:
  - establish shared runtime infrastructure before higher-level orchestration
- Scope:
  - `common/observability.py`
  - `common/tracing.py`
  - `common/events.py`
  - `common/context.py`
  - `common/config.py`
- Deliverables:
  - unified `loguru` logging
  - `run_id`, `session_id`, `trace_id` support
  - base event types for runtime lifecycle
  - `RunContext` model
- Unit test acceptance:
  - trace id can be bound and reset
  - event objects serialize predictably
  - `RunContext` can be created with sane defaults
  - logging setup does not raise and can be initialized repeatedly
- Integration test need:
  - not required
- PR exit criteria:
  - all unit tests pass
  - no integration dataset required

### PR 2 - Skilling Layer

- Goal:
  - convert skills from loose files into runtime-ready inputs
- Scope:
  - `clawcore/skilling/loader.py`
  - `clawcore/skilling/models.py`
  - `clawcore/skilling/prompt.py`
  - skill metadata fixtures
- Deliverables:
  - `Skill` data model
  - skill directory loader
  - `skills_prompt` builder
  - document-skill metadata for recommended tools and allowed scripts
- Unit test acceptance:
  - load valid skills from a fixture directory
  - ignore invalid or incomplete skill entries safely
  - render `skills_prompt` with stable ordering
  - parse tool and script metadata predictably
- Integration test need:
  - yes
- Integration dataset:
  - `tests/fixtures/skills/basic/`
  - `tests/fixtures/skills/invalid/`
  - `tests/fixtures/skills/multi/`
- PR exit criteria:
  - all unit tests pass
  - fixture-backed integration tests pass locally

### PR 3 - GitHub Skill Installer

- Goal:
  - support installing document-skills directly from GitHub subdirectory URLs
- Scope:
  - `clawcore/skilling/install.py`
  - `clawcore/skilling/github.py`
  - `clawcore/skilling/manifest.py`
  - optional example installer entrypoint
- Deliverables:
  - support GitHub `tree/...` skill URLs only
  - parse:
    - repo
    - ref
    - subdirectory path
  - download the target skill directory into local `skills/<name>/`
  - validate installed skill contents
  - require `SKILL.md`
  - scan `scripts/**`
  - generate or update `skill.json`
  - make installed skill compatible with `clawcore.skilling.load_skills()`
- Unit test acceptance:
  - parse valid GitHub skill URLs
  - reject unsupported URLs
  - reject malformed GitHub tree URLs
  - detect `SKILL.md` correctly
  - collect script paths correctly
  - generate stable `skill.json`
- Integration test need:
  - yes
- Integration dataset:
  - `tests/fixtures/install/github_skill_url_cases.json`
  - `tests/fixtures/install/github_download/xlsx_like/`
  - initial integration can use local fixture-backed download simulation
- PR exit criteria:
  - all unit tests pass
  - install integration tests pass locally
  - installed skill can be loaded by the existing skilling loader

### PR 4 - Tooling Layer

- Goal:
  - standardize runtime-owned tools for skill-guided actions
- Scope:
  - `clawcore/tooling/base.py`
  - `clawcore/tooling/builtin/read.py`
  - `clawcore/tooling/builtin/write.py`
  - `clawcore/tooling/builtin/exec_script.py`
  - `clawcore/tooling/registry.py`
  - `clawcore/tooling/policy.py`
  - `clawcore/tooling/executor.py`
  - `clawcore/tooling/result.py`
- Deliverables:
  - base tool protocol
  - tool registry
  - runtime-owned built-in tools:
    - `read`
    - `write`
    - `exec_script`
  - allowlist and denylist policy
  - low-risk vs restricted tool policy split
  - structured `ToolCall` and `ToolResult`
  - `exec_script` with explicit skill-aware script validation
- Unit test acceptance:
  - registry can register and resolve tools
  - duplicate tool registration behavior is explicit
  - policy blocks denied tools
  - executor returns normalized tool results
  - tool failures are surfaced as structured errors
  - `read` reads file content correctly
  - `write` writes file content correctly
  - script execution is blocked when the script is not declared by the active skill
  - script execution succeeds when the script is declared by the active skill
- Integration test need:
  - yes
- Integration dataset:
  - `tests/fixtures/tools/cases.json`
  - include:
    - read success
    - write success
    - blocked tool
    - declared script success
    - undeclared script blocked
    - invalid input
    - tool failure
- PR exit criteria:
  - all unit tests pass
  - tool execution integration cases pass locally

### PR 5 - Runtime Core

- Goal:
  - implement the first usable ReAct runtime for document-skills + tool execution
- Scope:
  - `clawcore/runtime/session.py`
  - `clawcore/runtime/state.py`
  - `clawcore/runtime/prompt_builder.py`
  - `clawcore/runtime/react.py`
  - `clawcore/runtime/hooks.py`
  - `clawcore/llm/base.py`
  - `clawcore/llm/mock.py`
- Deliverables:
  - session state and history management
  - system prompt builder
  - minimal ReAct runner
  - abstract LLM client plus mock backend
  - runtime event emission
  - active skill selection tracking for the current run
- Unit test acceptance:
  - runtime builds a system prompt from skill and tool inputs
  - runtime completes a no-tool turn
  - runtime completes a single-tool turn
  - runtime stops on max step protection
  - runtime records observations into session state
  - runtime emits start, tool, observe, and finish events
  - runtime can enforce script execution against the active skill declaration
- Integration test need:
  - yes
- Integration dataset:
  - `tests/fixtures/runtime/react_cases.json`
- cases:
    - direct answer
    - one tool call then final answer
    - invalid tool request
    - declared script execution
    - undeclared script blocked
    - max-steps exhausted
- PR exit criteria:
  - all unit tests pass
  - mock runtime integration cases pass locally

### PR 6 - Agent Application Layer

- Goal:
  - prove that business agents can be built cleanly on top of `clawcore`
- Scope:
  - `agents/base.py`
  - one real demo agent
  - `examples/`
  - optional CLI entrypoint
- Deliverables:
  - app-level agent abstraction
  - one example business agent composed from skills and tools
  - agent-owned candidate skill binding
  - on-demand skill loading through `read_skill`
  - loaded-skill tracking inside runtime state
  - prompt guidance that teaches the model when to call `read_skill`
  - async OpenAI-compatible adapter for real ReAct execution
  - example runnable flow
- Unit test acceptance:
  - agent wires prompt, tools, and runtime correctly
  - agent returns final answer from runtime
  - agent-specific defaults do not mutate shared runtime state
  - runtime can load more than one skill during a single run
  - OpenAI-compatible ReAct responses parse into runtime steps
- Integration test need:
  - yes
- Integration dataset:
  - `tests/fixtures/agents/demo_agent_cases.json`
- PR exit criteria:
  - all unit tests pass
  - example agent integration tests pass locally

### PR 7 - FastAPI API Layer

- Goal:
  - add an HTTP API surface without coupling FastAPI into `agents`
- Scope:
  - `apps/api/main.py`
  - `apps/api/schemas.py`
  - `apps/api/dependencies.py`
  - optional local dev launcher
- Deliverables:
  - FastAPI application bootstrap
  - `GET /health`
  - `GET /agents`
  - `POST /runs`
  - `POST /runs/debug`
  - API response surface for:
    - `final_answer`
    - `scratchpad`
    - `tool_results`
    - `events`
    - `trace`
- Unit test acceptance:
  - route schemas validate request and response payloads
  - agent lookup and dependency wiring are deterministic
  - debug serialization is stable
- Integration test need:
  - yes
- Integration dataset:
  - `tests/fixtures/api/run_cases.json`
- PR exit criteria:
  - all unit tests pass
  - API integration tests pass locally
  - manual owner sign-off on debug payload usability

## Testing Strategy

### Rules

- Every PR must include unit tests for the behavior it introduces.
- If a PR introduces cross-module behavior, add integration tests in the same PR.
- Integration tests should prefer deterministic fixtures over live model calls.
- V1 should use a mock or scripted LLM backend for runtime integration tests.
- No PR is considered complete without automated acceptance coverage.

### Proposed test layout

```text
tests/
├── unit/
│   ├── common/
│   ├── skilling/
│   ├── tooling/
│   ├── runtime/
│   └── agents/
├── integration/
│   ├── test_skills_pipeline.py
│   ├── test_tool_execution_pipeline.py
│   ├── test_runtime_react_loop.py
│   └── test_demo_agent_flow.py
└── fixtures/
    ├── skills/
    ├── tools/
    ├── runtime/
    └── agents/
```

### Integration test governance

- Integration tests should be introduced starting from PR 2.
- Fixture datasets should be reviewed for readability and long-term maintainability.
- Final integration test sign-off is manual and should be gated by the repository owner.
- Human gate:
  - after automated integration tests pass, final approval should be done by you
  - especially for:
    - skill prompt quality
    - tool execution semantics
    - runtime loop behavior
    - demo agent behavior

## TODO

- Finish and review PR 1 implementation against the roadmap above
- Create `tests/unit` and `tests/integration` layout
- Add first fixture datasets under `tests/fixtures`
- Keep `DEV_NOTES.md` updated as each PR lands
