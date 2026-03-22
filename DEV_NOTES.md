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

- PR: 7
- Title: FastAPI API Layer
- Branch: main
- Status: landed
- Summary:
  - landed JSON-backed agent factory wiring for singleton agent construction
  - added `configs/agents/*.json` for app-level runtime configuration
  - added `src/apps/api/` with `GET /health`, `GET /agents`, `POST /runs`, and `POST /runs/debug`
  - added `.env` loading and a local API run entrypoint
  - added request-scoped trace logging across the API, runtime, and LLM adapter
  - added a generic agent-level `curl` tool and a weather-focused config flow
  - added runtime safeguards for repeated identical tool calls
- Tests:
  - `./.venv/bin/pytest tests/unit/common/test_observability.py tests/unit/runtime/test_react_runtime.py tests/integration/test_api_runs.py tests/unit/api/test_env.py tests/unit/api/test_dependencies.py tests/unit/api/test_schemas.py`
  - `./.venv/bin/pytest tests/unit/llm/test_openai_react.py tests/integration/test_weather_skill_flow.py`
- Notes:
  - built-in tools are loaded by default; config `tools` are reserved for agent-level tools under `src/agents/tools/`
  - the factory now assumes a repo-level `skills/` directory and a config-level `skills` allowlist
  - request `trace_id` is created once in FastAPI middleware and reused by `RunContext`
  - logs now print only `trace_id`; `run_id` and `session_id` remain internal runtime identifiers

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

### PR 6.5 - Agent Factory and Config Wiring

- Goal:
  - add a stable app-level factory that builds singleton agents from JSON config
- Scope:
  - `agents/factory.py`
  - JSON-backed agent spec loading and validation
  - factory unit tests
  - optional example wiring cleanup
- Deliverables:
  - JSON-backed `OpenAIRuntimeAgentSpec`
  - deterministic agent construction from config
  - singleton caching by config path
  - explicit cache clearing for future reload flows
  - built-in tools loaded by default
  - agent-level tool auto-discovery from `src/agents/tools/`
  - fixed repo-level `skills/` lookup plus config-level `skills` allowlist
  - default workspace resolution to `works/{agent_id}`
- Unit test acceptance:
  - valid JSON config builds the expected agent
  - invalid config fails with clear errors
  - repeated factory calls return the same agent instance
  - different config paths produce different agent instances
  - built-in tool resolution is deterministic
  - agent-level tool discovery is deterministic
- Integration test need:
  - not required
- PR exit criteria:
  - all unit tests pass
  - factory is usable by future FastAPI dependency wiring without extra boot logic

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
  - request-scoped trace-id binding for API logs
  - `GET /health`
  - `GET /agents`
  - `POST /runs`
  - `POST /runs/debug`
  - `.env`-backed local API launcher
  - API response surface for:
    - `final_answer`
    - `scratchpad`
    - `tool_results`
    - `events`
    - `trace`
  - debug and observability logging for API inputs plus LLM request/response cycles
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
  - request logs and runtime logs share the same trace id

### PR 8 - Planning Config and Routing

- Goal:
  - introduce planning as an explicit runtime capability without breaking the existing direct ReAct flow
- Scope:
  - `agents/factory.py`
  - `agents/runtime_agent.py`
  - `agents/openai_runtime_agent.py`
  - runtime config models
  - config fixtures and factory tests
- Deliverables:
  - planning config on JSON-backed agents
  - planning mode support:
    - `disabled`
    - `auto`
    - `always`
  - backward-compatible config parsing for a temporary `plan_enabled` alias if needed
  - runtime routing contract that selects:
    - direct execution
    - planned execution
  - no behavior change when planning mode is `disabled`
- Unit test acceptance:
  - valid planning config parses correctly
  - invalid planning config fails with clear errors
  - legacy config without planning still builds the same direct runtime agent
  - `disabled` mode routes to the existing direct path
  - `always` mode routes to the planned path
  - `auto` mode can be selected without changing existing direct-only configs
- Integration test need:
  - not required
- PR exit criteria:
  - all unit tests pass
  - existing API and runtime tests still pass without config changes
  - planning config is available for later PRs without forcing planner implementation details

### PR 9 - Planning State and Plan Models

- Goal:
  - add first-class runtime data structures for task plans, subgoals, and execution artifacts
- Scope:
  - `clawcore/models.py`
  - `clawcore/runtime/state.py`
  - `clawcore/runtime/result.py`
  - `apps/api/schemas.py`
  - tests for serialization and state transitions
- Deliverables:
  - structured plan model
  - structured subgoal model with statuses:
    - `pending`
    - `in_progress`
    - `completed`
    - `blocked`
    - `failed`
  - runtime state fields for:
    - current plan
    - active subgoal
    - execution artifacts
    - replanning count
  - debug response support for returning plan state cleanly
