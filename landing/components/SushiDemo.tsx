"use client";

import { useMemo, useRef, useState, type CSSProperties } from "react";
import {
  MAX_WEEK,
  MOOD_COLOR,
  committedState,
  healthColor,
  petArt,
  stateAtWeek,
} from "@/lib/petModel";

// Manual per-face position/size tuning — percentages of the 160/192px art
// box. Key = art.faceKey ("{Amount}_{Expression}", e.g. "Full_Happy"),
// matching the 9 face images 1:1. Edit any row to nudge/resize that one
// face independently of the others.
const DEFAULT_FACE_OFFSET = { width: 55, height: 55, top: 10, left: 50 };
const FACE_OFFSETS: Record<string, typeof DEFAULT_FACE_OFFSET> = {
  Full_Happy: { width: 55, height: 55, top: 40, left: 40 },
  Full_Mid: { width: 55, height: 55, top: 40, left: 45 },
  Full_Sad: { width: 55, height: 55, top: 10, left: 50 },
  Half_Happy: { width: 55, height: 55, top: 10, left: 50 },
  Half_Mid: { width: 55, height: 55, top: 40, left: 45 },
  Half_Sad: { width: 55, height: 55, top: 40, left: 50 },
  Low_Happy: { width: 55, height: 55, top: 10, left: 50 },
  Low_Mid: { width: 55, height: 55, top: 10, left: 50 },
  Low_Sad: { width: 28, height: 28, top: 53, left: 48 },
};

