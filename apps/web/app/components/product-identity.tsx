import Image from "next/image";
import { everydayByTitle } from "../lib/everyday";
import { Headphones, Smartphone, Laptop, Package, Watch, Wind } from "lucide-react";

/** Category illustration, not a claim that a stock photograph depicts the item. A known everyday
 * demo product shows its own labelled illustrative artwork instead. */
export default function ProductIdentity({ title }: { title: string }) {
  const everyday = everydayByTitle(title);
  if (everyday) return <div className="product-identity has-art" data-category={everyday.moment}><Image src={everyday.image} alt={everyday.alt} width={480} height={480} sizes="(max-width: 700px) 90vw, 30vw" /><span>Illustrative artwork</span></div>;
  const key = title.toLowerCase();
  const category = /headphone|earbud|airpod|sony wh/.test(key) ? "Audio" : /phone|iphone|pixel|galaxy/.test(key) ? "Mobile" : /laptop|macbook|notebook/.test(key) ? "Computing" : /watch/.test(key) ? "Wearables" : /vacuum|dyson|cleaner/.test(key) ? "Home" : "Group purchase";
  const Icon = { Audio: Headphones, Mobile: Smartphone, Computing: Laptop, Wearables: Watch, Home: Wind, "Group purchase": Package }[category];
  return <div className="product-identity" data-category={category}><Icon size={44} strokeWidth={1.15} aria-hidden="true" /><span>{category}</span></div>;
}
