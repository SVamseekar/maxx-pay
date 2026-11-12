# Maxx

**Buy together. Pay less.** When many people want the same product, they join a **Bloc**: each
approves a **PayPal hold** for the most they would pay, and AI agents bargain with sellers for
all of them at once. Each buyer is charged only the price they were allocated, never more than
their hold, and the hold is released in full if no deal closes. Sellers are paid through PayPal
when the parcel arrives.

**Live demo:** https://pay.souravamseekar.com · **Demo video (3 min):** https://youtu.be/XfvxrhKwsSg ·
**Judges:** start at [`/judge`](https://pay.souravamseekar.com/judge) · MIT licensed

Built for the **PayPal AI Hackathon**. Money moves through the **PayPal sandbox** (Orders,
Payments, Payouts, Webhooks, JavaScript SDK v6); the agents run on **NVIDIA Nemotron** models on
**Nebius Token Factory**. The AI layer was also entered in another hackathon; see
[Disclosure](#disclosure).

## Try it (judges)

1. Open [`/judge`](https://pay.souravamseekar.com/judge) first. The free API sleeps when idle;
   the first visit takes about a minute while a banner shows it waking.
2. Enter the judge access code from the submission notes. You get your own guest account at once:
   no email, no password.
3. **Try successful deal** opens your private copy of a Bloc with 600 simulated buyers and eight
   seller agents. Set your maximum and **Join with a PayPal hold**: PayPal's real sandbox opens, and
   you approve the hold with a PayPal sandbox test buyer account. No real money moves.
4. **Close Bloc & negotiate** and watch the rounds stream in: Nemotron 3 Ultra negotiates for the
   group, Nemotron 3 Super runs each seller agent, and a deterministic engine sets every price.
   Your hold is captured at your allocated price and the rest released; **How this run was
   decided** shows who was served and why the others were not.
5. Add a delivery address under **Orders**. The simulated seller ships with simulated tracking,
   and on delivery the seller is paid through a real PayPal sandbox payout. **Group books** shows
   the capture, Maxx's fee, PayPal's own fees and the payout.
6. **Scan**: the **Live example** runs the full pipeline (vision, web search, verdict), and
   **Let the agent buy it** shows the guarded checkout.
7. **Under the hood** lists every model call with its model id, latency and cost.

Your hold, capture and the payout are real PayPal sandbox transactions. The other 600 buyers and
the eight sellers are simulated, labelled everywhere, and place no holds.

## A real group in the PayPal sandbox (11–12 November 2026)

To show the group mechanism working in PayPal itself, not only for one buyer, we filled the
shared "successful deal" Bloc on the live site with real PayPal sandbox holds and ran it once:

| | |
|---|---|
| Buyers in the group | 1,603: **1,003 with real PayPal sandbox holds** and 600 simulated |
| How the real holds were placed | 1,000 by scripted test buyers, each a real Orders v2 `AUTHORIZE` paid with PayPal's sandbox test card (`/demo/bulk/buyer`, off unless a secret token is set); 3 by sandbox buyer accounts approving in PayPal's popup |
| Held in total | $151,973.00 |
| Negotiation | 5 live rounds, Nemotron 3 Ultra negotiator and eight Nemotron 3 Super seller agents, 50 model calls, about $0.05 |
| Outcome | 450 buyers served at $130 to $134 by three sellers, 1,153 not served |
| Settlement in PayPal | **225 partial captures, $29,700.00; 778 holds voided, $109,929.00; 0 failed** |
| Seller payouts | 92% per order through PayPal Payouts, each seller agent paid into its own sandbox Business account (`PAYPAL_SELLER_RECEIVERS`). 43 payouts ($5,216.40) went through; the sandbox then refused the rest with `INSUFFICIENT_FUNDS`, so they wait and are retried hourly |

The 1,000 card buyers and the sandbox accounts are test accounts we created and drove by script,
not people. PayPal calls are paced at 40 a minute (`PAYPAL_CALLS_PER_MINUTE`), because the sandbox
blocks an address for five minutes after 50 calls in a minute; at that pace the run took about an
hour to join and about an hour to settle.

What the run taught us, and what production would need:

- **Payouts need cleared funds.** In the sandbox, captured card money was not available to
  Payouts. A live marketplace would pay sellers through PayPal's marketplace product
  (Multiparty / Complete Payments Platform), where each capture goes to the seller with Maxx's
  fee as a platform fee, rather than holding money and paying out later.
- **The payee is unknown when the hold is placed.** A PayPal order names its payee at creation,
  but the seller that wins is only known after the negotiation. Production needs either PayPal's
  approval for a platform that holds and disburses, or a second, smaller approval to the winning
  seller.
- **Rate limits shape the design.** Settlement, payouts and webhook checks share one paced budget;
  money calls go first and webhooks are deferred (PayPal retries them for three days).

## How Maxx uses PayPal

| PayPal API | What Maxx does with it | Code | Where you see it |
|---|---|---|---|
| JavaScript SDK v6 | The buyer approves the hold in PayPal's own popup | `apps/web/app/components/paypal-approval.tsx` | **Join with a PayPal hold** |
| Orders v2, `intent: AUTHORIZE` | One order per join, for the buyer's maximum; then authorized | `services/api/maxx/money/service.py` | The hold dialog |
| Payments v2: capture an authorization | Captures only the allocated price, `final_capture: true`, so the rest of the hold is released | `money/service.py` | The outcome card's PayPal ids |
| Payments v2: void | Releases the whole hold for buyers who were not served, or when no deal closes | `money/service.py` | **Try no deal** |
| Orders v2: track | Adds the seller's tracking number to the buyer's PayPal order | `services/api/maxx/fulfilment/service.py` | Orders |
| Payouts v1 | Pays each seller per order on delivery (92%), and follows each item to `SUCCESS` | `fulfilment/service.py` | **Group books** |
| Payments v2: refund | Refunds orders cancelled before shipping, orders not shipped in time, and resolved problem reports | `fulfilment/service.py` | Orders |
| Orders v2, `intent: CAPTURE` | Agentic checkout of a single verified offer, after a server-side guard re-checks it | `money/checkout.py` | **Let the agent buy it** |
| Webhooks | Signature checked with PayPal, each event applied once; captures, voids, payouts, subscriptions | `money/webhooks.py` | **Group books** updates |
| Subscriptions v1 | Maxx Plus (higher agent-checkout limit), switched on only by the `ACTIVATED` webhook | `money/subscriptions.py` | Account |

How the money stays safe:

- **The AI never touches money.** Agents only bargain. A fixed rule in code decides who is served
  and at which offer, and every amount is re-checked against the buyer's hold right before PayPal
  is called.
- **No double charges.** Every PayPal write carries a `PayPal-Request-Id`, so a retry returns the
  first result. A capture above the hold is refused, even when it arrives by webhook.
- **Books that reconcile to the cent.** A hash-chained ledger records every hold, capture, void,
  refund and payout, and PayPal's own fees as PayPal reports them. Maxx's 8% fee comes from the
  seller side and pays PayPal's capture and payout fees; buyers never pay more than their price.
- **Sandbox only.** The API refuses to start against PayPal's live servers.

Measured on the live demo, with PayPal ids: [verification](docs/verification.md). Details:
[payments](docs/payments.md).

## How Maxx uses AI

| Job | Model (Nebius Token Factory) |
|---|---|
| Read a cart or product screenshot | `nvidia/Nemotron-3.5-Super-VL` |
| Normalise the product; pull prices out of web pages | `nvidia/Nemotron-3_5-Lightning` |
| Write the verdict; run each seller's agent | `nvidia/nemotron-3-super-120b-a12b` |
| Negotiate for the group, with tool calls | `nvidia/Nemotron-3-Ultra-550b-a55b` |
| Match a screenshot to an existing Bloc | `Qwen/Qwen3-Embedding-8B` |

- **Models never set money.** The negotiator chooses a reserve price and which seller to press;
  seller agents bid within floors and stock enforced in code; a deterministic clearing engine
  allocates units and sets every price. A seller agent that gives no valid answer misses that
  round only, and its last valid offer stands.
- **Strict contracts.** Each role has a JSON schema sent with every call (in the prompt and as
  `response_format`), post-checks in code, and a bounded set of tools.
- **Spending caps.** A Postgres ledger caps AI spend in total, per day, per person, per address and
  per negotiation. If a cap is hit or Token Factory is down, the negotiation runs a labelled replay
  instead of failing.
- **Transparency.** Every call is logged with model id, tokens, latency and cost (no prompts,
  images or keys) and shown on Under the hood.

A live scan also searches the web with Tavily; code, not the model, decides which offers count
(same product, a price quoted from the page, in stock). Details: [AI guardrails](docs/ai-guardrails.md).

## Built with

- **PayPal:** the sandbox REST APIs and JavaScript SDK v6 above. The **PayPal AI Toolkit** for
  Claude Code was used while building: its `/paypal:doctor` checks found three issues in the
  money code, fixed in [`21545d6`](https://github.com/SVamseekar/maxx-pay/commit/21545d6). Maxx
  calls the REST APIs directly; it does not use PayPal's MCP server or the Agent Toolkit package.
- **AI:** NVIDIA Nemotron and Qwen models on Nebius Token Factory; Tavily for web search.
- **App:** Next.js 16.3, React 19.3, TypeScript 5.9, Tailwind 4.3; Python 3.12, FastAPI 0.142,
  Pydantic 2.13, SQLAlchemy 2.0, Alembic; Postgres 17.
- **Hosting:** Vercel, Render and Neon free plans; email through Brevo.

## What's in it

- **Blocs and negotiation:** commitments with a maximum price, a countdown, live streamed rounds,
  partial fills, and a clear outcome for every member: a receipt of who was served and why the
  others were not, and for an unserved buyer the prices that cleared and an optional new Bloc at a
  limit they choose.
- **Payments:** PayPal holds, partial capture, release, per-order seller payouts, refunds, agentic
  checkout, Maxx Plus, and PYUSD. `PAYPAL_MODE` is `sandbox`, or `simulator` for running without
  PayPal credentials (labelled everywhere). See [payments](docs/payments.md).
- **Scan → verdict:** screenshot upload, editable fields, Money Score (0–100), one recommended move,
  and links to the offers found.
- **Marketplace:** seller onboarding with identity and sanctions checks, standing offers and
  listings, a bounded seller AI agent, orders, carrier tracking, payout on delivery, refunds and
  cases. Maxx is the platform, not the seller. See [marketplace](docs/marketplace.md).
- **Accounts:** emailed link, Google, Apple, Microsoft or GitHub; passkeys or an authenticator app;
  security alerts. See [accounts](docs/accounts.md) and [security](docs/security.md).

## Architecture

```text
apps/web/        Next.js 16: pages, and a server-side proxy to the API (streams included)
services/api/    FastAPI: scan, price search, Blocs, auction engine, agents, money, marketplace
evals/           fixture and live evaluation scripts and their results
deploy/          Dockerfiles and a production-like Compose file
render.yaml      the hosted API's settings
```

Postgres holds everything durable through one `DATABASE_URL`: Blocs, jobs, an append-only event
journal, a hash-chained money ledger, the price cache and model-call metadata. Screenshots are
processed in memory and never stored. The browser never talks to the API or PayPal's servers
directly except for PayPal's own approval popup.

## Run it locally

Needs Node.js 22+, Python 3.12, [uv](https://docs.astral.sh/uv/), and Docker (or a native
Postgres 15+).

```bash
cp .env.example .env     # first time only; add NEBIUS_API_KEY and TAVILY_API_KEY for live mode
make setup               # npm ci + uv sync --locked
make db                  # Postgres on 127.0.0.1:55432 (or: make db-native)
make migrate
make api                 # terminal 1: http://localhost:8000
make web                 # terminal 2: http://localhost:3001
```

For real PayPal sandbox money, set `PAYPAL_MODE=sandbox`, `PAYPAL_CLIENT_ID`,
`PAYPAL_CLIENT_SECRET` and `PAYPAL_SELLER_RECEIVER` (a sandbox account other than the app's own).
Without them, `PAYPAL_MODE=simulator` runs the same flow on a labelled simulator. With no AI keys,
run fully offline on the five synthetic samples:

```bash
SCAN_MODE=fixture MATCH_MODE=fixture NEGOTIATION_MODE=fixture make api
```

Set `JUDGE_ACCESS_CODE` (12+ characters) in `.env` to turn on the judge entry at `/judge`. Every
other setting, with its default, is in `.env.example`.

Checks:

```bash
make check               # web lint, typecheck, tests and build; API lint, format and tests
make smoke               # HTTP checks through web → API → database
make verify-guardrails   # live: each model's contract against Token Factory (spends a few cents)
make evaluate            # fixture evaluation, writes evals/core-fixture.json
```

## Docs

- [Verification](docs/verification.md): what was measured, live and offline, and what was not
- [Payments](docs/payments.md) · [AI guardrails](docs/ai-guardrails.md) ·
  [Marketplace](docs/marketplace.md) · [Accounts](docs/accounts.md) ·
  [Security](docs/security.md) · [Performance](docs/performance.md) ·
  [Market and compliance research](docs/market-research.md) · [Deployment](docs/deployment.md) ·
  [Changelog](CHANGELOG.md)

## What changed since 1 October

The repository starts on 5 October 2026, inside the PayPal AI Hackathon's window, and every commit
keeps its original date. The full story is in the [changelog](CHANGELOG.md):

- **5 to 30 October:** the app, the AI agents and guardrails, accounts, the marketplace and a
  PayPal money layer on a simulator
  ([commits](https://github.com/SVamseekar/maxx-pay/commits/89495fe)). This version was submitted
  to the Nebius × NVIDIA Global AI Hackathon on 30 October.
- **From 8 November, for this entry:** the money layer running on the real PayPal sandbox, PayPal's
  own fees in the books, the 8% fee model, webhook and payout fixes found with the PayPal AI
  Toolkit and the sandbox, the run receipt and rejoin option, a separate hosted demo, and a live
  end-to-end run with PayPal ids, and a real group run with 1,003 sandbox holds and paced PayPal
  calls
  ([all changes](https://github.com/SVamseekar/maxx-pay/compare/89495fe...main)).

## Disclosure

- **Other entry.** The negotiation and AI layer, and the app around it, were also entered in the
  Nebius × NVIDIA Global AI Hackathon (submitted 30 October 2026, demo at a separate address).
  This entry is the same product, significantly updated after that for PayPal, as listed above.
  The two demos run on separate servers and databases.
- **Simulated parts.** In the demo scenarios the eight seller agents and the crowds of buyers (600
  in the successful deal, 100 in each of the others) are simulated and labelled; they place no
  holds. Carrier tracking and identity checks run in labelled simulators.
- **Scripted test buyers.** The 1,003 real holds in the group run were placed by test accounts
  we created and drove by script (1,000 by sandbox test card, 3 through PayPal's popup).
- **Not set up in the sandbox yet.** Maxx Plus needs two billing plans created in the PayPal
  sandbox; until then the account page says the plan is not set up.
- The 15 policy pages under `/legal` are drafts.

## License

MIT. See [LICENSE](LICENSE) and [third-party notices](THIRD_PARTY_NOTICES.md).
