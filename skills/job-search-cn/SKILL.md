---
name: job-search-cn
description: "Use Tavily search for public job discovery in China. Best for: finding publicly indexed openings on BOSS直聘 and related sites, summarizing role patterns, and surfacing candidate-fit opportunities. In this project, use the built-in `tavily` search tool only. Treat results as public-web discovery, not as logged-in platform recommendations."
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

## When NOT to Use

❌ **DON'T use this skill when:**

- The task requires logged-in BOSS直聘 access or personalized platform recommendations
- The user expects full platform coverage or hidden listings
- The task needs resume submission, messaging recruiters, or account actions

## Tooling Boundary

This repository currently exposes only the built-in `tavily` **search** tool.

- Prefer query-based domain targeting such as `site:zhipin.com`
- Use `search_depth: "advanced"` when the user needs a shortlist with explanations
- Prefer `topic: "general"` for job pages, because job-search pages are not always treated as news
- Treat results as **publicly indexed positions**, not guaranteed live availability

## Query Patterns

### Public BOSS Listing Discovery

```json
{
  "query": "site:zhipin.com 算法工程师 北京 大模型 招聘",
  "max_results": 8,
  "search_depth": "advanced",
  "topic": "general"
}
```

### Role Recommendation

Use a compact profile inside the query:

```json
{
  "query": "site:zhipin.com Python 后端 上海 3-5年 招聘 OR site:zhipin.com AI Agent 产品经理 深圳 招聘",
  "max_results": 10,
  "search_depth": "advanced",
  "topic": "general"
}
```

### Demand Summary

```json
{
  "query": "site:zhipin.com 大模型工程师 杭州 招聘 要求 薪资",
  "max_results": 10,
  "search_depth": "advanced",
  "topic": "general"
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

Suggested structure:

1. Best-fit openings
2. Why they match
3. Common hiring signals
4. Search limitations

## Caveats

- BOSS直聘 pages may be partially indexed, stale, or blocked from full retrieval
- Tavily results should be treated as lead discovery, not a guaranteed complete listing set
- If the user wants stronger personalization, ask for role, city, years of experience, and salary preference
