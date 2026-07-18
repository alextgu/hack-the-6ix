import SushiDemo from "@/components/SushiDemo";

// PLACEHOLDER — swap for the real bot handle.
const BOT_HANDLE = "@YourBotHandle";
const BOT_URL = `https://t.me/${BOT_HANDLE.replace(/^@/, "")}`;

const SPONSORS = ["Stay22", "Phoebe", "Freesolo", "MongoDB Atlas", "ElevenLabs", "Gemini"];

const STEPS = [
  {
    n: "01",
    title: "It hatches",
    body: "Add the bot to your group chat. Sushi-kun hatches and starts reading the Japan trip taking shape — city, dates, budget, group size.",
  },
  {
    n: "02",
    title: "It reacts",
    body: "Live Stay22 hotel prices drive its physical health; group engagement drives its mental health. Every real decision heals it; silence and rising prices make it sick.",
  },
  {
    n: "03",
    title: "It finds the holdup",
    body: "Phoebe, the coordination agent, diagnoses the one blocker — a person, a date clash, a budget gap — and works to remove it instead of nagging everyone.",
  },
  {
    n: "04",
    title: "You commit",
    body: "When the group commits, Stay22 returns the real booking and Sushi-kun graduates. The sentence in the group chat finally becomes a booked trip.",
  },
];

function CTAButton({ className = "" }: { className?: string }) {
  return (
    <a
      href={BOT_URL}
      className={`inline-flex items-center gap-2 rounded-xl bg-amber-400 px-6 py-3 text-sm font-semibold text-neutral-950 transition hover:bg-amber-300 ${className}`}
    >
      Add to Telegram
      <span className="text-neutral-600">{BOT_HANDLE}</span>
    </a>
  );
}

export default function Home() {
  return (
    <main className="min-h-screen bg-neutral-950 text-neutral-100">
      {/* ─── Hero ─────────────────────────────────────────────────────────── */}
      <section className="mx-auto max-w-5xl px-6 pb-16 pt-24 text-center">
        <p className="mb-4 text-sm font-medium uppercase tracking-widest text-amber-400">
          Plan That Trip to Japan
        </p>
        <h1 className="mx-auto max-w-3xl text-4xl font-bold leading-tight tracking-tight sm:text-6xl">
          Everyone wants to go to Japan. Nobody books it.
        </h1>
        <p className="mx-auto mt-6 max-w-2xl text-lg text-neutral-400">
          A Telegram bot turns your stalled group chat into a pet whose health is
          live hotel data. It gets sick as you procrastinate. The only way to save
          it is to actually book the trip.
        </p>
        <div className="mt-8">
          <CTAButton />
        </div>
      </section>

      {/* ─── Interactive demo ─────────────────────────────────────────────── */}
      <section className="mx-auto max-w-5xl px-6 py-12">
        <div className="mb-8 text-center">
          <h2 className="text-2xl font-semibold sm:text-3xl">Meet Sushi-kun</h2>
          <p className="mx-auto mt-2 max-w-xl text-neutral-400">
            Drag the slider to fast-forward the weeks. Watch the 時価 climb, the
            rooms sell off, and Sushi-kun spoil. Then book it.
          </p>
        </div>
        <SushiDemo />
      </section>

      {/* ─── How it works ─────────────────────────────────────────────────── */}
      <section className="mx-auto max-w-5xl px-6 py-16">
        <h2 className="mb-10 text-center text-2xl font-semibold sm:text-3xl">How it works</h2>
        <div className="grid gap-4 sm:grid-cols-2">
          {STEPS.map((s) => (
            <div
              key={s.n}
              className="rounded-2xl border border-neutral-800 bg-neutral-900 p-6"
            >
              <div className="mb-3 text-sm font-semibold text-amber-400">{s.n}</div>
              <h3 className="mb-2 text-lg font-semibold">{s.title}</h3>
              <p className="text-sm leading-relaxed text-neutral-400">{s.body}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ─── 時価 market price ────────────────────────────────────────────── */}
      <section className="mx-auto max-w-5xl px-6 py-16">
        <div className="rounded-2xl border border-neutral-800 bg-gradient-to-b from-neutral-900 to-neutral-950 p-8 sm:p-12">
          <div className="grid items-center gap-8 sm:grid-cols-[auto_1fr]">
            <div className="text-center sm:text-left">
              <div className="text-6xl font-bold text-amber-400">時価</div>
              <div className="mt-1 text-sm text-neutral-500">jika — &ldquo;market price&rdquo;</div>
            </div>
            <div>
              <h2 className="text-2xl font-semibold">Priced like the sushi counter</h2>
              <p className="mt-3 text-neutral-400">
                At a sushi bar, 時価 means &ldquo;market price&rdquo; — no number on the
                menu, it&apos;s whatever the market says today. Sushi-kun&apos;s physical
                health is exactly that: live Stay22 prices and availability across
                Expedia, Booking, Hotels.com and Vrbo. As the group waits, prices
                rise and rooms sell off — procrastination literally makes him sick.
                The hotel never shows up as a list; it only surfaces the moment you
                commit.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* ─── Final CTA ────────────────────────────────────────────────────── */}
      <section className="mx-auto max-w-5xl px-6 py-20 text-center">
        <h2 className="mx-auto max-w-2xl text-3xl font-bold sm:text-4xl">
          Stop letting the trip die in the group chat.
        </h2>
        <p className="mx-auto mt-4 max-w-xl text-neutral-400">
          Add Sushi-kun. Give your friends something that gets sad when you don&apos;t book.
        </p>
        <div className="mt-8">
          <CTAButton />
        </div>
      </section>

      {/* ─── Footer ───────────────────────────────────────────────────────── */}
      <footer className="border-t border-neutral-900 px-6 py-10">
        <div className="mx-auto max-w-5xl text-center">
          <div className="text-xs uppercase tracking-widest text-neutral-600">Powered by</div>
          <div className="mt-3 flex flex-wrap items-center justify-center gap-x-6 gap-y-2 text-sm text-neutral-400">
            {SPONSORS.map((s) => (
              <span key={s}>{s}</span>
            ))}
          </div>
          <div className="mt-6 text-xs text-neutral-600">
            Built at Hack the 6ix · Plan That Trip to Japan
          </div>
        </div>
      </footer>
    </main>
  );
}