- Unit test acceptance:
  - plan and subgoal models serialize predictably
  - runtime state can hold direct-mode runs without requiring a plan
  - runtime state can hold planned-mode runs with multiple subgoals
  - artifact updates are stable and deterministic
  - debug schema exposes plan data without breaking old clients
- Integration test need:
  - not required
- PR exit criteria:
  - all unit tests pass
  - direct-mode runtime behavior remains backward compatible
  - plan data model is stable enough for planner and executor PRs

### PR 10 - Planner Interface and Prompting

- Goal:
  - introduce a dedicated planner contract that can generate a task plan before execution
- Scope:
  - `clawcore/llm/base.py`
  - `clawcore/llm/mock.py`
  - new planner adapter module(s)
  - planning prompt builder
  - planner unit tests
- Deliverables:
  - planner-specific response schema
  - abstract planner interface separate from step-by-step direct ReAct execution
  - prompt builder for plan generation
  - planner output with:
    - goal
    - subgoals
    - success criteria
    - optional assumptions or blockers
  - mock planner backend for deterministic tests
- Unit test acceptance:
  - planner prompt contains tools, skills, and user intent in stable format
  - valid planner output parses into structured plan models
  - invalid planner output fails clearly
  - mock planner can drive deterministic planned-mode tests
- Integration test need:
  - not required
- PR exit criteria:
  - all unit tests pass
  - planner contract is stable and usable by runtime orchestration
  - no change to direct-mode runtime semantics

### PR 11 - Planned Runtime Execution

- Goal:
  - execute multi-step tasks through a plan-execute-review loop while preserving the existing direct mode
- Scope:
  - `clawcore/runtime/react.py`
  - `clawcore/runtime/session.py`
  - `clawcore/runtime/prompt_builder.py`
  - runtime integration tests
- Deliverables:
  - planned execution path
  - subgoal-aware execution loop
  - artifact handoff between subgoals
  - review step after subgoal execution
  - final answer synthesis from accumulated artifacts
  - direct mode remains the default behavior when planning is disabled
- Unit test acceptance:
  - runtime can execute a simple multi-subgoal plan
  - completed subgoals update statuses correctly
  - artifacts from one subgoal can be consumed by the next
  - planned runs still honor max-step protections
  - direct runs still behave exactly as before
- Integration test need:
  - yes
- Integration dataset:
  - `tests/fixtures/runtime/planned_cases.json`
- cases:
    - plan with two sequential subgoals
    - plan with mixed skill and tool usage
    - direct-mode task bypasses planner
    - planned-mode task returns final answer from artifacts
    - blocked subgoal surfaces a clear failure
- PR exit criteria:
  - all unit tests pass
  - planned runtime integration cases pass locally
  - existing direct runtime fixtures remain green

### PR 12 - Replanning and Failure Recovery

- Goal:
  - improve OOD robustness by letting the runtime inspect failures and revise the plan instead of exiting immediately
- Scope:
  - `clawcore/runtime/react.py`
  - planner adapter module(s)
  - runtime state tracking for retries and replans
  - runtime integration tests
- Deliverables:
  - structured failure classification for:
    - tool failure
    - missing context
    - blocked subgoal
    - exhausted plan
  - bounded replanning support
  - configurable replan limit
  - runtime observations that capture why replanning happened
  - clearer failure messages for unrecoverable runs
- Unit test acceptance:
  - failed subgoals can trigger replanning when enabled
  - replanning count is tracked correctly
  - runtime stops after the configured replan limit
  - unrecoverable failures still surface deterministically
- Integration test need:
  - yes
- Integration dataset:
  - extend `tests/fixtures/runtime/planned_cases.json`
- cases:
    - tool failure followed by successful replan
    - missing context followed by inserted research step
    - repeated failure hits replan limit
- PR exit criteria:
  - all unit tests pass
  - replanning integration cases pass locally
  - failure recovery does not regress existing direct-mode behavior

### PR 13 - Planned Agent Demo and API Debug Surface

- Goal:
  - prove the planning stack end-to-end with one realistic multi-step agent workflow and expose enough debug state to inspect it
- Scope:
  - `configs/agents/`
  - `examples/`
  - `apps/api/schemas.py`
  - optional API docs updates
  - integration tests
- Deliverables:
  - one planning-enabled demo agent config
  - one realistic planned workflow example such as:
    - gather weather
    - gather context
    - draft content
    - send output
  - API debug output for plan, subgoal status, and artifacts
  - example documentation for choosing between direct and planned modes
- Unit test acceptance:
  - demo config parses correctly
  - debug response includes plan state for planned runs
  - direct-run debug responses remain backward compatible
- Integration test need:
  - yes
- Integration dataset:
  - `tests/fixtures/api/planned_run_cases.json`
  - `tests/fixtures/agents/planned_agent_cases.json`
- PR exit criteria:
  - all unit tests pass
  - end-to-end planned agent flow passes locally with mock backends
  - API debug payload is usable for manual inspection of planning behavior

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
