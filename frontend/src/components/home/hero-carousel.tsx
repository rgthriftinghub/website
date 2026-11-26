"use client";

/**
 * Full-bleed hero carousel.
 *
 * Wide images with the headline laid over them, scrolled horizontally. Built on
 * native scroll-snap rather than a transform-based slider, so it stays swipeable
 * on touch, keyboard-scrollable, and correct when a slide is focused — behaviour
 * a JS slider has to reimplement badly.
 *
 * Auto-advance stops permanently once the visitor takes control (swipe, arrow, or
 * dot). Motion that keeps fighting the user is worse than no motion.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import Image from "next/image";
import { ArrowLeft, ArrowRight } from "lucide-react";

import { ButtonLink } from "@/components/ui/button";
import { HERO_SLIDES } from "@/lib/editorial";
import { cn } from "@/lib/utils";

const AUTO_ADVANCE_MS = 6500;

export function HeroCarousel({ images = [] }: { images?: { src: string; alt: string }[] }) {
  const slides = HERO_SLIDES.map((slide, slideIndex) => ({
    ...slide,
    ...(images[slideIndex] ?? {}),
  }));
  const trackRef = useRef<HTMLDivElement>(null);
  const [index, setIndex] = useState(0);
  // Once true, auto-advance never resumes.
  const [userTookOver, setUserTookOver] = useState(false);

  const scrollTo = useCallback((next: number) => {
    const track = trackRef.current;
    if (!track) return;
    const clamped = (next + slides.length) % slides.length;
    track.scrollTo({ left: track.clientWidth * clamped, behavior: "smooth" });
  }, [slides.length]);

  // Derive the active slide from actual scroll position rather than tracking it
  // separately — a swipe and a button press then agree by construction.
  useEffect(() => {
    const track = trackRef.current;
    if (!track) return;
    let frame = 0;
    const onScroll = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        const width = track.clientWidth || 1;
        setIndex(Math.round(track.scrollLeft / width));
      });
    };
    track.addEventListener("scroll", onScroll, { passive: true });
    return () => {
      cancelAnimationFrame(frame);
      track.removeEventListener("scroll", onScroll);
    };
  }, []);

  useEffect(() => {
    if (userTookOver) return;
    // Respect a reduced-motion preference: no automatic movement at all.
    const reduced =
      typeof window !== "undefined" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduced) return;

    const timer = window.setInterval(() => {
      const track = trackRef.current;
      if (!track) return;
      const width = track.clientWidth || 1;
      const current = Math.round(track.scrollLeft / width);
      track.scrollTo({
        left: width * ((current + 1) % slides.length),
        behavior: "smooth",
      });
    }, AUTO_ADVANCE_MS);
    return () => window.clearInterval(timer);
  }, [userTookOver, slides.length]);

  const take = (next: number) => {
    setUserTookOver(true);
    scrollTo(next);
  };

  return (
    <section
      aria-roledescription="carousel"
      aria-label="RG Thrifting Hub collections"
      className="relative isolate border-b border-line bg-ink"
      onPointerDown={() => setUserTookOver(true)}
    >
      <div
        ref={trackRef}
        className="hero-track flex snap-x snap-mandatory overflow-x-auto overflow-y-hidden"
        tabIndex={0}
        aria-label="Collection slides, scrollable"
      >
        {slides.map((slide, slideIndex) => (
          <article
            key={slide.image}
            aria-roledescription="slide"
            aria-label={`${slideIndex + 1} of ${slides.length}`}
            className="relative w-full shrink-0 snap-start"
          >
            {/* The phone hero is a single image-backed panel: its portrait-like
                crop keeps the three-person group, with copy over a soft scrim. */}
            <div className="relative h-[min(68svh,112vw)] min-h-[410px] max-h-[500px] w-full bg-ink sm:h-[66vh] sm:min-h-0 sm:max-h-none lg:h-[76vh] lg:min-h-[600px]">
              <Image
                src={slide.image}
                alt={slide.alt}
                fill
                // First slide is the LCP element.
                priority={slideIndex === 0}
                sizes="100vw"
                className="object-cover object-[95%_top] sm:hidden"
              />
              <Image
                src={slide.image}
                alt={slide.alt}
                fill
                priority={slideIndex === 0}
                sizes="100vw"
                className="hidden object-cover sm:block sm:object-[75%_top]"
              />
              {/* The gradient preserves text contrast across the image. */}
              <div
                aria-hidden
                className="absolute inset-0 bg-[linear-gradient(180deg,rgba(7,16,24,0.02)_0%,rgba(7,16,24,0.12)_30%,rgba(7,16,24,0.72)_58%,rgba(7,16,24,0.42)_100%)] sm:bg-gradient-to-r sm:from-ink sm:via-ink/55 sm:to-transparent"
              />

              <div className="absolute inset-0 flex items-end pb-14 sm:items-center sm:pb-0">
                <div className="mx-auto w-full max-w-7xl px-5 sm:px-6 lg:px-8">
                  <div className="max-w-[72%] sm:max-w-xl">
                    <p className="flex items-center gap-2 text-[9px] font-semibold uppercase tracking-[0.16em] text-gold sm:gap-3 sm:text-[11px] sm:tracking-[0.22em]">
                      <span className="h-px w-7 bg-gold sm:w-8" aria-hidden />
                      {slide.eyebrow}
                    </p>

                    <h1 className="mt-2 font-display text-[clamp(1.65rem,7.2vw,2.25rem)] leading-[0.96] tracking-[-0.03em] text-paper drop-shadow-[0_1px_8px_rgba(0,0,0,0.55)] sm:mt-5 sm:text-6xl sm:leading-[0.98] lg:text-[4.8rem]">
                      {slide.title}
                      <br />
                      <span className="italic text-gold">{slide.titleAccent}</span>
                    </h1>

                    <p className="mt-2 max-w-[22rem] text-[11px] leading-[1.4] text-paper/90 drop-shadow-[0_1px_6px_rgba(0,0,0,0.65)] sm:mt-6 sm:max-w-md sm:text-[15px] sm:leading-[1.7]">
                      {slide.body}
                    </p>

                    <div className="mt-3 flex w-full flex-col items-start gap-2 sm:mt-9 sm:w-auto sm:max-w-none sm:flex-row sm:flex-wrap sm:items-center sm:gap-3">
                      <ButtonLink
                        href={slide.href}
                        variant="gold"
                        size="lg"
                        className="h-10 min-w-0 w-full justify-center gap-1 px-2 py-2 text-[9px] leading-tight tracking-[0.06em] whitespace-normal sm:h-13 sm:w-auto sm:justify-start sm:gap-2 sm:px-8 sm:py-0 sm:text-sm sm:tracking-[0.14em]"
                      >
                        {slide.cta}
                        <ArrowRight className="size-3.5 shrink-0 sm:size-4" aria-hidden />
                      </ButtonLink>
                      <ButtonLink
                        href="/shop?is_new_arrival=true"
                        size="lg"
                        className="h-10 min-w-0 w-full justify-center gap-1 border border-paper/35 bg-transparent px-2 py-2 text-[9px] leading-tight tracking-[0.06em] whitespace-normal text-paper hover:bg-paper hover:text-ink sm:h-13 sm:w-auto sm:justify-start sm:gap-2 sm:px-8 sm:py-0 sm:text-sm sm:tracking-[0.14em]"
                      >
                        This week&rsquo;s arrivals
                      </ButtonLink>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </article>
        ))}
      </div>

      {/* Controls sit above the track, inset to the same gutter as the type. */}
      <div className="pointer-events-none absolute inset-x-0 bottom-7 z-10">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-5 sm:px-6 lg:px-8">
          <div className="pointer-events-auto flex items-center gap-2.5">
          {slides.map((slide, dotIndex) => (
              <button
                key={slide.image}
                type="button"
                onClick={() => take(dotIndex)}
                aria-label={`Show slide ${dotIndex + 1}: ${slide.eyebrow}`}
                aria-current={dotIndex === index || undefined}
                className={cn(
                  "h-[3px] transition-all duration-300",
                  dotIndex === index
                    ? "w-10 bg-gold"
                    : "w-5 bg-paper/30 hover:bg-paper/60"
                )}
              />
            ))}
          </div>

          <div className="pointer-events-auto hidden items-center gap-2 sm:flex">
            <button
              type="button"
              onClick={() => take(index - 1)}
              aria-label="Previous slide"
              className="grid size-10 place-items-center border border-paper/25 text-paper transition-colors hover:border-gold hover:bg-gold hover:text-ink"
            >
              <ArrowLeft className="size-4" aria-hidden />
            </button>
            <button
              type="button"
              onClick={() => take(index + 1)}
              aria-label="Next slide"
              className="grid size-10 place-items-center border border-paper/25 text-paper transition-colors hover:border-gold hover:bg-gold hover:text-ink"
            >
              <ArrowRight className="size-4" aria-hidden />
            </button>
          </div>
        </div>
      </div>
    </section>
  );
}
