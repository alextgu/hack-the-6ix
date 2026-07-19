import SushiDemo from "@/components/SushiDemo";
import Reveal from "@/components/Reveal";
import Petals from "@/components/Petals";
import ModelBenchmark from "@/components/ModelBenchmark";
import PipelineSlideshow from "@/components/PipelineSlideshow";

const BOT_HANDLE = "@PetSamaBot";
const BOT_URL = `https://t.me/${BOT_HANDLE.replace(/^@/, "")}`;

const SPONSORS = ["Stay22", "Phoebe", "Freesolo", "MongoDB Atlas", "ElevenLabs", "Gemini"];

const PIPELINE_CARDS = [
  {
    phase: "Onboard",
    media: "/pipeline-tabi-checkin.png",
    mediaExtra: "/pet/all-avatars-fade.gif",
    mediaType: "duo" as const,
    fit: "contain" as const,
    mediaAlt: "Tabi planning dashboard and avatar states",
    imageSide: "right" as const,
    steps: [
      {
        title: "Start the Trip",
        body: "Add Tabi to your group chat.",
      },
      {
        title: "Natural Planning",
        body: "Chat normally about your trip.",
      },
      {
        title: "Understand Everyone",
        body: "Tabi extracts destinations, dates, budgets, and preferences from the conversation.",
      },
    ],
  },
  {
    phase: "Align",
    media: "/pipeline-chat.png",
    mediaExtra: undefined as string | undefined,
    mediaType: "image" as const,
    fit: "contain" as const,
    mediaAlt: "Telegram group chat with Tabi planning Japan",
    imageSide: "left" as const,
    steps: [
      {
        title: "Build Consensus",
        body: "Tabi reconciles everyone's responses into one plan, identifies the real blockers, and proposes the next step.",
      },
      {
        title: "Group Decision",
        body: "The group approves the proposal or continues discussing until everyone is aligned.",
      },
    ],
  },
  {
    phase: "Book",
    media: "_v7N3bwIQSQ",
    mediaExtra: undefined as string | undefined,
    mediaType: "youtube" as const,
    fit: "cover" as const,
    mediaAlt: "Hotel swipe deck booking through Stay22",
    imageSide: "right" as const,
    steps: [
      {
        title: "Make it Real",
        body: "Tabi books the trip using live Stay22 hotel deals, recommends lower-carbon travel options, and finalizes the itinerary.",
      },
      {
        title: "Celebrate",
        body: "The pet recovers to full health, the group receives a commemorative trip token, and the trip officially becomes real.",
      },
    ],
  },
];

