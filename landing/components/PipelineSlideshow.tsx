"use client";

import { useCallback, useEffect, useState } from "react";
import PipelineYouTube from "@/components/PipelineYouTube";

type Step = { title: string; body: string };
export type PipelineCard = {
  phase: string;
  media: string;
  mediaExtra?: string;
  mediaType: "duo" | "image" | "youtube";
  fit: "contain" | "cover";
  mediaAlt: string;
  imageSide: "left" | "right";
  steps: Step[];
};

const AUTO_MS = 20_000; // advance every 20s; resets on any manual nav

/** One-at-a-time slideshow of the pipeline phases. Auto-advances every 20s,
 *  pauses while hovered; arrows + dots for manual control (which resets the timer). */
export default function PipelineSlideshow({ cards }: { cards: PipelineCard[] }) {
  const n = cards.length;
  const [i, setI] = useState(0);
  const [hovered, setHovered] = useState(false);
  const go = useCallback((next: number) => setI(((next % n) + n) % n), [n]);

  // Timer is keyed on `i`, so any change — auto or manual — restarts the 20s.
  // Paused while the slideshow is hovered.
  useEffect(() => {
    if (hovered) return;
    const t = setTimeout(() => setI((c) => (c + 1) % n), AUTO_MS);
    return () => clearTimeout(t);
  }, [i, n, hovered]);

  const card = cards[i];
  const imageFirst = card.imageSide === "left";
  const mediaClass =
    card.fit === "contain"
      ? "absolute inset-0 h-full w-full object-contain p-3 sm:p-4"
      : "absolute inset-0 h-full w-full object-cover";

  return (
    <div
      className="relative"
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      <article
        key={i}
        className="pipe-slide overflow-hidden"
        style={{
          borderRadius: "var(--radius)",
          background: "var(--surface)",
          boxShadow: "var(--shadow)",
        }}
      >
        <div className="grid items-stretch lg:grid-cols-[1.55fr_minmax(0,1fr)]">
          <div
            className={`relative min-h-[300px] overflow-hidden sm:min-h-[360px] lg:min-h-[460px] ${
              imageFirst ? "lg:order-1" : "lg:order-2"
            }`}
            style={{ background: "var(--card-peach)" }}
          >
            {card.mediaType === "youtube" ? (
              <PipelineYouTube videoId={card.media} title={card.mediaAlt} />
            ) : card.mediaType === "duo" && card.mediaExtra ? (
              <div className="absolute inset-0 flex items-center justify-center gap-3 p-4 sm:gap-5 sm:p-6">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={card.media}
                  alt={card.mediaAlt}
                  className="h-[92%] max-h-full w-auto max-w-[60%] object-contain drop-shadow-sm"
                />
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={card.mediaExtra}
                  alt="Tabi avatar states fading through health moods"
                  className="h-[86%] max-h-full w-auto max-w-[46%] object-contain"
                />
              </div>
            ) : (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={card.media} alt={card.mediaAlt} className={mediaClass} />
            )}
            <div
              className="pointer-events-none absolute inset-0"
              style={{ boxShadow: "inset 0 0 0 1px rgba(42,36,28,0.05)" }}
              aria-hidden
            />
          </div>

          <div
            className={`relative flex flex-col justify-center overflow-hidden p-7 sm:p-8 lg:p-9 ${
              imageFirst ? "lg:order-2" : "lg:order-1"
            }`}
          >
            <span
              aria-hidden
              className="ds-title pointer-events-none absolute -top-3 right-3 select-none leading-none tabular-nums"
              style={{ fontSize: "6.5rem", color: "var(--fg)", opacity: 0.05 }}
            >
              {i + 1}
            </span>
            <p
              className="mb-5 inline-flex w-fit items-center gap-2 text-xs font-semibold uppercase tracking-[0.22em]"
              style={{ color: "var(--card-coral-ink)" }}
            >
              <span
                className="inline-block h-1.5 w-1.5 rounded-full"
                style={{ background: "var(--card-coral-ink)" }}
              />
              Phase {i + 1} · {card.phase}
            </p>
            <ul className="relative flex flex-col gap-4">
              {card.steps.map((step, si) => (
                <li key={step.title} className="flex gap-3">
                  <span
                    className="ds-title mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs tabular-nums"
                    style={{ background: "var(--card-peach)", color: "var(--fg)" }}
                  >
                    {si + 1}
                  </span>
                  <div>
                    <h3 className="ds-title text-base leading-snug sm:text-[1.05rem]">
                      {step.title}
                    </h3>
                    <p className="mt-1 text-[0.82rem] leading-relaxed" style={{ color: "var(--muted)" }}>
                      {step.body}
                    </p>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </article>

      {/* Arrows — overlap the card edges, vertically centered. */}
      <button
        type="button"
        aria-label="Previous phase"
        onClick={() => go(i - 1)}
        className="pipe-arrow"
        style={{ left: 0 }}
      >
        <iconify-icon icon="heroicons:chevron-left" width="22" height="22" />
      </button>
      <button
        type="button"
        aria-label="Next phase"
        onClick={() => go(i + 1)}
        className="pipe-arrow"
        style={{ right: 0 }}
      >
        <iconify-icon icon="heroicons:chevron-right" width="22" height="22" />
      </button>

      {/* Dots */}
      <div className="mt-6 flex items-center justify-center gap-2.5">
        {cards.map((c, d) => (
          <button
            key={c.phase}
            type="button"
            aria-label={`Go to phase ${d + 1}: ${c.phase}`}
            aria-current={d === i}
            onClick={() => go(d)}
            className="pipe-dot"
            data-active={d === i}
          />
        ))}
      </div>
    </div>
  );
}
