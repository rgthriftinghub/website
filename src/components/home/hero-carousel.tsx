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
            {/* Tall on phones, cinematic on desktop. */}
            <div className="relative h-[86svh] min-h-[560px] w-full sm:h-[66vh] sm:min-h-0 lg:h-[76vh] lg:min-h-[600px]">
              <Image
                src={slide.image}
                alt={slide.alt}
                fill
                // First slide is the LCP element.
                priority={slideIndex === 0}
                sizes="100vw"
                className="object-cover object-[62%_top] sm:object-[75%_top]"
              />
              {/* Scrim: the image already darkens left-to-right, this guarantees
                  contrast for the type at every viewport width. */}
              <div
                aria-hidden
                className="absolute inset-0 bg-gradient-to-t from-ink via-ink/55 to-ink/15 sm:bg-gradient-to-r sm:from-ink sm:via-ink/55 sm:to-transparent"
              />

              <div className="absolute inset-0 flex items-end pb-20 sm:items-center sm:pb-0">
                <div className="mx-auto w-full max-w-7xl px-5 sm:px-6 lg:px-8">
                  <div className="max-w-xl">
                    <p className="flex items-center gap-3 text-[11px] font-semibold uppercase tracking-[0.22em] text-gold">
                      <span className="h-px w-8 bg-gold" aria-hidden />
                      {slide.eyebrow}
                    </p>

                    <h1 className="mt-4 font-display text-[2.3rem] leading-[1.02] tracking-[-0.02em] text-paper sm:mt-5 sm:text-6xl sm:leading-[0.98] lg:text-[4.8rem]">
                      {slide.title}
                      <br />
                      <span className="italic text-gold">{slide.titleAccent}</span>
                    </h1>

                    <p className="mt-4 max-w-md text-[14px] leading-[1.65] text-paper/75 sm:mt-6 sm:text-[15px] sm:leading-[1.7]">
                      {slide.body}
                    </p>

                    <div className="mt-6 flex flex-col gap-2.5 sm:mt-9 sm:flex-row sm:flex-wrap sm:items-center sm:gap-3">
                      <ButtonLink
                        href={slide.href}
                        variant="gold"
                        size="lg"
                        className="justify-center sm:justify-start"
                      >
                        {slide.cta}
                        <ArrowRight className="size-4" aria-hidden />
                      </ButtonLink>
                      <ButtonLink
                        href="/shop?is_new_arrival=true"
                        size="lg"
                        className="justify-center border border-paper/25 bg-transparent text-paper hover:bg-paper hover:text-ink sm:justify-start"
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
