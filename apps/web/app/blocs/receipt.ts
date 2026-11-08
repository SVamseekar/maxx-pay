import type { Bloc, Member } from "./types";

/** How the clearing rule works, in the words the receipt uses. Matches services/api/maxx/negotiate/engine.py. */
export const CLEARING_RULE = "Highest maximums are matched to the cheapest offers first; equal maximums go to whoever joined first. Each buyer pays the price of the seller they are matched to.";

type ReceiptBloc = Pick<Bloc, "status" | "typical_price" | "members" | "events" | "outcome">;

/** The per-run receipt: every number comes from the saved outcome and events, nothing is inferred. */
export function runReceipt(bloc: ReceiptBloc) {
  const outcome = bloc.outcome;
  const allocations = outcome?.allocations ?? [];
  const prices = allocations.map(a => Number(a.price));
  const sellers = (outcome?.offers ?? []).map(o => ({
    seller: o.seller_id, price: Number(o.price), offered: o.max_qty,
    sold: allocations.filter(a => a.seller_id === o.seller_id).length,
  })).sort((a, b) => a.price - b.price || a.seller.localeCompare(b.seller));
  const unserved = { below_price: 0, sold_out: 0, unknown: 0 };
  for (const id of outcome?.unserved ?? []) unserved[outcome?.reasons?.[id] ?? "unknown"] += 1;
  const skippedRounds = new Map<string, number[]>();
  for (const event of bloc.events) {
    if (event.type !== "seller_skipped" || !event.data.seller) continue;
    skippedRounds.set(event.data.seller, [...(skippedRounds.get(event.data.seller) ?? []), event.data.round ?? 0]);
  }
  return {
    sellers,
    served: allocations.length,
    low: prices.length ? Math.min(...prices) : null,
    high: prices.length ? Math.max(...prices) : null,
    unserved,
    withdrew: outcome?.withdrew ?? [],
    aboveReserve: outcome?.above_reserve ?? [],
    skipped: [...skippedRounds].map(([seller, rounds]) => ({ seller, rounds })),
  };
}

/**
 * What a buyer this Bloc did not serve is shown: their own reason, the prices that cleared, and
 * where the limit slider starts in a new Bloc. The start is a suggestion the buyer can move: above
 * their old maximum, never below the lowest price that cleared, never above the typical price.
 */
export function unservedView(bloc: ReceiptBloc, you: Pick<Member, "id" | "max_price">) {
  const { low, high } = runReceipt(bloc);
  const reason = bloc.outcome?.reasons?.[you.id] ?? null;
  const suggested = Math.min(Number(bloc.typical_price), Math.max(low ?? 0, Math.floor(Number(you.max_price)) + 1));
  return { reason, low, high, suggested };
}
