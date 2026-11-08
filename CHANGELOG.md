# Changelog

What changed in Maxx and when, newest first. Each chapter links to its commits; every commit keeps
its original date. Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Maxx has no
numbered releases yet; chapters are named by date and purpose.

## Unreleased: PayPal AI Hackathon entry (from 8 November 2026)

[All changes since the Nebius submission](https://github.com/SVamseekar/maxx-pay/compare/89495fe...main)

### Added

- The money layer runs on the **real PayPal sandbox**: a hold approved in PayPal's popup, partial
  capture of the allocated price, void for everyone else, and a per-order seller payout on
  delivery ([`c138069`](https://github.com/SVamseekar/maxx-pay/commit/c138069)).
- PayPal's own fees in the books: the capture fee from `seller_receivable_breakdown` and the
  payout item fee, with Maxx's margin after both
  ([`c138069`](https://github.com/SVamseekar/maxx-pay/commit/c138069)).
- A receipt for every run, "How this run was decided": the clearing rule, each seller's final
  offer and units sold, the price range served, and why the others were not served
  ([`fcf7b27`](https://github.com/SVamseekar/maxx-pay/commit/fcf7b27)).
- For a buyer who was not served: their reason, the prices that cleared, and an optional new Bloc
  for the same product at a limit they choose
  ([`fcf7b27`](https://github.com/SVamseekar/maxx-pay/commit/fcf7b27)).
- A separate hosted demo at https://pay.souravamseekar.com on its own servers and database, and a
  live end-to-end run recorded with PayPal ids
  ([`eb9e579`](https://github.com/SVamseekar/maxx-pay/commit/eb9e579)).

### Changed

- Maxx's fee is 8% (was 5%), taken from the seller side; Maxx pays PayPal's capture and payout
  fees from it ([`c138069`](https://github.com/SVamseekar/maxx-pay/commit/c138069)).
- A seller agent that breaks its reply contract now misses that round only; its last valid offer
  stands. If every seller fails in one round, rounds stop
  ([`fcf7b27`](https://github.com/SVamseekar/maxx-pay/commit/fcf7b27)).
- The line beside the Join button says the maximum is a hard cap and a fixed rule in code, not a
  model, decides who is served ([`fcf7b27`](https://github.com/SVamseekar/maxx-pay/commit/fcf7b27)).
- `render.yaml` describes this entry's own service on the PayPal sandbox
  ([`8827101`](https://github.com/SVamseekar/maxx-pay/commit/8827101)).

### Fixed

- The web app now reads the monorepo's root `.env`, so its Content-Security-Policy allows PayPal's
  sandbox and the approval popup loads
  ([`c138069`](https://github.com/SVamseekar/maxx-pay/commit/c138069)).
- Two racing hold requests no longer leave an unapproved PayPal order in the books
  ([`c138069`](https://github.com/SVamseekar/maxx-pay/commit/c138069)).
- Found with the PayPal AI Toolkit's `/paypal:doctor` checks: failed PayPal calls keep and log
  PayPal's `debug_id`; cancelling a subscription sends a `PayPal-Request-Id`; a failed
  subscription payment is recorded ([`21545d6`](https://github.com/SVamseekar/maxx-pay/commit/21545d6)).
- A payout batch still `PROCESSING` is no longer marked failed
  ([`8827101`](https://github.com/SVamseekar/maxx-pay/commit/8827101)).

## 24 to 30 October 2026: AI guardrails, judge entry and price search

Submitted to the Nebius × NVIDIA Global AI Hackathon on 30 October
([commits](https://github.com/SVamseekar/maxx-pay/compare/6dd5ae9...89495fe)).

### Added

- Strict contracts for every AI role: a JSON schema sent with each call, post-checks in code, and
  bounded tools for the negotiator and seller agents.
- A hard, database-backed AI spending cap, charged to the person or pool that caused each call,
  with an admin view and a pause switch.
- One-tap judge entry, private demo copies, and a banner while the free API wakes.
- Live price search: offers confirmed on store pages and scored against the maker's own store.
- Screenshot reading with Nemotron 3.5 Super VL, chosen after a live comparison.
- Email with a designed HTML part, sent through Brevo on port 2525.

### Fixed

- Money is sent to models as numbers only; the visitor's address travels to the API signed with a
  shared secret; regex work on page text is bounded.

## 23 October 2026: accounts, PayPal money layer and marketplace

[Commits](https://github.com/SVamseekar/maxx-pay/compare/e082dc1...6dd5ae9)

### Added

- Accounts and sign-in: emailed link, social sign-in, passkeys and an authenticator app.
- The PayPal money layer, on a labelled simulator: holds, capture, release, payouts, webhooks,
  agentic checkout and Maxx Plus, with a hash-chained ledger
  ([`3df5309`](https://github.com/SVamseekar/maxx-pay/commit/3df5309)).
- The seller marketplace: onboarding with verification, listings, orders, carrier tracking,
  payout on delivery, refunds and cases.
- A redesigned web app.

### Fixed

- A spoofable client address and a stream slot leak; issues found running the seller and buyer
  journeys on Postgres.

## 5 to 8 October 2026: foundation

[Commits](https://github.com/SVamseekar/maxx-pay/compare/a601d11...e082dc1)

### Added

- The project skeleton: the Next.js and FastAPI apps, Postgres, migrations and health checks
  ([`a601d11`](https://github.com/SVamseekar/maxx-pay/commit/a601d11)).
- The core of Maxx: screenshot scan and verdict, Blocs, the deterministic clearing engine, and the
  negotiator and seller agents on Nebius Token Factory
  ([`b4371f3`](https://github.com/SVamseekar/maxx-pay/commit/b4371f3)).
