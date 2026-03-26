# 提示词拼接工程梳理

本文整理当前项目中提示词的拼接结构，重点按两种运行模式拆解：

- `react` 模式：直接进入执行循环，不先产出 plan
- `plan` 模式：先调用 planner 生成 plan，再按 subgoal 驱动执行

同时，本文按最终发给 LLM 的两类 message 来组织：

- `system`：静态规则、协议和能力说明
- `user`：当前回合的运行态上下文

目标不是逐行复述代码，而是回答三个问题：

1. 最终 prompt 是怎么拼出来的
2. 每一段内容来自哪里
3. `react` 和 `plan` 两种模式的差异在哪里

## 1. 总体结构

当前项目不是传统的“多轮消息历史回放”模式，而是每次请求都重新构造一个小而稳定的 prompt。

无论是 planner LLM 还是 executor LLM，最终都会发送两条 message：

```json
[
  {
    "role": "system",
    "content": "...拼接后的 system prompt..."
  },
  {
    "role": "user",
    "content": "...结构化运行态上下文 JSON..."
  }
]
```

核心特点：

- `system` 负责定义行为边界、工具和技能路由规则、输出协议
- `user` 负责承载本轮任务上下文，不直接回放完整历史对话
- tool 执行历史不会原样全部喂回模型，而是经过压缩后进入 `runtime.observations`、`step_summaries`、`subgoal_handoffs`

相关代码位置：

- `react` executor message 构造：`src/clawcore/llm/openai_react.py`
- `plan` planner message 构造：`src/clawcore/llm/openai_planner.py`
- system prompt builder：`src/clawcore/runtime/prompt_builder.py`
- executor 上下文构造：`src/clawcore/runtime/state.py`

## 2. 运行模式概览

### 2.1 React 模式

`react` 模式指不先做 planner 拆解，直接让 executor LLM 进入 ReAct 循环。

执行入口：

- `RuntimeAgent.run()` / `run_debug()`
- 当 `planning.mode == disabled` 时，走 `ReActRuntime.run()` 或 `run_debug()`

在这个模式下：

- 只会调用 executor LLM
- `system` 使用 `SystemPromptBuilder`
- `user` 使用 `build_executor_context()`

### 2.2 Plan 模式

`plan` 模式指先由 planner LLM 产出结构化 plan，再逐个 subgoal 执行。

执行入口：

- `RuntimeAgent.run()` / `run_debug()`
- 当 `planning.mode != disabled` 时，走 `run_planner_first()` 或 `run_debug_planner_first()`

在这个模式下，有两类 LLM 请求：

1. planner 请求
2. executor 请求

对应关系：

- planner 负责把用户需求拆成 `goal + subgoals + success_criteria + assumptions`
- executor 负责只执行当前 `active_subgoal`

## 3. React 模式的提示词拼接

### 3.1 React 模式的 system message

最终结构：

```text
base_instructions

Skill loading policy:
...

Available tools:
...

Available skills:
...

<executor protocol instructions>
```

可拆成 5 段。

#### A. `base_instructions`

来源：

- agent config 的 `base_instructions`
- 在 agent 初始化时进入 `AgentRunConfig`
- 运行时通过 `base_instructions` 参数传入 `SystemPromptBuilder.build()`

典型用途：

- 补充 agent 专属行为约束
- 注入业务性偏好

例子：

- `Use the echo_payload tool before answering the user.`

#### B. `Skill loading policy`

来源：

- `SystemPromptBuilder.build()` 内部固定文本

作用：

- 先看技能摘要，不要一上来裸调工具
- 如果技能明显匹配，优先走技能
- 需要完整技能说明时再调用 `read_skill`

这部分更偏“路由策略”和“成本控制策略”。

#### C. `Available tools`

来源：

- `ToolRegistry.names()`
- `ToolRegistry.descriptions()`

拼接方式：

- 列出所有可调用工具名
- 如果工具有 `description`，就以 `- tool_name: description` 形式输出

作用：

- 告诉模型当前回合有哪些能力
- 把工具 payload 语义暴露给模型

#### D. `Available skills`

来源：

- 运行配置中的 `skills`
- 由 `build_skills_prompt()` 渲染

渲染格式：

```xml
<available_skills>
  <skill>
    <name>...</name>
    <description>...</description>
    <location>...</location>
    <tools>...</tools>
    <scripts>...</scripts>
  </skill>
</available_skills>
```

作用：

- 让模型先看技能摘要，再决定是否调用 `read_skill`
- `location` 指向技能文档路径，便于模型理解这是可加载资源

#### E. executor protocol instructions

来源：

- `src/clawcore/llm/openai_react.py` 中的 `_PROTOCOL_INSTRUCTIONS`

这一段不是 builder 拼出来的，而是在真正请求 LLM 时追加到 `state.system_prompt` 后面。

作用包括：

- 规定输出必须是 JSON
- 规定 `action` / `final_answer` 二选一
- 约束重复工具调用
- 约束技能路由
- 约束语言保持
- 在 planner-first 模式下要求只执行 `active_subgoal`

