/**
 * ScreenSynchronisation — Supervision de la synchronisation offline→cloud (§4.8 CDC, étape 15).
 *
 * Ce module n'avait pas de route dédiée dans la v1 (le panneau de synchro
 * était intégré dans ScreenTableauBord). Il est exposé ici comme écran
 * autonome pour monitoring détaillé et actions de maintenance.
 *
 * Affiche :
 *  - Statut connexion (ping Supabase, dernière synchro réussie)
 *  - Compteurs : en attente, en échec, conflits non résolus
 *  - Bouton "Rejouer les échecs"
 *  - Indicateur visuel de l'état global (OK / Dégradé / Hors-ligne)
 *
 * Polling automatique toutes les 15 s pour rester à jour sans action manuelle.
 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  RefreshCw, Loader2, Wifi, WifiOff, AlertTriangle,
  CheckCircle2, Clock, RotateCcw, CloudOff, Cloud,
} from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { api } from "@/lib/api-client";
import { fmtDate } from "@/lib/format";
import type { EtatSync } from "@/lib/types";

// ── Carte de métrique ─────────────────────────────────────────────────────────

function CarteMesure({
  label, valeur, sous, alerte,
}: { label: string; valeur: number | string; sous?: string; alerte?: boolean }) {
  return (
    <div className={`rounded-xl border p-5 ${alerte ? "border-destructive/40 bg-destructive/5" : "border-border/70 bg-surface/40"}`}>
      <div className="text-xs uppercase tracking-wide text-muted-foreground mb-1">{label}</div>
      <div className={`font-display text-3xl numeric ${alerte ? "text-destructive" : ""}`}>{valeur}</div>
      {sous && <div className="text-xs text-muted-foreground mt-1">{sous}</div>}
    </div>
  );
}

// ── Composant principal exporté ───────────────────────────────────────────────

export function ScreenSynchronisation() {
  const qc = useQueryClient();

  const { data: etat, isLoading, refetch } = useQuery<EtatSync>({
    queryKey: ["sync-etat-detail"],
    queryFn: () => api.synchronisation.etat(),
    refetchInterval: 15_000,   // polling 15 s
    staleTime: 10_000,
  });

  const rejouer = useMutation({
    mutationFn: () => api.synchronisation.rejouer(),
    onSuccess: (r) => {
      toast.success(`${r.rejoues} événement(s) rejoué(s).`);
      void qc.invalidateQueries({ queryKey: ["sync-etat-detail"] });
    },
    onError: (e) => toast.error("Erreur de rejeu", { description: String(e) }),
  });

  // Calcul de l'état global
  const enLigne       = etat?.est_connecte ?? etat?.supabase_accessible ?? false;
  const enAttente     = etat?.nb_en_attente ?? etat?.nombre_evenements_en_attente ?? 0;
  const enEchec       = etat?.nb_en_echec   ?? etat?.nombre_evenements_en_echec   ?? 0;
  const conflits      = etat?.conflits_non_resolus ?? 0;
  const dernierSync   = etat?.derniere_synchro_reussie ?? etat?.derniere_sync_reussie ?? null;
  const aDesProblemes = enEchec > 0 || conflits > 0;

  const etatGlobal = !enLigne
    ? { label: "Hors-ligne", couleur: "text-destructive", bg: "bg-destructive/10 border-destructive/30", Icon: WifiOff }
    : aDesProblemes
      ? { label: "Dégradé",   couleur: "text-warning",     bg: "bg-warning/10 border-warning/30",         Icon: AlertTriangle }
      : { label: "Opérationnel", couleur: "text-success",  bg: "bg-success/10 border-success/30",          Icon: CheckCircle2 };

  return (
    <div className="flex h-screen flex-col overflow-hidden">
      <header className="flex items-center justify-between border-b border-border/70 bg-surface/80 px-6 py-4">
        <div>
          <h1 className="font-display text-3xl leading-none">Synchronisation</h1>
          <p className="text-xs text-muted-foreground mt-1">
            Surveillance offline → cloud · Polling toutes les 15 s
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="sm" onClick={() => void refetch()} disabled={isLoading} title="Actualiser maintenant">
            {isLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
          </Button>
          <Button
            variant="secondary"
            onClick={() => rejouer.mutate()}
            disabled={rejouer.isPending || enEchec === 0}
            className="gap-2"
            title={enEchec === 0 ? "Aucun échec à rejouer" : `Rejouer ${enEchec} événement(s)`}
          >
            {rejouer.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <RotateCcw className="h-4 w-4" />}
            Rejouer les échecs
          </Button>
        </div>
      </header>

      <div className="flex-1 overflow-y-auto px-6 py-6 space-y-6">
        {isLoading && !etat ? (
          <div className="flex items-center justify-center py-20 text-muted-foreground gap-2">
            <Loader2 className="h-6 w-6 animate-spin" />
            Chargement de l'état de synchronisation…
          </div>
        ) : (
          <>
            {/* Bannière état global */}
            <div className={`flex items-center gap-4 rounded-xl border p-5 ${etatGlobal.bg}`}>
              <etatGlobal.Icon className={`h-8 w-8 ${etatGlobal.couleur} shrink-0`} />
              <div>
                <div className={`font-display text-2xl ${etatGlobal.couleur}`}>{etatGlobal.label}</div>
                <div className="text-sm text-muted-foreground mt-0.5">
                  {dernierSync
                    ? `Dernière synchronisation réussie : ${fmtDate(dernierSync)}`
                    : "Aucune synchronisation réussie enregistrée."}
                </div>
              </div>
              <div className="ml-auto shrink-0">
                {enLigne
                  ? <Cloud className="h-6 w-6 text-success/60" />
                  : <CloudOff className="h-6 w-6 text-destructive/60" />}
              </div>
            </div>

            {/* Métriques */}
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
              <CarteMesure
                label="Connexion" valeur={enLigne ? "En ligne" : "Hors-ligne"}
                sous={enLigne ? "Supabase accessible" : "Mode offline actif"}
                alerte={!enLigne}
              />
              <CarteMesure
                label="En attente" valeur={enAttente}
                sous={enAttente === 0 ? "File vide" : "Événement(s) à synchroniser"}
              />
              <CarteMesure
                label="En échec" valeur={enEchec}
                sous={enEchec === 0 ? "Aucun échec" : "Utilisez « Rejouer »"}
                alerte={enEchec > 0}
              />
              <CarteMesure
                label="Conflits" valeur={conflits}
                sous={conflits === 0 ? "Aucun conflit" : "Résolution manuelle requise"}
                alerte={conflits > 0}
              />
            </div>

            <Separator />

            {/* Guide de résolution */}
            <div className="rounded-xl border border-border/70 bg-surface/40 p-6">
              <h2 className="font-display text-lg mb-4">Guide de résolution</h2>
              <div className="space-y-4 text-sm">
                <div className="flex gap-3">
                  <WifiOff className="h-4 w-4 text-destructive shrink-0 mt-0.5" />
                  <div>
                    <span className="font-medium">Hors-ligne</span> — Les ventes continuent d'être enregistrées localement (Dexie). Elles seront automatiquement transmises dès le retour de la connexion.
                  </div>
                </div>
                <div className="flex gap-3">
                  <RotateCcw className="h-4 w-4 text-warning shrink-0 mt-0.5" />
                  <div>
                    <span className="font-medium">Événements en échec</span> — Cliquez sur « Rejouer les échecs » pour tenter une nouvelle transmission. Si l'erreur persiste, consultez les logs du serveur.
                  </div>
                </div>
                <div className="flex gap-3">
                  <AlertTriangle className="h-4 w-4 text-warning shrink-0 mt-0.5" />
                  <div>
                    <span className="font-medium">Conflits non résolus</span> — Un conflit indique que deux postes ont modifié la même ressource simultanément. La résolution doit être effectuée manuellement dans le tableau de bord cloud.
                  </div>
                </div>
                <div className="flex gap-3">
                  <Clock className="h-4 w-4 text-muted-foreground shrink-0 mt-0.5" />
                  <div>
                    <span className="font-medium">Polling automatique</span> — Cet écran interroge le serveur toutes les 15 secondes. Utilisez le bouton d'actualisation pour forcer une vérification immédiate.
                  </div>
                </div>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
