import test from "node:test";
import assert from "node:assert/strict";
import { EVERYDAY, everydayByTitle, randomOther, unitPrice } from "../app/lib/everyday.ts";

test("consumables show a unit price; durable goods do not", () => {
  const pods = EVERYDAY.find(p => p.id === "laundry-pods");
  assert.equal(unitPrice(pods), "$0.34 a load");
  assert.equal(unitPrice(pods, 28.8), "$0.30 a load");
  assert.equal(unitPrice(EVERYDAY.find(p => p.id === "stroller")), null);
});

test("something else is drawn evenly from the other products, never the one on screen", () => {
  const seen = new Set();
  for (let i = 0; i < 9; i++) seen.add(randomOther("skillet", () => i / 9).id);
  assert.equal(seen.size, EVERYDAY.length - 1);
  assert.ok(!seen.has("skillet"));
});

test("a room finds its product picture by the Bloc title", () => {
  assert.equal(everydayByTitle("Demo air fryer · 6 qt")?.image, "/artwork/everyday/air-fryer.webp");
  assert.equal(everydayByTitle("Some custom product"), undefined);
});
