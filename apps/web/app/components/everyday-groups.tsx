"use client";
import Image from "next/image";
import Link from "next/link";
import { useRef, useState } from "react";
import { ArrowUpRight, Shuffle } from "lucide-react";
import { api } from "../blocs/types";
import { useAuth } from "./auth";
import { loginPath } from "../lib/auth-helpers";
import { useMoneyConfig } from "../lib/money";
import { EVERYDAY, randomOther, unitPrice, type EverydayProduct } from "../lib/everyday";
import { usd } from "../blocs/types";
import { ErrorNotice } from "./ui";

/**
 * Everyday demo products, each opening the person's own private Bloc: a simulated crowd, eight
 * simulated sellers, and their real PayPal sandbox hold when payments are on.
 */
export default function EverydayGroups({ from }: { from: "/blocs" | "/judge" }) {
  const { user, status } = useAuth();
  const money = useMoneyConfig();
  const paying = Boolean(money?.enabled);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [picked, setPicked] = useState<string | null>(null);
  const cards = useRef<Record<string, HTMLElement | null>>({});

  async function start(product: EverydayProduct) {
    setBusy(product.id); setError("");
    try {
      const { bloc_id } = await api<{ bloc_id: string }>(`/api/demo/lab/success?product=${product.id}`, {});
      // Without payments there is no hold step, so join at a limit a little under the typical price.
      if (!paying) await api(`/api/blocs/${bloc_id}/join`, { max_price: (product.typical * 0.9).toFixed(2) });
      window.location.assign(`/blocs/${bloc_id}/room`);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not open this group. Try again.");
      setBusy(null);
    }
  }

  function surprise() {
    const next = randomOther(picked);
    setPicked(next.id);
    cards.current[next.id]?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  return <section className="everyday" id="everyday" aria-labelledby="everyday-h">
    <div className="everyday-head">
      <div>
        <p className="section-label">Everyday groups</p>
        <h2 id="everyday-h">The things you buy anyway.</h2>
        <p>You get one. The group buys many, so sellers can offer a bulk price and nobody has to store bulk at home. Each opens your own practice group with simulated buyers and seller agents.</p>
      </div>
      <div className="everyday-surprise">
        <button type="button" onClick={surprise}><Shuffle size={15} aria-hidden="true" /> Show me something else</button>
        <p className="small muted" role="status">{picked ? `Picked at random from ${EVERYDAY.length}: ${EVERYDAY.find(p => p.id === picked)?.name}.` : `${EVERYDAY.length} demo products. Made-up items, illustrative prices.`}</p>
      </div>
    </div>
    {error && <ErrorNotice message={error} />}
    <div className="everyday-grid">
      {EVERYDAY.map(product => {
        const each = unitPrice(product);
        return <article key={product.id} ref={el => { cards.current[product.id] = el; }} className={`everyday-card${picked === product.id ? " is-picked" : ""}`}>
          <div className="everyday-art"><Image src={product.image} alt={product.alt} width={512} height={512} sizes="(max-width: 700px) 50vw, 20vw" /></div>
          <div className="everyday-body">
            <span className="everyday-moment">{product.moment}</span>
            <h3>{product.name}</h3>
            <p className="everyday-price"><strong>{usd(product.typical)}</strong> typical{each ? <span> · {each}</span> : null}</p>
            {status === "ready" && !user
              ? <Link className="button" href={loginPath(`${from}#everyday`)}>Sign in to try <ArrowUpRight size={14} aria-hidden="true" /></Link>
              : <button type="button" disabled={busy !== null || status !== "ready"} onClick={() => void start(product)}>{busy === product.id ? "Opening…" : "Start a group"} <ArrowUpRight size={14} aria-hidden="true" /></button>}
          </div>
        </article>;
      })}
    </div>
    <p className="small muted everyday-note">Demo products with no brand and no stock. A typical price is what this kind of item usually costs in the US; your group can clear lower, or not at all.</p>
  </section>;
}
