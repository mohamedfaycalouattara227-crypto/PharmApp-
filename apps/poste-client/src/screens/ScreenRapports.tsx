/**
 * ScreenRapports — Rapports & Statistiques (§4.8 CDC).
 *
 * Extrait de _app.rapports.tsx lors du découpage modulaire (v2).
 * La route conserve uniquement la définition TanStack Router.
 *
 * Onglets : Ventes, Top produits, Marges (titulaire), Export CSV.
 * Graphiques : barres SVG inline sans dépendance externe.
 */

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { BarChart3, TrendingUp, Package, Download, RefreshCw } from "lucide-react";

import { api } from "@/lib/api-client";
import { fmtFCFA, fmtNombre, LIBELLES_MODE_PAIEMENT } from "@/lib/format";
import type { MargeProduit, TopProduit } from "@/lib/types";

const HIERARCHIE: Record<string, number> = {
  stagiaire: 0, caissier: 1, assistant: 2, gestionnaire_stock: 3,
  pharmacien_adjoint: 4, titulaire: 5, administrateur: 6,
};
function getRole(): string { return window.sessionStorage.getItem("pharmapp.role") ?? ""; }
function peutVoirMarges(): boolean { return (HIERARCHIE[getRole()] ?? -1) >= 5; }
function getDateDebut(joursMoins: number): string {
  const d = new Date(); d.setDate(d.getDate() - joursMoins); return d.toISOString().slice(0, 10);
}
function getDateAujourd(): string { return new Date().toISOString().slice(0, 10); }

// ── Mini-graphique barres SVG ────────────────────────────────────────────────

