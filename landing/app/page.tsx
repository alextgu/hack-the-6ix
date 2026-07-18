import SushiDemo from "@/components/SushiDemo";
import Reveal from "@/components/Reveal";
import Petals from "@/components/Petals";

// PLACEHOLDER — swap for the real bot handle.
const BOT_HANDLE = "@YourBotHandle";
const BOT_URL = `https://t.me/${BOT_HANDLE.replace(/^@/, "")}`;

const SPONSORS = ["Stay22", "Phoebe", "Freesolo", "MongoDB Atlas", "ElevenLabs", "Gemini"];

const STEPS = [
  {
    kanji: "一",
    title: "It hatches",
    body: "Add the bot to your group chat. Sushi-kun hatches and starts reading the Japan trip taking shape — city, dates, budget, group size.",
  },
  {
    kanji: "二",
    title: "It reacts",
    body: "Live Stay22 hotel prices drive its physical health; group engagement drives its mental health. Every real decision heals it; silence and rising prices make it sick.",
  },
  {
    kanji: "三",
    title: "It finds the holdup",
    body: "Phoebe, the coordination agent, diagnoses the one blocker — a person, a date clash, a budget gap — and works to remove it instead of nagging everyone.",
  },
  {
    kanji: "四",
    title: "You commit",
    body: "When the group commits, Stay22 returns the real booking and Sushi-kun graduates. The sentence in the group chat finally becomes a booked trip.",
  },
];

function CTAButton() {
  return (
    <a
      href={BOT_URL}
      className="cta-glow inline-flex items-center gap-2.5 rounded-2xl px-7 py-3.5 text-sm font-semibold"
      style={{
        background: "linear-gradient(90deg, var(--amber), var(--amber-deep))",
        color: "var(--night)",
      }}
    >
      Add to Telegram
      <span style={{ color: "rgba(18,19,31,0.55)" }}>{BOT_HANDLE}</span>
    </a>
  );
}

