---
name: trend-research
description: "Use Tavily search to monitor public web trends, social buzz, and frontier AI developments. Best for: X/Twitter and Xiaohongshu public trend discovery, LLM and agent progress tracking, and fast topic briefings. In this project, prefer the built-in `tavily` search tool only. Do not assume Tavily extract, crawl, or research endpoints are available unless the toolset explicitly exposes them."
homepage: https://docs.tavily.com/documentation/agent-skills
metadata: { "openclaw": { "emoji": "📡", "requires": { "env": ["TAVILY_API_KEY"] } } }
---

# Trend Research

Monitor public trends and fast-moving topics with Tavily search.

## When to Use

✅ **USE this skill when:**

- The user wants public trend discovery on `x.com` or `xiaohongshu.com`
- The user wants a quick briefing on what people are discussing online
- The user asks for the latest `LLM`, `AI agent`, or model-release developments
- The user needs a short current-awareness report with links and citations

## When NOT to Use

❌ **DON'T use this skill when:**

- The task requires logged-in social feeds or private content
- The user expects complete social media coverage or exact platform analytics
- The task needs deep crawling, post-level extraction, or sentiment scoring from raw full text
- The task is historical research better suited to a curated dataset

## Tooling Boundary

This repository currently exposes only the built-in `tavily` **search** tool.

- Prefer `topic: "news"` for fast-moving developments
- Prefer `search_depth: "advanced"` for important summaries
- Prefer `time_range: "day"` or `time_range: "week"` for latest/trending requests
- Use `start_date` / `end_date` when the user gives an explicit date window
- Prefer `include_domains` for strict domain targeting, for example `["x.com", "twitter.com"]` or `["xiaohongshu.com"]`
- Use `exclude_domains` to suppress obvious noise sources such as `reddit.com`, `youtube.com`, `medium.com`, `facebook.com`
- Use query text `site:x.com` style hints only as a fallback, not as the primary filtering mechanism
- Do **not** assume Tavily `extract`, `crawl`, or `research` APIs are available unless the runtime adds those tools

## Query Patterns

### Social Trend Discovery

Use domain hints inside the query:

```json
{
  "query": "AI agent 热点 近一周",
  "max_results": 8,
  "search_depth": "advanced",
  "topic": "news",
  "time_range": "week",
  "include_domains": ["x.com", "twitter.com", "xiaohongshu.com"],
  "exclude_domains": ["reddit.com", "youtube.com", "medium.com", "facebook.com"]
}
```

Recommended query building:

- Prefer `include_domains: ["x.com", "twitter.com"]` for X public pages
- Prefer `include_domains: ["xiaohongshu.com"]` for Xiaohongshu public pages
- Add `exclude_domains` when the user wants platform-specific discussion, so generic blog mirrors or video pages do not dominate
- Add timeframe words like `today`, `this week`, `近一周`, `最近`
- Add topic anchors like `热点`, `趋势`, `讨论`, `发布`, `评测`

### LLM And Agent Frontier Tracking

```json
{
  "query": "latest LLM releases AI agent frameworks model updates this week",
  "max_results": 8,
  "search_depth": "advanced",
  "topic": "news"
}
```

Recommended sources to bias toward in query wording:

- official blogs
- company announcements
- research labs
- engineering blogs
- launch posts

Example expanded query:

```json
{
  "query": "latest LLM and AI agent progress official blog launch release research this week OpenAI Anthropic Google DeepMind Meta",
  "max_results": 10,
  "search_depth": "advanced",
  "topic": "news",
  "time_range": "week",
  "include_domains": [
    "openai.com",
    "anthropic.com",
    "deepmind.google",
    "blog.google",
    "x.ai",
    "langchain.com"
  ]
}
```

## Output Style

When answering the user:

- Start with a 2-4 sentence headline summary
- Then list the top developments or hot topics
- Include source titles and links when available
- Separate confirmed facts from inferred trend observations

Suggested structure:

1. What is trending
2. Why it matters
3. Representative sources
4. Caveats

## Caveats

- X and Xiaohongshu coverage is limited to publicly discoverable pages Tavily can surface
- Social results may skew toward reposts, public profile pages, or mirrored articles
- For "latest" requests, prioritize recent pages and explicitly mention dates
- If coverage looks sparse, say so instead of overclaiming
