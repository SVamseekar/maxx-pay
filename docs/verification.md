# What has been verified, and how

Every number here was measured, with the date and where it ran. Anything not measured is listed
at the end. Fixture and replay results are kept apart from live results.

## Automated tests

- **API:** 562 tests pass (1 skipped). They cover the auction engine's invariants, the money
  ledger, the role contracts for every model, the price-search trust rules, accounts and sign-in,
  the PayPal simulator, seller onboarding, fulfilment and the email layout. Provider calls in tests
  use mock transports.
- **Web:** ESLint, TypeScript and 55 unit tests pass.
- Run them with `make check`.

## Live on the hosted demo with real PayPal sandbox: 8 November 2026

On https://pay.souravamseekar.com (Vercel web, Render API, Neon database, all free plans), a
headless Chrome took the judge path: judge entry with the access code, **Try successful deal**,
**Join with a PayPal hold** in PayPal's own sandbox popup with a US test buyer, **Close Bloc &
negotiate** with live Nemotron agents, a delivery address, and the simulated seller shipping with
simulated tracking.

| Step | Result | PayPal ids |
|---|---|---|
| Hold | $170.00 authorized | order `66F12448KB923753S`, authorization `13A276960V113700A` |
| Negotiation | Allocated at $138.00; 451 of 601 buyers served at $130.00 to $142.00; the run receipt listed each seller's final offer and units sold | |
| Capture | $138.00, the rest of the hold released; PayPal fee $5.31 | capture `75823843P1282020X` |
| Tracking | The simulated seller's tracking number was added to the buyer's PayPal order (Orders v2 `/track`); PayPal shows the tracker as SHIPPED | tracker `75823843P1282020X-1ZMAXX010261483331` |
| Payout on delivery | $126.96 to the seller (92%), Maxx fee $11.04 (8%), status SENT; PayPal payout fee $0.25 | payout item `BXTHCSAPTZXSY` |
| Books | Reconciled. Maxx keeps $11.04 − $5.31 − $0.25 = $5.48; no PayPal fee left unknown | |
| Webhooks | PayPal sent `PAYMENT.CAPTURE.COMPLETED` and `PAYMENT.PAYOUTS-ITEM.SUCCEEDED` to the live API; each passed signature verification (HTTP 200) | webhook `4YW58479VN8475801` |

## Real PayPal sandbox, through the app: 8 November 2026

Run locally with `PAYPAL_MODE=sandbox`, a US sandbox business account as the platform and a US
sandbox personal account as the buyer. A headless Chrome drove the app the way a person does: a
private copy of each demo scenario, **Join with a PayPal hold**, sign-in and approval in PayPal's
own popup, **Close Bloc & negotiate** with live Nemotron agents, a delivery address, and the
simulated seller shipping with simulated tracking. Every PayPal call was real.

| Step | Result | PayPal ids |
|---|---|---|
| Hold | $170.00 authorized | order `2CL35057632099428`, authorization `3FW33047PT236334B` |
| Negotiation | Allocated at $138.00 (451 of 601 buyers served) | |
| Capture | $138.00 of the $170.00 hold, final capture; the other $32.00 released. PayPal fee $5.31 (3.49% + $0.49), read from the capture response | capture `5HY848385T833710G` |
| Payout on delivery | $126.96 to the seller (92%); Maxx fee $11.04 (8%). Item SUCCESS, PayPal payout fee $0.25 | batch `UQ9WKHH4YU2Y2`, item `KMBHZV8MCJ4HU` |
| Books | Reconciled. Maxx keeps $11.04 − $5.31 − $0.25 = $5.48. No PayPal fee left unknown. | |
| No-deal scenario | $170.00 hold voided, nothing captured | order `8MK87314SL881341D`, authorization `0G311446KP156490S` |

Two bugs found by the run and fixed, each with a test:

- The page's Content-Security-Policy left PayPal out, so the approval popup could not load. The
  web app never read the root `.env`: Next.js had already cached its own env, so the second
  `loadEnvConfig` call did nothing. It now forces the reload.
