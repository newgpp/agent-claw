# clawcore 模块功能梳理与重构准备

## 目标

这份文档用于在重构前先把 `clawcore` 的职责边界、调用关系、当前耦合点和建议拆分顺序梳理清楚，避免一上来直接改代码导致运行时行为漂移。

---

## 一句话定位

`clawcore` 是整个项目的“运行时内核”：

- `llm` 负责把模型能力包装成统一的 planner / executor 接口
- `runtime` 负责驱动 ReAct 循环和 planner-first 执行流程
- `tooling` 负责工具注册、策略校验和执行
- `skilling` 负责技能从磁盘加载、提示词注入、GitHub 安装
- `models` 负责跨模块共享的数据结构
- `registry.py` 提供一个偏兼容层的简化注册入口

它本身不直接关心业务 Agent 的配置来源，也不关心 API 暴露方式；这些由 `agents`、`apps` 层向上承接。

---

## 模块地图

### 1. `src/clawcore/models.py`

核心共享模型，职责很纯：

- `ToolCall`：LLM 发出的工具调用请求
- `ToolResult`：工具执行后的标准化结果
- `TokenUsage` / `RuntimeTokenUsage`：planner 与 executor 的 token 统计
- `PlanStatus` / `PlanSubgoal` / `PlanArtifact` / `ExecutionPlan`：planner-first 模式的计划结构
- `ReActStep`：单轮 ReAct 输出，约束为“工具调用”和“最终答案”二选一

重构判断：

- 这是稳定层，应该尽量保持“纯数据模型”属性
- 可以继续作为跨子模块共享的 canonical contract
- 不建议把运行时逻辑塞回这里

### 2. `src/clawcore/llm`

职责是“协议适配”，不是运行时编排。

子模块：

- `base.py`
  - 定义 `BaseLLM.next_step()` 和 `BasePlanner.create_plan()` 抽象接口
- `mock.py`
  - 提供测试用的 `MockLLM`、`MockPlanner`
- `openai_react.py`
  - 把运行时上下文转成 OpenAI chat completion 请求
  - 负责把 JSON 响应解析成 `ReActStep`
  - 负责累计 executor token usage
- `openai_planner.py`
  - 把 planning context 转成 planner 请求
  - 负责把 JSON 响应解析成 `ExecutionPlan`
  - 负责累计 planner token usage

当前特点：

- `llm` 基本没有业务逻辑，主要是 prompt protocol + JSON parse
- 但 `openai_react.py` 内置了很多运行时规则文案，和 `runtime` 的执行规则强绑定

重构机会：

- 可以把“协议提示词”从 adapter 中抽出去，变成独立 prompt spec / policy spec
- `OpenAIReActLLM` 与 `OpenAIPlanner` 存在明显重复：
  - 请求构造
  - usage 提取
  - content 提取
  - JSON 日志输出
- 后续可抽一个 `OpenAIChatJSONClient` 或 `OpenAIJSONResponder`

### 3. `src/clawcore/runtime`

这是真正的核心编排层。

子模块职责：

- `state.py`
  - 维护一次运行的完整内存态
  - 同时维护 `prompt_state` 和 `debug_state`
  - 提供 `build_executor_context()`，把状态压缩成 LLM 真正需要看到的上下文
- `session.py`
  - 在 `RuntimeState` 外再包一层 `history`
  - 提供 `append_observation()`，同步更新 scratchpad 和 prompt observations
- `prompt_builder.py`
  - 负责 direct runtime 和 planning runtime 的 system prompt 拼装
- `result.py`
  - 定义 debug 返回对象 `RuntimeRunResult`
- `hooks.py`
  - 定义 runtime event hook 的轻量抽象
- `react.py`
  - 真正驱动执行流程
  - 同时支持 direct ReAct 和 planner-first 两套路径

`react.py` 目前承担的职责最多：

- 创建 run context / observability 绑定
- 初始化 `RuntimeState` / `AgentSession`
- 构造 system prompt
- direct 模式执行
- planner-first 模式执行
- 多 subgoal 顺序推进
- tool call 去重缓存
- 工具执行事件发射
- `read_skill` 后 active skill 切换
- write 成功后的 file cache
- Tavily observation 摘要
- read_skill 结果压缩摘要
- fast-path completion 判定
- step summary 生成

结论：

- `react.py` 已经是“God Object / God Module”苗头
- 它是最值得优先拆分的地方

### 4. `src/clawcore/tooling`

职责比较清晰，是 runtime 下游的工具执行层。

子模块：

- `base.py`
  - `BaseTool`
  - `ToolExecutionContext`
- `registry.py`
  - 工具注册与分发
  - 支持 `BaseTool` 和 `CallableTool`
- `policy.py`
  - allow/deny 级别的简单执行策略
