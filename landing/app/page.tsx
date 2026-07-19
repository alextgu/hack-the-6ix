import type { ReactNode } from "react";
import SushiDemo from "@/components/SushiDemo";
import Reveal from "@/components/Reveal";
import Petals from "@/components/Petals";

// PLACEHOLDER — swap for the real bot handle.
const BOT_HANDLE = "@YourBotHandle";
const BOT_URL = `https://t.me/${BOT_HANDLE.replace(/^@/, "")}`;

const SPONSORS = ["Stay22", "Phoebe", "Freesolo", "MongoDB Atlas", "ElevenLabs", "Gemini"];

const MECHANICS = [
  {
    icon: "heroicons:chat-bubble-left-right",
    title: "Listens in chat",
    body: "Picks up city, dates, budget, and group size from the conversation as the trip takes shape.",
  },
  {
    icon: "heroicons:heart",
    title: "Physical bar",
    body: "Tied to live Stay22 market pressure. Prices rising and rooms selling off make the pet sick.",
  },
  {
    icon: "heroicons:user-group",
    title: "Mental bar",
    body: "Tracks group engagement. Phoebe targets the keystone whose yes unsticks everyone else.",
  },
  {
    icon: "heroicons:speaker-wave",
    title: "Voice and booking",
    body: "When health crashes, it nudges with voice. On commit, Stay22 hands over a finished booking.",
  },
];

const PILLARS = [
  {
    icon: "heroicons:chat-bubble-left-right",
    title: "Read",
    body: "Gemini parses the group chat into trip constraints (city, dates, budget, group size) and reconciles conflicting answers into one plan.",
  },
  {
    icon: "heroicons:currency-dollar",
    title: "Price",
    body: "Stay22 feeds live hotel pricing and availability into Physical health. Procrastination shows up as rising prices and rooms selling off.",
  },
  {
    icon: "heroicons:photo",
    title: "Render",
    body: "The Telegram Mini App draws the pet's moods and posts the updated face whenever either bar moves, so the group sees the trip's vital signs in chat.",
  },
  {
    icon: "heroicons:speaker-wave",
    title: "Speak",
    body: "ElevenLabs gives the pet a voice with real emotional inflection: bright when the trip's alive, weak when a bar bottoms out.",
  },
  {
    icon: "heroicons:megaphone",
    title: "Pitch",
    body: "Phoebe diagnoses the one blocker (person, timing, or issue), targets the keystone, and removes the objection. Freesolo trains that agent via GRPO self-play with a turn-level, ground-truth reward.",
  },
  {
    icon: "heroicons:circle-stack",
    title: "Store",
    body: "MongoDB Atlas holds group, pet, and preference state: vector search for matching, time-series for health and price history, change streams for live updates.",
  },
];

const ACCOMPLISHMENTS = [
  {
    icon: "heroicons:user-group",
    title: "Finding the keystone",
    body: "Phoebe learns friend roles from behavior (keystone, anchor, flake) and targets the person whose yes unsticks the whole group, instead of broadcasting nags.",
  },
  {
    icon: "heroicons:cpu-chip",
    title: "Freesolo over a frontier baseline",
    body: "Our GRPO-trained agent beat a frontier baseline on held-out friend-group scenarios, scored with a verifiable commit reward rather than a hackable LLM judge.",
  },
  {
    icon: "heroicons:musical-note",
    title: "Voice that lands",
    body: "The ElevenLabs voice is charming when the trip is healthy and heartbreaking when it isn't, with emotional inflection that makes the pet feel like a creature, not a notification.",
  },
];

const LEARNINGS = [
  {
    icon: "heroicons:circle-stack",
    title: "MongoDB is the nervous system",
    body: "One database covered matching (vector search), memory (time-series health/price), and live sync (change streams), not just CRUD.",
  },
  {
    icon: "heroicons:heart",
    title: "Personality beats deep reasoning",
    body: "Feeling \"alive\" came more from mood, voice, and timely nudges than from longer chain-of-thought. The group reacts to presence.",
  },
  {
    icon: "heroicons:shield-check",
    title: "Self-play needs a hard reward",
    body: "GRPO only worked once we paired self-play with a verifiable turn-level reward and adversarial tests against reward hacking.",
  },
];

