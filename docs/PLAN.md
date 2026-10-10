# SPY News-Trading Bot — Plan

A bot that reads market news during market hours, asks a fast decision model whether to buy a SPY call, a SPY put or nothing, and places the order through Robinhood Agentic Trading. It starts with $100 of real money and needs no per-trade approval.

## Decisions so far

| Topic | Decision |
| --- | --- |
| What we trade | SPY options only (no SPX) |
| Allowed actions | Buy a call, buy a put, or do nothing. No selling to open. |
| Money | Real money from the start, $100 in the Robinhood agentic account. No practice mode. |
| Autonomy | Fully autonomous. No trade waits for approval. |
| Trigger | News first. Other factors are added later as extra context for the model. |
| Hours | Only act on news during regular market hours (9:30 AM–4:00 PM ET) |
| Decision model | Microsoft-Decision-1 or TypeSafe Jev through OpenRouter, picked by benchmark + logged results |
| AI budget | $2/day, all of it for the decision model for now. Can grow later. |
| News data | Free sources only for now |
| Where it runs | Cloud server in Ashburn, VA: AWS us-east-1 recommended (see Cloud server). The Mac can't use Ethernet. |
| Latency tactics | Warm connection, OpenRouter balance kept above $10, everything prepared before news hits (mandatory). Backup requests come later. |
| Priority | Lowest possible Total Trade Latency |

## How it works

One program runs during market hours. AI makes the call; plain code enforces every limit.

1. **Listen.** News feeds push headlines in. Each one gets a "received" timestamp, and duplicates are dropped.
2. **Keep a market snapshot (always updating).** SPY price, move today, move in the last few minutes, move since the headline, VIX, time to close, today's scheduled events with expected values, recent headlines, and a short "what's going on" summary refreshed every few minutes.
3. **Decide.** One decision-model call gets the headline + snapshot and answers: does this move SPY, buy call / buy put / no trade, is it already priced in, how big a move.
4. **Check risk rules (plain code, never AI).** Market hours only, one position at a time, confidence above our threshold, contract fits the cash.
5. **Pick the contract (plain code).** Prepared before the headline: nearest expiry, closest strike to the current price that fits the cash. Limit order at the ask plus a small buffer.
6. **Send the order** through Robinhood's agent connection (MCP).
7. **Exit (plain code).** See Exits.
8. **Log everything.** Headline, every timestamp, model probabilities, order, fill, result. This is how we check whether the model's confidence is real.

## News sources

Start with three free sources: one broad streaming feed, the government sources that move the S&P during market hours, and presidential posts.

