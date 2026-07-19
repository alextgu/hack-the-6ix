import Reveal from "@/components/Reveal";
import Petals from "@/components/Petals";
import ModelBenchmark from "@/components/ModelBenchmark";
import PipelineSlideshow from "@/components/PipelineSlideshow";
import AmbientMusic from "@/components/AmbientMusic";

const BOT_HANDLE = "@PetSamaBot";
const BOT_URL = `https://t.me/${BOT_HANDLE.replace(/^@/, "")}`;

// A real coin minted on Solana devnet — clickable, verifiable on-chain.
const MINT_EXPLORER =
  "https://explorer.solana.com/address/9F2u1WywuPryEuZBzzgoqQfvfSTLvgSdnQLDLjVvrHv8?cluster=devnet";
// Demo walkthrough — click to play, never autoplays.
const DEMO_VIDEO = "https://www.youtube.com/embed/t1_Amtt9RSQ?start=6&rel=0&modestbranding=1";

const SPONSORS = ["Stay22", "Phoebe", "Freesolo", "MongoDB Atlas", "ElevenLabs", "Gemini"];

const PIPELINE_CARDS = [
  {
    phase: "Meet Tabi",
    media: "",
    mediaExtra: undefined as string | undefined,
    mediaType: "demo" as const,
    fit: "contain" as const,
    mediaAlt: "Interactive health-bar simulation of Tabi the sushi pet",
    imageSide: "left" as const,
    steps: [
      {
        title: "Try it",
        body: "Drag the weeks forward — prices climb, the chat goes quiet, and Tabi rots. Book to revive her.",
      },
    ],
  },
  {
    phase: "Onboard",
    media: "/pipeline-tabi-checkin.png",
    mediaExtra: "/pet/all-avatars-fade.gif",
    mediaType: "duo" as const,
    fit: "contain" as const,
    mediaAlt: "Tabi planning dashboard and avatar states",
    imageSide: "right" as const,
    steps: [
      { title: "Joins the chat", body: "Add Tabi to your group chat." },
      { title: "Listens to everything", body: "She reads the conversation — text, voice notes, images." },
      { title: "Understands everyone", body: "Destinations, dates, budgets, and preferences, per person." },
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
      { title: "Tinder-style votes", body: "Everyone swipes on hotels and options — one tap each." },
      { title: "Reconciles the group", body: "She melts conflicting answers into one plan and names the blocker." },
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
      { title: "Iterates until agreement", body: "Propose, vote, unblock — over and over until the whole group commits." },
      { title: "Makes it real", body: "Books a live Stay22 hotel and the trip officially happens." },
    ],
  },
];

// The real roster, in the order a message actually moves through them:
// four LangGraph nodes (supervisor routes, stage/profile trackers read state,
// messenger writes) plus four standalone modules. Names match app/agents/.
const AGENTS = [
  "supervisor",
  "stage tracker",
  "profile tracker",
  "messenger",
  "brain",
  "phoebe",
  "greenplanner",
  "face",
];

// The brain — the agents behind Tabi (script beat 3).
const BRAIN = [
  {
    icon: "heroicons:microphone",
    title: "Multimodal scraper",
    body: "Pulls constraints from text, voice notes, and images.",
  },
  {
    icon: "heroicons:funnel",
    title: "The reconciler",
    body: "Melts everyone's price, location, and time into one plan.",
  },
  {
    icon: "heroicons:megaphone",
    title: "Blocker agent",
    body: "Finds who's stalling the trip — and calls them out by name.",
  },
  {
    icon: "heroicons:cpu-chip",
    title: "Gemini × LangGraph",
    body: "A team of agents, run as one deterministic supervisor.",
  },
];

