---
name: market-intel
description: "Use Tavily search for market intelligence on public companies. Best for: recent company news, event timelines, catalyst summaries, and media-reported stock moves. In this project, use the built-in `tavily` search tool only; do not assume a real-time market data API is available."
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

## When NOT to Use

❌ **DON'T use this skill when:**

- The user requires precise real-time quote data or exchange-grade pricing
- The task needs historical OHLCV data, fundamentals, or portfolio analytics
- The user wants investment advice or a buy/sell recommendation

## Tooling Boundary

This repository currently exposes only the built-in `tavily` **search** tool.

- Prefer `topic: "news"` for recent company coverage
- Use `search_depth: "advanced"` for company-specific synthesis
- Do **not** promise exact market prices unless separately verified with a market data tool
- Treat stock-price movement as a **reported media narrative**, not a guaranteed causal fact

## Query Patterns

### Recent Company News

```json
{
  "query": "Tesla latest news today earnings guidance analysts site:reuters.com OR site:bloomberg.com OR site:cnbc.com",
  "max_results": 8,
  "search_depth": "advanced",
  "topic": "news"
}
```

### Price Move Context

```json
{
  "query": "NVIDIA stock up down today why latest news catalysts Reuters CNBC MarketWatch",
  "max_results": 8,
  "search_depth": "advanced",
  "topic": "news"
}
```

### Earnings And Event Timeline

```json
{
  "query": "Apple recent earnings guidance product launch regulatory news timeline",
  "max_results": 10,
  "search_depth": "advanced",
  "topic": "news"
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
