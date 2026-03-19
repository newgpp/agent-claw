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

- PR: 1
- Title: Common Foundation
- Branch: current working branch
- Status: in progress
- Summary:
  - added runtime config, runtime events, and run context
  - expanded observability to support `run_id`, `session_id`, and `trace_id`
  - added unit tests for `common`
- Tests:
  - `./.venv/bin/pytest -q tests/unit/common tests/test_echo_agent.py`
- Notes:
  - no integration dataset required for PR 1

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
    - optional skill env injection
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
  - `clawcore/skilling/env.py`
- Deliverables:
  - `Skill` data model
  - skill directory loader
  - `skills_prompt` builder
  - optional environment override hook for selected skills
- Unit test acceptance:
  - load valid skills from a fixture directory
  - ignore invalid or incomplete skill entries safely
  - render `skills_prompt` with stable ordering
  - optional env override setup and restore behave correctly
- Integration test need:
  - yes
- Integration dataset:
  - `tests/fixtures/skills/basic/`
  - `tests/fixtures/skills/invalid/`
  - `tests/fixtures/skills/multi/`
- PR exit criteria:
  - all unit tests pass
  - fixture-backed integration tests pass locally

### PR 3 - Tooling Layer

- Goal:
  - standardize tool registration, policy, and execution
- Scope:
  - `clawcore/tooling/base.py`
  - `clawcore/tooling/registry.py`
  - `clawcore/tooling/policy.py`
  - `clawcore/tooling/executor.py`
  - `clawcore/tooling/result.py`
- Deliverables:
  - base tool protocol
  - tool registry
  - allowlist and denylist policy
  - structured `ToolCall` and `ToolResult`
  - one or two demo tools for development
- Unit test acceptance:
  - registry can register and resolve tools
  - duplicate tool registration behavior is explicit
  - policy blocks denied tools
  - executor returns normalized tool results
  - tool failures are surfaced as structured errors
- Integration test need:
  - yes
- Integration dataset:
  - `tests/fixtures/tools/cases.json`
  - include success, blocked, invalid input, and failure cases
- PR exit criteria:
  - all unit tests pass
  - tool execution integration cases pass locally

### PR 4 - Runtime Core

- Goal:
  - implement the first usable ReAct runtime
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
- Unit test acceptance:
  - runtime builds a system prompt from skill and tool inputs
  - runtime completes a no-tool turn
  - runtime completes a single-tool turn
  - runtime stops on max step protection
  - runtime records observations into session state
  - runtime emits start, tool, observe, and finish events
- Integration test need:
  - yes
- Integration dataset:
  - `tests/fixtures/runtime/react_cases.json`
  - cases:
    - direct answer
    - one tool call then final answer
    - invalid tool request
    - max-steps exhausted
- PR exit criteria:
  - all unit tests pass
  - mock runtime integration cases pass locally

### PR 5 - Agent Application Layer

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
  - example runnable flow
- Unit test acceptance:
  - agent wires prompt, tools, and runtime correctly
  - agent returns final answer from runtime
  - agent-specific defaults do not mutate shared runtime state
- Integration test need:
  - yes
- Integration dataset:
  - `tests/fixtures/agents/demo_agent_cases.json`
- PR exit criteria:
  - all unit tests pass
  - example agent integration tests pass locally

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