它本质上是“执行协议”。

### 3.2 React 模式的 user message

最终结构：

```text
Runtime context:
{...JSON...}
```

JSON 来源：

- `RuntimeState.build_executor_context()`

典型结构：

```json
{
  "user_request": {
    "raw_input": "..."
  },
  "runtime": {
    "active_skill": "...",
    "loaded_skills": ["..."],
    "step_summaries": [],
    "subgoal_handoffs": [],
    "observations": [],
    "artifacts": [],
    "file_cache": []
  }
}
```

在纯 `react` 模式下：

- 一般没有 `execution.active_subgoal`
- 一般没有 `plan_summary`

核心字段说明：

- `user_request.raw_input`
  - 原始用户问题
- `runtime.active_skill`
  - 当前已选中的技能
- `runtime.loaded_skills`
  - 本次运行已读入的技能集合
- `runtime.observations`
  - prompt-safe 的工具观察结果
- `runtime.file_cache`
  - 已缓存的小文件内容，减少重复 `read`

### 3.3 React 模式中 observation 如何进入 prompt

工具执行完成后，运行时不会简单把原始结果全部塞回去，而是分成两份：

- `scratchpad`
  - 完整版观察，用于调试和 planner 输入
- `prompt_observations`
  - 压缩版观察，用于 executor 下一轮 prompt

处理流程：

1. 执行 tool
2. 构建 `observation`
3. 构建 `prompt_observation`
4. `scratchpad.append(observation)`
5. `prompt_observations.append(prompt_observation)`

这意味着：

- debug 可见的是较完整信息
- prompt 可见的是压缩后的信息

#### `read_skill` 的特殊处理

`read_skill` 不会把整篇技能文档全文直接作为 observation 回灌。

它会被压成类似：

```json
read_skill_summary: {
  "skill_name": "...",
  "summary": "...",
  "full_doc_available": true
}
```

这样能告诉模型“技能已经读过，而且全文可用”，但不需要每轮都重新塞长文档。

#### skill 级 prompt observation 摘要器

如果某个 skill 目录下存在 `prompt_observation.py`，运行时会优先调用其中的 `summarize_tool_result()`，把特定工具结果压成更短的 prompt-friendly 形式。

现有例子：

- `skills/weather/prompt_observation.py`

它会把天气大 JSON 压成几行天气摘要，而不是原样回灌。

## 4. Plan 模式的提示词拼接

`plan` 模式要分成两段来看：

1. planner 的提示词拼接
2. executor 的提示词拼接

### 4.1 Planner 的 system message

最终结构：

```text
base_instructions

Planning policy:
...

Available tools:
...

Available skills:
...

<planner protocol instructions>
```

同样可以拆成 5 段。

#### A. `base_instructions`

来源与 `react` 模式相同。

#### B. `Planning policy`

来源：

- `PlanningPromptBuilder.build()` 内部固定文本

核心意图：

- 判断任务是否真的需要多步
- 倾向更短的 plan
- 技能优先于 ad hoc 工具调用
- 搜索收益不高时及时收口
- 补充 success criteria 和 assumptions

这部分是“规划策略”。

#### C. `Available tools`

来源与 `react` 相同。

#### D. `Available skills`

来源与 `react` 相同。

#### E. planner protocol instructions

来源：

- `src/clawcore/llm/openai_planner.py` 中的 `_PLANNER_PROTOCOL_INSTRUCTIONS`

作用：

- 强制 planner 输出一个固定 JSON
- 定义 plan 的 schema
- 限制 subgoal 的拆分粒度
- 要求尽量少的 subgoal
- 明确何时允许 `subgoals: []`

这部分本质上是“规划器输出协议”。

### 4.2 Planner 的 user message

最终结构：

```text
Planning context:
{...JSON...}
```

JSON 来源：

- `OpenAIPlanner._build_messages()`

字段较少，当前只包含：

```json
{
  "user_input": "...",
  "loaded_skills": ["..."],
  "active_skill": "...",
  "scratchpad_observations": ["..."]
}
```

注意：

- planner 不使用 `build_executor_context()`
- planner 看不到 executor 那套完整 `runtime` 结构
- planner 关注的是“该怎么拆计划”，不是“怎么执行当前一步”

### 4.3 Plan 模式下 executor 的 system message

当 planner 产出 plan 之后，后续真正执行 subgoal 时，executor 的 system 拼接结构和 `react` 模式本质一致：

```text
base_instructions

Skill loading policy:
...

Available tools:
...

Available skills:
...

<executor protocol instructions>
```

差异不在 `system` 的静态结构，而在 `user` 上下文多了 subgoal 作用域信息。

### 4.4 Plan 模式下 executor 的 user message

在 planner-first 模式下，executor 仍然调用 `build_executor_context()`，但会额外包含两块：

