import { Database, Fingerprint, ShieldAlert, ShieldCheck } from "lucide-react";

export default function MissionLedgerPanel({ ledger }) {
  if (!ledger || ledger.status === "empty") return null;
  const corrupt = ledger.status === "corrupt";
  return <section className={`mx-3 mb-2 rounded-xl border p-3 ${corrupt ? "border-red-300/25 bg-red-300/[0.05]" : "border-cyan-300/15 bg-cyan-300/[0.035]"}`} aria-label="Omega Mission Ledger">
    <div className="flex items-center justify-between gap-2"><div className="flex items-center gap-2"><Database className={`h-3.5 w-3.5 ${corrupt ? "text-red-200" : "text-cyan-200"}`} /><div><div className="text-[9px] font-mono uppercase tracking-[0.18em] text-cyan-200/70">Mission Ledger</div><div className="text-xs text-white/70">{corrupt ? "Integrity failure — quarantined" : "Durable proof journal"}</div></div></div>{corrupt ? <ShieldAlert className="h-3.5 w-3.5 text-red-200" /> : <ShieldCheck className="h-3.5 w-3.5 text-cyan-200" />}</div>
    <div className="mt-2 grid grid-cols-3 gap-1.5 text-center font-mono text-[9px]"><div className="rounded border border-white/5 bg-black/20 p-1.5"><div className="text-white/35">missions</div><div className="mt-0.5 text-white/80">{corrupt ? 0 : ledger.missions?.length || 0}</div></div><div className="rounded border border-white/5 bg-black/20 p-1.5"><div className="text-white/35">events</div><div className="mt-0.5 text-white/80">{corrupt ? 0 : ledger.events?.length || 0}</div></div><div className="rounded border border-white/5 bg-black/20 p-1.5"><div className="text-white/35">integrity</div><div className={`mt-0.5 ${corrupt ? "text-red-200" : "text-cyan-200"}`}>{corrupt ? "fail" : "verified"}</div></div></div>
    <div className="mt-2 flex items-start gap-1.5 text-[9px] leading-relaxed text-white/35"><Fingerprint className="mt-0.5 h-3 w-3 shrink-0" />{corrupt ? "Local records were not trusted. No recovered mission state was loaded." : `head: ${(ledger.head || "pending").slice(0, 12)} · reload-safe · local-only`}</div>
  </section>;
}
