import SushiDemo from "@/components/SushiDemo";
import Reveal from "@/components/Reveal";
import Petals from "@/components/Petals";

// PLACEHOLDER — swap for the real bot handle.
const BOT_HANDLE = "@YourBotHandle";
const BOT_URL = `https://t.me/${BOT_HANDLE.replace(/^@/, "")}`;

const SPONSORS = ["Stay22", "Phoebe", "Freesolo", "MongoDB Atlas", "ElevenLabs", "Gemini"];

const STEPS = [
  {
    icon: "heroicons:sparkles",
    title: "It hatches",
    body: "Add the bot to your group chat. Sushi-kun hatches and starts reading the Japan trip taking shape — city, dates, budget, group size.",
  },
  {
    icon: "heroicons:heart",
    title: "It reacts",
    body: "Live Stay22 hotel prices drive its physical health; group engagement drives its mental health. Every real decision heals it; silence and rising prices make it sick.",
  },
  {
    icon: "heroicons:magnifying-glass",
    title: "It finds the holdup",
    body: "Phoebe, the coordination agent, diagnoses the one blocker — a person, a date clash, a budget gap — and works to remove it instead of nagging everyone.",
  },
  {
    icon: "heroicons:check-badge",
    title: "You commit",
    body: "When the group commits, Stay22 returns the real booking and Sushi-kun graduates. The sentence in the group chat finally becomes a booked trip.",
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

export default function Home() {
  return (
    <main className="min-h-screen" style={{ color: "var(--fg)" }}>
      {/* ─── Hero — split: copy ~55% / poster ~45% ─────────────────────────── */}
      <section className="hero-split relative lg:grid lg:min-h-dvh lg:grid-cols-[minmax(0,55fr)_minmax(0,45fr)]">
        <div className="relative flex flex-col justify-center px-6 py-16 sm:px-10 sm:py-20 lg:px-12 lg:py-24 xl:px-16">
          <Petals />

          <div className="relative mx-auto w-full max-w-xl lg:mx-0 lg:max-w-[34rem]">
            <Reveal>
              <p className="ds-chip mb-7" style={{ display: "inline-flex" }}>
                <iconify-icon icon="heroicons:map-pin" width="14" height="14" />
                Plan That Trip to Japan
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
                A Telegram bot turns your stalled group chat into a pet whose health is live
                hotel data. It gets sick as you procrastinate. The only way to save it is to
                actually book the trip.
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
            alt="Vintage Tokyo travel poster — pagoda and cherry blossoms"
            className="absolute inset-0 h-full w-full object-cover object-[center_20%] lg:object-center"
            decoding="async"
            fetchPriority="high"
          />
        </div>
      </section>

      {/* ─── Interactive demo ─────────────────────────────────────────────── */}
      <section className="relative mx-auto max-w-5xl px-6 py-16">
        <Reveal>
          <div className="mb-10 text-center">
            <h2 className="ds-title text-3xl sm:text-4xl">Meet Sushi-kun</h2>
            <p className="mx-auto mt-3 max-w-xl leading-relaxed" style={{ color: "var(--muted)" }}>
              Drag the slider to fast-forward the weeks. Watch the 時価 climb, the rooms
              sell off, and Sushi-kun spoil. Then book it.
            </p>
          </div>
        </Reveal>
        <Reveal delay={150}>
          <SushiDemo />
        </Reveal>
      </section>

      {/* ─── How it works ─────────────────────────────────────────────────── */}
      <section className="mx-auto max-w-5xl px-6 py-20">
        <Reveal>
          <h2 className="ds-title mb-12 text-center text-3xl sm:text-4xl">How it works</h2>
        </Reveal>
        <div className="grid gap-5 sm:grid-cols-2">
          {STEPS.map((s, i) => (
            <Reveal key={s.title} delay={i * 110}>
              <div className="ds-health-card card-lift h-full">
                <div className="bar-top">
                  <div className="bar-icon">
                    <iconify-icon icon={s.icon} width="22" height="22" />
                  </div>
                  <h3 className="bar-name">{s.title}</h3>
                </div>
                <p className="text-sm leading-relaxed" style={{ color: "var(--muted)" }}>
                  {s.body}
                </p>
              </div>
            </Reveal>
          ))}
        </div>
      </section>

      {/* ─── 時価 market price ────────────────────────────────────────────── */}
      <section className="mx-auto max-w-5xl px-6 py-16">
        <Reveal>
          <div
            className="relative overflow-hidden p-9 sm:p-14"
            style={{
              borderRadius: "var(--radius)",
              background: "var(--surface)",
              boxShadow: "var(--shadow)",
            }}
          >
            <div className="grid items-center gap-10 sm:grid-cols-[auto_1fr]">
              <div className="text-center sm:text-left">
                <div className="ds-title text-7xl leading-none sm:text-8xl">時価</div>
                <div className="mt-3 flex items-center justify-center gap-2 text-sm sm:justify-start" style={{ color: "var(--muted)" }}>
                  <iconify-icon icon="heroicons:currency-dollar" width="14" height="14" />
                  jika — &ldquo;market price&rdquo;
                </div>
              </div>
              <div>
                <h2 className="ds-title text-2xl sm:text-3xl">Priced like the sushi counter</h2>
                <p className="mt-4 leading-relaxed" style={{ color: "var(--muted)" }}>
                  At a sushi bar, 時価 means &ldquo;market price&rdquo; — no number on the menu,
                  it&apos;s whatever the market says today. Sushi-kun&apos;s physical health is
                  exactly that: live Stay22 prices and availability across Expedia, Booking,
                  Hotels.com and Vrbo. As the group waits, prices rise and rooms sell off —
                  procrastination literally makes him sick. The hotel never shows up as a
                  list; it only surfaces the moment you commit.
                </p>
              </div>
            </div>
          </div>
        </Reveal>
      </section>

      {/* ─── Final CTA ────────────────────────────────────────────────────── */}
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
              Add Sushi-kun. Give your friends something that gets sad when you don&apos;t
              book — and a spring morning in Kyoto when you do.
            </p>
          </Reveal>
          <Reveal delay={300}>
            <div className="mt-10 flex justify-center">
              <CTAButton />
            </div>
          </Reveal>
        </div>
      </section>

      {/* ─── Footer ───────────────────────────────────────────────────────── */}
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
            Built at Hack the 6ix · Plan That Trip to Japan · いってらっしゃい
          </div>
        </div>
      </footer>
    </main>
  );
}
