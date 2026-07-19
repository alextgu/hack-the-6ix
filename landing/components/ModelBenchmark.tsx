// Held-out eval: our fine-tuned 4B vs a frontier model, zero-shot.
// Three metrics on different scales → small-multiple bar pairs (each its own
// scale), not one dual-axis chart. Palette validated (dataviz skill): Ours
// #b5472a (persimmon) vs Frontier #3b5bc0 (indigo) — CVD ΔE 23.6, contrast OK.
// All numbers are the real campaign results; identity is legend + direct
// labels, never color alone. Static (no client JS) — safe for the export.

const OURS = "#b5472a";
const FRONTIER = "#3b5bc0";

type Metric = {
  name: string;
  sub: string;
  unit: string;
  max: number;
  decimals: number;
  frontier: number;
  ours: number;
};

// Numbers are the committed held-out run: training/eval/results-*.jsonl
// (50 examples, 0 errors). Regenerate: python -m training.eval_harness
// --model gemini|flash:<run> --dump <path>. Decoding is stochastic, so a
// re-run moves these by ~0.01 — the file is the source of truth.
const METRICS: Metric[] = [
  { name: "Gold-F1", sub: "closeness to the ideal reply", unit: "", max: 0.4, decimals: 3, frontier: 0.078, ours: 0.317 },
  { name: "In-voice", sub: "sounds like the pet, not an assistant", unit: "%", max: 100, decimals: 0, frontier: 0, ours: 98 },
];

function Bar({ label, value, unit, max, decimals, color, strong }: {
  label: string; value: number; unit: string; max: number; decimals: number; color: string; strong?: boolean;
}) {
  const pct = Math.max(0, Math.min(100, (value / max) * 100));
  const shown = `${value.toFixed(decimals)}${unit}`;
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
      <span style={{ width: 66, flexShrink: 0, fontSize: 12.5, color: "var(--muted)", textAlign: "right" }}>{label}</span>
      <div style={{ position: "relative", flex: 1, height: 16, borderRadius: 9999, background: "rgba(42,36,28,0.06)" }}>
        <div
          style={{
            position: "absolute", left: 0, top: 0, bottom: 0,
            width: `max(4px, ${pct}%)`,
            background: color,
            borderRadius: 9999,
            boxShadow: strong ? `0 1px 8px ${color}55` : "none",
          }}
        />
      </div>
      <span style={{
        width: 52, flexShrink: 0, fontSize: 13.5, textAlign: "right",
        fontWeight: strong ? 700 : 500, fontVariantNumeric: "tabular-nums",
        color: strong ? color : "var(--fg)",
      }}>{shown}</span>
    </div>
  );
}

export default function ModelBenchmark() {
  return (
    <figure
      className="card-lift"
      style={{
        margin: 0, background: "var(--surface)", borderRadius: "var(--radius, 20px)",
        boxShadow: "var(--sheen), var(--shadow, 0 8px 30px rgba(42,36,28,0.10))",
        padding: "26px 26px 22px", maxWidth: 560, width: "100%",
      }}
    >
      <figcaption style={{ marginBottom: 4 }}>
        <div style={{ fontSize: 12, letterSpacing: "0.14em", textTransform: "uppercase", color: OURS, fontWeight: 700 }}>
          We trained the pet&apos;s brain ourselves
        </div>
        <h3 className="font-display" style={{ margin: "4px 0 2px", fontSize: 22, color: "var(--fg)" }}>
          Our 4B model vs. a frontier model
        </h3>
        <div style={{ fontSize: 13, color: "var(--muted)" }}>held-out eval · 50 examples · higher is better</div>
      </figcaption>

      {/* legend — identity is never color-alone */}
      <div style={{ display: "flex", gap: 18, margin: "14px 0 18px", fontSize: 12.5 }}>
        <span style={{ display: "inline-flex", alignItems: "center", gap: 7, color: "var(--fg)", fontWeight: 700 }}>
          <span style={{ width: 11, height: 11, borderRadius: 3, background: OURS }} /> Our 4B <span style={{ color: "var(--muted)", fontWeight: 500 }}>(live)</span>
        </span>
        <span style={{ display: "inline-flex", alignItems: "center", gap: 7, color: "var(--muted)" }}>
          <span style={{ width: 11, height: 11, borderRadius: 3, background: FRONTIER }} /> Frontier <span style={{ opacity: 0.8 }}>(zero-shot)</span>
        </span>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
        {METRICS.map((m) => (
          <div key={m.name}>
            <div style={{ display: "flex", flexWrap: "wrap", justifyContent: "space-between", alignItems: "baseline", gap: "2px 12px", marginBottom: 8 }}>
              <span style={{ fontSize: 14.5, fontWeight: 700, color: "var(--fg)" }}>{m.name}</span>
              <span style={{ fontSize: 12, color: "var(--muted)", marginLeft: "auto" }}>{m.sub}</span>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              <Bar label="Our 4B" value={m.ours} unit={m.unit} max={m.max} decimals={m.decimals} color={OURS} strong />
              <Bar label="Frontier" value={m.frontier} unit={m.unit} max={m.max} decimals={m.decimals} color={FRONTIER} />
            </div>
          </div>
        ))}
      </div>

      <div style={{
        marginTop: 20, paddingTop: 16, borderTop: "1px solid rgba(42,36,28,0.1)",
        fontSize: 13.5, color: "var(--fg)", lineHeight: 1.5,
      }}>
        Trained on data the product generated about itself — SFT → distillation → GRPO on
        Qwen&nbsp;4B — and the live pet runs on it right now.
      </div>
    </figure>
  );
}
