"use client";
import { useEffect, useState } from "react";
import { apiRequest } from "@/lib/api/client";

const TITLES: Record<string, string> = { shipping: "Shipping", returns: "Return & Exchange", refund: "Refund", privacy: "Privacy", faq: "Frequently asked questions", about: "About us", contact: "Contact" };
export function StoreInfoPage({ slug }: { slug: string }) {
  const [body, setBody] = useState<string | null>(null);
  useEffect(() => { let live = true; apiRequest<{title:string;body:string}>(`/content/${encodeURIComponent(slug)}`).then((v) => { if(live) { document.title = `${v.title} | RG Thrifting Hub`; setBody(v.body); } }).catch(() => { if(live) setBody(""); }); return () => { live = false; }; }, [slug]);
  return <article className="mx-auto max-w-3xl px-4 py-14 sm:px-6"><p className="eyebrow">RG Thrifting Hub</p><h1 className="mt-2 text-4xl">{TITLES[slug] ?? "Store information"}</h1><div className="mt-8 whitespace-pre-wrap text-sm leading-7 text-ink-muted">{body || (body === null ? "Loading…" : "This information is being updated. Please contact us on WhatsApp.")}</div></article>;
}
