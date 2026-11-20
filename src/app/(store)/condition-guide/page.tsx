import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Condition Guide",
  description: "Learn how RG Thrifting Hub grades pre-loved clothing before listing each piece.",
};

const GRADES = [
  { title: "Premium Plus", slug: "premium-plus", copy: "Like-new condition with little to no visible wear. Any small imperfection is called out in the product description." },
  { title: "Premium", slug: "premium", copy: "Excellent overall condition with very light signs of previous use. The fabric, seams and fastenings are checked before listing." },
  { title: "Excellent", slug: "excellent", copy: "Well-kept pre-loved clothing with minor signs of wear. Any notable marks or repairs are described on the product page." },
  { title: "Good", slug: "good", copy: "A wearable pre-loved piece with visible signs of use. We describe known wear clearly so you can decide before ordering." },
];

export default function ConditionGuidePage() {
  return <main className="mx-auto max-w-4xl px-4 py-14 sm:px-6 lg:px-8"><p className="eyebrow">How we grade</p><h1 className="mt-3 font-display text-4xl sm:text-5xl">Condition Guide</h1><p className="mt-5 max-w-2xl text-sm leading-7 text-ink-muted">Each garment is checked by hand before it is listed. Grades describe the overall visible condition; product photos and descriptions show details for that individual item.</p><div className="mt-9 divide-y divide-line border-y border-line">{GRADES.map((grade) => <section key={grade.slug} className="py-6"><h2 className="font-display text-2xl"><Link href={`/condition/${grade.slug}`} className="underline decoration-gold underline-offset-4">{grade.title}</Link></h2><p className="mt-2 text-sm leading-7 text-ink-muted">{grade.copy}</p></section>)}</div><p className="mt-7 text-xs leading-6 text-stone">Pre-loved garments are individually sourced, so minor differences and signs of previous use can occur. Please review the photos and item notes before ordering.</p></main>;
}
