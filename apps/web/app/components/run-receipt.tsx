"use client";
import { useState } from "react";
import { ArrowRight } from "lucide-react";
import { request } from "../lib/client";
import { usd, type Bloc, type Member } from "../blocs/types";
import { CLEARING_RULE, runReceipt, unservedView } from "../blocs/receipt";
import { Disclosure } from "./ui";

const list = (ids: string[]) => ids.map(id => `Seller ${id}`).join(", ");
const range = (low: number | null, high: number | null) => low === null ? "—" : low === high ? usd(low) : `${usd(low)} to ${usd(high)}`;

/** Who this run served and why the others were not, from the saved outcome. Seller floors and stock never appear. */
export function RunReceipt({ bloc, defaultOpen = false }: { bloc: Bloc; defaultOpen?: boolean }) {
  const r = runReceipt(bloc);
  const notServed = r.unserved.below_price + r.unserved.sold_out + r.unserved.unknown;
  return <Disclosure className="run-receipt" title="How this run was decided" defaultOpen={defaultOpen}>
    <p>{CLEARING_RULE} No AI model takes part in this step.</p>
    {r.sellers.length > 0 && <table><thead><tr><th>Seller</th><th>Final offer</th><th>Units offered</th><th>Units sold</th></tr></thead>
      <tbody>{r.sellers.map(s => <tr key={s.seller}><td>{s.seller}</td><td>{usd(s.price)}</td><td>{s.offered}</td><td>{s.sold}</td></tr>)}</tbody></table>}
    <ul>
      <li><strong>{r.served} served</strong>{r.served > 0 && <> at {range(r.low, r.high)}, each at their seller’s price and never above their own maximum</>}.</li>
      {notServed > 0 && <li><strong>{notServed} not served.</strong>{r.unserved.below_price > 0 && <> {r.unserved.below_price} had a maximum below every offer.</>}{r.unserved.sold_out > 0 && <> {r.unserved.sold_out} could afford an offer, but its units went first to higher maximums, or to equal ones that joined earlier.</>}{r.unserved.unknown > 0 && <> {r.unserved.unknown} without a recorded reason (saved before reasons were kept).</>}</li>}
      {r.withdrew.length > 0 && <li>{list(r.withdrew)} withdrew and made no final offer.</li>}
      {r.aboveReserve.length > 0 && <li>{list(r.aboveReserve)} stayed above the group’s reserve price, so their offers were left out.</li>}
      {r.skipped.map(s => <li key={s.seller}>Seller {s.seller} gave no valid answer in round {s.rounds.join(" and ")}. Its last offer stood, and it was asked again the next round.</li>)}
    </ul>
    <p className="muted">Offers are the ones shown in the room as they were made. No buyer’s identity or seller’s private limits are shown.</p>
  </Disclosure>;
}

/** The outcome for a buyer this Bloc did not serve: why, what cleared, and an optional way to try again. */
export function UnservedOutcome({ bloc, you, paying }: { bloc: Bloc; you: Member; paying: boolean }) {
  const view = unservedView(bloc, you);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function again() {
    setBusy(true); setError("");
    try {
      const { bloc_id } = await request<{ bloc_id: string }>(`/api/blocs/${bloc.id}/again`, { body: {} });
      window.location.assign(`/blocs/${bloc_id}/room?max=${view.suggested.toFixed(2)}`);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Could not open a new Bloc."); setBusy(false); }
  }
  const released = paying ? "Your PayPal hold was released. Nothing was charged." : "Your commitment was released.";
  const why = bloc.status === "FAILED" ? (bloc.failure_reason ?? "No qualifying deal this time.")
    : view.reason === "below_price" ? `Your maximum of ${usd(you.max_price)} was below every seller’s final offer.`
    : view.reason === "sold_out" ? `Your maximum of ${usd(you.max_price)} covered an offer, but its units went first to buyers with higher maximums, or equal ones who joined earlier.`
    : `Your maximum of ${usd(you.max_price)} or seller capacity could not secure an allocation.`;
  return <div className="unserved-outcome">
    <p>{why} {released}</p>
    {view.low !== null && <p>Buyers in this Bloc were served at <strong>{range(view.low, view.high)}</strong>.</p>}
    {bloc.scenario === "failure" ? <p className="muted">This demo is set up so that no seller can meet the group’s limits, so a new copy would end the same way. Try the successful deal from the Demo lab instead.</p> : <>
    <button type="button" className="button" disabled={busy} onClick={() => void again()}>{busy ? "Opening…" : "Join a new Bloc with a higher limit"} <ArrowRight size={14} aria-hidden="true" /></button>
    <p className="muted">Optional. You choose the new limit and approve a new hold yourself; the slider starts at {usd(view.suggested)}{view.lowestServed !== null ? `, just above the lowest maximum served here (${usd(view.lowestServed)})` : ""}. A new Bloc can clear at different prices.</p></>}
    {error && <p role="alert">{error}</p>}
  </div>;
}
