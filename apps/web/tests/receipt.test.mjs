import assert from "node:assert/strict";
import test from "node:test";
import { runReceipt, unservedView } from "../app/blocs/receipt.ts";

const members = [
  { id: "m1", user_id: "x", max_price: "200.00", joined_order: 0, status: "WIN", final_price: "150.00", seller_id: "A" },
  { id: "m2", user_id: "y", max_price: "190.00", joined_order: 1, status: "WIN", final_price: "180.00", seller_id: "B" },
  { id: "m3", user_id: "me", max_price: "160.00", joined_order: 2, status: "BELOW_CLEARING", final_price: null, seller_id: null },
  { id: "m4", user_id: "z", max_price: "100.00", joined_order: 3, status: "BELOW_CLEARING", final_price: null, seller_id: null },
];
const bloc = {
  status: "SETTLED", typical_price: "200.00", members,
  events: [
    { id: 1, type: "seller_skipped", data: { round: 2, seller: "C" } },
    { id: 2, type: "seller_skipped", data: { round: 4, seller: "C" } },
  ],
  outcome: {
    allocations: [{ member_id: "m1", seller_id: "A", price: "150.00" }, { member_id: "m2", seller_id: "B", price: "180.00" }],
    unserved: ["m3", "m4"],
    offers: [{ seller_id: "A", price: "150.00", max_qty: 1 }, { seller_id: "B", price: "180.00", max_qty: 1 }],
    reasons: { m3: "sold_out", m4: "below_price" },
    withdrew: ["D"], above_reserve: ["E"],
  },
};

test("the receipt lists each seller's final offer, what it sold, and why buyers missed out", () => {
  const r = runReceipt(bloc);
  assert.deepEqual(r.sellers, [{ seller: "A", price: 150, offered: 1, sold: 1 }, { seller: "B", price: 180, offered: 1, sold: 1 }]);
  assert.deepEqual([r.served, r.low, r.high], [2, 150, 180]);
  assert.deepEqual(r.unserved, { below_price: 1, sold_out: 1, unknown: 0 });
  assert.deepEqual(r.withdrew, ["D"]);
  assert.deepEqual(r.aboveReserve, ["E"]);
  assert.deepEqual(r.skipped, [{ seller: "C", rounds: [2, 4] }]);
});

test("an unserved buyer sees their own reason, the prices that cleared, and a starting limit", () => {
  const view = unservedView(bloc, members[2]);
  assert.equal(view.reason, "sold_out");
  assert.deepEqual([view.low, view.high], [150, 180]);
  // Above the lowest maximum that was served ($190), since $161 or even $180 could lose again.
  assert.equal(view.lowestServed, 190);
  assert.equal(view.suggested, 191);
  const low = unservedView(bloc, members[3]);
  assert.equal(low.reason, "below_price");
  assert.equal(low.suggested, 191);
});

test("an outcome saved before the receipt existed still renders", () => {
  const old = { ...bloc, events: [], outcome: { allocations: bloc.outcome.allocations, unserved: ["m3", "m4"] } };
  const r = runReceipt(old);
  assert.deepEqual(r.sellers, []);
  assert.deepEqual(r.unserved, { below_price: 0, sold_out: 0, unknown: 2 });
  assert.equal(unservedView(old, members[2]).reason, null);
});

test("a no-deal Bloc suggests the buyer's own maximum and caps at the typical price", () => {
  const failed = { ...bloc, status: "FAILED", outcome: { allocations: [], unserved: ["m3"] } };
  const view = unservedView(failed, { ...members[2], max_price: "199.80" });
  assert.deepEqual([view.low, view.high, view.suggested], [null, null, 200]);
});