export default function Home() {
  return (
    <main className="min-h-screen" style={{ background: "var(--night)", color: "var(--ink)" }}>
      {/* ─── Hero — indigo night, lanterns, falling petals ────────────────── */}
      <section className="relative overflow-hidden">
        {/* breathing sky */}
        <div
          aria-hidden
          className="animate-breathe absolute inset-0"
          style={{
            background:
              "radial-gradient(60% 55% at 50% 0%, rgba(246,198,208,0.14), transparent 70%)," +
              "radial-gradient(45% 40% at 82% 28%, rgba(245,165,36,0.10), transparent 70%)," +
              "radial-gradient(50% 45% at 12% 34%, rgba(178,140,255,0.08), transparent 70%)",
          }}
        />
        {/* lantern glows */}
        <div
          aria-hidden
          className="animate-lantern absolute left-[8%] top-40 h-24 w-24 rounded-full"
          style={{ background: "var(--amber)", opacity: 0.5 }}
        />
        <div
          aria-hidden
          className="animate-lantern absolute right-[10%] top-64 h-16 w-16 rounded-full"
          style={{ background: "var(--sakura-deep)", opacity: 0.4, animationDelay: "2.5s" }}
        />
        <Petals />

        <div className="relative mx-auto max-w-5xl px-6 pb-24 pt-28 text-center sm:pt-36">
          <Reveal>
            <p
              className="font-display mb-5 text-sm font-semibold uppercase tracking-[0.35em]"
              style={{ color: "var(--sakura)" }}
            >
              ⛩ Plan That Trip to Japan
            </p>
          </Reveal>
          <Reveal delay={120}>
            <h1
              className="font-display mx-auto max-w-3xl text-4xl font-bold leading-[1.15] tracking-tight sm:text-6xl sm:leading-[1.1]"
              style={{ color: "var(--paper)" }}
            >
              Everyone wants to go to Japan.
              <br />
              <span
                style={{
                  background: "linear-gradient(90deg, var(--sakura-deep), var(--amber))",
                  WebkitBackgroundClip: "text",
                  backgroundClip: "text",
                  color: "transparent",
                }}
              >
                Nobody books it.
              </span>
            </h1>
          </Reveal>
          <Reveal delay={240}>
            <p className="mx-auto mt-7 max-w-2xl text-lg leading-relaxed" style={{ color: "var(--ink-dim)" }}>
              A Telegram bot turns your stalled group chat into a pet whose health is live
              hotel data. It gets sick as you procrastinate. The only way to save it is to
              actually book the trip.
            </p>
          </Reveal>
          <Reveal delay={360}>
            <div className="mt-10">
              <CTAButton />
            </div>
          </Reveal>
        </div>
      </section>

      {/* ─── Interactive demo — feel it rot ───────────────────────────────── */}
      <section className="relative mx-auto max-w-5xl px-6 py-16">
        <Reveal>
          <div className="mb-10 text-center">
            <div className="font-display mb-2 text-3xl" style={{ color: "var(--sakura-deep)" }} aria-hidden>
              寿司くん
            </div>
            <h2 className="font-display text-3xl font-bold sm:text-4xl" style={{ color: "var(--paper)" }}>
              Meet Sushi-kun
            </h2>
            <p className="mx-auto mt-3 max-w-xl leading-relaxed" style={{ color: "var(--ink-dim)" }}>
              Drag the slider to fast-forward the weeks. Watch the 時価 climb, the rooms
              sell off, and Sushi-kun spoil. Then book it.
            </p>
          </div>
        </Reveal>
        <Reveal delay={150}>
          <SushiDemo />
        </Reveal>
      </section>

      {/* ─── How it works — four kanji steps ──────────────────────────────── */}
      <section className="mx-auto max-w-5xl px-6 py-20">
        <Reveal>
          <h2
            className="font-display mb-12 text-center text-3xl font-bold sm:text-4xl"
            style={{ color: "var(--paper)" }}
          >
            How it works
          </h2>
        </Reveal>
        <div className="grid gap-5 sm:grid-cols-2">
          {STEPS.map((s, i) => (
            <Reveal key={s.kanji} delay={i * 110}>
              <div
                className="card-lift h-full rounded-3xl border p-7"
                style={{
                  borderColor: "rgba(246,198,208,0.12)",
                  background: "linear-gradient(180deg, rgba(35,36,65,0.6), rgba(26,27,46,0.9))",
                }}
              >
                <div
                  className="font-display mb-4 text-4xl font-semibold"
                  style={{ color: "var(--amber)" }}
                  aria-hidden
                >
                  {s.kanji}
                </div>
                <h3 className="font-display mb-2.5 text-xl font-bold" style={{ color: "var(--paper)" }}>
                  {s.title}
                </h3>
                <p className="text-sm leading-relaxed" style={{ color: "var(--ink-dim)" }}>
                  {s.body}
                </p>
              </div>
            </Reveal>
          ))}
        </div>
      </section>

      {/* ─── 時価 market price — the sushi-counter metaphor ───────────────── */}
      <section className="mx-auto max-w-5xl px-6 py-16">
        <Reveal>
          <div
            className="relative overflow-hidden rounded-3xl border p-9 sm:p-14"
            style={{
              borderColor: "rgba(245,165,36,0.22)",
              background:
                "radial-gradient(70% 90% at 15% 20%, rgba(245,165,36,0.10), transparent 60%)," +
                "linear-gradient(160deg, var(--night-mist), var(--night-soft) 60%, var(--night))",
            }}
          >
            <div
              aria-hidden
              className="animate-lantern absolute -right-8 -top-8 h-32 w-32 rounded-full"
              style={{ background: "var(--amber)", opacity: 0.25 }}
            />
            <div className="grid items-center gap-10 sm:grid-cols-[auto_1fr]">
              <div className="text-center sm:text-left">
                <div
                  className="font-display text-7xl font-bold leading-none sm:text-8xl"
                  style={{
                    background: "linear-gradient(180deg, var(--paper), var(--amber))",
                    WebkitBackgroundClip: "text",
                    backgroundClip: "text",
                    color: "transparent",
                  }}
                >
                  時価
                </div>
                <div className="mt-3 text-sm tracking-wide" style={{ color: "var(--ink-dim)" }}>
                  jika — &ldquo;market price&rdquo;
                </div>
              </div>
              <div>
                <h2 className="font-display text-2xl font-bold sm:text-3xl" style={{ color: "var(--paper)" }}>
                  Priced like the sushi counter
                </h2>
                <p className="mt-4 leading-relaxed" style={{ color: "var(--ink-dim)" }}>
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

      {/* ─── Final CTA — dawn breaks, go to Japan ─────────────────────────── */}
      <section className="relative overflow-hidden">
        <div
          aria-hidden
          className="absolute inset-0"
          style={{
            background:
              "radial-gradient(80% 100% at 50% 100%, rgba(245,165,36,0.16), transparent 60%)," +
              "radial-gradient(60% 70% at 50% 85%, rgba(246,198,208,0.12), transparent 70%)",
          }}
        />
        <Petals />
        <div className="relative mx-auto max-w-5xl px-6 py-28 text-center">
          <Reveal>
            <div className="font-display mb-4 text-2xl" style={{ color: "var(--sakura)" }} aria-hidden>
              🏮
            </div>
            <h2
              className="font-display mx-auto max-w-2xl text-3xl font-bold leading-snug sm:text-5xl"
              style={{ color: "var(--paper)" }}
            >
              Stop letting the trip die in the group chat.
            </h2>
          </Reveal>
          <Reveal delay={150}>
            <p className="mx-auto mt-5 max-w-xl leading-relaxed" style={{ color: "var(--ink-dim)" }}>
              Add Sushi-kun. Give your friends something that gets sad when you don&apos;t
              book — and a spring morning in Kyoto when you do.
            </p>
          </Reveal>
          <Reveal delay={300}>
            <div className="mt-10">
              <CTAButton />
            </div>
          </Reveal>
        </div>
      </section>

      {/* ─── Footer ───────────────────────────────────────────────────────── */}
      <footer className="border-t px-6 py-12" style={{ borderColor: "rgba(246,198,208,0.08)" }}>
        <div className="mx-auto max-w-5xl text-center">
          <div className="text-xs uppercase tracking-[0.3em]" style={{ color: "var(--ink-dim)" }}>
            Powered by
          </div>
          <div
            className="mt-4 flex flex-wrap items-center justify-center gap-x-7 gap-y-2 text-sm"
            style={{ color: "var(--ink-dim)" }}
          >
            {SPONSORS.map((s) => (
              <span key={s} className="transition-colors duration-200 hover:text-[var(--sakura)]">
                {s}
              </span>
            ))}
          </div>
          <div className="font-display mt-8 text-xs" style={{ color: "rgba(169,165,184,0.55)" }}>
            Built at Hack the 6ix · Plan That Trip to Japan · いってらっしゃい
          </div>
        </div>
      </footer>
    </main>
  );
}
