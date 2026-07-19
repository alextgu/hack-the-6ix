"use client";

import { useEffect, useRef, useState } from "react";

/** Light Japanese Zen loop — opt-in (browsers block unmuted autoplay).
 *  Track: MemoryMusic — Peaceful Cherry Blossom (Jamendo / CC BY-NC-ND). */
const SRC = "/music/peaceful-cherry-blossom.mp3";
const VOLUME = 0.28;

export default function AmbientMusic() {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [playing, setPlaying] = useState(false);

  useEffect(() => {
    const audio = new Audio(SRC);
    audio.loop = true;
    audio.preload = "metadata";
    audio.volume = VOLUME;
    audioRef.current = audio;
    return () => {
      audio.pause();
      audio.src = "";
      audioRef.current = null;
    };
  }, []);

  /** Tiny mechanical "switch" blip via Web Audio — two short square-wave ticks
   *  (down-up for on, up-down for off). No asset, runs inside the user's click
   *  gesture so it's never blocked by autoplay policy. */
  function clickSound(turningOn: boolean) {
    try {
      type WA = typeof AudioContext;
      const Ctx: WA | undefined =
        window.AudioContext ??
        (window as unknown as { webkitAudioContext?: WA }).webkitAudioContext;
      if (!Ctx) return;
      const ctx = new Ctx();
      const t0 = ctx.currentTime;
      // Crisp mechanical tick: two very short, bright square blips through a
      // highpass so there's no body — just the snap.
      const hp = ctx.createBiquadFilter();
      hp.type = "highpass";
      hp.frequency.value = 1800;
      hp.connect(ctx.destination);
      const [f1, f2] = turningOn ? [3400, 4800] : [4800, 3400];
      [f1, f2].forEach((freq, k) => {
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.type = "square";
        osc.frequency.value = freq;
        const start = t0 + k * 0.028;
        gain.gain.setValueAtTime(0.09, start);
        gain.gain.exponentialRampToValueAtTime(0.0001, start + 0.016);
        osc.connect(gain).connect(hp);
        osc.start(start);
        osc.stop(start + 0.02);
      });
      setTimeout(() => ctx.close(), 200);
    } catch {
      /* sound is decoration — never let it break the toggle */
    }
  }

  async function toggle() {
    const audio = audioRef.current;
    if (!audio) return;
    if (playing) {
      clickSound(false);
      audio.pause();
      setPlaying(false);
      return;
    }
    clickSound(true);
    try {
      await audio.play();
      setPlaying(true);
    } catch {
      setPlaying(false);
    }
  }

  return (
    <button
      type="button"
      onClick={toggle}
      aria-pressed={playing}
      aria-label={playing ? "Pause ambient music" : "Play ambient music"}
      title={
        playing
          ? "Pause music — Peaceful Cherry Blossom (MemoryMusic)"
          : "Play light Japanese ambient — Peaceful Cherry Blossom (MemoryMusic)"
      }
      className="fixed bottom-5 right-5 z-50 inline-flex items-center justify-center p-2 transition-all hover:scale-110"
      style={{
        color: "#ffffff",
        opacity: playing ? 1 : 0.75,
        background: "transparent",
        border: "none",
        cursor: "pointer",
        filter: "drop-shadow(0 1px 5px rgba(42, 36, 28, 0.5))",
      }}
    >
      <iconify-icon
        icon={playing ? "heroicons:speaker-wave" : "heroicons:speaker-x-mark"}
        width="26"
        height="26"
        aria-hidden
      />
    </button>
  );
}