const NEXT_STEPS = [
  {
    icon: "heroicons:bolt",
    title: "Live change streams",
    body: "Push pet updates the instant health moves, with no polling lag between market ticks and the face in chat.",
  },
  {
    icon: "heroicons:phone",
    title: "Voice-driven booking",
    body: "Two-way ElevenLabs in Telegram: reply to the pet and it takes a real action, like holding a room, DMing the holdout, or kicking off onboarding.",
  },
  {
    icon: "heroicons:users",
    title: "More archetypes",
    body: "Expand beyond keystone / anchor / flake so Phoebe's targeting covers messier real friend groups.",
  },
  {
    icon: "heroicons:map",
    title: "A real pilot group",
    body: "Ship into one stalled Japan trip chat and measure whether the pet actually gets them to book.",
  },
];

function CTAButton({ large = false }: { large?: boolean }) {
  return (
    <a href={BOT_URL} className={large ? "ds-cta hero-cta" : "ds-cta"}>
      Add to Telegram
      <span
        style={{
          opacity: 0.7,
          fontFamily: "var(--font-body)",
          fontSize: large ? 14 : 13,
        }}
      >
        {BOT_HANDLE}
      </span>
    </a>
  );
}

function SectionTitle({
  children,
  eyebrow,
}: {
  children: ReactNode;
  eyebrow?: string;
}) {
  return (
    <div className="mb-10 text-center">
      {eyebrow ? (
        <p
          className="mb-3 text-xs uppercase tracking-[0.28em]"
          style={{ color: "var(--muted)" }}
        >
          {eyebrow}
        </p>
      ) : null}
      <h2 className="ds-title text-3xl sm:text-4xl">{children}</h2>
    </div>
  );
}

function CardGrid({
  items,
  cols = "sm:grid-cols-2",
}: {
  items: { icon: string; title: string; body: string }[];
  cols?: string;
}) {
  return (
    <div className={`grid gap-5 ${cols}`}>
      {items.map((item, i) => (
        <Reveal key={item.title} delay={i * 90}>
          <div className="ds-health-card card-lift h-full">
            <div className="bar-top">
              <div className="bar-icon">
                <iconify-icon icon={item.icon} width="22" height="22" />
              </div>
              <h3 className="bar-name">{item.title}</h3>
            </div>
            <p className="text-sm leading-relaxed" style={{ color: "var(--muted)" }}>
              {item.body}
            </p>
          </div>
        </Reveal>
      ))}
    </div>
  );
}

