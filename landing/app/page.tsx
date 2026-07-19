import SushiDemo from "@/components/SushiDemo";
import Reveal from "@/components/Reveal";
import Petals from "@/components/Petals";
import PipelineYouTube from "@/components/PipelineYouTube";
import ModelBenchmark from "@/components/ModelBenchmark";

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

const ACCOMPLISHMENTS = [
  {
    icon: "heroicons:user-group",
    title: "Finding the keystone",
    body: "An agent that finds the one person blocking the trip and nudges just them, by name, instead of spamming the whole chat. Phoebe learns roles from behavior (keystone, anchor, flake) so the nudge lands where it unsticks everyone else.",
  },
  {
    icon: "heroicons:cpu-chip",
    title: "Freesolo over a frontier baseline",
    body: "A 4B model trained on data our own product generated about itself beats a frontier model ~4× on held-out data (0.317 vs 0.078 gold-F1, 98% vs 0% pet-voice) and runs the live pet right now.",
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
    title: "Best data is home-grown",
    body: "The best training data isn't scraped. Logging every decision with its candidates, scores, and real outcome gave us a labelled dataset no one else has, on top of MongoDB covering matching, memory, and live sync.",
  },
  {
    icon: "heroicons:heart",
    title: "Personality beats deep reasoning",
    body: "Simple conversational logic with a strong personality reads as more \"alive\" to users than deeper reasoning would. Mood, voice, and timely nudges beat longer chain-of-thought.",
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
    body: "Make pet updates fully live with MongoDB change streams instead of polling, so the face in chat moves the instant health does.",
  },
  {
    icon: "heroicons:phone",
    title: "Voice-driven booking",
    body: "Expand tool-calling into a full voice-driven booking flow: reply to Tabi and it holds a room, DMs the holdout, or kicks off onboarding.",
  },
  {
    icon: "heroicons:users",
    title: "Self-play friend group",
    body: "Build a simulated friend group with keystone, anchor, and flake personas as a proper self-play training environment for Freesolo.",
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

function PipelineCards() {
  let stepNo = 0;
  return (
    <div className="mb-14 flex flex-col gap-6 sm:gap-7">
      {PIPELINE_CARDS.map((card, i) => {
        const steps = card.steps.map((step) => {
          stepNo += 1;
          return { ...step, n: stepNo };
        });
        const imageFirst = card.imageSide === "left";
        const mediaClass =
          card.fit === "contain"
            ? "absolute inset-0 h-full w-full object-contain p-3 sm:p-4"
            : "absolute inset-0 h-full w-full object-cover";

        return (
          <Reveal key={card.mediaAlt} delay={i * 100}>
            <article
              className="card-lift overflow-hidden"
              style={{
                borderRadius: "var(--radius)",
                background: "var(--surface)",
                boxShadow: "var(--shadow)",
              }}
            >
              {/* Media leads: ~60% of the row, taller panel so the visual carries the card. */}
              <div className="grid items-stretch lg:grid-cols-[1.55fr_minmax(0,1fr)]">
                <div
                  className={`relative min-h-[300px] overflow-hidden sm:min-h-[360px] lg:min-h-[460px] ${
                    imageFirst ? "lg:order-1" : "lg:order-2"
                  }`}
                  style={{ background: "var(--card-peach)" }}
                >
                  {card.mediaType === "youtube" ? (
                    <PipelineYouTube videoId={card.media} title={card.mediaAlt} />
                  ) : card.mediaType === "duo" && card.mediaExtra ? (
                    <div className="absolute inset-0 flex items-center justify-center gap-3 p-4 sm:gap-5 sm:p-6">
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img
                        src={card.media}
                        alt={card.mediaAlt}
                        className="h-[92%] max-h-full w-auto max-w-[60%] object-contain drop-shadow-sm"
                      />
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img
                        src={card.mediaExtra}
                        alt="Tabi avatar states fading through health moods"
                        className="h-[86%] max-h-full w-auto max-w-[46%] object-contain"
                      />
                    </div>
                  ) : (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={card.media} alt={card.mediaAlt} className={mediaClass} />
                  )}
                  {/* soft inner edge so the visual seats into the card */}
                  <div
                    className="pointer-events-none absolute inset-0"
                    style={{ boxShadow: "inset 0 0 0 1px rgba(42,36,28,0.05)" }}
                    aria-hidden
                  />
                </div>

                {/* Caption rail: condensed. Ghost step number + phase kicker + tight steps. */}
                <div
                  className={`relative flex flex-col justify-center overflow-hidden p-7 sm:p-8 lg:p-9 ${
                    imageFirst ? "lg:order-2" : "lg:order-1"
                  }`}
                >
                  <span
                    aria-hidden
                    className="ds-title pointer-events-none absolute -top-3 right-3 select-none leading-none tabular-nums"
                    style={{ fontSize: "6.5rem", color: "var(--fg)", opacity: 0.05 }}
                  >
                    {i + 1}
                  </span>
                  <p
                    className="mb-5 inline-flex w-fit items-center gap-2 text-xs font-semibold uppercase tracking-[0.22em]"
                    style={{ color: "var(--card-coral-ink)" }}
                  >
                    <span
                      className="inline-block h-1.5 w-1.5 rounded-full"
                      style={{ background: "var(--card-coral-ink)" }}
                    />
                    Phase {i + 1} · {card.phase}
                  </p>
                  <ul className="relative flex flex-col gap-4">
                    {steps.map((step) => (
                      <li key={step.n} className="flex gap-3">
                        <span
                          className="ds-title mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs tabular-nums"
                          style={{
                            background: "var(--card-peach)",
                            color: "var(--fg)",
                          }}
                        >
                          {step.n}
                        </span>
                        <div>
                          <h3 className="ds-title text-base leading-snug sm:text-[1.05rem]">
                            {step.title}
                          </h3>
                          <p
                            className="mt-1 text-[0.82rem] leading-relaxed"
                            style={{ color: "var(--muted)" }}
                          >
                            {step.body}
                          </p>
                        </div>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            </article>
          </Reveal>
        );
      })}
    </div>
  );
}

export default function Home() {
  return (
    <main style={{ color: "var(--fg)" }}>
      {/* ─── 1. Hero ──────────────────────────────────────────────────────── */}
      <section className="hero-split snap-start relative lg:grid lg:min-h-dvh lg:grid-cols-[minmax(0,55fr)_minmax(0,45fr)]">
        <div className="relative flex flex-col justify-center px-6 py-16 sm:px-10 sm:py-20 lg:px-12 lg:py-24 xl:px-16">
          <Petals />

          <div className="relative mx-auto w-full max-w-xl lg:mx-0 lg:max-w-[36rem]">
            <Reveal>
              <p className="ds-chip mb-7" style={{ display: "inline-flex" }}>
                <iconify-icon icon="heroicons:map-pin" width="14" height="14" />
                Tama-Go-Chi · Hack the 6ix
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

      {/* ─── 2. Problem — one big line, no title ──────────────────────────── */}
      <section className="snap-start snap-panel relative px-6">
        <Petals />
        <div className="relative mx-auto max-w-4xl text-center">
          <Reveal>
            <p className="ds-title text-[2.1rem] leading-[1.1] sm:text-5xl lg:text-6xl">
              Someone drops{" "}
              <span style={{ color: "var(--card-coral-ink)" }}>
                &ldquo;let&apos;s go to Japan bro.&rdquo;
              </span>
              <br className="hidden sm:block" /> Nobody ever books it.
            </p>
          </Reveal>
          <Reveal delay={160}>
            <p
              className="mx-auto mt-8 max-w-2xl text-lg leading-relaxed sm:text-2xl"
              style={{ color: "var(--muted)" }}
            >
              A few react, dates get half-discussed, the thread dies. The trip stays a
              sentence — so we turned it into a creature that dies with it.
            </p>
          </Reveal>
        </div>
      </section>

      {/* ─── 3. Video — full-bleed, no title ──────────────────────────────── */}
      <section className="snap-start snap-panel px-6">
        <Reveal className="mx-auto w-full max-w-6xl">
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
      </section>

      {/* ─── 4. How it works — the 3-step pipeline (cards self-label) ─────── */}
      <section className="snap-start px-6 py-24">
        <div className="mx-auto max-w-5xl">
          <Reveal>
            <p className="kicker mb-8">How it works</p>
          </Reveal>
          <PipelineCards />
        </div>
      </section>

      {/* ─── 5. The interactive scrubber — the centerpiece, big ───────────── */}
      <section className="snap-start snap-panel px-6">
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
      <section className="snap-start snap-panel px-6 py-20">
        <div className="mx-auto max-w-5xl">
          <Reveal>
            <p className="kicker mb-8">What&apos;s under the hood</p>
          </Reveal>
          <CardGrid items={PILLARS} cols="sm:grid-cols-2 lg:grid-cols-3" />
        </div>
      </section>

      {/* ─── 7. Proof — the benchmark leads, accomplishments support ──────── */}
      <section className="snap-start snap-panel px-6 py-20">
        <div className="mx-auto max-w-5xl">
          <Reveal>
            <div className="mb-10 flex justify-center">
              <ModelBenchmark />
            </div>
          </Reveal>
          <CardGrid items={ACCOMPLISHMENTS} cols="sm:grid-cols-3" />
        </div>
      </section>

      {/* ─── 8. Learned + next — de-titled, small kickers only ────────────── */}
      <section className="snap-start px-6 py-24">
        <div className="mx-auto max-w-5xl space-y-16">
          <div>
            <Reveal>
              <p className="kicker mb-6">What we learned</p>
            </Reveal>
            <CardGrid items={LEARNINGS} cols="sm:grid-cols-3" />
          </div>
          <div>
            <Reveal>
              <p className="kicker mb-6">Where it goes next</p>
            </Reveal>
            <CardGrid items={NEXT_STEPS} />
          </div>
        </div>
      </section>

      {/* ─── 9. Footer / CTA ──────────────────────────────────────────────── */}
      <section className="snap-start snap-panel relative overflow-hidden px-6">
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
            Built at Hack the 6ix · Tama-Go-Chi · いってらっしゃい
          </div>
        </div>
      </footer>
    </main>
  );
}
