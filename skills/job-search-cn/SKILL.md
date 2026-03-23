---
name: job-search-cn
description: "Use Tavily search for public job discovery in China. Trigger this skill for requests about 招聘, 岗位, 职位, 薪资, 任职要求, BOSS直聘, 猎聘, 拉勾, 城市岗位搜索, or role shortlists such as '帮我找上海最近发布的 AI Agent 产品经理岗位'. Best for: finding publicly indexed openings on BOSS直聘 and related sites, summarizing role patterns, and surfacing candidate-fit opportunities. In this project, use the built-in `tavily` search tool only. Treat results as public-web discovery, not as logged-in platform recommendations."
homepage: https://docs.tavily.com/documentation/agent-skills
metadata: { "openclaw": { "emoji": "💼", "requires": { "env": ["TAVILY_API_KEY"] } } }
---

# Job Search CN

Find publicly searchable job openings and summarize role patterns for the user.

## When to Use

✅ **USE this skill when:**

- The user wants recommended jobs based on title, city, salary band, or skill keywords
- The user asks for BOSS直聘 public listings or role discovery
- The user wants to compare hiring demand across companies or cities
- The user needs a shortlist of relevant openings from public web results
- The request mentions Chinese recruiting terms such as `招聘`、`岗位`、`职位`、`薪资`、`任职要求`
- The request names job platforms such as `BOSS直聘`、`猎聘`、`拉勾`
- Typical queries include `帮我找上海/北京最近发布的...岗位`、`整理岗位名称/公司/薪资范围/核心要求`

## When NOT to Use

❌ **DON'T use this skill when:**

- The task requires logged-in BOSS直聘 access or personalized platform recommendations
- The user expects full platform coverage or hidden listings
- The task needs resume submission, messaging recruiters, or account actions

## Tooling Boundary

This repository currently exposes only the built-in `tavily` **search** tool.

- Prefer `include_domains` for strict site targeting such as `["zhipin.com"]`
- Use `search_depth: "advanced"` when the user needs a shortlist with explanations
- Prefer `topic: "general"` for job pages, because job-search pages are not always treated as news
- Prefer `time_range: "week"` for “最近发布/最近一周” requests
- Use `start_date` / `end_date` when the user provides explicit hiring windows
- Use `exclude_domains` to suppress unrelated aggregators, video pages, and forum chatter when needed
- Treat results as **publicly indexed positions**, not guaranteed live availability

## Query Patterns

### Public BOSS Listing Discovery

```json
{
  "query": "算法工程师 北京 大模型 招聘",
  "max_results": 8,
  "search_depth": "advanced",
  "topic": "general",
  "include_domains": ["zhipin.com"],
  "time_range": "week"
}
```

### Role Recommendation

Use a compact profile inside the query:

```json
{
  "query": "Python 后端 上海 3-5年 招聘 OR AI Agent 产品经理 深圳 招聘",
  "max_results": 10,
  "search_depth": "advanced",
  "topic": "general",
  "include_domains": ["zhipin.com", "liepin.com", "lagou.com"],
  "exclude_domains": ["zhihu.com", "bilibili.com", "youtube.com"]
}
```

### Demand Summary

```json
{
  "query": "大模型工程师 杭州 招聘 要求 薪资",
  "max_results": 10,
  "search_depth": "advanced",
  "topic": "general",
  "include_domains": ["zhipin.com", "liepin.com", "lagou.com"],
  "time_range": "month"
}
```

## Output Style

When answering:

- Restate the user's target role, city, and constraints
- Provide a shortlist of likely relevant public openings
- Summarize common requirements:
  - years of experience
  - core skills
  - industry/domain
  - typical salary ranges if visible
- Clearly say when a recommendation is based on public search results rather than platform-native ranking
- If public results are sparse, stale, or mostly company pages, stop after a few targeted searches and return:
  - the best leads you found
  - what fields are confirmed vs inferred
  - the limitations of public indexing
- Do not keep retrying many near-duplicate queries once results stop improving materially

Suggested structure:

1. Best-fit openings
2. Why they match
3. Common hiring signals
4. Search limitations

## Caveats

- BOSS直聘 pages may be partially indexed, stale, or blocked from full retrieval
- Tavily results should be treated as lead discovery, not a guaranteed complete listing set
- If repeated queries mostly return company homepages, aggregator pages, or empty results, provide a bounded summary instead of continuing to search indefinitely
- If the user wants stronger personalization, ask for role, city, years of experience, and salary preference