function BarSVG({ data }: { data: { label: string; valeur: number }[] }) {
  const max = Math.max(...data.map((d) => d.valeur), 1);
  const h = 100;
  const w = Math.max(500, data.length * 40);
  return (
    <div className="overflow-x-auto">
      <svg viewBox={`0 0 ${w} ${h + 20}`} className="w-full" style={{ minWidth: 300 }}>
        {data.map((d, i) => {
          const barH = (d.valeur / max) * h;
          const x    = (i / data.length) * w + 4;
          const bw   = (w / data.length) - 8;
          return (
            <g key={i}>
              <rect x={x} y={h - barH} width={bw} height={barH} className="fill-primary/70 hover:fill-primary" rx="3" />
              <text x={x + bw / 2} y={h + 14} textAnchor="middle" className="fill-muted-foreground" fontSize="9">
                {d.label.length > 8 ? d.label.slice(0, 7) + "…" : d.label}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

// ── Onglets ──────────────────────────────────────────────────────────────────

function OngletVentes() {
  const [debut, setDebut] = useState(getDateDebut(30));
  const [fin, setFin]     = useState(getDateAujourd());

  const { data, isLoading, refetch } = useQuery({
    queryKey: ["rapport-ventes", debut, fin],
    queryFn: () => api.rapports.ventes({ debut, fin }),
    staleTime: 60_000,
  });

  const chartData = Object.entries(data?.repartition_paiement ?? {})
    .map(([k, v]) => ({ label: LIBELLES_MODE_PAIEMENT[k] ?? k, valeur: Number(v) }))
    .filter((d) => d.valeur > 0);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end gap-3">
        <div><label className="label">Du</label><input className="input w-40" type="date" value={debut} onChange={(e) => setDebut(e.target.value)} /></div>
        <div><label className="label">Au</label><input className="input w-40" type="date" value={fin} onChange={(e) => setFin(e.target.value)} /></div>
        <button onClick={() => refetch()} className="btn btn-ghost flex items-center gap-2"><RefreshCw className="h-4 w-4" /> Actualiser</button>
      </div>
      {isLoading ? <div className="text-center py-12 text-muted-foreground">Chargement…</div> : data ? (
        <>
          <div className="grid grid-cols-3 gap-4">
            <div className="rounded-xl bg-surface/60 border border-border/70 p-5">
              <div className="text-sm text-muted-foreground mb-1">Chiffre d'affaires</div>
              <div className="text-2xl font-display font-semibold">{fmtFCFA(data.ca_total ?? data.chiffre_affaires)}</div>
            </div>
            <div className="rounded-xl bg-surface/60 border border-border/70 p-5">
              <div className="text-sm text-muted-foreground mb-1">Nombre de ventes</div>
              <div className="text-2xl font-display font-semibold">{fmtNombre(data.nb_ventes ?? data.total_ventes)}</div>
            </div>
            <div className="rounded-xl bg-surface/60 border border-border/70 p-5">
              <div className="text-sm text-muted-foreground mb-1">Total remises</div>
              <div className="text-2xl font-display font-semibold text-warning">{fmtFCFA(data.remises_total ?? 0)}</div>
            </div>
          </div>
          {chartData.length > 0 && (
            <div className="rounded-xl border border-border/70 bg-surface/40 p-5">
              <h3 className="font-medium mb-4">Répartition par mode de paiement</h3>
              <BarSVG data={chartData} />
              <div className="mt-4 grid grid-cols-3 gap-3 text-sm">
                {chartData.map((d) => (
                  <div key={d.label} className="flex items-center justify-between">
                    <span className="text-muted-foreground">{d.label}</span>
                    <span className="font-medium">{fmtFCFA(d.valeur)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      ) : null}
    </div>
  );
}

function OngletTopProduits() {
  const [periode, setPeriode] = useState(30);
  const { data, isLoading, refetch } = useQuery({
    queryKey: ["top-produits", periode],
    queryFn: () => api.rapports.topProduits({ periode, limit: 30 }),
    staleTime: 60_000,
  });
  const produits = data ?? [];

  return (
    <div className="space-y-4">
      <div className="flex items-end gap-3">
        <div>
          <label className="label">Période</label>
          <select className="input w-36" value={periode} onChange={(e) => setPeriode(Number(e.target.value))}>
            <option value={7}>7 jours</option>
            <option value={30}>30 jours</option>
            <option value={90}>3 mois</option>
            <option value={365}>1 an</option>
          </select>
        </div>
        <button onClick={() => refetch()} className="btn btn-ghost flex items-center gap-2"><RefreshCw className="h-4 w-4" /></button>
      </div>
      {isLoading ? <div className="text-center py-12 text-muted-foreground">Chargement…</div>
        : produits.length === 0 ? <div className="text-center py-12 text-muted-foreground">Aucune donnée sur cette période.</div>
        : (
          <div className="rounded-xl border border-border/70 overflow-hidden">
            <table className="w-full text-sm border-collapse">
              <thead className="bg-surface/80">
                <tr className="text-muted-foreground text-left">
                  <th className="py-3 pl-4 pr-2 font-medium w-10">#</th>
                  <th className="py-3 pr-4 font-medium">Médicament</th>
                  <th className="py-3 pr-4 font-medium">DCI</th>
                  <th className="py-3 pr-4 font-medium text-right">Qté vendue</th>
                  <th className="py-3 pr-4 font-medium text-right">CA</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/40">
                {produits.map((p: TopProduit, i: number) => (
                  <tr key={i} className="hover:bg-surface/60">
                    <td className="py-2.5 pl-4 pr-2 text-muted-foreground">{i + 1}</td>
                    <td className="py-2.5 pr-4 font-medium">{p.medicament__nom}</td>
                    <td className="py-2.5 pr-4 text-muted-foreground text-xs">{p.medicament__denomination_commune_internationale || "—"}</td>
                    <td className="py-2.5 pr-4 text-right font-mono">{fmtNombre(p.quantite_totale)}</td>
                    <td className="py-2.5 pr-4 text-right font-mono">{fmtFCFA(p.ca_total ?? p.chiffre_affaires ?? 0)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
    </div>
  );
}

function OngletMarges() {
  const [debut, setDebut] = useState(getDateDebut(30));
  const [fin, setFin]     = useState(getDateAujourd());
  const { data, isLoading } = useQuery({
    queryKey: ["marges", debut, fin],
    queryFn: () => api.rapports.marges({ debut, fin }),
    staleTime: 60_000,
  });

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end gap-3">
        <div><label className="label">Du</label><input className="input w-40" type="date" value={debut} onChange={(e) => setDebut(e.target.value)} /></div>
        <div><label className="label">Au</label><input className="input w-40" type="date" value={fin} onChange={(e) => setFin(e.target.value)} /></div>
      </div>
      {isLoading ? <div className="text-center py-12 text-muted-foreground">Chargement…</div>
        : !data || data.length === 0 ? <div className="text-center py-12 text-muted-foreground">Aucune donnée de marge sur cette période.</div>
        : (
          <div className="rounded-xl border border-border/70 overflow-hidden">
            <table className="w-full text-sm border-collapse">
              <thead className="bg-surface/80">
                <tr className="text-muted-foreground text-left">
                  <th className="py-3 pl-4 pr-4 font-medium">Médicament</th>
                  <th className="py-3 pr-4 font-medium text-right">Qté</th>
                  <th className="py-3 pr-4 font-medium text-right">CA</th>
                  <th className="py-3 pr-4 font-medium text-right">PA moyen</th>
                  <th className="py-3 pr-4 font-medium text-right">Marge brute</th>
                  <th className="py-3 pr-4 font-medium text-right">Taux</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/40">
                {(data as MargeProduit[]).map((m, i) => (
                  <tr key={i} className="hover:bg-surface/60">
                    <td className="py-2.5 pl-4 pr-4 font-medium">{m.medicament_nom}</td>
                    <td className="py-2.5 pr-4 text-right font-mono">{fmtNombre(m.quantite_totale ?? 0)}</td>
                    <td className="py-2.5 pr-4 text-right font-mono">{fmtFCFA(m.ca_total ?? 0)}</td>
                    <td className="py-2.5 pr-4 text-right font-mono">{fmtFCFA(m.pa_moyen ?? m.cout_moyen ?? 0)}</td>
                    <td className={`py-2.5 pr-4 text-right font-mono ${Number(m.marge_brute ?? m.marge) < 0 ? "text-destructive" : "text-success"}`}>{fmtFCFA(m.marge_brute ?? m.marge ?? 0)}</td>
                    <td className={`py-2.5 pr-4 text-right ${Number(m.taux_marge_pct) < 10 ? "text-warning" : "text-foreground"}`}>{m.taux_marge_pct} %</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
    </div>
  );
}

function OngletExport() {
  const [debut, setDebut] = useState(getDateDebut(30));
  const [fin, setFin]     = useState(getDateAujourd());
  return (
    <div className="space-y-6 max-w-lg">
      <p className="text-sm text-muted-foreground">Téléchargez le détail de toutes les ventes validées au format CSV (compatible Excel / LibreOffice Calc).</p>
      <div className="space-y-3">
        <div><label className="label">Du</label><input className="input w-48" type="date" value={debut} onChange={(e) => setDebut(e.target.value)} /></div>
        <div><label className="label">Au</label><input className="input w-48" type="date" value={fin} onChange={(e) => setFin(e.target.value)} /></div>
      </div>
      <a href={api.rapports.exportVentesUrl(debut, fin)} download={`ventes_${debut}_${fin}.csv`} className="btn btn-primary flex w-fit items-center gap-2">
        <Download className="h-4 w-4" /> Télécharger CSV
      </a>
    </div>
  );
}

// ── Composant principal exporté ──────────────────────────────────────────────

type Onglet = "ventes" | "top-produits" | "marges" | "export";

export function ScreenRapports() {
  const [onglet, setOnglet] = useState<Onglet>("ventes");

  const onglets: { id: Onglet; label: string; icon: React.ComponentType<{ className?: string }>; restreint?: boolean }[] = [
    { id: "ventes",       label: "Ventes",       icon: BarChart3 },
    { id: "top-produits", label: "Top produits",  icon: Package },
    ...(peutVoirMarges() ? [{ id: "marges" as Onglet, label: "Marges", icon: TrendingUp, restreint: true }] : []),
    { id: "export",       label: "Export CSV",    icon: Download },
  ];

  return (
    <div className="flex h-screen flex-col overflow-hidden">
      <header className="flex items-center gap-3 border-b border-border/70 bg-surface/80 px-6 py-4">
        <BarChart3 className="h-5 w-5 text-muted-foreground" />
        <h1 className="font-display text-2xl">Rapports & Statistiques</h1>
      </header>
      <div className="border-b border-border/70 px-6 flex gap-4">
        {onglets.map((o) => {
          const Icon = o.icon;
          return (
            <button key={o.id} onClick={() => setOnglet(o.id)} className={`py-3 text-sm font-medium border-b-2 transition-colors flex items-center gap-1.5 ${onglet === o.id ? "border-primary text-primary" : "border-transparent text-muted-foreground hover:text-foreground"}`}>
              <Icon className="h-4 w-4" />{o.label}
              {o.restreint && <span className="ml-1 text-xs text-muted-foreground">(titulaire)</span>}
            </button>
          );
        })}
      </div>
      <div className="flex-1 overflow-auto px-6 py-6">
        {onglet === "ventes"       && <OngletVentes />}
        {onglet === "top-produits" && <OngletTopProduits />}
        {onglet === "marges"       && (peutVoirMarges() ? <OngletMarges /> : <div className="text-center py-16 text-muted-foreground">Accès réservé au pharmacien titulaire.</div>)}
        {onglet === "export"       && <OngletExport />}
      </div>
    </div>
  );
}
