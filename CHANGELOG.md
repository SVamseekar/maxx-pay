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
- **Everyday groups** on Blocs and the demo lab: ten made-up everyday products (skillet, air
  fryer, stand mixer, air purifier, laundry pods, sonic toothbrush, diapers, travel stroller, dog
  food, headphones), each opening the person's own practice Bloc with a simulated crowd and seller
  agents. Typical prices are illustrative and based on ordinary US prices; consumables show a unit
  price. "Show me something else" picks one at random and says so. Original illustrative artwork
  for each product, also shown on Bloc cards and in the room header.
- The three shared demo scenarios each show a different product: headphones (successful deal),
  a stand mixer (no deal) and an air purifier (seller withdrawal).
- Each simulated seller agent can be paid into its own PayPal sandbox account
  (`PAYPAL_SELLER_RECEIVERS`), so payouts fan out to several sellers instead of one shared
  receiver.
- A scripted card-buyer tool fills a shared demo Bloc with real PayPal sandbox holds: each
  guest test buyer's hold is one Orders call paid with PayPal's sandbox test card, then
  settles, ships and pays out like any other order. PayPal calls are paced
  (`PAYPAL_CALLS_PER_MINUTE`) to stay under the sandbox's per-minute limit.

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
- Agent checkout only buys from offers the server sealed in the scan answer (`offers_seal`); a
  price or stock flag changed in the browser is refused.
- "Join a new Bloc with a higher limit" now starts the slider just above the lowest maximum that
  was served, and the no-deal demo no longer offers a new copy that would fail the same way.
- Wording that said "simulated" on the sandbox site now holds in both payment modes.

### Fixed

- A judge's guest account was asked to confirm who they are before agent checkout over $200,
  with no password, passkey or inbox to do it with. Judge sessions now skip that re-check.

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
- A judge's private demo copy could take another person's hold, and real sellers saw and bid into
  it. Only its owner can now hold, join or close it, and sellers never see it.
- In live mode the seller model could ignore the withdrawal scenario's scripted exit; code now
  enforces it.
- The settlement panel overflowed its card, and on a phone the outcome card was cut off.
- Refunds showed as "Paid" in receipts and the room; the group books now list refunds.
- The closing round showed a message to every seller although none was asked.
- Confirming an already-paid checkout offer again created a phantom receipt.
- PayPal's payout fee dropped out of the books after a refund; a fee not yet reported is counted.
- Admin reconcile compared payments made in another payment mode.
- Cancelling someone else's unfinished hold answered "cancelled"; cancelling an order twice said
  it had shipped.
- My Blocs said "Left" for demo copies never joined; "0 of 0 active buyers" on finished Blocs;
  wrong plurals ("1 buyers", "1 days").

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
