/**
 * Gestion des stocks (§4.3 du cahier des charges).
 *
 * Quatre onglets :
 *   1. Vue d'ensemble — médicaments + stock total + badge alerte
 *   2. Lots           — détail par lot + badge péremption
 *   3. Mouvements     — historique filtrable
 *   4. Alertes        — alertes non résolues avec action de résolution
 *
 * Dialog "Ajuster stock" : lot_id + nouvelle_quantite + motif.
 * Bouton "Démarrer inventaire" réservé aux gestionnaires de stock.
 */

import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Package, AlertTriangle, ArrowUpDown, ClipboardList,
  Loader2, CheckCircle2, RefreshCw, Filter,
} from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from "@/components/ui/dialog";
import { api } from "@/lib/api-client";
import { fmtFCFA, fmtDateCourte } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { LotDetail, AlerteStock, MouvementStock, Medicament } from "@/lib/types";

/**
 * Export de compatibilité — les écrans encore en placeholder (ex. clients)
 * importent ce composant depuis ce fichier pour afficher un état "À venir".
 * À supprimer au fur et à mesure que les écrans sont implémentés.
 */
export function Placeholder({ titre, sous }: { titre: string; sous?: string }) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-3 text-center p-8">
      <Package className="h-12 w-12 text-muted-foreground/40" />
      <h2 className="font-display text-2xl">{titre}</h2>
      {sous && <p className="text-sm text-muted-foreground max-w-sm">{sous}</p>}
      <span className="mt-2 inline-flex items-center rounded-full bg-primary/10 px-3 py-1 text-xs font-medium text-primary">
        Prochaine itération
      </span>
    </div>
  );
}

export const Route = createFileRoute("/_app/stock")({
  component: PageStock,
  head: () => ({
    meta: [
      { title: "Gestion des stocks — PharmApp" },
      { name: "description", content: "Vue d'ensemble, lots, mouvements et alertes de stock." },
    ],
  }),
});

type Onglet = "overview" | "lots" | "mouvements" | "alertes";

const ONGLETS: { id: Onglet; label: string; icon: React.ReactNode }[] = [
  { id: "overview",   label: "Vue d'ensemble", icon: <Package className="h-4 w-4" /> },
  { id: "lots",       label: "Lots",           icon: <ClipboardList className="h-4 w-4" /> },
  { id: "mouvements", label: "Mouvements",     icon: <ArrowUpDown className="h-4 w-4" /> },
  { id: "alertes",    label: "Alertes",        icon: <AlertTriangle className="h-4 w-4" /> },
];

function PageStock() {
  const [onglet, setOnglet] = useState<Onglet>("overview");
  const [dialogAjuster, setDialogAjuster] = useState(false);

  return (
    <div className="flex h-screen flex-col overflow-hidden">
      {/* ── En-tête ──────────────────────────────────────────────────────── */}
      <header className="flex items-center justify-between border-b border-border/70 bg-surface/60 px-6 py-4 backdrop-blur shrink-0">
        <div>
          <h1 className="font-display text-3xl leading-none">Gestion des stocks</h1>
          <p className="text-xs text-muted-foreground mt-1">
            Lots FEFO · Ajustements · Inventaires · Alertes
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            onClick={() => setDialogAjuster(true)}
          >
            Ajuster un stock
          </Button>
          <BoutonDemarrerInventaire />
        </div>
      </header>

      {/* ── Barre d'onglets ───────────────────────────────────────────────── */}
      <div className="flex gap-1 px-6 py-3 border-b border-border/60 bg-surface/40 shrink-0">
        {ONGLETS.map((o) => (
          <button
            key={o.id}
            onClick={() => setOnglet(o.id)}
            className={cn(
              "flex items-center gap-2 rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
              onglet === o.id
                ? "bg-primary text-primary-foreground"
                : "text-muted-foreground hover:bg-surface-strong hover:text-foreground",
            )}
          >
            {o.icon}
            {o.label}
          </button>
        ))}
      </div>

      {/* ── Contenu de l'onglet actif ─────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto">
        {onglet === "overview"   && <OngletOverview />}
        {onglet === "lots"       && <OngletLots />}
        {onglet === "mouvements" && <OngletMouvements />}
        {onglet === "alertes"    && <OngletAlertes />}
      </div>

      {/* ── Dialog ajustement ─────────────────────────────────────────────── */}
      <DialogAjusterStock
        ouvert={dialogAjuster}
        onFermer={() => setDialogAjuster(false)}
      />
    </div>
  );
}