```json
{
  "execution": {
    "active_subgoal": {
      "id": "s1",
      "task": "...",
      "notes": "..."
    },
    "rules": [
      "Only execute the active subgoal.",
      "Use the user request as background constraints, not as permission to expand scope.",
      "Do not start later subgoals, even if you can infer them.",
      "When the active subgoal is satisfied, return final_answer immediately."
    ]
  },
  "plan_summary": {
    "goal": "...",
    "status": "...",
    "completed_subgoal_ids": ["..."],
    "remaining_subgoal_ids": ["..."],
    "success_criteria": ["..."],
    "assumptions": ["..."]
  }
}
```

这里是 `plan` 模式和 `react` 模式最关键的上下文差异。

作用：

- `execution.active_subgoal`
  - 告诉 executor 这一轮只能做哪一个子任务
- `execution.rules`
  - 进一步明确只允许当前子任务执行
- `plan_summary`
  - 给 executor 一点全局背景，但不直接授权它越界执行后续步骤

## 5. `step_summaries` 和 `subgoal_handoffs` 的作用

这两个字段只在 planner-first 的多 subgoal 场景下才真正重要。

### 5.1 `step_summaries`

含义：

- 每个已完成 subgoal 的一句话摘要

形态：

```json
[
  "s1: 获取天气 -> 香港当前 26C，未来三天有雨。"
]
```

作用：

- 给后续 subgoal 快速了解前面做了什么
- 成本低，适合作为高层进度线索

### 5.2 `subgoal_handoffs`

含义：

- 已完成 subgoal 留给后续 subgoal 的 observation 级交接材料

形态：

```json
[
  {
    "subgoal_id": "s1",
    "observations": [
      "Weather summary for Hong Kong ...",
      "read: ..."
    ]
  }
]
```

作用：

- 提供比 `step_summaries` 更细的证据
- 让后续 subgoal 不必重新调工具，也能继续推理

### 5.3 二者区别

- `step_summaries` 偏“结果摘要”
- `subgoal_handoffs` 偏“关键观察交接”

二者都会进入 executor 的 `runtime` 上下文。

## 6. 两种模式下的最终拼接模板

### 6.1 React 模式

#### system

```text
{base_instructions}

Skill loading policy:
{fixed skill routing policy}

Available tools:
{tool descriptions}

Available skills:
{skills prompt block}

{executor protocol instructions}
```

#### user

```text
Runtime context:
{
  "user_request": {...},
  "runtime": {
    "active_skill": ...,
    "loaded_skills": ...,
    "step_summaries": ...,
    "subgoal_handoffs": ...,
    "observations": ...,
    "artifacts": ...,
    "file_cache": ...
  }
}
```

### 6.2 Plan 模式中的 planner 请求

#### system

```text
{base_instructions}

Planning policy:
{fixed planning policy}

Available tools:
{tool descriptions}

Available skills:
{skills prompt block}

{planner protocol instructions}
```

#### user

```text
Planning context:
{
  "user_input": ...,
  "loaded_skills": ...,
  "active_skill": ...,
  "scratchpad_observations": ...
}
```

### 6.3 Plan 模式中的 executor 请求

#### system

```text
{base_instructions}

Skill loading policy:
{fixed skill routing policy}

Available tools:
{tool descriptions}

Available skills:
{skills prompt block}

{executor protocol instructions}
```

#### user

```text
Runtime context:
{
  "user_request": {...},
  "runtime": {...},
  "execution": {
    "active_subgoal": {...},
    "rules": [...]
  },
  "plan_summary": {
    "goal": ...,
    "status": ...,
    "completed_subgoal_ids": ...,
    "remaining_subgoal_ids": ...,
    "success_criteria": ...,
    "assumptions": ...
  }
}
```

## 7. 当前这套拼接工程的设计特点

### 7.1 优点

- prompt 结构稳定，不依赖长历史回放
- `system` 和 `user` 的职责分离比较清楚
- planner 和 executor 各自有独立协议
- 工具结果进入 prompt 前会压缩，token 成本更可控
- subgoal 之间通过 `step_summaries` 和 `subgoal_handoffs` 做交接

### 7.2 现状上的边界

- planner protocol 和 executor protocol 仍然定义在 LLM adapter 层，不在统一 prompts 模块
- builder 层和 adapter 层都持有一部分 prompt 规则，规则分布仍然偏散
- subgoal 隔离主要是 prompt 级软约束，不是硬隔离的独立 subagent

## 8. 快速索引

如果要继续追代码，建议按这个顺序看：

1. `src/agents/runtime_agent.py`
2. `src/clawcore/runtime/react.py`
3. `src/clawcore/runtime/prompt_builder.py`
4. `src/clawcore/runtime/state.py`
5. `src/clawcore/llm/openai_planner.py`
6. `src/clawcore/llm/openai_react.py`
7. `src/clawcore/runtime/helpers/observation.py`
8. `src/clawcore/skilling/prompt.py`

这样能最快看清：

- 配置如何进入 runtime
- system prompt 如何构造
- user context 如何构造
- tool observation 如何进入下一轮 prompt
- planner 和 executor 的职责边界