- `executor.py`
  - 负责“先过 policy，再调用 registry”
  - 统一返回 `ToolExecutionResult`
- `result.py`
  - 定义 `SUCCESS / ERROR / BLOCKED`
- `builtin/*.py`
  - `read`
  - `write`
  - `read_skill`
  - `exec_script`

当前特点：

- 层次是清楚的：`runtime -> executor -> registry -> tool`
- built-in tool 设计简单直接，可维护性还不错
- 但路径安全、沙箱边界、权限模型现在都比较薄

重构机会：

- `read` / `write` / `exec_script` 都自己处理路径和文件系统边界，可抽成统一的 workspace access layer
- `risk_level` 目前只是静态字段，`ToolPolicy` 还没有真正消费它
- 未来如果要做分级授权、只读工作区、skill 级权限，可以从这里扩展

### 5. `src/clawcore/skilling`

职责是“技能是如何被发现、表达、加载、安装”的整套机制。

子模块：

- `models.py`
  - `SkillDefinition`
- `loader.py`
  - 从 `skills/` 目录加载技能
  - 支持 `SKILL.md + skill.json + frontmatter + markdown 首段描述`
- `prompt.py`
  - 把技能列表渲染成 `<available_skills>` prompt block
- `github.py`
  - 解析 GitHub tree URL，计算 archive 路径
- `install.py`
  - 下载 zip、提取 skill 目录、校验、收集 scripts、落地 manifest
- `manifest.py`
  - 写 `skill.json`
- `cli.py`
  - 安装命令行参数

当前特点：

- `loader` 和 `install` 是两个方向：
  - `loader` 解决“本地 skill 如何进入 runtime”
  - `install` 解决“远程 skill 如何进入本地”
- `read_skill` 工具和 runtime 对 skill 的处理，依赖这里提供的 `SkillDefinition`

重构机会：

- `loader.py` 目前混合了：
  - 文件发现
  - metadata 合并
  - frontmatter 解析
  - description 推断
- 可以拆成：
  - `skill_sources/fs.py`
  - `skill_metadata.py`
  - `skill_parser.py`
- `install.py` 以后若支持 GitHub 以外来源，建议抽 `SkillInstaller` / `SkillSourceRef`

### 6. `src/clawcore/registry.py`

这是一个“历史兼容 / 便捷封装”层：

- 重新导出并包装 `tooling.registry.ToolRegistry`
- 增加字符串 + callable 的注册方式
- 额外保留 `SkillRegistry`

当前判断：

- 这个文件对新架构价值不大
- 容易和 `clawcore.tooling.registry.ToolRegistry` 形成概念重复

重构建议：

- 如果外部引用不多，最终可以逐步下线
- 或者把它明确标成 compatibility facade

---

## 核心调用链

### 1. 运行装配链

上层装配入口主要在 `agents`：

1. `agents/factory.py`
2. 读取 JSON agent spec
3. 装配 built-in tools + agent tools + skills
4. 创建 `OpenAIReActConfig`
5. 创建 `OpenAIRuntimeAgent`
6. 在 agent 内部实例化 `ReActRuntime`

### 2. Direct ReAct 链路

1. `RuntimeAgent.run()` / `run_debug()`
2. 调用 `ReActRuntime.run()` 或 `run_debug()`
3. `_run_debug_direct()`
4. 初始化 `RuntimeState` / `AgentSession`
5. `SystemPromptBuilder.build()`
6. `_run_subgoal_loop()`
7. `llm.next_step(session)`
8. 若有 tool action，则走 `_execute_tool_action()`
9. `ToolExecutor.execute()`
10. 工具结果写回 `state.tool_results / observations / trace`
11. 直到得到 `final_answer`

### 3. Planner-First 链路

1. `RuntimeAgent._resolve_runner()`
2. 选择 `run_planner_first()` / `run_debug_planner_first()`
3. `PlanningPromptBuilder.build()`
4. `planner.create_plan(session)`
5. `_execute_plan()`
6. 按 subgoal 顺序设置 `active_subgoal_*`
7. 每个 subgoal 都复用 `_run_subgoal_loop()`
8. subgoal 完成后生成 `artifact` + `step_summary`
9. 所有 subgoal 完成后汇总最终结果

这里的关键设计很好：

- planner 和 executor 的上下文是分开的
- executor 只看到当前 subgoal，而不是整个用户需求的无限展开版
- `prompt_state` 和 `debug_state` 明确区分了“给模型的上下文”和“给开发者排障的上下文”

这部分建议保留，不要在重构时破坏。

---

## 当前设计优点

### 1. 分层方向是对的

尽管有些模块偏重，但大方向已经清晰：

- 模型协议层在 `llm`
- 编排层在 `runtime`
- 工具执行层在 `tooling`
- 技能管理层在 `skilling`