// ── Onglet 1 — Vue d'ensemble ─────────────────────────────────────────────────

function OngletOverview() {
  const [recherche, setRecherche] = useState("");

  const { data, isLoading } = useQuery({
    queryKey: ["medicaments-stock", recherche],
    queryFn: () => api.medicaments.liste({ search: recherche, page_size: 100 }),
  });

  const medicaments: Medicament[] = data?.results ?? [];

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center gap-3">
        <Input
          placeholder="Rechercher un médicament…"
          value={recherche}
          onChange={(e) => setRecherche(e.target.value)}
          className="max-w-sm"
        />
        {isLoading && <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />}
      </div>

      <div className="card-elevated overflow-hidden">
        <table className="w-full text-sm">
          <thead className="border-b border-border/70 bg-surface-strong/50">
            <tr>
              <th className="text-left px-4 py-3 font-medium text-muted-foreground">Médicament</th>
              <th className="text-left px-4 py-3 font-medium text-muted-foreground">Forme / Dosage</th>
              <th className="text-right px-4 py-3 font-medium text-muted-foreground">Prix public</th>
              <th className="text-right px-4 py-3 font-medium text-muted-foreground">Stock total</th>
              <th className="text-center px-4 py-3 font-medium text-muted-foreground">État</th>
            </tr>
          </thead>
          <tbody>
            {medicaments.length === 0 && !isLoading && (
              <tr>
                <td colSpan={5} className="px-4 py-10 text-center text-muted-foreground text-sm">
                  Aucun médicament trouvé.
                </td>
              </tr>
            )}
            {medicaments.map((m, i) => {
              const stock = m.stock_total_disponible ?? m.stock_total ?? 0;
              const enAlerte = m.est_en_alerte_stock;
              return (
                <tr
                  key={m.id}
                  className={cn(
                    "border-b border-border/40 hover:bg-surface-strong/30",
                    i % 2 === 0 ? "" : "bg-surface/30",
                  )}
                >
                  <td className="px-4 py-3">
                    <p className="font-medium">{m.nom}</p>
                    {m.denomination_commune_internationale && (
                      <p className="text-xs text-muted-foreground">{m.denomination_commune_internationale}</p>
                    )}
                  </td>
                  <td className="px-4 py-3 text-muted-foreground">
                    {[m.forme_pharmaceutique ?? m.forme, m.dosage].filter(Boolean).join(" · ")}
                  </td>
                  <td className="px-4 py-3 text-right numeric">
                    {fmtFCFA(m.prix_public ?? m.prix_vente)}
                  </td>
                  <td className={cn("px-4 py-3 text-right numeric font-medium", enAlerte ? "text-warning" : stock === 0 ? "text-destructive" : "")}>
                    {stock}
                  </td>
                  <td className="px-4 py-3 text-center">
                    {stock === 0 ? (
                      <span className="inline-flex items-center rounded-full bg-destructive/15 px-2 py-0.5 text-xs font-medium text-destructive">
                        Rupture
                      </span>
                    ) : enAlerte ? (
                      <span className="inline-flex items-center rounded-full bg-warning/15 px-2 py-0.5 text-xs font-medium text-warning">
                        Alerte
                      </span>
                    ) : (
                      <span className="inline-flex items-center rounded-full bg-success/15 px-2 py-0.5 text-xs font-medium text-success">
                        OK
                      </span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ── Onglet 2 — Lots ───────────────────────────────────────────────────────────

function OngletLots() {
  const [filtrePeremption, setFiltrePeremption] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ["lots-detail", { peremption_proche: filtrePeremption }],
    queryFn: () => api.lots.liste({
      peremption_proche: filtrePeremption,
      est_actif: true,
      page_size: 100,
    }),
  });

  const lots: LotDetail[] = data?.results ?? [];

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center gap-3">
        <button
          onClick={() => setFiltrePeremption(!filtrePeremption)}
          className={cn(
            "flex items-center gap-2 rounded-md border px-3 py-1.5 text-sm transition-colors",
            filtrePeremption
              ? "border-warning bg-warning/10 text-warning"
              : "border-border text-muted-foreground hover:border-warning/50",
          )}
        >
          <Filter className="h-3.5 w-3.5" />
          {filtrePeremption ? "Péremption proche activée" : "Filtrer : péremption proche"}
        </button>
        {isLoading && <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />}
      </div>

      <div className="card-elevated overflow-hidden">
        <table className="w-full text-sm">
          <thead className="border-b border-border/70 bg-surface-strong/50">
            <tr>
              <th className="text-left px-4 py-3 font-medium text-muted-foreground">Médicament</th>
              <th className="text-left px-4 py-3 font-medium text-muted-foreground">N° lot</th>
              <th className="text-right px-4 py-3 font-medium text-muted-foreground">Qté dispo</th>
              <th className="text-right px-4 py-3 font-medium text-muted-foreground">PA unitaire</th>
              <th className="text-right px-4 py-3 font-medium text-muted-foreground">Péremption</th>
              <th className="text-center px-4 py-3 font-medium text-muted-foreground">État</th>
            </tr>
          </thead>
          <tbody>
            {lots.length === 0 && !isLoading && (
              <tr>
                <td colSpan={6} className="px-4 py-10 text-center text-muted-foreground text-sm">
                  Aucun lot correspondant.
                </td>
              </tr>
            )}
            {lots.map((l, i) => {
              const joursRestants = Math.ceil(
                (new Date(l.date_peremption).getTime() - Date.now()) / 86_400_000
              );
              const perimant = joursRestants <= 30;
              const tresUrgent = joursRestants <= 15;
              return (
                <tr
                  key={l.id}
                  className={cn(
                    "border-b border-border/40 hover:bg-surface-strong/30",
                    i % 2 === 0 ? "" : "bg-surface/30",
                  )}
                >
                  <td className="px-4 py-3 font-medium">{l.medicament_nom}</td>
                  <td className="px-4 py-3 font-mono text-xs">{l.numero_lot}</td>
                  <td className="px-4 py-3 text-right numeric">{l.quantite_disponible}</td>
                  <td className="px-4 py-3 text-right numeric text-muted-foreground">
                    {l.prix_achat_unitaire ? fmtFCFA(l.prix_achat_unitaire) : "—"}
                  </td>
                  <td className={cn(
                    "px-4 py-3 text-right",
                    tresUrgent ? "text-destructive font-medium" : perimant ? "text-warning font-medium" : "",
                  )}>
                    {fmtDateCourte(l.date_peremption)}
                    {perimant && <span className="ml-1 text-xs">({joursRestants} j)</span>}
                  </td>
                  <td className="px-4 py-3 text-center">
                    {l.est_perime ? (
                      <span className="inline-flex rounded-full bg-destructive/15 px-2 py-0.5 text-xs font-medium text-destructive">Périmé</span>
                    ) : tresUrgent ? (
                      <span className="inline-flex rounded-full bg-destructive/10 px-2 py-0.5 text-xs font-medium text-destructive">Urgent</span>
                    ) : perimant ? (
                      <span className="inline-flex rounded-full bg-warning/10 px-2 py-0.5 text-xs font-medium text-warning">Proche</span>
                    ) : (
                      <span className="inline-flex rounded-full bg-success/10 px-2 py-0.5 text-xs font-medium text-success">OK</span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ── Onglet 3 — Mouvements ─────────────────────────────────────────────────────

const TYPES_MOUVEMENT = [
  { value: "",                label: "Tous les types" },
  { value: "reception",       label: "Réception" },
  { value: "vente",           label: "Vente" },
  { value: "retour_client",   label: "Retour client" },
  { value: "ajustement_plus", label: "Ajustement +" },
  { value: "ajustement_moins",label: "Ajustement −" },
  { value: "peremption",      label: "Péremption" },
  { value: "perte",           label: "Perte / vol" },
];

function OngletMouvements() {
  const [typeFiltreM, setTypeFiltreM] = useState("");

  const { data, isLoading, refetch } = useQuery({
    queryKey: ["mouvements-stock", typeFiltreM],
    queryFn: () => api.stocks.mouvements(typeFiltreM ? { type_mouvement: typeFiltreM, page_size: 100 } : { page_size: 100 }),
  });

  const mouvements: MouvementStock[] = data?.results ?? [];

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center gap-3">
        <select
          value={typeFiltreM}
          onChange={(e) => setTypeFiltreM(e.target.value)}
          className="rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary/40"
        >
          {TYPES_MOUVEMENT.map((t) => (
            <option key={t.value} value={t.value}>{t.label}</option>
          ))}
        </select>
        <Button variant="ghost" size="sm" onClick={() => void refetch()} disabled={isLoading}>
          {isLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
        </Button>
        {data && (
          <span className="text-xs text-muted-foreground">
            {data.count} mouvement(s)
          </span>
        )}
      </div>

      <div className="card-elevated overflow-hidden">
        <table className="w-full text-sm">
          <thead className="border-b border-border/70 bg-surface-strong/50">
            <tr>
              <th className="text-left px-4 py-3 font-medium text-muted-foreground">Date</th>
              <th className="text-left px-4 py-3 font-medium text-muted-foreground">Médicament</th>
              <th className="text-left px-4 py-3 font-medium text-muted-foreground">Lot</th>
              <th className="text-left px-4 py-3 font-medium text-muted-foreground">Type</th>
              <th className="text-right px-4 py-3 font-medium text-muted-foreground">Qté</th>
              <th className="text-right px-4 py-3 font-medium text-muted-foreground">Après</th>
              <th className="text-left px-4 py-3 font-medium text-muted-foreground">Réf.</th>
            </tr>
          </thead>
          <tbody>
            {mouvements.length === 0 && !isLoading && (
              <tr>
                <td colSpan={7} className="px-4 py-10 text-center text-muted-foreground text-sm">
                  Aucun mouvement trouvé.
                </td>
              </tr>
            )}
            {mouvements.map((m, i) => (
              <tr
                key={m.id}
                className={cn("border-b border-border/40 hover:bg-surface-strong/30", i % 2 === 0 ? "" : "bg-surface/30")}
              >
                <td className="px-4 py-3 text-muted-foreground whitespace-nowrap">{fmtDateCourte(m.cree_le)}</td>
                <td className="px-4 py-3 font-medium">{m.medicament_nom}</td>
                <td className="px-4 py-3 font-mono text-xs text-muted-foreground">{m.lot_nom}</td>
                <td className="px-4 py-3">
                  <span className={cn(
                    "inline-flex rounded-full px-2 py-0.5 text-xs font-medium",
                    m.quantite > 0 ? "bg-success/10 text-success" : "bg-destructive/10 text-destructive",
                  )}>
                    {m.type_mouvement_libelle}
                  </span>
                </td>
                <td className={cn("px-4 py-3 text-right numeric font-medium", m.quantite > 0 ? "text-success" : "text-destructive")}>
                  {m.quantite > 0 ? "+" : ""}{m.quantite}
                </td>
                <td className="px-4 py-3 text-right numeric text-muted-foreground">{m.quantite_apres}</td>
                <td className="px-4 py-3 text-xs text-muted-foreground font-mono">{m.reference_document || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ── Onglet 4 — Alertes ────────────────────────────────────────────────────────

function OngletAlertes() {
  const qc = useQueryClient();
  const [afficherResolues, setAfficherResolues] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ["alertes-stock-detail", afficherResolues],
    queryFn: () => api.alertes.liste(afficherResolues ? {} : { est_resolue: false }),
  });

  const resoudre = useMutation({
    mutationFn: (id: string) => api.alertes.resoudre(id),
    onSuccess: () => {
      toast.success("Alerte résolue.");
      void qc.invalidateQueries({ queryKey: ["alertes-stock-detail"] });
      void qc.invalidateQueries({ queryKey: ["tableau-bord"] });
    },
    onError: (e) => toast.error("Erreur", { description: String(e) }),
  });

  const alertes: AlerteStock[] = data?.results ?? [];

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center gap-3">
        <label className="flex items-center gap-2 text-sm text-muted-foreground cursor-pointer select-none">
          <input
            type="checkbox"
            checked={afficherResolues}
            onChange={(e) => setAfficherResolues(e.target.checked)}
            className="rounded border-border"
          />
          Afficher les alertes résolues
        </label>
        {isLoading && <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />}
      </div>

      {alertes.length === 0 && !isLoading ? (
        <div className="card-elevated p-10 text-center text-sm text-muted-foreground">
          <CheckCircle2 className="h-10 w-10 mx-auto mb-3 text-success" />
          {afficherResolues ? "Aucune alerte enregistrée." : "Aucune alerte active en ce moment."}
        </div>
      ) : (
        <div className="card-elevated overflow-hidden">
          <table className="w-full text-sm">
            <thead className="border-b border-border/70 bg-surface-strong/50">
              <tr>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">Médicament</th>
                <th className="text-center px-4 py-3 font-medium text-muted-foreground">Niveau</th>
                <th className="text-right px-4 py-3 font-medium text-muted-foreground">Stock signalé</th>
                <th className="text-right px-4 py-3 font-medium text-muted-foreground">Seuil</th>
                <th className="text-right px-4 py-3 font-medium text-muted-foreground">Détectée le</th>
                <th className="text-center px-4 py-3 font-medium text-muted-foreground">Statut</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody>
              {alertes.map((a, i) => (
                <tr key={a.id} className={cn("border-b border-border/40 hover:bg-surface-strong/30", i % 2 === 0 ? "" : "bg-surface/30")}>
                  <td className="px-4 py-3 font-medium">{a.medicament_nom}</td>
                  <td className="px-4 py-3 text-center">
                    <span className={cn(
                      "inline-flex rounded-full px-2 py-0.5 text-xs font-medium",
                      a.niveau === "rupture"
                        ? "bg-destructive/15 text-destructive"
                        : "bg-warning/15 text-warning",
                    )}>
                      {a.niveau === "rupture" ? "Rupture" : "Alerte"}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right numeric">{a.stock_au_moment_alerte}</td>
                  <td className="px-4 py-3 text-right numeric text-muted-foreground">{a.seuil_depasse}</td>
                  <td className="px-4 py-3 text-right text-muted-foreground">{fmtDateCourte(a.cree_le)}</td>
                  <td className="px-4 py-3 text-center">
                    {a.est_resolue ? (
                      <span className="inline-flex items-center gap-1 rounded-full bg-success/10 px-2 py-0.5 text-xs font-medium text-success">
                        <CheckCircle2 className="h-3 w-3" /> Résolue
                      </span>
                    ) : (
                      <span className="inline-flex rounded-full bg-destructive/10 px-2 py-0.5 text-xs font-medium text-destructive">
                        Active
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-right">
                    {!a.est_resolue && (
                      <Button
                        size="sm" variant="ghost"
                        onClick={() => resoudre.mutate(a.id)}
                        disabled={resoudre.isPending}
                        title="Marquer comme résolue"
                      >
                        <CheckCircle2 className="h-4 w-4" />
                      </Button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ── Dialog ajustement de stock ────────────────────────────────────────────────

const MOTIFS_AJUSTEMENT = [
  { value: "inventaire",  label: "Écart d'inventaire" },
  { value: "casse",       label: "Casse / détérioration" },
  { value: "peremption",  label: "Mise au rebut (périmé)" },
  { value: "vol",         label: "Vol / perte" },
  { value: "erreur",      label: "Erreur de saisie" },
  { value: "retour",      label: "Retour fournisseur" },
];

function DialogAjusterStock({ ouvert, onFermer }: { ouvert: boolean; onFermer: () => void }) {
  const qc = useQueryClient();
  const [lotId, setLotId]         = useState("");
  const [quantite, setQuantite]   = useState("");
  const [motif, setMotif]         = useState("inventaire");
  const [notes, setNotes]         = useState("");
  const [erreur, setErreur]       = useState<string | null>(null);

  const reset = () => {
    setLotId(""); setQuantite(""); setMotif("inventaire"); setNotes(""); setErreur(null);
  };

  const fermer = () => { reset(); onFermer(); };

  const ajuster = useMutation({
    mutationFn: () => {
      if (!lotId.trim()) throw new Error("L'identifiant du lot est obligatoire.");
      const q = parseInt(quantite, 10);
      if (isNaN(q) || q < 0) throw new Error("La quantité doit être un entier positif ou nul.");
      return api.stocks.ajuster({ lot_id: lotId.trim(), nouvelle_quantite: q, motif: `${motif}: ${notes}`.trim() });
    },
    onSuccess: () => {
      toast.success("Stock ajusté avec succès.");
      void qc.invalidateQueries({ queryKey: ["lots-detail"] });
      void qc.invalidateQueries({ queryKey: ["medicaments-stock"] });
      void qc.invalidateQueries({ queryKey: ["tableau-bord"] });
      fermer();
    },
    onError: (e) => {
      const msg = e instanceof Error ? e.message : String(e);
      setErreur(msg);
    },
  });

  return (
    <Dialog open={ouvert} onOpenChange={(open) => !open && fermer()}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Ajuster un stock de lot</DialogTitle>
        </DialogHeader>

        <div className="space-y-4 py-2">
          <div>
            <Label>Identifiant du lot (UUID)</Label>
            <Input
              className="mt-2 font-mono text-sm"
              placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
              value={lotId}
              onChange={(e) => setLotId(e.target.value)}
            />
            <p className="text-xs text-muted-foreground mt-1">
              Visible dans l'onglet "Lots" de cette page.
            </p>
          </div>

          <div>
            <Label>Nouvelle quantité (après ajustement)</Label>
            <Input
              type="number" min={0} className="numeric mt-2"
              placeholder="0"
              value={quantite}
              onChange={(e) => setQuantite(e.target.value)}
            />
          </div>

          <div>
            <Label>Motif</Label>
            <select
              value={motif}
              onChange={(e) => setMotif(e.target.value)}
              className="mt-2 w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary/40"
            >
              {MOTIFS_AJUSTEMENT.map((m) => (
                <option key={m.value} value={m.value}>{m.label}</option>
              ))}
            </select>
          </div>

          <div>
            <Label>Notes / justification</Label>
            <Input
              className="mt-2"
              placeholder="Détails complémentaires…"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
            />
          </div>

          {erreur && (
            <div role="alert" className="rounded-lg border border-destructive/40 bg-destructive/10 px-4 py-3 text-sm text-destructive">
              {erreur}
            </div>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={fermer}>Annuler</Button>
          <Button onClick={() => ajuster.mutate()} disabled={ajuster.isPending}>
            {ajuster.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckCircle2 className="h-4 w-4" />}
            Valider l'ajustement
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ── Bouton démarrer inventaire ────────────────────────────────────────────────

function BoutonDemarrerInventaire() {
  const qc = useQueryClient();
  const demarrer = useMutation({
    mutationFn: () => api.stocks.demarrerInventaire(),
    onSuccess: () => {
      toast.success("Inventaire démarré. Rendez-vous dans vos inventaires pour le compléter.");
      void qc.invalidateQueries({ queryKey: ["stocks-inventaires"] });
    },
    onError: (e) => toast.error("Impossible de démarrer l'inventaire", { description: String(e) }),
  });

  return (
    <Button
      variant="secondary"
      onClick={() => demarrer.mutate()}
      disabled={demarrer.isPending}
    >
      {demarrer.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <ClipboardList className="h-4 w-4" />}
      Démarrer inventaire
    </Button>
  );
}
