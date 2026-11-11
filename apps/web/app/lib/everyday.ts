/**
 * Everyday demo products a person can try in their own private Bloc. All made up: no brand, no
 * merchant, no stock. Typical prices are illustrative, anchored to ordinary US prices for each
 * kind of item. Mirrors services/api/maxx/demo/catalogue.py (tests/test_everyday.py checks it).
 */
export type EverydayProduct = {
  id: string;
  name: string;
  title: string;
  typical: number;
  moment: "Kitchen" | "Home" | "Care" | "Family" | "Pets" | "Listening";
  unit?: { count: number; noun: string };
  image: string;
  alt: string;
};

export const EVERYDAY: readonly EverydayProduct[] = [
  { id: "skillet", name: "Cast iron skillet, 12-inch", title: "Demo cast iron skillet · 12-inch", typical: 35, moment: "Kitchen", image: "/artwork/everyday/skillet.webp", alt: "Illustrative black cast iron skillet on limestone" },
  { id: "air-fryer", name: "Air fryer, 6 qt", title: "Demo air fryer · 6 qt", typical: 120, moment: "Kitchen", image: "/artwork/everyday/air-fryer.webp", alt: "Illustrative off-white air fryer on limestone" },
  { id: "stand-mixer", name: "Stand mixer, 4.5 qt", title: "Demo stand mixer · 4.5 qt", typical: 230, moment: "Kitchen", image: "/artwork/everyday/stand-mixer.webp", alt: "Illustrative pale green stand mixer on limestone" },
  { id: "air-purifier", name: "HEPA air purifier", title: "Demo air purifier · HEPA", typical: 190, moment: "Home", image: "/artwork/everyday/air-purifier.webp", alt: "Illustrative grey air purifier beside a plant" },
  { id: "laundry-pods", name: "Laundry pods, 96 loads", title: "Demo laundry pods · 96 loads", typical: 33, moment: "Home", unit: { count: 96, noun: "load" }, image: "/artwork/everyday/laundry-pods.webp", alt: "Illustrative jar of laundry pods beside a folded towel" },
  { id: "toothbrush", name: "Sonic toothbrush", title: "Demo sonic toothbrush", typical: 60, moment: "Care", image: "/artwork/everyday/toothbrush.webp", alt: "Illustrative white electric toothbrush in its stand" },
  { id: "diapers", name: "Diapers, size 3, 160", title: "Demo diapers · Size 3, 160", typical: 45, moment: "Family", unit: { count: 160, noun: "diaper" }, image: "/artwork/everyday/diapers.webp", alt: "Illustrative stack of white diapers in a basket" },
  { id: "stroller", name: "Travel stroller", title: "Demo travel stroller", typical: 300, moment: "Family", image: "/artwork/everyday/stroller.webp", alt: "Illustrative sand-coloured compact stroller" },
  { id: "dog-food", name: "Dry dog food, 30 lb", title: "Demo dry dog food · 30 lb", typical: 55, moment: "Pets", unit: { count: 30, noun: "lb" }, image: "/artwork/everyday/dog-food.webp", alt: "Illustrative paper sack of kibble beside a bowl" },
  { id: "headphones", name: "Wireless headphones", title: "Demo headphones · Black", typical: 200, moment: "Listening", image: "/artwork/headphones.webp", alt: "Illustrative black headphones on a stone surface" },
];

export const everydayByTitle = (title: string) => EVERYDAY.find(p => p.title === title);

/** "$0.34 a load": the price of one unit at the typical pack price, for consumables only. */
export function unitPrice(product: Pick<EverydayProduct, "typical" | "unit">, price = product.typical): string | null {
  if (!product.unit) return null;
  const each = price / product.unit.count;
  return `$${each.toFixed(2)} a ${product.unit.noun}`;
}

/** A uniformly random product other than the current one: chance, not a recommendation. */
export function randomOther(currentId: string | null, random = Math.random): EverydayProduct {
  const pool = EVERYDAY.filter(p => p.id !== currentId);
  return pool[Math.floor(random() * pool.length)];
}