| Source | What it covers | Speed | Cost | Status |
| --- | --- | --- | --- | --- |
| [Alpaca news stream](https://alpaca.markets/blog/introducing-news-api-for-real-time-fiancial-news/) (Benzinga content) | Broad: macro, companies, politics, tagged by ticker | Seconds, pushed to us | Possibly free on the basic plan | Backbone. Confirm the free plan still includes the live stream. |
| Fed + government press releases (Fed, Treasury, White House) | FOMC statements (2:00 PM ET), Fed speeches, policy | The original source | Free | Check every 1–2 seconds during known event windows |
| Presidential social posts | Tariff and policy posts that have moved the S&P during the trading day | Seconds, if we find a fast feed | Not known yet | Research a fast, free way to get them |
| X accounts that repost Bloomberg/Reuters headlines | Fast relays of the big newswires | Seconds | X API is paid | Skipped for now (paid) |

The same Alpaca account can supply live SPY prices for the market snapshot. On the free plan that price comes from one exchange (IEX) only, which is fine for direction but not exact. If Alpaca's live news turns out to be paid, the fallback is free news RSS feeds, which are slower.

## Decision model (OpenRouter Decisions API)

Microsoft-Decision-1 (released Oct 9, 2026) and TypeSafe Jev are both live on OpenRouter and both cost $0.042 per 1M input tokens with free output. Neither is a chat model. Both return a probability for each answer we offer.

| | Microsoft-Decision-1 | TypeSafe Jev 1.13 |
| --- | --- | --- |
| OpenRouter id | `microsoft/microsoft-decision-1` | `typesafe/jev-1.13` |
| Provider | Azure | TypeSafe |
| Max input | 32,768 tokens | 64,000 tokens |
| Model time | No figure yet | ~0.14 s on its OpenRouter page |

**Endpoint:** `POST https://openrouter.ai/api/alpha/decisions` (labelled alpha; it may change). A request has `model`, `state` (headline + market snapshot) and `questions`. Question types:

- `noul`: yes/no, returns the probability of yes
- `choice`: pick one label, returns the pick, a confidence and a probability per label
- `score`: an ordered scale, returns a score and a probability per level

**Draft questions for each headline (one call answers all four):**

| Name | Type | Question | Answers |
| --- | --- | --- | --- |
| `moves_spy` | noul | Will this move SPY noticeably in the next 15 minutes? | yes / no |
| `action` | choice | What should we do? | BUY_CALL / BUY_PUT / NO_TRADE |
| `priced_in` | noul | Has SPY already moved on this news? | yes / no |
| `size` | score | How big a move? | small / medium / large |

**Cost:** about 1,500 tokens per headline, so about $0.06 per 1,000 headlines and $0.19–$0.63/day for 3,000–10,000 headlines. That fits inside $2/day. A larger "market summary" model would come out of a future budget.

**Caveat:** "90% means right 9 times in 10" comes from the model makers' own benchmarks, not markets. Our logs have to show that it holds for SPY headlines before we trust it.

## Execution with $100

Our program connects to Robinhood's agent server and calls its order tools directly, with no chatbot in between.

- **Connection.** Robinhood Agentic Trading uses a separate account, and the agent can only touch money in it. Robinhood says agents can trade stocks and options ([Q2 2026 results](https://investors.robinhood.com/node/16381/pdf)). Access is through Robinhood's hosted MCP server with a browser sign-in. You sign in yourself; the bot never handles your password.
- **Unknown #1: are SPY option orders available through it?** One third-party integration ([Gumloop's docs](https://docs.gumloop.com/nodes/mcp/robinhood.md)) lists only stock and ETF orders. The first test connects and prints the server's tool list.
- **What $100 buys.** One contract costs its quoted price × 100, so the bot can only buy contracts quoted under about $1.00. If nothing fits, it skips the trade.
- **Limit orders, not market orders.** Option spreads widen on news. We send a limit at the ask plus a small buffer.
- **Settlement.** Options settle the next business day. With $100 the account is effectively cash-only (margin needs $2,000+), so expect roughly one round trip per day. Confirm once the account is open.
- **Day-trade rule.** The SEC approved removing the $25,000 pattern-day-trader rule on April 14, 2026, effective June 4, 2026; brokers have until October 20, 2027 to switch ([Schwab summary](https://advisorservices.schwab.com/story/sec-approves-scrapping-25000-day-trader-minimum)). Check how Robinhood applies it to agentic accounts.
- **Safety net.** If Robinhood's agent server supports stop orders on options, place one right after each fill so an outage on our side can't leave a position unmanaged.

## Cloud server

Run the bot in Ashburn, Virginia. Almost everything it talks to is there or enters through an Ashburn edge.

| Endpoint | Where it is | Verified? |
| --- | --- | --- |
| OpenRouter | Cloudflare, Ashburn (IAD) edge | Yes |
| Alpaca news + prices | Google Cloud us-east4 (Ashburn) | Yes |
| Robinhood (`agent.robinhood.com`, `api.robinhood.com`) | Amazon CloudFront edges in Ashburn; backend probably AWS us-east-1 | Edge yes, backend no |
| Decision-1 (Azure) | Region not published yet | No |
| Jev (TypeSafe) | Cloudflare front; backend not visible | No |

| Option | Location | Size | Cost | Catch |
| --- | --- | --- | --- | --- |
| **AWS EC2 t4g.small (pick)** | us-east-1 | 2 vCPU / 2 GB | Free trial hours through Dec 31, 2026 ([EC2 FAQ](https://aws.amazon.com/ec2/faqs/)) | Public IPv4 is $3.65/mo extra ([VPC pricing](https://aws.amazon.com/vpc/pricing/)) |
| AWS Lightsail (after the trial) | us-east-1 | 2 vCPU / 1 GB | $7/mo, IPv4 included ([pricing](https://aws.amazon.com/lightsail/pricing/)) | None found |
| Oracle Always Free (runner-up) | Ashburn | Arm, up to 2 OCPU / 12 GB | $0 ([docs](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm)) | Reclaimed if idle 7 days; Ashburn must be your home region |

Ruled out: Hetzner Ashburn ($20.49/mo since June 2026), Google's free tier (doesn't include Ashburn), and New Jersey/NYC hosts (an estimated 5–8 ms farther, not measured).

## Total Trade Latency (TTL)

TTL = time from a source publishing a headline to our order being filled. We log every stage, every time.

| Stage | Clock points | What sets it | How we cut it |
| --- | --- | --- | --- |
| Feed | published → received | The news source | Push feeds (websockets), not polling; drop slow sources |
| Decide | received → decision back | Model + network | Ashburn server, warm connection, one call, small snapshot |
| Order | decision → order sent | Our code | Contract and order pre-built before news hits |
| Broker | order sent → acknowledged → filled | Robinhood + market maker | Warm connection, limit at ask + small buffer |

- Server clock synced to AWS Time Sync so timestamps compare across sources.
- Dashboard of p50 and p95 per stage. If p95 goes over budget, the bot pauses itself.
- Starting target for the part we control (received → order sent): under 500 ms at p95. Tighten once measured.
- What TTL can't do: SPY and ES futures reprice within about 5 ms of a macro surprise ([Chordia, Green & Kottimukkalur 2018](https://ideas.repec.org/a/oup/rfinst/v31y2018i12p4650-4687..html)). Low TTL keeps us from being late to moves that last minutes. It doesn't win the first jump.

### Where the time actually goes

Our own code is the smallest part. Optimize the biggest stage first, measured, not guessed.

| Stage | Rough size | Biggest lever |
| --- | --- | --- |
| Feed (free sources) | Seconds | Go to the original source (e.g. the Fed's site) for scheduled events; drop slow feeds |
| Decision model | ~140 ms for Jev (OpenRouter's figure); Decision-1 not measured | Fast path below; skip OpenRouter's hop only if the benchmark shows it matters |
| Network from Ashburn | ~1–2 ms per hop (estimate) vs ~12–100 ms from home Wi-Fi | The Ashburn server |
| Robinhood order | Not measured | Warm connection; measure first |
| Our code (parse, check, build order) | Under 1 ms in Python | Nothing yet. A compiled language (Rust/C++) saves microseconds, which only matters once everything above is in single-digit ms. |

Unknowns that could change the server choice: Decision-1's Azure region and Jev's backend location. One unverified report places Jev on the US West Coast, which would add ~60–70 ms per call from any East Coast server. The benchmark run from the server settles this.

### Fast path for scheduled events

For scheduled releases we know the time and the possible outcomes in advance. So we ask the decision model **before** the release, once per scenario. Example: Fed holds / cuts 25 / cuts 50 / hikes, each with the market snapshot as of 1:59 PM. The answers are stored as a lookup table.

At 2:00:00 the bot only has to read the result from the original source and look up the pre-made decision. That takes the model out of TTL entirely (~0 ms decision time), the same way the fastest firms trade structured data rather than reading text. Unscheduled headlines still go through the live model call.

## Market awareness

The decision model knows nothing about today. It only sees what we put in `state`. It is also built on an older base model, and old knowledge can hurt: GPT's prior knowledge of companies made sentiment backtests worse, and removing company names helped ([Glasserman & Lin](https://arxiv.org/abs/2309.17322)).

So every call carries facts, not assumptions:

1. **Surprise, not level.** The expected value next to the actual one (e.g., "CPI 3.1% vs 3.0% expected"). Markets move on the surprise.
2. **Price already moved?** SPY's change since the headline arrived, and over the last 1, 5 and 15 minutes.
3. **Today's backdrop.** SPY change on the day, VIX, time to close, today's scheduled events.
4. **Recent narrative.** The last 10–20 headlines, built in code (no extra AI cost). An AI-written summary can come later when the budget grows.
5. **Clear rules in the question.** Each answer's `criteria` spell out what counts as BUY_CALL / BUY_PUT / NO_TRADE.

We log every probability and check it against what SPY actually did (calibration by news category), before raising size or lowering thresholds.

## Exits

Research says most of a news move happens in the first minute, overshoots are corrected within 2–3 minutes, and volatility stays high for about 15 minutes ([Ederington & Lee 1993](https://ideas.repec.org/a/bla/jfinan/v48y1993i4p1161-91.html)). Real shocks can hold all day (Apr 9, 2025: S&P +9.5%). False ones reverse fast (Apr 7, 2025: a fake tariff-pause report reversed in about 20 minutes, [Fortune](https://fortune.com/2025/04/07/trump-tariff-pause-walter-bloomberg-fake-report-debunked-markets/)).

**Proposed exit rules (starting values, tuned from logs):**

1. **Thesis stop:** exit if SPY falls back to where it was when the headline arrived. That means the news didn't stick. It is based on SPY, not the option price, which swings too much on spreads.
2. **Trailing stop instead of a fixed profit target:** once SPY has moved our way, exit if it gives back half of its best move since entry. No cap on winners, and we keep at least half of the gain.
3. **Time stop by news type:**
    - Unscheduled headline: 30 minutes max.
    - FOMC statement trade: hold into the press conference. The statement move correlates 44% with the press-conference move, which settles about 20 minutes into the Q&A ([LBS research](https://lbsresearch.london.edu/id/eprint/2203)). Exit by about 2:50 PM ET.
4. **Option-value stop:** exit if the option's value is down 50%, whatever SPY does. This catches time decay and volatility dropping after scheduled events ([VIX falls over ~45 min after FOMC](https://research.ou.nl/en/publications/when-no-news-is-good-news-the-decrease-in-investor-fear-after-the/)).
5. **Hard close:** flat by 3:45 PM ET. Same-day options lose value fastest late in the day.
6. **Entry cost filter:** skip the trade if the option's bid-ask spread is over 10% of its mid price.

## Autonomy and guardrails

No trade waits for approval (Robinhood's agentic account allows this). Safety comes from plain-code limits that pause the bot. It never asks for approval.

- Runs as an auto-restarting service on the server. Starts before the open, stops after the close.
- Pauses itself on: daily loss limit hit, 3 losses in a row, TTL p95 over budget, model or broker errors, or a stale market snapshot.
- Kill switch: one command stops trading and closes any open position.
- One phone notification per trade and one end-of-day report (free tool such as ntfy).
- A safety stop order at Robinhood after every fill, if the agent server supports it.

## Strategy reality check

Honest summary: the speed race on SPY is already lost, and retail short-dated options lose money on average. Any edge has to come from judgment over minutes, specific news types, and keeping costs low.

- **Speed:** SPY/ES reprice within about 5 ms of macro surprises. Even the fastest firms only make about $19k per event in SPY ([Chordia et al.](https://ideas.repec.org/a/oup/rfinst/v31y2018i12p4650-4687..html)). After Thomson Reuters' 2-second early release, most of the price change happened in under 200 ms ([Hu, Pan & Wang](https://ideas.repec.org/a/eee/jfinec/v126y2017i2p399-421.html)).
- **LLM news alpha fades:** in Lopez-Lira & Tang, the strategy's Sharpe ratio fell from 6.54 (late 2021) to 1.22 (early 2024). It was mostly small stocks, and it lost money at 20 bps round-trip costs ([paper](https://arxiv.org/html/2304.07619v6)). No study found a tradable seconds-scale LLM edge on SPY.
- **Retail 0DTE results:** retail lost $70M+ in SPX 0DTE (2021–2023), with about 60% of losses from trading costs and effective spreads of 4.9–6.1% ([summary of Beckmeyer, Branger & Gayda](https://www.wealthmanagement.com/equities/retail-investors-are-in-love-with-same-day-options)).
- **Big firms on generative AI:** Citadel's Ken Griffin said it "falls short" for finding alpha ([Bloomberg Government](https://news.bgov.com/new-york-brief/griffin-says-genai-fails-to-help-hedge-funds-beat-markets-1)).

**Where a ~1-second trader might still have an edge (to test, not assume):**

1. **Fed press conferences:** the best-documented slow adjustment for the index (44% correlation, minutes-long).
2. **False or recycled headlines:** fading moves that should reverse (Apr 7, 2025; the 2013 fake AP tweet). Plausible, but no study shows systematic profit.
3. **Major unscheduled policy shocks:** rare, but the move can continue for hours.

**What this means for the build:** NO_TRADE is the default. We log the model's answer and what SPY did next for **every** headline, including the ones we don't trade. With one round trip a day, that is the only way to learn fast. News categories that lose get switched off automatically.

## Future blueprints

Not part of v1. Captured so they aren't lost.

### Fed press conference strategy

The best-documented slow index reaction: the S&P move in the 2:00 PM statement window correlates 44% with the move during the 2:30 PM press conference. The effect builds during the minutes when the Chair explains what changed in the statement, and settles about 20 minutes into the Q&A ([LBS research](https://lbsresearch.london.edu/id/eprint/2203)).

1. **2:00 PM statement:** use the scheduled-event fast path to enter in the direction of the surprise.
2. **2:30 PM press conference:** turn the live broadcast into text sentence by sentence (speech-to-text), and score each sentence with the decision model: more hawkish, more dovish, or no change vs the statement.
3. **Hold or exit:** hold while the Chair's remarks confirm the statement's direction. Exit early if they contradict it. Exit by ~20 minutes into the Q&A at the latest.
4. **Watch IV:** volatility falls for about 45 minutes after the statement, which shrinks long option value even if SPY doesn't move.

Needs: a live audio source and a fast speech-to-text service (budget TBD), plus past press conferences with minute-level SPY data to test against.

## Next steps and open questions

**Setup (you):**

- [ ] GitHub sign-in (`gh auth login`) and the commit name/email for this repo
- [ ] Open the Robinhood agentic account, fund $100, get options approval to buy calls and puts
- [ ] OpenRouter account and API key; keep the balance above $10 and set no per-key limit
- [ ] Free Alpaca account (news + SPY prices)
- [ ] AWS account (or Oracle) for the Ashburn server

**Build (Claude):**

- [ ] Run `bench/bench_decision1.py` from the Ashburn server: Decision-1 vs Jev
- [ ] Script 1: connect to Robinhood's agent server and print its tool list (you sign in yourself)
- [ ] Logging format with every TTL timestamp and every model probability
- [ ] Scheduled-event fast path (pre-decided lookup table), FOMC first

**Open questions:**

- [ ] Exit rules: OK with the proposed starting values?
- [ ] Does Robinhood's agent server support SPY option orders and stop orders on options?
- [ ] Does Alpaca's free plan still include the live news stream?
- [ ] A fast, free way to get presidential posts?

## Conversation log

1. **Can I build my own software that trades through Robinhood, and is it free?** Yes: Agentic Trading (via MCP, separate account) and the Crypto Trading API (crypto only). No subscription found.
2. **Plan the setup: fastest public news, Decision-1 + OpenRouter, dependencies.** Agentic Trading supports options. Decision-1 is a decision scorer, not a chatbot. Our edge is judgment, not speed. Proposed the headline → model → risk rules → order pipeline.
3. **Answers:** build it real (no practice mode), SPY only, $10/day budget, aim for ~1 s, market hours only, model must know the market, $100 start, buy calls/puts only. Created the plan doc.
4. **Latency through OpenRouter; local only; no paid news; $2/day.** Measured about 30 ms to OpenRouter on a warm connection from the Mac, with Wi-Fi spikes of ~100 ms. Wrote the Decision-1 vs Jev benchmark.
5. **No Ethernet, so research a cheap, fast cloud server. Warm connection, balance above $10 and pre-built orders agreed; backup requests later. Budget is for the decision model only. Make this repo. Exits: don't cut winners short, don't give it all back. Concerns: market awareness, TTL, profitable and fully autonomous.** Research findings and proposals are in the sections above.
6. **Is AWS the fastest for everything? Anything goes (custom compilers etc.) for the lowest ms. Getting to 1 s will be hard. Add the Fed press conference as a future blueprint. Keep the plan in the repo. Is all the alpha gone?** Ashburn is the best single location for our endpoints; our code is under 1 ms, so compilers come last. The big wins are the original-source feed and the pre-decided fast path for scheduled events. The press conference plan is under Future blueprints. Alpha isn't all gone: the speed edge on obvious SPY headlines is, but interpretation over minutes, false-headline fades and specific event types are still open questions for our logs to answer.

## Sources

- [OpenRouter – Microsoft-Decision-1](https://openrouter.ai/microsoft/microsoft-decision-1) · [TypeSafe Jev](https://openrouter.ai/typesafe/jev-1.13) · [Decisions API](https://openrouter.ai/docs/api/api-reference/alphadecisions/submit-a-decisions-questions-and-answers-request) · [Latency and performance](https://openrouter.ai/docs/features/latency-and-performance)
- [Microsoft – Introducing Microsoft-Decision-1](https://commandline.microsoft.com/microsoft-decision-1-model-foundry/)
- [Robinhood – Open to Agents](https://robinhood.com/newsroom/robinhood-is-now-open-to-agents/) · [Q2 2026 results](https://investors.robinhood.com/node/16381/pdf)
- [Alpaca – News API](https://alpaca.markets/blog/introducing-news-api-for-real-time-fiancial-news/)
- [AWS EC2 FAQ](https://aws.amazon.com/ec2/faqs/) · [AWS Lightsail pricing](https://aws.amazon.com/lightsail/pricing/) · [Oracle Always Free](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm)
- [Chordia, Green & Kottimukkalur 2018](https://ideas.repec.org/a/oup/rfinst/v31y2018i12p4650-4687..html) · [Hu, Pan & Wang 2017](https://ideas.repec.org/a/eee/jfinec/v126y2017i2p399-421.html) · [Ederington & Lee 1993](https://ideas.repec.org/a/bla/jfinan/v48y1993i4p1161-91.html)
- [Lopez-Lira & Tang](https://arxiv.org/html/2304.07619v6) · [Glasserman & Lin](https://arxiv.org/abs/2309.17322)
- [Retail 0DTE losses (Beckmeyer et al. summary)](https://www.wealthmanagement.com/equities/retail-investors-are-in-love-with-same-day-options) · [Bryzgalova, Pavlova & Sikorskaya](https://doi.org/10.1111/jofi.13285)
- [FOMC statement vs press conference (LBS)](https://lbsresearch.london.edu/id/eprint/2203) · [VIX after FOMC](https://research.ou.nl/en/publications/when-no-news-is-good-news-the-decrease-in-investor-fear-after-the/)
- [Apr 7, 2025 false report (Fortune)](https://fortune.com/2025/04/07/trump-tariff-pause-walter-bloomberg-fake-report-debunked-markets/) · [Griffin on GenAI](https://news.bgov.com/new-york-brief/griffin-says-genai-fails-to-help-hedge-funds-beat-markets-1)
- [Schwab – end of the $25k day-trader rule](https://advisorservices.schwab.com/story/sec-approves-scrapping-25000-day-trader-minimum)
