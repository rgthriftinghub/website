import type { Metadata } from "next";
import Link from "next/link";

import { ButtonLink } from "@/components/ui/button";

export const metadata: Metadata = {
  title: "Shop by Condition",
  description: "Choose a clear condition grade for preloved clothing at RG Thrifting Hub.",
};

const GRADES = [
  { slug: "premium-plus", title: "Premium Plus", detail: "Like-new pieces with little to no visible wear." },
  { slug: "premium", title: "Premium", detail: "Excellent pieces with only very light signs of previous use." },
  { slug: "excellent", title: "Excellent", detail: "Well-kept pre-loved items with minor, clearly described wear." },
  { slug: "good", title: "Good", detail: "Wear is present and described so you can make an informed choice." },
];

export default function ConditionIndexPage() {
  return <main className="mx-auto max-w-7xl px-4 py-12 sm:px-6 lg:px-8">
    <p className="eyebrow">Shop by condition</p>
    <h1 className="mt-3 font-display text-4xl sm:text-5xl">Find your kind of pre-loved</h1>
    <p className="mt-4 max-w-2xl text-sm leading-7 text-ink-muted">Every piece is checked by hand and graded consistently. Open a grade to see the items currently available.</p>
    <div className="mt-9 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">{GRADES.map((grade) => <Link key={grade.slug} href={`/condition/${grade.slug}`} className="border border-line bg-paper p-6 transition-colors hover:border-gold"><span className="eyebrow">Condition grade</span><h2 className="mt-3 font-display text-2xl">{grade.title}</h2><p className="mt-3 text-sm leading-6 text-ink-muted">{grade.detail}</p><span className="mt-6 inline-block text-xs font-semibold uppercase tracking-wider underline decoration-gold underline-offset-4">Shop {grade.title}</span></Link>)}</div>
    <p className="mt-8 text-sm"><ButtonLink href="/condition-guide" variant="secondary">Read the Condition Guide</ButtonLink></p>
  </main>;
}
