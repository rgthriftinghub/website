"use client";
import { useEffect, useState } from "react";
import { apiRequest } from "@/lib/api/client";
import { Button } from "@/components/ui/button";

type Review = { id: string; rating: number; title: string | null; body: string | null; created_at: string };
export function ProductReviews({ slug, average, count }: { slug: string; average: number; count: number }) {
  const [reviews, setReviews] = useState<Review[]>([]);
  const [rating, setRating] = useState(5);
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [message, setMessage] = useState("");
  useEffect(() => { apiRequest<Review[]>(`/products/${encodeURIComponent(slug)}/reviews`, { revalidate: 30 }).then(setReviews).catch(() => setReviews([])); }, [slug]);
  async function submit(event: React.FormEvent) {
    event.preventDefault(); setMessage("");
    try {
      await apiRequest<Review>(`/products/${encodeURIComponent(slug)}/reviews`, { method: "POST", body: { rating, title: title || null, body: body || null } });
      setMessage("Your review has been saved.");
      setReviews(await apiRequest<Review[]>(`/products/${encodeURIComponent(slug)}/reviews`));
    } catch (error) { setMessage(error instanceof Error ? error.message : "Could not save review."); }
  }
  return <section className="mt-14 border-t border-line pt-8" aria-labelledby="reviews-title">
    <h2 id="reviews-title" className="font-display text-2xl">Customer reviews</h2>
    <p className="mt-2 text-sm text-ink-muted">{count ? `★ ${average.toFixed(1)} / 5 · ${count} ${count === 1 ? "review" : "reviews"}` : "No ratings yet"}</p>
    <form onSubmit={submit} className="mt-6 grid max-w-xl gap-3">
      <label className="text-xs uppercase tracking-wider text-ink-muted">Rating <select className="ml-3 border border-line bg-paper p-2" value={rating} onChange={e => setRating(Number(e.target.value))}>{[5,4,3,2,1].map(n => <option key={n} value={n}>{n} stars</option>)}</select></label>
      <input aria-label="Review title" className="border border-line bg-paper p-3 text-sm" placeholder="Review title" maxLength={120} value={title} onChange={e => setTitle(e.target.value)} />
      <textarea aria-label="Your review" className="border border-line bg-paper p-3 text-sm" placeholder="Share your experience" maxLength={3000} rows={4} value={body} onChange={e => setBody(e.target.value)} />
      <Button type="submit" className="w-fit">Submit review</Button>
      {message ? <p role="status" className="text-sm text-ink-muted">{message}</p> : null}
      <p className="text-xs text-stone">Reviews are accepted from customers with a delivered order.</p>
    </form>
    <div className="mt-8 grid gap-4 md:grid-cols-2">{reviews.map(review => <article key={review.id} className="border border-line p-4"><p className="text-gold-deep">{"★".repeat(review.rating)}{"☆".repeat(5-review.rating)}</p>{review.title ? <h3 className="mt-2 font-medium">{review.title}</h3> : null}{review.body ? <p className="mt-2 text-sm text-ink-muted">{review.body}</p> : null}<time className="mt-3 block text-xs text-stone">{new Date(review.created_at).toLocaleDateString()}</time></article>)}</div>
  </section>;
}