- Two hold requests racing (a double click, or React's double effect in development) each created
  a PayPal order. The unapproved one stayed in the books as a hold and showed in place of the real
  one. When a hold is authorized, any other unapproved order for the same join is now retired, and
  orders that never held money are left out of the books and receipts.

## Live on the Nebius entry's hosted demo: 30 October 2026

On https://maxx.souravamseekar.com (the Nebius × NVIDIA entry, PayPal simulator), through the same path a judge takes (judge entry, a private
copy of the successful-deal scenario, a $170 simulated PayPal hold, **Close Bloc & negotiate**,
rounds streamed through the web app):

| | |
|---|---|
| Outcome | Settled after 5 rounds, in 34 seconds |
| Model calls | 49 on Nebius Token Factory: 9 Nemotron 3 Ultra (negotiator), 40 Nemotron 3 Super (seller agents) |
| Cost | $0.0186 |
| Allocation | 451 of 601 buyers served: 300 at $135, 150 at $138, 1 at $142, against a $200 typical price. 150 holds released; nobody paid above their maximum. |
| Stream | 1,301 events delivered over server-sent events, Render → Vercel → browser |

## Live negotiations: 28 October 2026

Local runs against live Token Factory, 600 simulated buyers and eight seller agents: 3 to 5 rounds,
29 to 48 model calls, about $0.026 to $0.035 per negotiation. A judge with a $170 maximum was
allocated at $138.00 against the $200 typical price.

## Live AI contracts: 26 October 2026

`make verify-guardrails` against live Token Factory (`evals/guardrails-live.json`):

- Both ways of turning Nemotron's thinking off work, and replies come back as bare JSON.
- Nemotron 3 Ultra calls tools correctly with thinking off.
- Screenshot reading on the synthetic set: 18 of 20 fields for Nemotron 3.5 Super VL (the same as
  the previous vision model, and faster), so the app uses Nemotron end to end.
- Fixes that came out of the run: the JSON schema is now sent with every call; Decimal `pattern`
  constraints are removed from the wire schema (Token Factory answered HTTP 500 to them); a
  negotiator read tool is offered only until it has been answered (Ultra re-read in a loop).

Costs measured then: an uncached scan about $0.0013 plus Tavily credits; a cached one $0.0005; one
negotiation round about $0.003.

## Live price search: 29–30 October 2026

How a scan finds offers is described in the README. Checked on real products:

| Product | Result |
|---|---|
| Over-ear headphones cart at $399.99 | The maker's own store at $228.00 delivered and in stock gave a Money Score of 30. A specialist store's $298 was left unscored: on backorder. Another store's offer was a different colour, so it was rejected. |
| Air fryer | A big-box store's price needed a new store card, so it was rejected. The maker's own store showed $129.99 with free shipping. |
| Generic, unbranded headphones | Non-matching products were rejected; the verdict says the evidence is thin instead of inventing a score. |

Tried and dropped, with Tavily's usage counter: quoting the model code with `exact_match` returned
no results; restricting to freshly fetched pages (`max_age_hours`) cut one search to four unpriced
results. Full-page text (`include_raw_content`) still costs 1 credit.

## Fixture and replay checks

These measure the app's own plumbing and rules, not model accuracy:

- 25/25 fields replayed on five synthetic screenshots (`evals/core-fixture.json`).
- 50/50 automatic product identities on 60 synthetic cases, ten of which correctly asked the
  person to confirm.
- 0 invariant violations in 200 random auctions, 188 of them partial fills: nobody is charged
  above their maximum, no seller sells below its floor or above its stock, everyone at one seller
  pays the same price.
- Bloc state, events and streams replay unchanged across an API restart.

## Not yet measured

- Screenshot-reading accuracy on a large, representative set of real carts (the plan was 40
  images), and product-match precision at scale.
- Negotiation quality and savings over many live runs.
- Real Stripe Identity and EasyPost calls: these run in labelled simulators.
- Database backup and restore on the hosted database.