function CTAButton({ large = false }: { large?: boolean }) {
  return (
    <a href={BOT_URL} className={large ? "ds-cta hero-cta" : "ds-cta"}>
      Add to Telegram
      <span style={{ opacity: 0.7, fontFamily: "var(--font-body)", fontSize: large ? 14 : 13 }}>
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
      <AmbientMusic />
      {/* ─── 1. HOOK ──────────────────────────────────────────────────────── */}
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
              <p className="mt-6 max-w-md text-lg leading-relaxed sm:text-xl" style={{ color: "var(--fg)" }}>
                Meet <strong>Tabi</strong> — the group-chat pet that{" "}
                <span style={{ color: "var(--card-coral-ink)" }}>dies if your trip doesn&apos;t happen.</span>
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

      {/* ─── 2. HOW IT WORKS ──────────────────────────────────────────────── */}
      <section className="snap-panel px-6 py-20">
        <div className="mx-auto max-w-5xl">
          <Reveal>
            <p className="kicker mb-4">How it works</p>
          </Reveal>
          <Reveal delay={60}>
            <p className="mb-8 max-w-3xl text-lg leading-relaxed sm:text-xl" style={{ color: "var(--fg)" }}>
              Tabi joins your group chat, listens to everything, runs{" "}
              <span style={{ color: "var(--card-coral-ink)" }}>Tinder-style votes</span>{" "}on
              everyone&apos;s picks, and iterates until the whole group agrees.
            </p>
          </Reveal>
          <Reveal delay={120}>
            <PipelineSlideshow cards={PIPELINE_CARDS} />
          </Reveal>
        </div>
      </section>

      {/* ─── 3. THE BRAIN ─────────────────────────────────────────────────── */}
      <section className="snap-panel px-6 py-20">
        <div className="mx-auto max-w-5xl">
          <Reveal>
            <p className="kicker mb-4">The brain</p>
          </Reveal>
          <Reveal delay={60}>
            <h2 className="ds-title max-w-3xl text-3xl leading-[1.1] sm:text-4xl lg:text-5xl">
              A team of Gemini agents on LangGraph — plus a model we trained ourselves.
            </h2>
          </Reveal>
          <Reveal delay={120}>
            <p className="mt-4 max-w-2xl text-base leading-relaxed sm:text-lg" style={{ color: "var(--muted)" }}>
              The blocker agent is <span style={{ color: "var(--fg)" }}>FreeSolo</span>{" — "}Qwen&nbsp;4B,
              fine-tuned with GRPO. On a held-out eval it beats a frontier model at finding the group&apos;s
              real blocker and speaking in the pet&apos;s voice:
            </p>
          </Reveal>

          <div className="mt-8 grid items-center gap-8 lg:grid-cols-[minmax(0,1fr)_auto]">
            <CardGrid items={BRAIN} cols="sm:grid-cols-2" />
            <Reveal delay={180}>
              <div className="flex justify-center">
                <ModelBenchmark />
              </div>
            </Reveal>
          </div>

          {/* The actual roster. Names only — the four cards above already say
              what they do, so this just shows there's a real team behind them
              rather than one prompt wearing hats. One quiet line, no new
              visual weight. */}
          <Reveal delay={240}>
            <p className="mt-8 text-xs leading-relaxed" style={{ color: "var(--muted)" }}>
              <span className="font-semibold" style={{ color: "var(--fg)" }}>
                Eight agents on the graph:
              </span>{" "}
              {AGENTS.join(" · ")}
            </p>
          </Reveal>
        </div>
      </section>

      {/* ─── 4. SEE IT LIVE → (transition to the live Telegram demo) ───────── */}
      <section className="snap-panel px-6 py-20">
        <div className="mx-auto w-full max-w-4xl text-center">
          <Reveal>
            <h2 className="ds-title text-4xl leading-[1.05] sm:text-6xl">
              See it live{" "}
              <span style={{ color: "var(--card-coral-ink)" }}>→</span>
            </h2>
          </Reveal>
          <Reveal delay={100}>
            <p className="mx-auto mt-5 max-w-xl text-base leading-relaxed sm:text-lg" style={{ color: "var(--muted)" }}>
              This is where we open Telegram and plan a real trip. Watch the walkthrough:
            </p>
          </Reveal>
          <Reveal delay={160} className="mt-8">
            <div
              className="framed mx-auto overflow-hidden"
              style={{ borderRadius: "var(--radius)", background: "var(--surface)", padding: 10 }}
            >
              <div
                className="relative w-full overflow-hidden"
                style={{
                  aspectRatio: "16 / 9",
                  borderRadius: "calc(var(--radius) - 12px)",
                  boxShadow: "inset 0 0 0 1px rgba(42,36,28,0.06)",
                }}
              >
                <iframe
                  src={DEMO_VIDEO}
                  title="Tabi demo walkthrough"
                  className="absolute inset-0 h-full w-full border-0"
                  allow="accelerometer; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
                  allowFullScreen
                  referrerPolicy="strict-origin-when-cross-origin"
                />
              </div>
            </div>
          </Reveal>
        </div>
      </section>

      {/* ─── 5. GREEN BY DEFAULT ──────────────────────────────────────────── */}
      <section className="snap-panel px-6 py-20">
        <div className="mx-auto max-w-5xl">
          <Reveal>
            <p className="kicker mb-4">Green by default</p>
          </Reveal>
          <Reveal delay={60}>
            <h2 className="ds-title max-w-3xl text-3xl leading-[1.1] sm:text-4xl lg:text-5xl">
              Every booking is carbon-scored the moment it&apos;s on the table.
            </h2>
          </Reveal>
          <Reveal delay={120}>
            <p className="mt-4 max-w-2xl text-base leading-relaxed sm:text-lg" style={{ color: "var(--muted)" }}>
              Flights, trains, hotels, even the airport transfer — priced in CO₂e from published
              government factors, computed locally, so the numbers are{" "}
              <span style={{ color: "var(--fg)" }}>impossible to inflate</span>.
            </p>
          </Reveal>

          <div className="mt-10 grid items-stretch gap-4 lg:grid-cols-[1.3fr_minmax(0,1fr)]">
            <Reveal delay={200}>
              <div className="grid h-full grid-cols-2 gap-3">
                {[
                  { e: "✈️", t: "Flights", s: "DEFRA — incl. radiative forcing" },
                  { e: "🚄", t: "Trains", s: "JR Central — Shinkansen factors" },
                  { e: "🏨", t: "Hotels", s: "by class & rooms the party needs" },
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
                <div className="ds-title mt-4 text-2xl leading-tight sm:text-3xl" style={{ color: "var(--card-coral-ink)" }}>
                  142 miles not driven
                </div>
                <div className="mt-2 text-sm" style={{ color: "var(--muted)" }}>
                  every green choice, counted and totalled
                </div>
              </div>
            </Reveal>
          </div>

          {/* The receipt — the claim above, with the arithmetic shown. Folded
              into this beat rather than given its own section, so the 6-beat
              pacing holds. */}
          <Reveal delay={300}>
            <div
              className="mt-4 grid items-center gap-5 rounded-2xl p-6 sm:p-7 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]"
              style={{ background: "var(--surface)", boxShadow: "var(--shadow)" }}
            >
              <div>
                <div className="flex items-center gap-2">
                  <iconify-icon
                    icon="heroicons:receipt-percent"
                    width="15"
                    height="15"
                    style={{ color: "var(--card-mint-ink)" }}
                  />
                  <span
                    className="text-[0.65rem] font-bold uppercase tracking-[0.2em]"
                    style={{ color: "var(--card-mint-ink)" }}
                  >
                    Show your work
                  </span>
                </div>
                <p className="ds-title mt-3 text-lg leading-snug sm:text-xl">
                  We never log a footprint. We log a difference.
                </p>
                <p className="mt-2 text-sm leading-relaxed" style={{ color: "var(--muted)" }}>
                  &ldquo;Your trip emits 3,080 kg&rdquo; is true and useless — it isn&apos;t a saving.
                  Every entry answers a narrower question:{" "}
                  <span style={{ color: "var(--fg)" }}>
                    versus the option actually on the table, how much less is this?
                  </span>
                </p>
              </div>

              <div className="flex flex-col gap-2.5 text-sm tabular-nums">
                <div className="flex items-baseline justify-between gap-4">
                  <span>
                    Nonstop <span style={{ color: "var(--muted)" }}>YYZ→NRT, 10,300 km</span>
                  </span>
                  <span className="font-semibold">3,079.6 kg</span>
                </div>
                <div className="flex items-baseline justify-between gap-4">
                  <span>
                    Via Chicago <span style={{ color: "var(--muted)" }}>+475 km, +1 landing</span>
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
            </div>
          </Reveal>

          <Reveal delay={320}>
            <p className="mt-6 text-xs" style={{ color: "var(--muted)" }}>
              Sources: DEFRA · EPA · JR Central. Baseline is the median of your own shortlist — savings only
              count when your pick beats it. Every figure computed from the live module.
            </p>
          </Reveal>
        </div>
      </section>

      {/* ─── 5b. Show your work — one viewport: method left, live proof right.
             The worked-example receipt lives in the Green section above, so
             this beat is method + evidence only (no duplicate arithmetic). ─── */}
      <section className="snap-panel px-6 py-16">
        <div className="mx-auto grid w-full max-w-6xl items-center gap-8 lg:grid-cols-[minmax(0,1.25fr)_minmax(0,1fr)]">
          {/* Left — the method */}
          <div>
            <Reveal>
              <p className="kicker mb-4">Show your work · the carbon math</p>
            </Reveal>
            <Reveal delay={60}>
              <h2 className="ds-title max-w-xl text-3xl leading-[1.08] sm:text-4xl">
                The ledger never records a footprint. It records a difference.
              </h2>
            </Reveal>
            <Reveal delay={120}>
              <p className="mt-3 max-w-xl text-sm leading-relaxed sm:text-base" style={{ color: "var(--muted)" }}>
                If a choice isn&apos;t better than the alternative on the table, nothing is
                recorded — carbon accounting that would survive an auditor.
              </p>
            </Reveal>

            <Reveal delay={180}>
              <div className="mt-6 grid gap-3 sm:grid-cols-2">
                {[
                  { icon: "heroicons:calculator", t: "Measure the pick", s: "Distance or nights × a published factor — every constant local, no API in the loop." },
                  { icon: "heroicons:scale", t: "Name the counterfactual", s: "The dirtiest flight listed, the deck-average hotel, the same trip by car." },
                  { icon: "heroicons:users", t: "Delta × the people", s: "Four people flying is four times the flight — factors scale by group size." },
                  { icon: "heroicons:shield-check", t: "Credit only if positive", s: "A worse pick earns zero, never a negative. Bad choices can't grow the ledger." },
                ].map((d, i) => (
                  <div key={d.t} className="ds-health-card card-lift">
                    <div className="bar-top">
                      <div className="bar-icon"><iconify-icon icon={d.icon} width="18" height="18" /></div>
                      <h3 className="bar-name text-sm">{d.t}</h3>
                      <span className="ml-auto text-xs tabular-nums" style={{ color: "var(--muted)" }} aria-hidden>0{i + 1}</span>
                    </div>
                    <p className="text-xs leading-relaxed" style={{ color: "var(--muted)" }}>{d.s}</p>
                  </div>
                ))}
              </div>
            </Reveal>

            <Reveal delay={240}>
              <div className="mt-6 pl-4" style={{ borderLeft: "3px solid var(--card-mint-ink)" }}>
                <p className="text-sm leading-relaxed sm:text-base">
                  <span className="font-semibold" style={{ color: "var(--card-mint-ink)" }}>
                    Not a slide — that&apos;s the live product.
                  </span>{" "}
                  <span style={{ color: "var(--muted)" }}>
                    Type{" "}
                    <code
                      className="rounded-md px-1.5 py-0.5 text-[0.85em]"
                      style={{ background: "rgba(42,36,28,0.06)", color: "var(--fg)" }}
                    >
                      /saved
                    </code>{" "}
                    in the chat and Tabi computes the group&apos;s real ledger on the spot, from the
                    same module behind every figure on this page.
                  </span>
                </p>
                <p className="mt-2 text-xs" style={{ color: "var(--muted)" }}>
                  Factors: DEFRA 2024 · CHSB 2023 · EPA · JR Central
                </p>
              </div>
            </Reveal>
          </div>

          {/* Right — the live /saved output in the actual chat, full column height */}
          <Reveal delay={200}>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src="/japannnn.png"
              alt="Tabi's live /saved green ledger in the Telegram chat: 19.9 kg CO2e avoided, EPA equivalents, 1,000-group scale-up, and sources (DEFRA, EPA, CHSB, JR Central)"
              className="framed mx-auto w-auto rounded-3xl"
              style={{ maxHeight: "min(78vh, 720px)" }}
              loading="lazy"
            />
          </Reveal>
        </div>
      </section>

      {/* ─── 6. THE COIN ──────────────────────────────────────────────────── */}
      <section className="snap-panel px-6 py-20">
        <div className="mx-auto grid max-w-5xl items-center gap-10 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
          <div>
            <Reveal>
              <p className="kicker mb-4">Your souvenir</p>
            </Reveal>
            <Reveal delay={80}>
              <h2 className="ds-title text-3xl leading-[1.1] sm:text-4xl lg:text-5xl">
                Book it, and Tabi mints your trip&apos;s Spotify Wrapped.
              </h2>
            </Reveal>
            <Reveal delay={140}>
              <p className="mt-5 max-w-md text-base leading-relaxed sm:text-lg" style={{ color: "var(--muted)" }}>
                A permanent memory card for the group — the destination, how many iterations and how
                long it took to book, and the carbon you avoided. Minted once on Solana, so it&apos;s
                immutable. Yours.
              </p>
            </Reveal>
          </div>

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
                  Trip Wrapped
                </span>
                <span className="text-xs" style={{ opacity: 0.6 }}>2026</span>
              </div>
              <div className="font-display mt-3 text-2xl">Kyoto · Aug 1–5</div>
              <div className="mt-6 flex flex-col gap-3 text-sm">
                {[
                  ["📍", "Destination", "Kyoto"],
                  ["🔁", "Iterations to book", "12"],
                  ["⏱️", "Time to book", "3 days"],
                  ["🌱", "Carbon avoided", "142 mi not driven"],
                ].map(([e, k, v]) => (
                  <div
                    key={k}
                    className="flex items-center justify-between gap-4"
                    style={{ borderTop: "1px solid rgba(245,239,224,0.12)", paddingTop: 10 }}
                  >
                    <span style={{ opacity: 0.8 }}>{e} {k}</span>
                    <span className="tabular-nums" style={{ fontWeight: 700 }}>{v}</span>
                  </div>
                ))}
              </div>
              <div className="mt-6 flex items-center justify-between gap-3 text-[0.7rem]" style={{ opacity: 0.6 }}>
                <span>minted on Solana devnet · immutable · one per group</span>
                <a
                  href={MINT_EXPLORER}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex shrink-0 items-center gap-1 underline underline-offset-2"
                  style={{ color: "#f5efe0", opacity: 0.9 }}
                >
                  verify
                  <iconify-icon icon="heroicons:arrow-top-right-on-square" width="12" height="12" />
                </a>
              </div>
            </div>
          </Reveal>
        </div>
      </section>

      {/* ─── Footer / CTA ─────────────────────────────────────────────────── */}
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
              Give your friends something that gets sad when you don&apos;t book — and a spring morning in
              Kyoto when you do.
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
