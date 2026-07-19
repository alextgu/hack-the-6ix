import type { ReactNode } from "react";
import SushiDemo from "@/components/SushiDemo";
import Reveal from "@/components/Reveal";
import Petals from "@/components/Petals";
import PipelineYouTube from "@/components/PipelineYouTube";

const BOT_HANDLE = "@PetSamaBot";
const BOT_URL = `https://t.me/${BOT_HANDLE.replace(/^@/, "")}`;

const SPONSORS = ["Stay22", "Phoebe", "Freesolo", "MongoDB Atlas", "ElevenLabs", "Gemini"];

const PIPELINE_CARDS = [
  {
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
    body: "A 4B model trained on data our own product generated about itself beats a frontier model ~4× on held-out data (0.33 vs 0.086 gold-F1, 96% vs 0% pet-voice) and runs the live pet right now.",
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

function PipelineCards() {
  let stepNo = 0;
  return (
    <div className="mb-14 flex flex-col gap-8">
      {PIPELINE_CARDS.map((card, i) => {
        const steps = card.steps.map((step) => {
          stepNo += 1;
          return { ...step, n: stepNo };
        });
        const imageFirst = card.imageSide === "left";
        const mediaClass =
          card.fit === "contain"
            ? "absolute inset-0 h-full w-full object-contain p-4 sm:p-6"
            : "absolute inset-0 h-full w-full object-cover";

        return (
          <Reveal key={card.mediaAlt} delay={i * 100}>
            <div
              className="overflow-hidden"
              style={{
                borderRadius: "var(--radius)",
                background: "var(--surface)",
                boxShadow: "var(--shadow)",
              }}
            >
              <div className="grid items-stretch lg:grid-cols-2">
                <div
                  className={`relative min-h-[280px] overflow-hidden sm:min-h-[320px] lg:min-h-[380px] ${
                    imageFirst ? "lg:order-1" : "lg:order-2"
                  }`}
                  style={{ background: "var(--card-peach)" }}
                >
                  {card.mediaType === "youtube" ? (
                    <PipelineYouTube
                      videoId={card.media}
                      title={card.mediaAlt}
                    />
                  ) : card.mediaType === "duo" && card.mediaExtra ? (
                    <div className="absolute inset-0 flex items-center justify-center gap-3 p-3 sm:gap-4 sm:p-5">
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img
                        src={card.media}
                        alt={card.mediaAlt}
                        className="h-full max-h-full w-auto max-w-[52%] object-contain"
                      />
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img
                        src={card.mediaExtra}
                        alt="Tabi avatar states fading through health moods"
                        className="h-[72%] max-h-full w-auto max-w-[40%] object-contain"
                      />
                    </div>
                  ) : (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img
                      src={card.media}
                      alt={card.mediaAlt}
                      className={mediaClass}
                    />
                  )}
                </div>
                <div
                  className={`flex flex-col justify-center gap-5 p-6 sm:gap-6 sm:p-8 ${
                    imageFirst ? "lg:order-2" : "lg:order-1"
                  }`}
                >
                  {steps.map((step) => (
                    <div key={step.n} className="flex gap-3">
                      <span
                        className="ds-title shrink-0 tabular-nums"
                        style={{ color: "var(--fg)", minWidth: "1.75rem" }}
                      >
                        {step.n}.
                      </span>
                      <div>
                        <h3 className="ds-title text-base sm:text-lg">
                          {step.title}
                        </h3>
                        <p
                          className="mt-1 text-sm leading-relaxed"
                          style={{ color: "var(--muted)" }}
                        >
                          {step.body}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </Reveal>
        );
      })}
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
        <PipelineCards />

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
          <SectionTitle eyebrow="How we built it">Six Pillars</SectionTitle>
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
