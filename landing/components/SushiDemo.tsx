"use client";

import { useEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import {
  MAX_WEEK,
  MOOD_COLOR,
  committedState,
  healthColor,
  petArt,
  stateAtWeek,
} from "@/lib/petModel";

const AVATAR_FADE_MS = 500;

const HEALTH_INFO = {
  Physical: {
    icon: "heroicons:heart",
    body: "Tied to real hotel pricing and availability. It withers as rooms sell out and the budget gets tighter.",
  },
  Mental: {
    icon: "heroicons:chat-bubble-left-right",
    body: "Tied to the group itself. It tracks how engaged the chat is. Deciding keeps it happy; silence makes it depressed.",
  },
} as const;

const MOOD_NOTE = "Every update, it posts its current mood back into the chat.";

function HealthCard({
  label,
  value,
  icon,
}: {
  label: keyof typeof HEALTH_INFO;
  value: number;
  icon: string;
}) {
  const color = healthColor(value);
  const dialogRef = useRef<HTMLDialogElement>(null);
  const info = HEALTH_INFO[label];

  return (
    <div className="ds-health-card" style={{ padding: "10px 12px", gap: 8 }}>
      <div className="bar-top" style={{ gap: 8 }}>
        <div className="bar-icon" style={{ width: 32, height: 32, borderRadius: 10 }}>
          <iconify-icon icon={icon} width="16" height="16" />
        </div>
        <div className="bar-name" style={{ fontSize: 12 }}>
          {label}
          <button
            type="button"
            className="ds-info-btn"
            aria-label={`About ${label} health`}
            onClick={() => dialogRef.current?.showModal()}
            style={{ width: 18, height: 18 }}
          >
            <iconify-icon icon="heroicons:information-circle" width="14" height="14" />
          </button>
        </div>
        <div className="bar-val" style={{ fontSize: 20, color }}>
          {Math.round(value)}
        </div>
      </div>
      <div className="bar-outer" style={{ height: 8 }}>
        <div
          className="bar-inner"
          style={{ width: `${value}%`, background: color }}
        />
      </div>

      <dialog
        ref={dialogRef}
        className="ds-info-dialog"
        onClick={(e) => {
          if (e.target === dialogRef.current) dialogRef.current.close();
        }}
      >
        <h3>
          <iconify-icon icon={info.icon} width="20" height="20" />
          {label}
        </h3>
        <p>{info.body}</p>
        <p className="note">{MOOD_NOTE}</p>
        <button
          type="button"
          className="ds-cta"
          onClick={() => dialogRef.current?.close()}
        >
          Got it
        </button>
      </dialog>
    </div>
  );
}

const SPARKS = [
  { x: -70, y: -50, delay: 0 },
  { x: 70, y: -55, delay: 0.08 },
  { x: -45, y: -85, delay: 0.16 },
  { x: 45, y: -80, delay: 0.05 },
  { x: 0, y: -95, delay: 0.12 },
  { x: -85, y: -10, delay: 0.2 },
  { x: 85, y: -15, delay: 0.14 },
];

export default function SushiDemo() {
  const [week, setWeek] = useState(0);
  const [booked, setBooked] = useState(false);

  const pet = useMemo(() => (booked ? committedState() : stateAtWeek(week)), [week, booked]);
  const glow = MOOD_COLOR[pet.mood];
  const art = useMemo(() => petArt(pet.physical, pet.mental), [pet]);

  // Crossfade when the sprite key changes (0.5s).
  const [shownSrc, setShownSrc] = useState(art.src);
  const [outgoingSrc, setOutgoingSrc] = useState<string | null>(null);
  const [fadeIn, setFadeIn] = useState(true);
  const shownRef = useRef({ key: art.key, src: art.src });
  const fadeTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (art.key === shownRef.current.key) return;

    const prevSrc = shownRef.current.src;
    shownRef.current = { key: art.key, src: art.src };

    if (fadeTimer.current) clearTimeout(fadeTimer.current);

    setOutgoingSrc(prevSrc);
    setShownSrc(art.src);
    setFadeIn(false);

    const raf = requestAnimationFrame(() => {
      requestAnimationFrame(() => setFadeIn(true));
    });
    fadeTimer.current = setTimeout(() => {
      setOutgoingSrc(null);
      fadeTimer.current = null;
    }, AVATAR_FADE_MS);

    return () => {
      cancelAnimationFrame(raf);
    };
  }, [art.key, art.src]);

  // Clear fade timer on unmount only.
  useEffect(() => {
    return () => {
      if (fadeTimer.current) clearTimeout(fadeTimer.current);
    };
  }, []);

  return (
    <div className="mx-auto grid w-full max-w-3xl items-stretch gap-4 lg:grid-cols-2">
      <div
        className="card-lift flex flex-col overflow-hidden"
        style={{
          borderRadius: "calc(var(--radius) * 0.85)",
          background: "var(--surface)",
          boxShadow: "var(--shadow)",
        }}
      >
        <div
          className="relative flex h-40 items-center justify-center overflow-hidden sm:h-44"
          style={{ background: "var(--card-peach)" }}
        >
          <div
            aria-hidden
            className="absolute bottom-4 h-6 w-32 rounded-full transition-all duration-700"
            style={{ background: glow, opacity: 0.22, filter: "blur(18px)" }}
          />

          <div
            key={booked ? "booked" : "alive"}
            className={`relative h-32 w-32 select-none sm:h-36 sm:w-36 ${
              booked ? "animate-pop" : pet.mood === "dying" ? "" : "animate-floaty"
            }`}
            role="img"
            aria-label={`Tama-Go-Chi looking ${pet.mood}`}
          >
            {outgoingSrc && (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={outgoingSrc}
                alt=""
                aria-hidden
                className="absolute inset-0 h-full w-full object-contain"
                style={{
                  opacity: fadeIn ? 0 : 1,
                  transition: `opacity ${AVATAR_FADE_MS}ms ease`,
                }}
              />
            )}
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={shownSrc}
              alt=""
              className="absolute inset-0 h-full w-full object-contain"
              style={{
                opacity: outgoingSrc ? (fadeIn ? 1 : 0) : 1,
                transition: outgoingSrc
                  ? `opacity ${AVATAR_FADE_MS}ms ease`
                  : undefined,
              }}
            />
          </div>

          {booked && (
            <div aria-hidden className="pointer-events-none absolute inset-0 flex items-center justify-center">
              {SPARKS.map((s, i) => (
                <span
                  key={i}
                  className="animate-sparkle absolute text-base"
                  style={
                    {
                      "--spark-x": `${s.x * 0.8}px`,
                      "--spark-y": `${s.y * 0.8}px`,
                      "--spark-delay": `${s.delay}s`,
                    } as CSSProperties
                  }
                >
                  ✨
                </span>
              ))}
            </div>
          )}
        </div>

        <div className="flex flex-1 flex-col gap-3 p-3.5 sm:p-4">
          <div className="flex flex-wrap justify-center gap-1.5">
            <span className="ds-stat" style={{ fontSize: 11 }}>
              ${pet.price}/night
            </span>
            <span className="ds-stat" style={{ fontSize: 11 }}>
              <iconify-icon icon="heroicons:building-office-2" width="12" height="12" />
              {pet.rooms} rooms left
            </span>
            <span className="ds-stat" style={{ fontSize: 11 }}>
              <iconify-icon icon="heroicons:calendar-days" width="12" height="12" />
              week {booked ? "-" : pet.week.toFixed(1)}
            </span>
          </div>

          <div className="space-y-2">
            <HealthCard label="Physical" value={pet.physical} icon="heroicons:heart" />
            <HealthCard
              label="Mental"
              value={pet.mental}
              icon="heroicons:chat-bubble-left-right"
            />
          </div>

          <div>
            <div
              className="mb-1.5 flex items-center justify-between"
              style={{ color: "var(--muted)", fontSize: 11 }}
            >
              <span>drag to procrastinate →</span>
              <span className="tabular-nums" style={{ color: "var(--fg)" }}>
                week {booked ? "-" : pet.week.toFixed(1)}
              </span>
            </div>
            <input
              type="range"
              min={0}
              max={MAX_WEEK}
              step={0.1}
              value={week}
              onChange={(e) => {
                setBooked(false);
                setWeek(Number(e.target.value));
              }}
              className="scrubber w-full"
              aria-label="Weeks of procrastination"
            />
          </div>

          <button
            type="button"
            onClick={() => setBooked(true)}
            disabled={booked}
            className="ds-cta w-full"
            style={
              booked
                ? {
                    background: "var(--health-good)",
                    color: "var(--surface)",
                    fontSize: 13,
                    padding: "11px 16px",
                  }
                : { fontSize: 13, padding: "11px 16px" }
            }
          >
            {booked ? "Booked, Sushi-kun is free" : "Book it → revive Sushi-kun"}
          </button>
        </div>
      </div>

      <article
        className="ds-hotel-card card-lift flex h-full min-h-[100%] flex-col"
        style={{ borderRadius: "calc(var(--radius) * 0.85)" }}
      >
        <div className="photo" style={{ flex: "1 1 auto", minHeight: 220 }}>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src="/shibuya-stream-hotel.png"
            alt="Shibuya Stream Hotel room"
            className="absolute inset-0 h-full w-full object-cover"
          />
          <div className="fade" style={{ height: 40 }} />
        </div>
        <div
          className="info"
          style={{
            flex: "0 0 auto",
            padding: "8px 10px 9px",
            gap: 4,
          }}
        >
          <div className="name-row" style={{ alignItems: "baseline", gap: 6 }}>
            <div className="name" style={{ fontSize: 14, lineHeight: 1.2 }}>
              Shibuya Stream Hotel
            </div>
            <div
              className="price"
              style={{
                display: "inline-flex",
                alignItems: "baseline",
                gap: 3,
                whiteSpace: "nowrap",
              }}
            >
              <span className="total" style={{ fontSize: 15 }}>
                ${pet.price}
              </span>
              <span className="per" style={{ marginTop: 0, fontSize: 10 }}>
                / night
              </span>
            </div>
          </div>
          <div className="meta" style={{ gap: 4 }}>
            <span className="tag rating" style={{ fontSize: 10, padding: "2px 7px", gap: 3 }}>
              <iconify-icon icon="heroicons:star" width="10" height="10" />
              4.7
            </span>
            <span className="tag type" style={{ fontSize: 10, padding: "2px 7px", gap: 3 }}>
              <iconify-icon icon="heroicons:building-office-2" width="10" height="10" />
              hotel
            </span>
            <span className="tag guests" style={{ fontSize: 10, padding: "2px 7px", gap: 3 }}>
              <iconify-icon icon="heroicons:user-group" width="10" height="10" />
              sleeps 2
            </span>
            <span className="tag cancel" style={{ fontSize: 10, padding: "2px 7px", gap: 3 }}>
              <iconify-icon icon="heroicons:shield-check" width="10" height="10" />
              free cancel
            </span>
          </div>
          <div className="addr" style={{ fontSize: 10, gap: 3 }}>
            <iconify-icon icon="heroicons:map-pin" width="11" height="11" />
            <span>1-2-3 Shibuya, Tokyo</span>
          </div>
        </div>
      </article>
    </div>
  );
}