const PILLARS = [
  {
    icon: "heroicons:microphone",
    title: "Multimodal intake",
    body: "Text, voice notes, and images — she reads the whole chat.",
  },
  {
    icon: "heroicons:cpu-chip",
    title: "Gemini × LangGraph",
    body: "A team of Gemini agents, orchestrated on LangGraph.",
  },
  {
    icon: "heroicons:funnel",
    title: "The reconciler",
    body: "Everyone's price, place, and dates → one plan.",
  },
  {
    icon: "heroicons:megaphone",
    title: "Blocker agent · Freesolo",
    body: "Qwen 4B, GRPO-tuned to find who's stalling and call them out — 4× a frontier model (0.32 vs 0.08).",
  },
  {
    icon: "heroicons:arrow-path",
    title: "Self-learning flywheel",
    body: "Every decision logged to MongoDB; she trains on her own data, smarter each trip.",
  },
  {
    icon: "heroicons:gift",
    title: "Book it, keep it",
    body: "Live Stay22 hotels via Tinder-style votes, sealed in a Solana trip coin — your Spotify Wrapped.",
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
    <main style={{ color: "var(--fg)" }}>
      {/* ─── 1. Hero ──────────────────────────────────────────────────────── */}
      <section className="hero-split relative lg:grid lg:min-h-dvh lg:grid-cols-[minmax(0,55fr)_minmax(0,45fr)]">
        <div className="relative flex flex-col justify-center px-6 py-16 sm:px-10 sm:py-20 lg:px-12 lg:py-24 xl:px-16">
          <Petals />

          <div className="relative mx-auto w-full max-w-xl lg:mx-0 lg:max-w-[36rem]">
            <Reveal>
              <p className="ds-chip mb-7" style={{ display: "inline-flex" }}>
                <iconify-icon icon="heroicons:map-pin" width="14" height="14" />
                Tabi · Hack the 6ix
              </p>
            </Reveal>
            <Reveal delay={100}>
              <h1 className="ds-title text-[2.5rem] leading-[1.06] sm:text-6xl lg:text-[3.7rem]">
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
                A Telegram pet whose health tracks live hotel prices and group engagement.
                The only way to save it is to actually book the trip.
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

      {/* ─── 2. Problem line + demo video (merged, condensed) ─────────────── */}
      <section className="snap-panel relative px-6">
        <Petals />
        <div className="relative mx-auto w-full max-w-4xl">
          <Reveal>
          <div
            className="framed overflow-hidden"
            style={{
              borderRadius: "var(--radius)",
              background: "var(--surface)",
              padding: 10,
            }}
          >
            {/* Swap this block for <video controls poster=… src=…> when the demo file is ready */}
            <div
              className="relative w-full overflow-hidden"
              style={{ aspectRatio: "16 / 9", borderRadius: "calc(var(--radius) - 12px)", boxShadow: "inset 0 0 0 1px rgba(42,36,28,0.06)" }}
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src="/tokyo-poster.png"
                alt=""
                className="absolute inset-0 h-full w-full object-cover"
              />
              <div className="absolute inset-0" style={{ background: "rgba(42, 36, 28, 0.30)" }} />
              <div className="relative z-[1] flex h-full flex-col items-center justify-center gap-4 px-6 text-center">
                <div
                  className="flex h-20 w-20 items-center justify-center rounded-full"
                  style={{ background: "var(--surface)", boxShadow: "var(--shadow)", color: "var(--fg)" }}
                  aria-hidden
                >
                  <iconify-icon icon="heroicons:play" width="34" height="34" />
                </div>
                <p className="ds-title text-lg sm:text-2xl" style={{ color: "var(--surface)" }}>
                  Demo video coming soon
                </p>
              </div>
            </div>
          </div>
          </Reveal>
          <Reveal delay={140}>
            <p className="mx-auto mt-8 max-w-3xl text-center text-xl leading-snug sm:text-2xl">
              Someone drops{" "}
              <span style={{ color: "var(--card-coral-ink)" }}>
                &ldquo;let&apos;s go to Japan bro.&rdquo;
              </span>{" "}
              Everyone&apos;s hyped. Nobody books. So we turned the trip into{" "}
              <span style={{ color: "var(--card-coral-ink)" }}>
                a creature that dies if you let it.
              </span>
            </p>
          </Reveal>
        </div>
      </section>

      {/* ─── 3. How it works — auto-advancing slideshow of the 3 phases ────── */}
      <section className="snap-panel px-6 py-24">
        <div className="mx-auto max-w-5xl">
          <Reveal>
            <p className="kicker mb-8">How it works</p>
          </Reveal>
          <Reveal delay={120}>
            <PipelineSlideshow cards={PIPELINE_CARDS} />
          </Reveal>
          <Reveal delay={200}>
            <p
              className="mx-auto mt-8 max-w-xl text-center text-sm leading-relaxed"
              style={{ color: "var(--muted)" }}
            >
              ↻ She runs this loop — propose, vote, unblock — over and over until the
              whole group commits.
            </p>
          </Reveal>
        </div>
      </section>

      {/* ─── 5. The interactive scrubber — the centerpiece, big ───────────── */}
      <section className="snap-panel px-6">
        <div className="mx-auto w-full max-w-5xl">
          <Reveal>
            <SushiDemo />
          </Reveal>
          <Reveal delay={140}>
            <p
              className="mx-auto mt-6 max-w-lg text-center text-sm leading-relaxed"
              style={{ color: "var(--muted)" }}
            >
              Drag the weeks forward — watch it rot as prices climb and the chat goes
              quiet, then book to revive it.
            </p>
          </Reveal>
        </div>
      </section>

      {/* ─── 6. Pillars — cards only ──────────────────────────────────────── */}
      <section className="snap-panel px-6 py-20">
        <div className="mx-auto max-w-5xl">
          <Reveal>
            <p className="kicker mb-8">What&apos;s under the hood</p>
          </Reveal>
          <CardGrid items={PILLARS} cols="sm:grid-cols-2 lg:grid-cols-3" />
        </div>
      </section>

      {/* ─── 7. Proof — the model benchmark ───────────────────────────────── */}
      <section className="snap-panel px-6 py-20">
        <div className="mx-auto max-w-5xl">
          <Reveal>
            <div className="flex justify-center">
              <ModelBenchmark />
            </div>
          </Reveal>
        </div>
      </section>

      {/* ─── 8. Green by default — the carbon engine ──────────────────────── */}
      <section className="snap-panel px-6 py-20">
        <div className="mx-auto max-w-5xl">
          <Reveal>
            <p className="kicker mb-6">Green by default</p>
          </Reveal>
          <Reveal delay={80}>
            <h2 className="ds-title max-w-3xl text-3xl leading-[1.1] sm:text-4xl lg:text-5xl">
              Every booking is carbon-scored the moment it&apos;s on the table.
            </h2>
          </Reveal>
          <Reveal delay={140}>
            <p className="mt-5 max-w-2xl text-base leading-relaxed sm:text-lg" style={{ color: "var(--muted)" }}>
              Flights, trains, hotels, even the airport transfer — priced in CO₂e from
              published government factors, computed locally. No API in the loop, so the
              numbers are <span style={{ color: "var(--fg)" }}>impossible to inflate</span>.
            </p>
          </Reveal>

          <div className="mt-10 grid items-stretch gap-4 lg:grid-cols-[1.3fr_minmax(0,1fr)]">
            {/* the four scored domains */}
            <Reveal delay={200}>
              <div className="grid h-full grid-cols-2 gap-3">
                {[
                  { e: "✈️", t: "Flights", s: "DEFRA, incl. radiative forcing" },
                  { e: "🚄", t: "Trains", s: "JR Central — Shinkansen ~17 g/km" },
                  { e: "🏨", t: "Hotels", s: "CHSB, by class & rooms needed" },
                  { e: "🚕", t: "Transfers", s: "airport → hotel last mile" },
                ].map((d) => (
                  <div key={d.t} className="ds-health-card card-lift">
                    <div className="text-2xl" aria-hidden>{d.e}</div>
                    <h3 className="ds-title mt-2 text-base">{d.t}</h3>
                    <p className="mt-1 text-xs leading-relaxed" style={{ color: "var(--muted)" }}>{d.s}</p>
                  </div>
                ))}
              </div>
            </Reveal>

            {/* the shared ledger — a live-feeling stat */}
            <Reveal delay={260}>
              <div
                className="flex h-full flex-col justify-center rounded-2xl p-7 text-center"
                style={{
                  background: "var(--card-peach)",
                  border: "1px solid rgba(107,63,40,0.14)",
                  boxShadow: "var(--sheen), var(--shadow)",
                }}
              >
                <div className="text-xs uppercase tracking-[0.24em]" style={{ color: "var(--muted)" }}>
                  the group&apos;s shared ledger
                </div>
                <div className="ds-title mt-3 text-5xl leading-none" style={{ color: "var(--card-coral-ink)" }}>
                  142
                </div>
                <div className="mt-2 text-sm" style={{ color: "var(--fg)" }}>
                  🚗 miles not driven <span style={{ color: "var(--muted)" }}>· ≈ 56 kg CO₂e avoided</span>
                </div>
              </div>
            </Reveal>
          </div>

          <Reveal delay={320}>
            <p className="mt-6 text-xs" style={{ color: "var(--muted)" }}>
              Baseline is the median of your own shortlist — savings only count when your pick
              beats it.
            </p>
          </Reveal>
        </div>
      </section>

      {/* ─── 8b. Show your work — the carbon methodology, proved ──────────── */}
      <section className="snap-panel px-6 py-20">
        <div className="mx-auto max-w-5xl">
          <Reveal>
            <p className="kicker mb-6">Show your work</p>
          </Reveal>
          <Reveal delay={80}>
            <h2 className="ds-title max-w-3xl text-3xl leading-[1.1] sm:text-4xl lg:text-5xl">
              The ledger never records a footprint. It records a difference.
            </h2>
          </Reveal>
          <Reveal delay={140}>
            <p className="mt-5 max-w-2xl text-base leading-relaxed sm:text-lg" style={{ color: "var(--muted)" }}>
              &ldquo;Your trip emits 3,080 kg&rdquo; is true and useless — it isn&apos;t a saving.
              Every entry answers a narrower question:{" "}
              <span style={{ color: "var(--fg)" }}>
                compared to the option that was actually on the table, how much less is this?
              </span>{" "}
              If a choice isn&apos;t better than its alternative, nothing is recorded at all.
            </p>
          </Reveal>

          <div className="mt-10 grid items-start gap-4 lg:grid-cols-[minmax(0,1fr)_1.05fr]">
            {/* the four steps — order matters, so they're numbered */}
            <Reveal delay={200}>
              <div className="grid h-full gap-3">
                {[
                  {
                    icon: "heroicons:calculator",
                    t: "Measure the pick",
                    s: "Distance or nights × a published factor. Every constant is local — a dead API can't move a carbon number.",
                  },
                  {
                    icon: "heroicons:scale",
                    t: "Name the counterfactual",
                    s: "The dirtiest flight on the list. The deck-average hotel. The same trip by car. Always something they could have picked.",
                  },
                  {
                    icon: "heroicons:users",
                    t: "Delta × the people",
                    s: "Per-person factors scale by group size, because four people flying is four times the flight.",
                  },
                  {
                    icon: "heroicons:shield-check",
                    t: "Credit only if positive",
                    s: "Pick the worst room on the deck and you earn zero, never a negative. The ledger can't go up on a bad choice.",
                  },
                ].map((d, i) => (
                  <div key={d.t} className="ds-health-card card-lift">
                    <div className="bar-top">
                      <div className="bar-icon">
                        <iconify-icon icon={d.icon} width="20" height="20" />
                      </div>
                      <h3 className="bar-name">{d.t}</h3>
                      <span
                        className="ml-auto text-xs tabular-nums"
                        style={{ color: "var(--muted)" }}
                        aria-hidden
                      >
                        0{i + 1}
                      </span>
                    </div>
                    <p className="text-xs leading-relaxed" style={{ color: "var(--muted)" }}>
                      {d.s}
                    </p>
                  </div>
                ))}
              </div>
            </Reveal>

            {/* the receipt — the actual arithmetic, itemised */}
            <Reveal delay={260}>
              <div
                className="flex h-full flex-col rounded-2xl p-6 sm:p-7"
                style={{ background: "var(--surface)", boxShadow: "var(--shadow)" }}
              >
                <div className="flex items-center gap-2">
                  <iconify-icon
                    icon="heroicons:receipt-percent"
                    width="16"
                    height="16"
                    style={{ color: "var(--card-mint-ink)" }}
                  />
                  <span
                    className="text-[0.68rem] font-bold uppercase tracking-[0.2em]"
                    style={{ color: "var(--card-mint-ink)" }}
                  >
                    Worked example · Toronto → Tokyo, 4 people
                  </span>
                </div>

                <div
                  className="mt-5 flex flex-col gap-3 text-sm tabular-nums"
                  style={{ fontFamily: "var(--font-body)" }}
                >
                  <div className="flex items-baseline justify-between gap-4">
                    <span>
                      Nonstop{" "}
                      <span style={{ color: "var(--muted)" }}>10,300 km × 0.1495 × 2</span>
                    </span>
                    <span className="font-semibold">3,079.6 kg</span>
                  </div>
                  <div className="flex items-baseline justify-between gap-4">
                    <span>
                      Via Chicago{" "}
                      <span style={{ color: "var(--muted)" }}>10,775 km + 50 kg stop</span>
                    </span>
                    <span className="font-semibold">3,321.7 kg</span>
                  </div>

                  <div style={{ borderTop: "1px dashed var(--card-peach)" }} className="my-1" />

                  <div className="flex items-baseline justify-between gap-4">
                    <span style={{ color: "var(--muted)" }}>Avoided per person</span>
                    <span className="font-semibold">242.1 kg</span>
                  </div>
                  <div className="flex items-baseline justify-between gap-4">
                    <span style={{ color: "var(--muted)" }}>× 4 travellers</span>
                    <span className="ds-title text-2xl" style={{ color: "var(--card-mint-ink)" }}>
                      968.4 kg
                    </span>
                  </div>
                </div>

                <div
                  className="mt-5 rounded-xl px-4 py-3 text-xs leading-relaxed"
                  style={{ background: "var(--card-mint)", color: "var(--card-mint-ink)" }}
                >
                  Note what isn&apos;t claimed: the trip still emits over three tonnes a head.
                  The ledger only says this choice avoided 242 kg of it — the detour distance
                  plus one more takeoff and landing.
                </div>
              </div>
            </Reveal>
          </div>

          <Reveal delay={320}>
            <div className="mt-6 flex flex-wrap items-center gap-x-5 gap-y-2 text-xs" style={{ color: "var(--muted)" }}>
              <span className="inline-flex items-center gap-1.5">
                <iconify-icon icon="heroicons:document-check" width="14" height="14" />
                Factors: DEFRA 2024 · CHSB 2023 · EPA · JR Central
              </span>
              <span className="inline-flex items-center gap-1.5">
                <iconify-icon icon="heroicons:beaker" width="14" height="14" />
                Every figure computed from the live module, not written by hand
              </span>
            </div>
          </Reveal>
        </div>
      </section>

      {/* ─── 9. The trip coin — Spotify-Wrapped memory card ───────────────── */}
      <section className="snap-panel px-6 py-20">
        <div className="mx-auto grid max-w-5xl items-center gap-10 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
          <div>
            <Reveal>
              <p className="kicker mb-6">Your souvenir</p>
            </Reveal>
            <Reveal delay={80}>
              <h2 className="ds-title text-3xl leading-[1.1] sm:text-4xl lg:text-5xl">
                Book it, and Tabi mints your trip&apos;s Spotify Wrapped.
              </h2>
            </Reveal>
            <Reveal delay={140}>
              <p className="mt-5 max-w-md text-base leading-relaxed sm:text-lg" style={{ color: "var(--muted)" }}>
                A custom coin, minted to the group on Solana — a permanent memory card of
                everything it took to finally go. Immutable. Yours.
              </p>
            </Reveal>
          </div>

          {/* the wrapped card */}
          <Reveal delay={180}>
            <div
              className="mx-auto w-full max-w-sm rounded-3xl p-7 text-left"
              style={{
                background: "linear-gradient(160deg, #2a241c 0%, #3a2f26 100%)",
                border: "1px solid rgba(245,239,224,0.14)",
                boxShadow: "inset 0 1px 0 rgba(245,239,224,0.12), 0 24px 60px rgba(42,36,28,0.35)",
                color: "#f5efe0",
              }}
            >
              <div className="flex items-center justify-between">
                <span className="text-xs uppercase tracking-[0.24em]" style={{ opacity: 0.6 }}>
                  Japan Trip Coin
                </span>
                <span className="text-xs" style={{ opacity: 0.6 }}>◎ Solana</span>
              </div>
              <div className="font-display mt-3 text-2xl">Kyoto · Aug 1–5</div>
              <div className="mt-6 flex flex-col gap-3 text-sm">
                {[
                  ["📍", "Destination", "Kyoto"],
                  ["🔁", "Iterations to book", "12"],
                  ["⏱️", "Time to book", "3 days"],
                  ["🌱", "CO₂e avoided", "56 kg"],
                ].map(([e, k, v]) => (
                  <div key={k} className="flex items-center justify-between" style={{ borderTop: "1px solid rgba(245,239,224,0.12)", paddingTop: 10 }}>
                    <span style={{ opacity: 0.8 }}>{e} {k}</span>
                    <span className="tabular-nums" style={{ fontWeight: 700 }}>{v}</span>
                  </div>
                ))}
              </div>
              <div className="mt-6 text-[0.7rem]" style={{ opacity: 0.5 }}>
                minted on devnet · immutable · one per group
              </div>
            </div>
          </Reveal>
        </div>
      </section>

      {/* ─── 10. Footer / CTA ─────────────────────────────────────────────── */}
      <section className="snap-panel relative overflow-hidden px-6">
        <Petals />
        <div className="relative mx-auto max-w-3xl text-center">
          <Reveal>
            <h2 className="ds-title mx-auto text-4xl leading-[1.06] sm:text-6xl">
              Stop letting the trip die in the group chat.
            </h2>
          </Reveal>
          <Reveal delay={150}>
            <p className="mx-auto mt-6 max-w-xl text-lg leading-relaxed" style={{ color: "var(--muted)" }}>
              Give your friends something that gets sad when you don&apos;t book — and a
              spring morning in Kyoto when you do.
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
            Built at Hack the 6ix · Tabi · いってらっしゃい
          </div>
          <div className="mt-12">
            <div className="text-xs uppercase tracking-[0.3em]" style={{ color: "var(--muted)" }}>
              the team
            </div>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src="/team.jpg"
              alt="The team behind Tabi at Hack the 6ix"
              className="mx-auto mt-4 w-full max-w-lg rounded-2xl"
              style={{ boxShadow: "var(--shadow)" }}
              loading="lazy"
            />
          </div>
        </div>
      </footer>
    </main>
  );
}
