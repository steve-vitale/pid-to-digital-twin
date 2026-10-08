# What it cost, and what it would cost at a plant

Every measured number here comes from [`out/costs.md`](../out/costs.md) (generated from the run records by
`scripts/cost_report.py`) or from another file named beside it. Anything not measured is labeled **assumed** or
**not measured**, never blended in.

## 1. What this project spent (measured)

| Item | Amount | Notes |
|---|---|---|
| Gemini 3.1 Pro API | **$15.30** estimated | Reported tokens priced at deliberately high list rates, so it's an upper estimate, not a bill |
| Gemma 4 31B (hosted, same API) | **$1.28** estimated | Priced at the same rates, which overstates an open model |
| **Total metered model spend** | **$16.57 of a $25 cap** | Ties to the spend ledger `runs/gemini_spend.json` to the cent |
| Claude (claude-opus-5-5, Claude Code CLI) | $0 marginal; **$36.37** API-equivalent | Flat subscription. The CLI reports what the same calls would cost on the API |
| GPT (gpt-6.1-sol, Codex CLI) | $0 marginal; not metered | Flat subscription. The CLI reports no cost, so none is claimed |
| Model compute time | 14.4 h of wall clock across 303 drawing runs | 7.7 h of it was the open-weight model, mostly timeouts |
| Line tracer (code, no AI) | 37 min across 174 runs; 0.3–30 s per sheet | Runs on a laptop CPU |
| Ignition | $0 | Trial mode (2 hours, resettable). Production licensing is quoted by the vendor; not priced here |
| Hardware | $0 extra | One Windows PC |
| Human time | **Not tracked** | The author directed and checked the work; agents wrote most of the code. No hours log was kept, so none is claimed |

## 2. Time and cost per drawing, per model (measured)

From `out/costs.md`. "Serial" is the summed model-call time; tiled runs make 4 calls in parallel, so wall time is
shorter.

| Model | Whole sheet: wall s / $ | Tiled 2×2 (the declared method): wall s / serial s / $ |
|---|---|---|
| GPT via Codex | 119 / not metered | 74 / 223 / not metered |
| Claude | 112 / $0.26 API-equivalent | 89 / 292 / $0.56 API-equivalent |
| Gemini | 64 / $0.13 estimated | 34 / 101 / $0.22 estimated |
| Gemma 4 31B (hosted) | 1,610 incl. timeouts; finished drawings 179–280 s / about $0.07 estimated | not run |

Add about 13 s per sheet for the line tracer.

**Why GPT has no dollar figure:** Codex ran on a subscription and reports no cost. A plant would get a quote or
use API list prices at the time.

## 3. Scaling to a plant: per 1,000 sheets

Machine cost comes from the measured per-sheet figures above (tiled + traced, the declared method). People cost
comes from the measured error rate, but **minutes per correction are assumed**, because they weren't measured here.

| | GPT (best accuracy) | Claude | Gemini (cheapest) |
|---|---|---|---|
| Model cost | not metered here | about $560 API-equivalent | about $220 (upper estimate) |
| Serial compute | about 62 h | about 81 h | about 28 h |
| Wall time with 4 parallel calls | about 21 h | about 25 h | about 10 h |

**Machine cost is small.** Even at API prices it's hundreds of dollars per thousand sheets, with about a day of
unattended runtime.

**People are the real cost.** Here is how to size it:
- **Corrections:** the declared method needed about 16–40 corrections per 100 items on sealed drawings
  ([GOAL.md](GOAL.md) results). The 12-sheet twin has 2,886 review items, about 240 per sheet. At GPT's 17.8 per 100,
  that's roughly 43 corrections per sheet. *Assumes the holdout rate carries over to the twin's items.*
- **Where to look:** the risk tiers put 1,053 of the 2,886 items (36%) in red and amber. The green pile was 94–100%
  right on unseen drawings, so it gets spot checks instead of item-by-item review.
- **Minutes per correction: not measured.** At an *assumed* 1 minute each, 43 corrections is about 45 minutes per
  sheet, or about 700 reviewer hours per 1,000 sheets. At 2 minutes, double it.

**Measure these two at your site before trusting any total:**
1. **The manual baseline:** minutes per sheet to capture the same items by hand.
2. **Minutes per correction:** time real reviewers on a pilot unit.

The saving is (1) minus (machine time + corrections × (2)).

The operator review that would have measured (2) here was deferred by the project owner.

## 4. The offline (air-gapped) option

Estimates, dated October 2026, from [AT_YOUR_PLANT.md](AT_YOUR_PLANT.md) §6:
- a workstation that can run a 30B-class open model: about $20k–$30k (96 GB GPU about $14k–$18k);
- annotation to tune and test it: 200 sheets at 1–2 engineer-hours each, so 200–400 hours.

**Measured here:** the hosted Gemma 4 31B, before any tuning, finished 9 of 12 sheets at about 3–5 minutes each. It
scored about 0.53 symbol F1 where it finished, against about 0.85–0.90 for the cloud models. Self-hosted speed was
not measured.

## 5. What is not measured, and why

| Missing | Why | How to get it |
|---|---|---|
| Token counts for past runs | Not saved by the harness until 2026-10-08 | Recorded on every run from now on (`usage` in each run record) |
| GPT cost | Subscription; the CLI reports none | API list price × tokens, now recorded where the CLI prints them |
| Review minutes, manual baseline | Needs real reviewers; the operator review was deferred | Time a pilot unit (§3) |
| Build effort in people-hours | No hours log | Not reconstructable honestly |
| Ignition / PI production licenses | Vendor-quoted | Ask the vendor or integrator; the build used the free trial |
| Self-hosted open-model speed | Ran on a hosted endpoint only | Benchmark on the target GPU before buying |