### 2. planner-first 的执行边界比较清楚

`RuntimeState.build_executor_context()` 明确把：

- `active_subgoal`
- `plan_summary`
- `runtime.file_cache`
- `step_summaries`

压成 executor 可消费的上下文，这是后面做复杂 agent runtime 时很有价值的资产。

### 3. debug / prompt 双视图很实用

这是一个很好的 runtime 内核设计点：

- `prompt_state` 解决 token 成本
- `debug_state` 解决排查和 API debug 输出

以后即使重构，也建议保留这个双层视图概念。

### 4. 工具与技能都有最小可用闭环

- tools 可以注册、限制、执行、标准化返回
- skills 可以加载、提示、全文读取、远程安装

说明当前系统已经有比较完整的最小闭环，不需要推倒重来。

---

## 当前主要问题与耦合点

### 1. `runtime/react.py` 过重

最明显的问题。

它同时承担：

- lifecycle orchestration
- subgoal orchestration
- event emission
- observation shaping
- skill summary extraction
- tool dedupe
- file cache maintenance
- fast-path heuristic

风险：

- 修改任一小策略都容易影响主执行链
- 单测覆盖不够细时，回归会很隐蔽
- 很难替换其中某个策略而不动核心循环

### 2. prompt 规则散落

规则目前分布在：

- `runtime/prompt_builder.py`
- `llm/openai_react.py` 的 `_PROTOCOL_INSTRUCTIONS`
- `llm/openai_planner.py` 的 `_PLANNER_PROTOCOL_INSTRUCTIONS`
- `runtime/state.py` 的 `build_executor_context()`

问题：

- 执行规则并不只存在于一个地方
- 运行时 policy、提示词 policy、上下文结构三者耦合较紧

### 3. runtime 与 skill 摘要逻辑耦合

`react.py` 里有一整套：

- `_summarize_skill_content`
- `_extract_skill_recommended_tools`
- `_extract_skill_command_examples`
- `_extract_skill_call_hint`

这说明 runtime 已经开始承担“skill 内容理解器”的职责。

更合理的归属可能是：

- `skilling.runtime_view`
- 或 `skilling.summarizer`

### 4. runtime 与具体工具名硬编码耦合

比如：

- `read_skill`
- `tavily`
- `write`
- `send_email`

都直接出现在 `react.py` 的 fast-path、observation summarize 和状态更新逻辑里。

影响：

- runtime 不再是纯中立编排器
- 每新增特殊工具，都倾向继续往 runtime 塞分支

### 5. 兼容注册层命名重复

- `clawcore.registry.ToolRegistry`
- `clawcore.tooling.registry.ToolRegistry`

容易让后续维护者困惑。

### 6. 文件系统边界模型偏弱

`read` / `write` / `exec_script` 都能直接 resolve 路径。

当前适合开发期，但如果后面想做：

- 多租户
- 沙箱
- 只允许 workspace 子目录
- skill 专属执行目录

现在的抽象还不够。

---

## 重构目标建议

建议这次重构不要以“代码更漂亮”为目标，而是以这 5 个结果为准：

1. `runtime` 只保留执行编排，不再塞太多策略细节
2. prompt policy / protocol spec 集中管理
3. tool-specific 特殊处理从 runtime 主循环中抽离
4. skill 的摘要和运行时视图回到 `skilling` 领域内
5. 为后续权限控制、更多 LLM provider、更多 planner 模式留出口

---

## 推荐拆分思路

### 方案一：先做“小切口重构”，风险最低

适合当前项目。

#### 第一步：拆 `react.py` 的辅助策略

先不改主流程，只做函数搬家：

- `runtime/react.py`
  - 保留主执行循环
- 新增 `runtime/observation.py`
  - `_build_observation`
  - `_build_prompt_observation`
  - `_summarize_tavily_observation`
- 新增 `runtime/fast_path.py`
  - `_try_fast_path_completion`
  - `_infer_expected_tools_for_task`
  - `_build_fast_path_summary`
- 新增 `skilling/runtime_summary.py`
  - `_summarize_skill_content`
  - `_extract_skill_recommended_tools`
  - `_extract_skill_command_examples`
  - `_extract_skill_call_hint`
- 新增 `runtime/cache.py`
  - `_cache_written_file`
  - `_resolve_workspace_path`
  - tool call signature / dedupe helper

收益：

- 不改变外部接口
- 单测容易补
- 可以快速让 `react.py` 降重

#### 第二步：统一 prompt protocol

建议新增一个目录，例如：

- `src/clawcore/prompts/`

里面拆成：

- `executor_protocol.py`
- `planner_protocol.py`
- `system_prompt.py`

目标是把：

- protocol instructions
- planning policy
- skill loading policy
- tool 使用约束

