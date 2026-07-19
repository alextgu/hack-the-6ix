"use client";

import { useEffect, useRef, useState } from "react";

/** Muted autoplay YouTube Short — portrait crop to cut letterbox bars. */
export default function PipelineYouTube({
  videoId,
  title,
}: {
  videoId: string;
  title: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [active, setActive] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    const io = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) setActive(true);
      },
      { threshold: 0.35 },
    );
    io.observe(el);
    return () => io.disconnect();
  }, []);

  const src =
    `https://www.youtube.com/embed/${videoId}` +
    `?autoplay=1&mute=1&playsinline=1&loop=1&playlist=${videoId}` +
    `&controls=0&disablekb=1&fs=0&iv_load_policy=3&rel=0&modestbranding=1`;

  return (
    <div
      ref={ref}
      className="absolute inset-0 flex items-center justify-center"
      style={{ background: "#1a1612" }}
    >
      {/* 9:16 short frame — clips YouTube's side letterboxing */}
      <div className="relative h-full max-h-full w-auto overflow-hidden" style={{ aspectRatio: "9 / 16" }}>
        {active ? (
          <iframe
            src={src}
            title={title}
            className="pointer-events-none absolute left-1/2 top-1/2 border-0"
            style={{
              width: "177.78%",
              height: "100%",
              transform: "translate(-50%, -50%) scale(1.15)",
              transformOrigin: "center center",
            }}
            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
            tabIndex={-1}
            referrerPolicy="strict-origin-when-cross-origin"
          />
        ) : (
          <div
            className="absolute inset-0 flex items-center justify-center"
            style={{ background: "var(--card-peach)", color: "var(--muted)" }}
          >
            <iconify-icon icon="heroicons:play-circle" width="48" height="48" />
          </div>
        )}
      </div>
    </div>
  );
}
