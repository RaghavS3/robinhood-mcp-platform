# robinhood-mcp-platform

Autonomous trading on Robinhood Agentic Trading (Robinhood's MCP server), built to grow into a platform for several strategies.

**First strategy:** trade SPY options on market news. Each headline gets scored by a fast decision model (Microsoft-Decision-1 or TypeSafe Jev, through OpenRouter's Decisions API) together with a live market snapshot. The bot then buys a SPY call, buys a SPY put, or does nothing.

> This trades real money with no per-trade approval. Long options can lose 100% of what was paid.

## Status

Planning and latency benchmarks. There is no trading code yet.

## Layout

| Path | What it is |
| --- | --- |
| [`docs/PLAN.md`](docs/PLAN.md) | Plan, decisions, research and open questions |
| [`bench/bench_decision1.py`](bench/bench_decision1.py) | Latency benchmark: Decision-1 vs Jev through OpenRouter |

## Run the benchmark

Needs Python 3.9+ and no extra packages.

```bash
export OPENROUTER_API_KEY=...   # set it in your shell; never commit it
python3 bench/bench_decision1.py
```

Without a key it only measures the network path to OpenRouter. A full run costs less than $0.01.