集中起来，避免规则散落在 runtime / llm 两边。

#### 第三步：清理兼容层

评估 `src/clawcore/registry.py` 的实际调用面。

如果几乎没人用：

- 标注 deprecated
- 上层统一改用 `clawcore.tooling`

### 方案二：做“能力对象化”，适合第二阶段

当第一阶段稳定后，可以把 runtime 中一些概念升级成对象：

- `PlanExecutor`
- `SubgoalExecutor`
- `ObservationCompressor`
- `RuntimeEventBus`
- `ToolCallDeduper`
- `WorkspaceFileCache`

这样 `ReActRuntime` 就会变成一个真正的 façade，而不是所有逻辑都亲自处理。

这个方向更长期，但一次性做风险更大。

---

## 推荐重构顺序

建议按下面顺序来，不要同时大改：

1. 先补足 `runtime/react.py` 相关行为测试
2. 再拆 observation / fast-path / skill-summary 辅助模块
3. 再整理 prompt protocol 和 prompt builder
4. 再考虑 registry 兼容层收敛
5. 最后才动 tooling 权限模型和 workspace 安全边界

原因：

- 前三步主要是“搬家 + 解耦”，收益快、回归风险低
- 后两步更偏架构演进，适合在行为稳定后推进

---

## 建议优先补的测试点

重构前建议确保这些行为有测试兜底：

### runtime 主链路

- direct 模式单步工具调用
- planner-first 模式单 subgoal
- planner-first 模式多 subgoal 顺序执行
- 超过 `max_steps` 时正确报错
- tool error / blocked 时正确中断

### runtime 特殊策略

- 重复 tool call 会复用结果
- `write` 成功后进入 `cached_files`
- `read_skill` 成功后切换 `active_skill`
- Tavily 结果进入 prompt 时被摘要
- simple single-tool subgoal 触发 fast-path completion

### skilling

- frontmatter / skill.json / markdown description 的优先级
- GitHub 安装后 script 收集与 manifest 落盘

---

## 一个更理想的目标结构

后面如果要逐步演进，我建议朝这个结构靠：

```text
clawcore/
  models.py
  llm/
    base.py
    openai/
      client.py
      planner.py
      executor.py
  prompts/
    executor_protocol.py
    planner_protocol.py
    builders.py
  runtime/
    engine.py
    plan_executor.py
    subgoal_executor.py
    state.py
    session.py
    observation.py
    fast_path.py
    events.py
    cache.py
  tooling/
    base.py
    executor.py
    policy.py
    registry.py
    workspace.py
    builtin/
  skilling/
    models.py
    loader.py
    install.py
    manifest.py
    prompt.py
    runtime_summary.py
```

这不是要求一次改完，而是给重构一个“方向感”。

---

## 我对这次重构的建议结论

### 可以保留的核心设计

- `models.py` 的数据契约
- planner-first 里 `active_subgoal` 的执行边界
- `prompt_state` / `debug_state` 双视图
- `tooling` 的 registry + executor + policy 分层
- `skilling` 的加载与安装双路径

### 应该优先下手的部分

- `runtime/react.py` 拆薄
- prompt rule 集中化
- skill summary 逻辑迁出 runtime
- runtime 对具体工具名的硬编码收敛

### 不建议现在就做的事情

- 不建议直接推翻 `clawcore` 目录结构
- 不建议一开始就把 planner / runtime / tooling 全量对象化
- 不建议没有测试兜底就重写 `ReActRuntime`

---

## 实操建议

如果你准备正式开重构，我建议下一步直接开一个小里程碑：

### Milestone 1

- 目标：`react.py` 降重，但行为不变
- 手段：只搬迁辅助函数，不改公开接口
- 验收：
  - 现有测试通过
  - 新增 runtime 特殊策略测试
  - `react.py` 体积明显下降

### Milestone 2

- 目标：prompt 规则集中化
- 手段：抽 `prompts/` 模块，统一 direct / planner protocol
- 验收：
  - prompt 输出行为一致
  - LLM adapter 只负责请求，不再持有大段规则文案

### Milestone 3

- 目标：runtime 去工具特化
- 手段：把 tool-specific summarize / fast-path 策略改成可插拔策略
- 验收：
  - 新增特殊工具时不需要改 runtime 主循环

---

## 总结

`clawcore` 现在的整体方向是健康的，真正的问题不是“架构错了”，而是 runtime 核心文件逐渐吸收了太多细节策略，开始变成维护压力的集中点。

所以这次重构最合适的打法不是推倒重来，而是：

1. 先守住现有行为
2. 再把 `react.py` 从“全能控制器”拆回“执行编排器”
3. 把 prompt、skill summary、tool special-case 逐步迁回各自领域

这样改，风险最低，收益也最稳定。
