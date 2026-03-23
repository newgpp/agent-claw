---
name: market-intel
description: "Use Tavily search for market intelligence on public companies. Trigger this skill for requests about 股价, 财报, 最近新闻, 时间线, 为什么涨跌, 市场怎么看, 催化剂, ticker/company latest updates, or prompts such as '查询特斯拉最近两周的重要新闻，并结合股价表现整理时间线'. Best for: recent company news, event timelines, catalyst summaries, and media-reported stock moves. In this project, prefer `topic: \"finance\"`, `time_range`, and strict `include_domains` / `exclude_domains` filtering so results stay anchored to mainstream financial publishers and company IR pages rather than noisy forums, video pages, or generic mirrors. Do not assume a real-time market data API is available."
homepage: https://docs.tavily.com/documentation/agent-skills
metadata: { "openclaw": { "emoji": "📈", "requires": { "env": ["TAVILY_API_KEY"] } } }
---

# Market Intel

Track recent public-company news and summarize reported price-move drivers.

## When to Use

✅ **USE this skill when:**

- The user asks for the latest news about a US-listed company
- The user wants to know what may have moved a stock recently
- The user needs a recent event timeline for earnings, guidance, products, M&A, regulation, or analyst reactions
- The user wants a quick market-intelligence brief for one or more tickers
- The request mentions finance-language triggers such as `股价`、`涨跌`、`财报`、`最近新闻`、`事件时间线`、`市场怎么看`
- The user asks for recent developments about a named public company or ticker such as `Tesla/TSLA` or `NVIDIA/NVDA`
- Typical queries include `最近 7 天/两周发生了什么`、`为什么涨跌`、`整理事件时间线`

## When NOT to Use

❌ **DON'T use this skill when:**

- The user requires precise real-time quote data or exchange-grade pricing
- The task needs historical OHLCV data, fundamentals, or portfolio analytics
- The user wants investment advice or a buy/sell recommendation

## Tooling Boundary

This repository currently exposes only the built-in `tavily` **search** tool.

- Prefer `topic: "finance"` for public-company news and reported stock-move context
- Use `search_depth: "advanced"` for company-specific synthesis
- Prefer `time_range: "day"` or `time_range: "week"` for latest company coverage
- Use `start_date` / `end_date` when the user gives an explicit date window
- Prefer `include_domains` to keep results anchored to mainstream financial publishers and company IR pages
- Use `exclude_domains` aggressively to suppress low-signal mirrors, forums, video pages, social posts, tokenized-stock pages, and generic content farms
- If the first search returns noisy sources, tighten domain filters before trying a broader query
- Do **not** promise exact market prices unless separately verified with a market data tool
- Treat stock-price movement as a **reported media narrative**, not a guaranteed causal fact

## Source Priority

For company-news and stock-move requests, prefer sources in roughly this order:

1. Company IR / newsroom / earnings materials
2. Reuters
3. Bloomberg
4. CNBC
5. MarketWatch / Yahoo Finance / WSJ / Barron's / Morningstar

Avoid leaning on these unless the user explicitly asks for them or coverage is genuinely sparse:

- YouTube
- Reddit
- Facebook
- Threads
- Medium
- personal blogs
- crypto tokenized-stock pages
- generic charting pages
- forum mirrors and content farms

When the user asks "为什么涨跌" or "市场怎么看":

- Prefer reports that tie a stock move to a dated catalyst
- Prefer mainstream finance coverage over generic opinion pieces
- Prefer one or two cleaner searches over many noisy retries

## Query Patterns

### Recent Company News

```json
{
  "query": "Tesla latest news earnings guidance analysts",
  "max_results": 8,
  "search_depth": "advanced",
  "topic": "finance",
  "time_range": "week",
  "include_domains": [
    "tesla.com",
    "reuters.com",
    "bloomberg.com",
    "cnbc.com",
    "finance.yahoo.com",
    "marketwatch.com"
  ],
  "exclude_domains": ["youtube.com", "facebook.com", "reddit.com", "medium.com", "mexc.com"]
}
```

### Price Move Context

```json
{
  "query": "NVIDIA stock up down why latest news catalysts",
  "max_results": 8,
  "search_depth": "advanced",
  "topic": "finance",
  "time_range": "week",
  "include_domains": [
    "nvidia.com",
    "reuters.com",
    "bloomberg.com",
    "cnbc.com",
    "finance.yahoo.com",
    "marketwatch.com",
    "morningstar.com"
  ],
  "exclude_domains": [
    "youtube.com",
    "facebook.com",
    "threads.com",
    "reddit.com",
    "medium.com",
    "mexc.com",
    "tradingview.com",
    "forex.com"
  ]
}
```

### Earnings And Event Timeline

```json
{
  "query": "Apple recent earnings guidance product launch regulatory news timeline",
  "max_results": 10,
  "search_depth": "advanced",
  "topic": "finance",
  "time_range": "month",
  "include_domains": [
    "apple.com",
    "reuters.com",
    "bloomberg.com",
    "wsj.com",
    "cnbc.com",
    "finance.yahoo.com",
    "marketwatch.com"
  ],
  "exclude_domains": ["youtube.com", "facebook.com", "reddit.com", "medium.com"]
}
```

### Stock Move Triage

When the user specifically asks about a recent rise/fall:

```json
{
  "query": "NVIDIA stock down why latest catalyst analyst commentary",
  "max_results": 6,
  "search_depth": "advanced",
  "topic": "finance",
  "time_range": "week",
  "include_domains": [
    "reuters.com",
    "bloomberg.com",
    "cnbc.com",
    "marketwatch.com",
    "finance.yahoo.com",
    "morningstar.com"
  ],
  "exclude_domains": [
    "youtube.com",
    "facebook.com",
    "threads.com",
    "reddit.com",
    "medium.com",
    "mexc.com",
    "tradingview.com"
  ]
}
```

## Output Style

When answering:

- Name the company and exact date range used
- Summarize the top 3-5 recent developments
- If discussing price movement, say `reported drivers` or `likely catalysts`
- Distinguish:
  - confirmed events
  - analyst/media interpretation
  - your inference

Suggested structure:

1. Latest headline summary
2. Event timeline
3. Reported price-move drivers
4. Source links

## Caveats

- Tavily can surface finance news, but it is not a dedicated quote feed in this project
- If the user asks for exact percentage change or current price, say that price precision is not guaranteed here
- Prefer mainstream financial publishers and company IR pages when possible
