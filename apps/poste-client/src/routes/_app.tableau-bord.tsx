/**
 * Tableau de bord (§4.1 du cahier des charges).
 *
 * Cinq KPIs temps réel + table des alertes non résolues + lots en péremption.
 * Polling automatique toutes les 30 secondes.
 * L'état de synchronisation est affiché en bas de page.
 */

import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useRef } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  TrendingUp, ShoppingCart, AlertTriangle, Clock, Wifi, WifiOff,
  RefreshCw, CheckCircle2, Loader2, PackageX,
} from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { api } from "@/lib/api-client";
import { fmtFCFA, fmtDate, fmtDateCourte } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { TableauBord, AlerteStock, LotDetail, EtatSync } from "@/lib/types";

export const Route = createFileRoute("/_app/tableau-bord")({
  component: PageTableauBord,
  head: () => ({
    meta: [
      { title: "Tableau de bord — PharmApp" },
      { name: "description", content: "KPIs, alertes stock et état de synchronisation." },
    ],
  }),
});

const POLL_INTERVAL = 30_000; // 30 s

function PageTableauBord() {
  const qc = useQueryClient();

  // ── Données ──────────────────────────────────────────────────────────────
  const { data: kpis, isLoading: kpisLoading } = useQuery<TableauBord>({
    queryKey: ["tableau-bord"],
    queryFn: () => api.rapports.tableauBord(),
    refetchInterval: POLL_INTERVAL,
  });

  const { data: alertesData } = useQuery({
    queryKey: ["alertes-stock", { est_resolue: false }],
    queryFn: () => api.alertes.liste({ est_resolue: false }),
    refetchInterval: POLL_INTERVAL,
  });

  const { data: lotsData } = useQuery({
    queryKey: ["lots", { peremption_proche: true }],
    queryFn: () => api.lots.liste({ peremption_proche: true, page_size: 20 }),
    refetchInterval: POLL_INTERVAL,
  });

  const { data: syncData } = useQuery<EtatSync>({
    queryKey: ["sync-etat"],
    queryFn: () => api.sync.etat(),
    refetchInterval: POLL_INTERVAL,
  });

  // ── Résolution d'alerte ───────────────────────────────────────────────────
  const resoudreAlerte = useMutation({
    mutationFn: (id: string) => api.alertes.resoudre(id),
    onSuccess: () => {
      toast.success("Alerte marquée comme résolue.");
      void qc.invalidateQueries({ queryKey: ["alertes-stock"] });
      void qc.invalidateQueries({ queryKey: ["tableau-bord"] });
    },
    onError: (e) => toast.error("Impossible de résoudre l'alerte", { description: String(e) }),
  });

  const alertes  = alertesData?.results ?? [];
  const lots     = lotsData?.results ?? [];

  return (
    <div className="flex h-screen flex-col overflow-hidden">
      {/* ── En-tête ────────────────────────────────────────────────────── */}
      <header className="flex items-center justify-between border-b border-border/70 bg-surface/60 px-6 py-4 backdrop-blur shrink-0">
        <div>
          <h1 className="font-display text-3xl leading-none">Tableau de bord</h1>
          <p className="text-xs text-muted-foreground mt-1">
            Mis à jour toutes les 30 secondes · Journée en cours
          </p>
        </div>
        <SyncBadge sync={syncData} />
      </header>

      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        {/* ── KPIs ──────────────────────────────────────────────────────── */}
        <section>
          <h2 className="font-display text-xl mb-4">Performance du jour</h2>
          {kpisLoading ? (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" /> Chargement…
            </div>
          ) : (
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
              <KpiCard
                label="CA du jour"
                value={fmtFCFA(kpis?.ca_aujourd_hui ?? 0)}
                icon={<TrendingUp className="h-5 w-5" />}
                couleur="text-money"
              />
              <KpiCard
                label="Ventes validées"
                value={String(kpis?.nb_ventes_aujourd_hui ?? 0)}
                icon={<ShoppingCart className="h-5 w-5" />}
                unite="ventes"
              />
              <KpiCard
                label="Alertes stock"
                value={String((kpis?.nb_alertes_stock ?? 0) + (kpis?.nb_ruptures ?? 0))}
                icon={<AlertTriangle className="h-5 w-5" />}
                couleur={(kpis?.nb_ruptures ?? 0) > 0 ? "text-destructive" : (kpis?.nb_alertes_stock ?? 0) > 0 ? "text-warning" : undefined}
                sous={kpis?.nb_ruptures ? `dont ${kpis.nb_ruptures} rupture(s)` : undefined}
              />
              <KpiCard
                label="Péremptions proches"
                value={String(kpis?.nb_peremptions_proches ?? 0)}
                icon={<Clock className="h-5 w-5" />}
                couleur={(kpis?.nb_peremptions_proches ?? 0) > 0 ? "text-warning" : undefined}
                sous={kpis ? `≤ ${kpis.seuil_peremption_jours} jours` : undefined}
              />
            </div>
          )}
        </section>

        <Separator />

        {/* ── Alertes stock non résolues ────────────────────────────────── */}
        <section>
          <div className="flex items-center justify-between mb-3">
            <h2 className="font-display text-xl">Alertes de stock actives</h2>
            {alertes.length > 0 && (
              <Badge variant="secondary">{alertes.length}</Badge>
            )}
          </div>
          {alertes.length === 0 ? (
            <div className="card-elevated p-6 text-center text-sm text-muted-foreground">
              <CheckCircle2 className="h-8 w-8 mx-auto mb-2 text-success" />
              Aucune alerte active — tous les stocks sont au-dessus des seuils.
            </div>
          ) : (
            <div className="card-elevated overflow-hidden">
              <table className="w-full text-sm">
                <thead className="border-b border-border/70 bg-surface-strong/50">
                  <tr>
                    <th className="text-left px-4 py-3 font-medium text-muted-foreground">Médicament</th>
                    <th className="text-center px-4 py-3 font-medium text-muted-foreground">Niveau</th>
                    <th className="text-right px-4 py-3 font-medium text-muted-foreground">Stock actuel</th>
                    <th className="text-right px-4 py-3 font-medium text-muted-foreground">Seuil</th>
                    <th className="text-right px-4 py-3 font-medium text-muted-foreground">Détectée le</th>
                    <th className="px-4 py-3" />
                  </tr>
                </thead>
                <tbody>
                  {alertes.map((a: AlerteStock, i: number) => (
                    <tr key={a.id} className={cn("border-b border-border/40 hover:bg-surface-strong/30", i % 2 === 0 ? "" : "bg-surface/30")}>
                      <td className="px-4 py-3 font-medium">{a.medicament_nom}</td>
                      <td className="px-4 py-3 text-center">
                        <NiveauBadge niveau={(a.niveau ?? "alerte") as "alerte" | "rupture"} />
                      </td>
                      <td className="px-4 py-3 text-right numeric">{a.stock_au_moment_alerte}</td>
                      <td className="px-4 py-3 text-right numeric text-muted-foreground">{a.seuil_depasse}</td>
                      <td className="px-4 py-3 text-right text-muted-foreground">{fmtDateCourte(a.cree_le)}</td>
                      <td className="px-4 py-3 text-right">
                        <Button
                          size="sm" variant="ghost"
                          disabled={resoudreAlerte.isPending}
                          onClick={() => resoudreAlerte.mutate(a.id)}
                          title="Marquer comme résolue"
                        >
                          <CheckCircle2 className="h-4 w-4" />
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        <Separator />

        {/* ── Lots en péremption prochaine ──────────────────────────────── */}
        <section>
          <div className="flex items-center justify-between mb-3">
            <h2 className="font-display text-xl">Lots en péremption proche</h2>
            {lots.length > 0 && (
              <Badge variant="secondary">{lots.length}</Badge>
            )}
          </div>
          {lots.length === 0 ? (
            <div className="card-elevated p-6 text-center text-sm text-muted-foreground">
              <PackageX className="h-8 w-8 mx-auto mb-2 text-muted-foreground" />
              Aucun lot n'expire dans le délai configuré.
            </div>
          ) : (
            <div className="card-elevated overflow-hidden">
              <table className="w-full text-sm">
                <thead className="border-b border-border/70 bg-surface-strong/50">
                  <tr>
                    <th className="text-left px-4 py-3 font-medium text-muted-foreground">Médicament</th>
                    <th className="text-left px-4 py-3 font-medium text-muted-foreground">N° lot</th>
                    <th className="text-right px-4 py-3 font-medium text-muted-foreground">Qté dispo</th>
                    <th className="text-right px-4 py-3 font-medium text-muted-foreground">Péremption</th>
                    <th className="text-right px-4 py-3 font-medium text-muted-foreground">Jours restants</th>
                  </tr>
                </thead>
                <tbody>
                  {lots.map((l: LotDetail, i: number) => {
                    const joursRestants = Math.ceil(
                      (new Date(l.date_peremption).getTime() - Date.now()) / 86_400_000
                    );
                    const urgence = joursRestants <= 15 ? "text-destructive" : joursRestants <= 30 ? "text-warning" : "text-muted-foreground";
                    return (
                      <tr key={l.id} className={cn("border-b border-border/40 hover:bg-surface-strong/30", i % 2 === 0 ? "" : "bg-surface/30")}>
                        <td className="px-4 py-3 font-medium">{l.medicament_nom}</td>
                        <td className="px-4 py-3 font-mono text-xs">{l.numero_lot}</td>
                        <td className="px-4 py-3 text-right numeric">{l.quantite_disponible}</td>
                        <td className="px-4 py-3 text-right">{fmtDateCourte(l.date_peremption)}</td>
                        <td className={cn("px-4 py-3 text-right numeric font-medium", urgence)}>
                          {joursRestants} j
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </section>

        {/* ── Synchronisation ───────────────────────────────────────────── */}
        {syncData && (
          <>
            <Separator />
            <section>
              <h2 className="font-display text-xl mb-3">Synchronisation</h2>
              <div className="card-elevated p-5 grid grid-cols-2 lg:grid-cols-4 gap-4 text-sm">
                <SyncStat label="Statut" value={LIBELLES_SYNC[syncData.statut_connexion ?? ""] ?? "—"} />
                <SyncStat
                  label="Dernière sync"
                  value={syncData.derniere_sync_reussie ? fmtDate(syncData.derniere_sync_reussie) : "Jamais"}
                />
                <SyncStat label="En attente" value={String(syncData.nombre_evenements_en_attente)} />
                <SyncStat
                  label="En échec"
                  value={String(syncData.nombre_evenements_en_echec)}
                  alerte={(syncData.nombre_evenements_en_echec ?? 0) > 0}
                />
              </div>
            </section>
          </>
        )}
      </div>
    </div>
  );
}

// ── Sous-composants ──────────────────────────────────────────────────────────

function KpiCard({
  label, value, icon, couleur, unite, sous,
}: {
  label: string;
  value: string;
  icon: React.ReactNode;
  couleur?: string;
  unite?: string;
  sous?: string;
}) {
  return (
    <div className="card-elevated p-5 space-y-2">
      <div className="flex items-center gap-2 text-muted-foreground text-xs uppercase tracking-wide">
        {icon}
        {label}
      </div>
      <div className={cn("font-display text-3xl leading-none numeric", couleur)}>
        {value}
        {unite && <span className="text-base font-sans font-normal text-muted-foreground ml-1">{unite}</span>}
      </div>
      {sous && <p className="text-xs text-muted-foreground">{sous}</p>}
    </div>
  );
}

function NiveauBadge({ niveau }: { niveau: "alerte" | "rupture" }) {
  return (
    <span className={cn(
      "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium",
      niveau === "rupture"
        ? "bg-destructive/15 text-destructive"
        : "bg-warning/15 text-warning",
    )}>
      {niveau === "rupture" ? "Rupture" : "Alerte"}
    </span>
  );
}

function SyncBadge({ sync }: { sync: EtatSync | undefined }) {
  if (!sync) return null;
  const en_ligne = sync.statut_connexion === "en_ligne";
  return (
    <div className={cn(
      "flex items-center gap-2 rounded-full px-3 py-1.5 text-xs font-medium",
      en_ligne ? "bg-success/15 text-success" : "bg-destructive/15 text-destructive",
    )}>
      {en_ligne ? <Wifi className="h-3.5 w-3.5" /> : <WifiOff className="h-3.5 w-3.5" />}
      {LIBELLES_SYNC[sync.statut_connexion ?? ""] ?? "—"}
      {(sync.nombre_evenements_en_attente ?? 0) > 0 && (
        <span className="font-normal opacity-70">· {sync.nombre_evenements_en_attente} en attente</span>
      )}
    </div>
  );
}

function SyncStat({ label, value, alerte }: { label: string; value: string; alerte?: boolean }) {
  return (
    <div>
      <p className="text-xs text-muted-foreground uppercase tracking-wide mb-1">{label}</p>
      <p className={cn("font-medium", alerte && "text-destructive")}>{value}</p>
    </div>
  );
}

const LIBELLES_SYNC: Record<string, string> = {
  en_ligne:   "En ligne",
  hors_ligne: "Hors ligne",
  degradee:   "Dégradée",
};
