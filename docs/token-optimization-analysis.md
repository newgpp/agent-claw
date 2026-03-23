# Planner-First 交付场景的 Token 优化分析

## 背景

在这类 planner-first 场景里，典型任务链路通常是：

- 查询天气
- 查询出行/研究信息
- 整理成可交付内容
- 发送邮件

当前 runtime 虽然能够正确完成任务，但 token 消耗明显偏高。

以这次 debug 请求为例：

`明天打算去杭州旅游，帮我查询下天气和出行指南，发送到zhangkaijian@aipark.com`

返回的 token 使用情况是：

- planner: `1242`
- executor: `12591`
- total: `13833`

对于这样一个复杂度中等的任务来说，`executor` 侧的消耗明显偏大。

## 核心结论

### 1. 工具原始结果被直接回灌给 executor

最大的 token 消耗来源，是工具结果在 prompt observation 阶段仍然过于原始。

当前 [src/clawcore/runtime/helpers/observation.py](/home/ff/Documents/agent-claw/src/clawcore/runtime/helpers/observation.py) 的行为是：

- 对非 `read_skill` 工具，直接使用 `"{tool_name}: {result_content}"`
- `build_prompt_observation()` 目前等同于 `build_observation()`

这意味着：

- `curl` 调天气接口时，如果拿到的是 `wttr.in?format=j1` 这种大 JSON，会被整段喂回后续 executor prompt
- 大型结构化结果会在后续多轮 LLM 调用里被重复发送

在这次杭州案例里，天气 JSON 包含：

- `current_condition`
- 多天 `weather`
- 每天很长的 `hourly` 数组

这些内容对后续“写邮件”来说远远超量。

### 2. Tavily 已做截断，但结果仍然偏长

目前 Tavily 已经在 [src/agents/tools/tavily.py](/home/ff/Documents/agent-claw/src/agents/tools/tavily.py) 内部做了长度限制，这比在 runtime 层做裁剪更合理。

但在旅游类查询里，返回结果仍然经常包含：

- 多条搜索结果
- 较长的 snippet
- 攻略/PDF 类高密度文本

所以虽然它已经比原来更好，但仍然会给 executor prompt 带来不小的体积。

### 3. planned execution 的上下文有重复

[src/clawcore/runtime/state.py](/home/ff/Documents/agent-claw/src/clawcore/runtime/state.py) 目前会同时把下面两类内容放进 executor context：

- `runtime.step_summaries`
- `runtime.artifacts[].summary`

而在 planned run 里，这两块内容经常是在重复描述同一件事。

结果就是：

- 一个子目标完成后，它的摘要会以两种形式进入后续 prompt
- 子目标越多，重复越多

### 4. 每个子目标完成后通常还要多走一轮确认

[src/clawcore/runtime/react.py](/home/ff/Documents/agent-claw/src/clawcore/runtime/react.py) 当前的执行模式基本是：

1. 模型决定调用哪个工具
2. 工具执行
3. 工具结果回灌
4. 模型再输出一次 `final_answer`，标记子目标完成

这个模式简单、稳定，但代价是：

- 每个完成的子目标，通常至少多消耗一轮 executor 调用

对于多子目标任务，这部分成本会被不断放大。

## 这不只是成本问题，也会影响质量

大 payload 不只是更贵，也更容易让模型抓错重点。

这次杭州案例里就出现了一个典型问题：

- 用户问的是“明天”
- 天气结果里同时有当前天气和未来预报
- 最终邮件里却拿错了字段，写成了当天数据

也就是说，当前设计在“花更多 token”的同时，还提高了模型选错字段的概率。

## 优化优先级

### 优先级 1：先压缩天气 observation，再喂给 executor

这是最值得先做的一刀。

不要再把 `curl` 返回的整段天气 JSON 直接回灌给 executor，而是改成紧凑摘要，例如只保留：

- 城市
- 请求的日期语义（`today` / `tomorrow`）
- 天气概况
- 温度区间
- 降水或降雨概率
- 风力
- 需要提醒的事项

这一步的预期收益最大：

- token 会明显下降
- prompt 噪音会显著减少
- 模型更容易抽取到正确天气字段

### 优先级 2：planned run 的 executor context 去重

对于 executor prompt，`step_summaries` 和 `artifacts[].summary` 建议二选一。

更推荐：

- 保留 `artifacts[].summary` 给 executor 使用
- `step_summaries` 只留给 debug/API 输出，不进入 executor context

这样既不影响排查，也能减少重复上下文。

### 优先级 3：进一步收紧 Tavily 的 prompt-facing payload

可以考虑：

- `max_results` 默认再降一点
- `max_content_chars` 继续压缩
- 或者让 Tavily tool 输出更结构化的摘要，而不是长 snippet

这一步也有收益，但通常不如先压天气 observation 直接。

### 优先级 4：减少子目标完成后的确认轮次

对一些明显终结性的子目标，例如：

- `send_email`
- 一次工具调用即可完成的简单获取动作

runtime 可以考虑在工具成功后直接结束当前子目标，而不是再让 executor 走一轮确认。

这会进一步降 token，但属于第二阶段优化，因为它会改变控制流，风险比前面几项略高。

## 推荐实施顺序

1. 给 `curl` 的天气结果增加紧凑型 prompt observation。
2. 在 planned executor context 里去掉 `step_summaries` 或 `artifacts` 其中一类重复信息。
3. 用同类“查询后发送邮件”的场景重新测一次 token。
4. 如果仍然偏高，再继续压 Tavily 的 prompt payload。
5. 最后再考虑减少子目标完成后的确认轮次。

## 建议的验收标准

对于同类请求，期望达到：

- executor token 明显低于当前大约 `12.6k` 的水平
- 用户可见输出仍然保持用户语言
- 天气提取能正确命中用户请求的日期，例如“明天”
- planned run 在上下文压缩后，仍然保留足够的信息完成后续交付动作

## 简短结论

当前这类场景的 token 消耗确实偏大，而且是结构性问题，不是偶发波动。

最主要的来源是：

- 工具 observation 过大
- planned context 重复
- 每个子目标完成都要多走一轮 executor

如果只做一件事，最值得优先做的是：

- 先把天气相关的 prompt observation 压缩掉，再喂给 executor