export default function Home() {
  return (
    <main className="min-h-screen" style={{ color: "var(--fg)" }}>
      {/* ─── 1. Hero ──────────────────────────────────────────────────────── */}
      <section className="hero-split relative lg:grid lg:min-h-dvh lg:grid-cols-[minmax(0,55fr)_minmax(0,45fr)]">
        <div className="relative flex flex-col justify-center px-6 py-16 sm:px-10 sm:py-20 lg:px-12 lg:py-24 xl:px-16">
          <Petals />

          <div className="relative mx-auto w-full max-w-xl lg:mx-0 lg:max-w-[34rem]">
            <Reveal>
              <p className="ds-chip mb-7" style={{ display: "inline-flex" }}>
                <iconify-icon icon="heroicons:map-pin" width="14" height="14" />
                Tama-Go-Chi · Hack the 6ix
              </p>
            </Reveal>
            <Reveal delay={100}>
              <h1 className="ds-title text-[2.15rem] leading-[1.12] sm:text-5xl lg:text-[3.15rem]">
                Everyone wants to go to Japan.
                <br />
                <span style={{ color: "var(--card-coral-ink)" }}>Nobody books it.</span>
              </h1>
            </Reveal>
            <Reveal delay={200}>
              <p
                className="mt-6 max-w-md text-base leading-relaxed sm:text-lg"
                style={{ color: "var(--muted)" }}
              >
                Built at Hack the 6ix: a Telegram pet whose Physical health tracks live
                hotel data and whose Mental health tracks group engagement. The only way
                to save it is to actually book the trip.
              </p>
            </Reveal>
            <Reveal delay={320}>
              <div className="mt-10 sm:mt-12">
                <CTAButton large />
              </div>
            </Reveal>
          </div>
        </div>

        <div className="hero-poster relative isolate h-[min(62vh,520px)] w-full overflow-hidden lg:h-auto lg:min-h-dvh">
          {/* eslint-disable-next-line @next/next/no-img-element -- full-bleed editorial panel */}
          <img
            src="/tokyo-poster.png"
            alt="Vintage Tokyo travel poster with pagoda and cherry blossoms"
            className="absolute inset-0 h-full w-full object-cover object-[center_20%] lg:object-center"
            decoding="async"
            fetchPriority="high"
          />
        </div>
      </section>

      {/* ─── 2. Problem / Inspiration ─────────────────────────────────────── */}
      <section className="relative mx-auto max-w-3xl px-6 py-20">
        <Petals />
        <div className="relative">
          <Reveal>
            <SectionTitle eyebrow="Inspiration">The groupchat that never leaves</SectionTitle>
          </Reveal>
          <Reveal delay={120}>
            <p className="text-center text-lg leading-relaxed sm:text-xl" style={{ color: "var(--muted)" }}>
              Every friend group has the same stalled ritual: someone drops{" "}
              <span style={{ color: "var(--fg)" }}>&ldquo;let&apos;s go to Japan bro&rdquo;</span>
              , a few people react, dates get half-discussed, and the thread dies. The trip
              stays a sentence. Tama-Go-Chi turns that failure mode into a creature whose
              health declines until someone commits.
            </p>
          </Reveal>
        </div>
      </section>

      {/* ─── 3. Video Demo ────────────────────────────────────────────────── */}
      <section className="mx-auto max-w-5xl px-6 py-16">
        <Reveal>
          <SectionTitle eyebrow="Demo">Watch it end-to-end</SectionTitle>
        </Reveal>
        <Reveal delay={120}>
          <div
            className="overflow-hidden"
            style={{
              borderRadius: "var(--radius)",
              background: "var(--surface)",
              boxShadow: "var(--shadow)",
            }}
          >
            {/* Swap this block for <video controls poster=… src=…> when the demo file is ready */}
            <div className="relative w-full" style={{ aspectRatio: "16 / 9" }}>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src="/tokyo-poster.png"
                alt=""
                className="absolute inset-0 h-full w-full object-cover"
              />
              <div
                className="absolute inset-0"
                style={{ background: "rgba(42, 36, 28, 0.28)" }}
              />
              <div className="relative z-[1] flex h-full flex-col items-center justify-center gap-3 px-6 text-center">
                <div
                  className="flex h-16 w-16 items-center justify-center rounded-full"
                  style={{
                    background: "var(--surface)",
                    boxShadow: "var(--shadow)",
                    color: "var(--fg)",
                  }}
                  aria-hidden
                >
                  <iconify-icon icon="heroicons:play" width="28" height="28" />
                </div>
                <p className="ds-title text-base sm:text-lg" style={{ color: "var(--surface)" }}>
                  Demo video coming soon
                </p>
              </div>
            </div>
          </div>
        </Reveal>
      </section>

      {/* ─── 4. What It Does (+ interactive demo) ─────────────────────────── */}
      <section className="mx-auto max-w-5xl px-6 py-20">
        <Reveal>
          <SectionTitle eyebrow="What it does">A pet that dies if you don&apos;t book</SectionTitle>
        </Reveal>
        <Reveal delay={80}>
          <p
            className="mx-auto mb-10 max-w-3xl text-center leading-relaxed"
            style={{ color: "var(--muted)" }}
          >
            Drop Tama-Go-Chi in the group. It listens for trip talk, extracts constraints,
            and maintains two bars:{" "}
            <span style={{ color: "var(--fg)" }}>Physical</span> (Stay22 hotel
            pricing and availability) and{" "}
            <span style={{ color: "var(--fg)" }}>Mental</span> (chat engagement). Silence
            and rising prices make it sick; real decisions heal it. When a bar bottoms out,
            it sends an ElevenLabs voice message into the chat. On commit, Stay22
            returns a finished booking instead of another unfinished plan.
          </p>
        </Reveal>
        <div className="mb-14">
          <CardGrid items={MECHANICS} cols="sm:grid-cols-2 lg:grid-cols-4" />
        </div>

        <Reveal delay={160}>
          <div className="mb-8 text-center">
            <h3 className="ds-title text-xl sm:text-2xl">Try the scrubber</h3>
            <p className="mx-auto mt-2 max-w-xl text-sm leading-relaxed" style={{ color: "var(--muted)" }}>
              Drag weeks forward. Watch Physical and Mental fall as prices climb and the chat
              goes quiet, then book to revive the pet.
            </p>
          </div>
        </Reveal>
        <Reveal delay={200}>
          <SushiDemo />
        </Reveal>
      </section>

      {/* ─── 5. How We Built It ───────────────────────────────────────────── */}
      <section className="mx-auto max-w-5xl px-6 py-20">
        <Reveal>
          <SectionTitle eyebrow="How we built it">Six pillars</SectionTitle>
        </Reveal>
        <CardGrid items={PILLARS} cols="sm:grid-cols-2 lg:grid-cols-3" />
      </section>

      {/* ─── 6. Accomplishments ───────────────────────────────────────────── */}
      <section className="mx-auto max-w-5xl px-6 py-16">
        <Reveal>
          <SectionTitle eyebrow="Accomplishments">What we&apos;re proud of</SectionTitle>
        </Reveal>
        <CardGrid items={ACCOMPLISHMENTS} cols="sm:grid-cols-3" />
      </section>

      {/* ─── 7. What We Learned ───────────────────────────────────────────── */}
      <section className="mx-auto max-w-5xl px-6 py-16">
        <Reveal>
          <SectionTitle eyebrow="What we learned">Takeaways</SectionTitle>
        </Reveal>
        <CardGrid items={LEARNINGS} cols="sm:grid-cols-3" />
      </section>

      {/* ─── 8. What's Next ───────────────────────────────────────────────── */}
      <section className="mx-auto max-w-5xl px-6 py-16">
        <Reveal>
          <SectionTitle eyebrow="What's next">Roadmap</SectionTitle>
        </Reveal>
        <CardGrid items={NEXT_STEPS} />
      </section>

      {/* ─── 9. Footer / CTA ──────────────────────────────────────────────── */}
      <section className="relative overflow-hidden">
        <Petals />
        <div className="relative mx-auto max-w-5xl px-6 py-28 text-center">
          <Reveal>
            <h2 className="ds-title mx-auto max-w-2xl text-3xl leading-snug sm:text-5xl">
              Stop letting the trip die in the group chat.
            </h2>
          </Reveal>
          <Reveal delay={150}>
            <p className="mx-auto mt-5 max-w-xl leading-relaxed" style={{ color: "var(--muted)" }}>
              Add Tama-Go-Chi. Give your friends something that gets sad when you don&apos;t
              book, and a spring morning in Kyoto when you do.
            </p>
          </Reveal>
          <Reveal delay={300}>
            <div className="mt-10 flex justify-center">
              <CTAButton />
            </div>
          </Reveal>
        </div>
      </section>

      <footer className="px-6 py-12" style={{ borderTop: "1px solid rgba(42, 36, 28, 0.08)" }}>
        <div className="mx-auto max-w-5xl text-center">
          <div className="text-xs uppercase tracking-[0.3em]" style={{ color: "var(--muted)" }}>
            Powered by
          </div>
          <div
            className="mt-4 flex flex-wrap items-center justify-center gap-x-7 gap-y-2 text-sm"
            style={{ color: "var(--muted)" }}
          >
            {SPONSORS.map((s) => (
              <span key={s}>{s}</span>
            ))}
          </div>
          <div className="ds-title mt-8 text-xs" style={{ color: "var(--muted)" }}>
            Built at Hack the 6ix · Tama-Go-Chi · いってらっしゃい
          </div>
        </div>
      </footer>
    </main>
  );
}
