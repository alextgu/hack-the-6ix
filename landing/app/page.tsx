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
    icon: "heroicons:chat-bubble-left-right",
    title: "Understand",
    body: "Gemini reads your group chat like another friend, extracting destinations, dates, budgets, group size, and preferences before reconciling everyone's conflicting answers into one realistic trip plan.",
  },
  {
    icon: "heroicons:currency-dollar",
    title: "Track",
    body: "Stay22 continuously monitors live hotel prices and availability. As deals disappear or prices increase, Tabi's physical health drops, turning procrastination into something the entire group can see.",
  },
  {
    icon: "heroicons:photo",
    title: "Express",
    body: "The Telegram Mini App brings Tabi to life through animated expressions and health bars. Every major planning update changes the pet's appearance, making the trip's progress instantly visible inside the chat.",
  },
  {
    icon: "heroicons:speaker-wave",
    title: "Communicate",
    body: "ElevenLabs gives Tabi an expressive voice that changes with its mood. Voice messages are transcribed, processed through the same planning pipeline, and answered naturally with emotional speech.",
  },
  {
    icon: "heroicons:megaphone",
    title: "Coordinate",
    body: "Phoebe identifies the single biggest blocker preventing the trip from happening, whether it's a person, scheduling conflict, or budget concern, and generates personalized nudges to move the group forward. Freesolo strengthens these conversations through GRPO-trained reinforcement learning.",
  },
  {
    icon: "heroicons:circle-stack",
    title: "Remember",
    body: "MongoDB Atlas stores every group's trip state, member preferences, pet health, hotel price history, and AI decisions. It powers vector search, live synchronization, and provides the training data that continually improves Tabi.",
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
                Tami · Hack the 6ix
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

      {/* ─── 8. Footer / CTA ──────────────────────────────────────────────── */}
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
            Built at Hack the 6ix · Tami · いってらっしゃい
          </div>
          <div className="mt-12">
            <div className="text-xs uppercase tracking-[0.3em]" style={{ color: "var(--muted)" }}>
              the team
            </div>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src="/team.jpg"
              alt="The team behind Tami at Hack the 6ix"
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