const HEALTH_INFO = {
  Physical: {
    icon: "heroicons:heart",
    body: "Tied to real hotel pricing and availability — it withers as rooms sell out and the budget gets tighter.",
  },
  Mental: {
    icon: "heroicons:chat-bubble-left-right",
    body: "Tied to the group itself — it tracks how engaged the chat is. Deciding keeps it happy; silence makes it depressed.",
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
  // Same hex thresholds as webapp/app.js healthColor (≥70 / ≥40 / else).
  const color = healthColor(value);
  const dialogRef = useRef<HTMLDialogElement>(null);
  const info = HEALTH_INFO[label];

  return (
    <div className="ds-health-card" style={{ padding: "14px 16px", gap: 12 }}>
      <div className="bar-top">
        <div className="bar-icon">
          <iconify-icon icon={icon} width="20" height="20" />
        </div>
        <div className="bar-name" style={{ fontSize: 14 }}>
          {label}
          <button
            type="button"
            className="ds-info-btn"
            aria-label={`About ${label} health`}
            onClick={() => dialogRef.current?.showModal()}
          >
            <iconify-icon icon="heroicons:information-circle" width="16" height="16" />
          </button>
        </div>
        <div className="bar-val" style={{ fontSize: 24, color }}>
          {Math.round(value)}
        </div>
      </div>
      <div className="bar-outer">
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
  const faceOffset = FACE_OFFSETS[art.faceKey] ?? DEFAULT_FACE_OFFSET;

  return (
    <div className="mx-auto grid w-full max-w-4xl gap-5 lg:grid-cols-2">
      <div
        className="card-lift flex flex-col overflow-hidden"
        style={{
          borderRadius: "var(--radius)",
          background: "var(--surface)",
          boxShadow: "var(--shadow)",
        }}
      >
        <div
          className="relative flex h-56 items-center justify-center overflow-hidden sm:h-64"
          style={{ background: "var(--card-peach)" }}
        >
          <div
            aria-hidden
            className="absolute bottom-6 h-8 w-40 rounded-full transition-all duration-700"
            style={{ background: glow, opacity: 0.22, filter: "blur(22px)" }}
          />

          <div
            key={booked ? "booked" : "alive"}
            className={`relative h-40 w-40 select-none transition-all duration-500 sm:h-48 sm:w-48 ${
              booked ? "animate-pop" : pet.mood === "dying" ? "" : "animate-floaty"
            }`}
            role="img"
            aria-label={`Sushi-kun looking ${pet.mood}`}
          >
            {/* sushi body underneath, face on top — both track the slider via `art` */}
            <img
              src={art.sushiSrc}
              alt=""
              aria-hidden
              className="absolute inset-0 h-full w-full object-contain"
            />
            <img
              src={art.faceSrc}
              alt=""
              aria-hidden
              className="absolute z-10 object-contain"
              style={{
                width: `${faceOffset.width}%`,
                height: `${faceOffset.height}%`,
                top: `${faceOffset.top}%`,
                left: `${faceOffset.left}%`,
                transform: "translateX(-50%)",
              }}
            />
          </div>

          {booked && (
            <div aria-hidden className="pointer-events-none absolute inset-0 flex items-center justify-center">
              {SPARKS.map((s, i) => (
                <span
                  key={i}
                  className="animate-sparkle absolute text-xl"
                  style={
                    {
                      "--spark-x": `${s.x}px`,
                      "--spark-y": `${s.y}px`,
                      "--spark-delay": `${s.delay}s`,
                    } as CSSProperties
                  }
                >
                  ✨
                </span>
              ))}
            </div>
          )}

          <span
            className="ds-chip absolute right-3 top-3"
            style={{ color: glow, background: "var(--surface)" }}
          >
            {pet.mood}
          </span>
        </div>

        <div className="flex flex-1 flex-col gap-4 p-5">
          <p className="ds-title min-h-[1.5rem] text-center text-[15px]" style={{ color: "var(--muted)" }}>
            「{pet.caption}」
          </p>

          <div className="flex flex-wrap justify-center gap-2">
            <span className="ds-stat">
              <iconify-icon icon="heroicons:currency-dollar" width="14" height="14" />
              ${pet.price}/night
            </span>
            <span className="ds-stat">
              <iconify-icon icon="heroicons:building-office-2" width="14" height="14" />
              {pet.rooms} rooms left
            </span>
            <span className="ds-stat">
              <iconify-icon icon="heroicons:calendar-days" width="14" height="14" />
              week {booked ? "—" : pet.week.toFixed(1)}
            </span>
          </div>

          <div className="space-y-3">
            <HealthCard label="Physical" value={pet.physical} icon="heroicons:heart" />
            <HealthCard
              label="Mental"
              value={pet.mental}
              icon="heroicons:chat-bubble-left-right"
            />
          </div>

          <div>
            <div className="mb-2 flex items-center justify-between text-xs" style={{ color: "var(--muted)" }}>
              <span>drag to procrastinate →</span>
              <span className="tabular-nums" style={{ color: "var(--fg)" }}>
                week {booked ? "—" : pet.week.toFixed(1)}
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
                ? { background: "var(--health-good)", color: "var(--surface)" }
                : undefined
            }
          >
            {booked ? "Booked — Sushi-kun is free" : "Book it → revive Sushi-kun"}
          </button>
        </div>
      </div>

      <article className="ds-hotel-card card-lift" style={{ minHeight: 420 }}>
        <div className="photo" style={{ minHeight: 200, flex: "1 1 auto" }}>
          <div
            className="absolute inset-0 flex items-center justify-center"
            style={{
              background: "linear-gradient(145deg, var(--card-peach), var(--card-sky))",
              color: "var(--card-peach-ink)",
            }}
          >
            <iconify-icon icon="heroicons:photo" width="64" height="64" />
          </div>
          <div className="fade" />
        </div>
        <div className="info">
          <div className="name-row">
            <div className="name">Shibuya Stream Hotel</div>
            <div className="price">
              <div className="total">${pet.price}</div>
              <div className="per">
                <iconify-icon icon="heroicons:moon" width="12" height="12" />
                / night
              </div>
            </div>
          </div>
          <div className="meta">
            <span className="tag rating">
              <iconify-icon icon="heroicons:star" width="12" height="12" />
              4.7
            </span>
            <span className="tag type">
              <iconify-icon icon="heroicons:building-office-2" width="12" height="12" />
              hotel
            </span>
            <span className="tag guests">
              <iconify-icon icon="heroicons:user-group" width="12" height="12" />
              sleeps 2
            </span>
            <span className="tag cancel">
              <iconify-icon icon="heroicons:shield-check" width="12" height="12" />
              free cancel
            </span>
          </div>
          <div className="addr">
            <iconify-icon icon="heroicons:map-pin" width="14" height="14" />
            <span>1-2-3 Shibuya, Tokyo</span>
          </div>
        </div>
      </article>
    </div>
  );
}
