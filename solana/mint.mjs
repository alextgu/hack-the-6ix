// Isolated devnet SPL mint for the "Japan Trip Coin" souvenir.
// Invoked by app/integrations/solana_coin.py via subprocess. ALWAYS exits 0
// with a JSON result on stdout ({ok:true,...} or {ok:false,reason,...}) so the
// Python caller only has to parse JSON — a mint failure can never crash it.
// SAFETY: refuses anything but a *-devnet/testnet cluster; never mainnet, never real funds.
import { Connection, Keypair, LAMPORTS_PER_SOL, clusterApiUrl } from "@solana/web3.js";
import { createMint, getOrCreateAssociatedTokenAccount, mintTo } from "@solana/spl-token";

function out(o) { process.stdout.write(JSON.stringify(o)); process.exit(0); }

async function loadTreasury() {
  const raw = (process.env.SOLANA_TREASURY_SECRET || "").trim();
  if (!raw) return null;
  let bytes;
  if (raw.startsWith("[")) bytes = Uint8Array.from(JSON.parse(raw));
  else bytes = (await import("bs58")).default.decode(raw); // base58 fallback
  return Keypair.fromSecretKey(bytes);
}

async function main() {
  const cluster = (process.env.SOLANA_CLUSTER || "devnet").trim();
  if (cluster === "mainnet-beta" || cluster === "mainnet") {
    return out({ ok: false, reason: "mainnet_blocked" }); // hard safety: souvenir is devnet-only
  }
  const treasury = await loadTreasury();
  if (!treasury) return out({ ok: false, reason: "no_treasury" });

  const conn = new Connection(clusterApiUrl(cluster), "confirmed");

  // Best-effort funding — a pre-funded treasury just skips this. Devnet airdrops
  // are rate-limited; if it fails we still try to mint and fail gracefully.
  let bal = await conn.getBalance(treasury.publicKey);
  if (bal < 0.05 * LAMPORTS_PER_SOL) {
    try {
      const sig = await conn.requestAirdrop(treasury.publicKey, 1 * LAMPORTS_PER_SOL);
      await conn.confirmTransaction(sig, "confirmed");
      bal = await conn.getBalance(treasury.publicKey);
    } catch (e) { /* rate-limited — proceed; mint fails gracefully if truly broke */ }
  }
  if (bal < 0.002 * LAMPORTS_PER_SOL) {
    return out({ ok: false, reason: "insufficient_funds", balance_sol: bal / LAMPORTS_PER_SOL });
  }

  // The coin: an SPL token mint (0 decimals), 1 unit minted to the treasury.
  const mint = await createMint(conn, treasury, treasury.publicKey, null, 0);
  const ata = await getOrCreateAssociatedTokenAccount(conn, treasury, mint, treasury.publicKey);
  const signature = await mintTo(conn, treasury, mint, ata.address, treasury, 1);

  // Souvenir metadata attributes — trait_type/value pairs (Metaplex shape),
  // omitting any that weren't supplied.
  const attributes = [
    ["Destination", process.env.COIN_LOCATION],
    ["Iterations to book", process.env.COIN_ITERATIONS],
    ["Time to book", process.env.COIN_TIME_SPENT],
    ["Did the least work", process.env.COIN_SLACKER],
    ["CO2e avoided", process.env.COIN_CO2E],
  ]
    .filter(([, v]) => (v || "").trim())
    .map(([trait_type, value]) => ({ trait_type, value: value.trim() }));

  out({
    ok: true,
    cluster,
    mint: mint.toBase58(),
    ata: ata.address.toBase58(),
    signature,
    explorer: `https://explorer.solana.com/address/${mint.toBase58()}?cluster=${cluster}`,
    name: process.env.COIN_NAME || "",
    booking_url: process.env.COIN_BOOKING_URL || "",
    image_url: process.env.TRIP_COIN_IMAGE_URL || "",
    attributes,
  });
}

main().catch((e) => out({ ok: false, reason: "exception", error: String((e && e.message) || e) }));
