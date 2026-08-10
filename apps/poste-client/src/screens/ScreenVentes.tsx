/**
 * ScreenVentes — Historique des ventes + création d'avoir (§4.4.3 CDC).
 *
 * Extrait de _app.ventes.tsx lors du découpage modulaire (v2).
 * La route conserve uniquement la définition TanStack Router.
 *
 * Fonctionnalités :
 *   - Liste paginée avec filtres (date, statut, mode paiement)
 *   - Badge statut (validée, annulée, avoir)
 *   - Dialog "Créer un avoir" : sélection des lignes à retourner, motif
 */

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  RotateCcw, Loader2, Search, X, ChevronDown, ChevronUp,
  FileText, AlertTriangle,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle,
  DialogFooter, DialogDescription,
} from "@/components/ui/dialog";
import { toast } from "sonner";

import { api, ApiError } from "@/lib/api-client";
import { fmtFCFA } from "@/lib/format";
import type { Vente } from "@/lib/types";

const STATUT_BADGE: Record<string, { label: string; cls: string }> = {
  validee:  { label: "Validée",  cls: "bg-success/10 text-success border-success/30" },
  annulee:  { label: "Annulée",  cls: "bg-destructive/10 text-destructive border-destructive/30" },
  avoir:    { label: "Avoir",    cls: "bg-amber-100 text-amber-800 border-amber-200" },
  en_cours: { label: "En cours", cls: "bg-muted text-muted-foreground" },
};

// ── Dialog Avoir ─────────────────────────────────────────────────────────────

function DialogAvoir({ vente, onFermer, onSuccess }: {
  vente: Vente; onFermer: () => void; onSuccess: () => void;
}) {
  const [motif, setMotif] = useState("");
  const [selections, setSelections] = useState<Record<string, number>>({});
  const lignes = vente.lignes ?? [];

  function setQte(ligneId: string, qte: number) {
    setSelections((prev) => ({ ...prev, [ligneId]: qte }));
  }

  const lignesRetour = Object.entries(selections)
    .filter(([, q]) => q > 0)
    .map(([ligne_id, quantite]) => ({ ligne_id, quantite }));

  const totalAvoir = lignes.reduce((acc, l) => {
    const qte = selections[l.id ?? ""] ?? 0;
    return acc + qte * Number(l.prix_unitaire_apres_remise ?? l.prix_unitaire ?? 0);
  }, 0);

  const queryClient = useQueryClient();
  const mutation = useMutation({
    mutationFn: () => api.ventes.avoir(vente.id, { lignes: lignesRetour, motif }),
    onSuccess: (data) => {
      toast.success("Avoir créé", { description: `${data.total_avoir} FCFA remboursés.` });
      queryClient.invalidateQueries({ queryKey: ["ventes"] });
      onSuccess();
    },
    onError: (err) => {
      toast.error(err instanceof ApiError ? err.detail : "Erreur lors de la création de l'avoir.");
    },
  });

  const peutValider = motif.trim().length >= 5 && lignesRetour.length > 0 && !mutation.isPending;

  return (
    <Dialog open onOpenChange={(v) => !v && onFermer()}>
      <DialogContent className="max-w-2xl max-w-[calc(100%-2rem)] md:max-w-2xl">
        <DialogHeader>
          <DialogTitle className="font-display text-xl">Créer un avoir — Vente {vente.numero}</DialogTitle>
          <DialogDescription>
            Sélectionnez les articles à retourner et indiquez un motif.
            Un avoir remet le stock en place et génère une note de crédit.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-5 py-2">
          <div className="rounded-xl border overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-muted/30 text-muted-foreground text-xs uppercase tracking-wide">
                  <th className="px-4 py-2 text-left">Article</th>
                  <th className="px-4 py-2 text-right">Qté vendue</th>
                  <th className="px-4 py-2 text-right">Prix unit.</th>
                  <th className="px-4 py-2 text-right w-32">Qté à retourner</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {lignes.map((l) => {
                  const ligneId = l.id ?? "";
                  const maxQte  = l.quantite;
                  const qte     = selections[ligneId] ?? 0;
                  const montantLigne = qte * Number(l.prix_unitaire_apres_remise ?? l.prix_unitaire ?? 0);
                  return (
                    <tr key={ligneId} className="hover:bg-muted/10">
                      <td className="px-4 py-3 font-medium">{l.medicament_nom ?? l.medicament}</td>
                      <td className="px-4 py-3 text-right tabular-nums">{l.quantite}</td>
                      <td className="px-4 py-3 text-right tabular-nums text-muted-foreground">
                        {fmtFCFA(Number(l.prix_unitaire_apres_remise ?? l.prix_unitaire ?? 0))}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center justify-end gap-1">
                          <button type="button" onClick={() => setQte(ligneId, Math.max(0, qte - 1))} className="h-7 w-7 flex items-center justify-center rounded border hover:bg-surface-strong">
                            <ChevronDown className="h-3.5 w-3.5" />
                          </button>
                          <Input type="number" min={0} max={maxQte} value={qte} onChange={(e) => setQte(ligneId, Math.min(maxQte, Math.max(0, Number(e.target.value))))} className="w-14 text-center h-7 text-sm" />
                          <button type="button" onClick={() => setQte(ligneId, Math.min(maxQte, qte + 1))} className="h-7 w-7 flex items-center justify-center rounded border hover:bg-surface-strong">
                            <ChevronUp className="h-3.5 w-3.5" />
                          </button>
                        </div>
                        {qte > 0 && <p className="text-right text-xs text-muted-foreground mt-0.5 tabular-nums">{fmtFCFA(montantLigne)}</p>}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {totalAvoir > 0 && (
            <div className="flex items-baseline justify-between rounded-lg bg-amber-50 border border-amber-200 px-4 py-3">
              <span className="text-sm font-medium text-amber-900">Total de l'avoir</span>
              <span className="numeric font-display text-xl text-amber-900">{fmtFCFA(totalAvoir)}</span>
            </div>
          )}

          <div>
            <Label className="text-xs uppercase tracking-wide text-muted-foreground">
              Motif du retour <span className="text-destructive">*</span>
            </Label>
            <Input className="mt-2" placeholder="Ex : Produit endommagé, erreur de délivrance, périmé…" value={motif} onChange={(e) => setMotif(e.target.value)} />
            {motif.trim().length > 0 && motif.trim().length < 5 && (
              <p className="text-xs text-destructive mt-1">Le motif doit contenir au moins 5 caractères.</p>
            )}
          </div>

          {lignesRetour.length === 0 && (
            <div className="flex items-start gap-2 rounded-lg bg-muted/30 p-3 text-sm text-muted-foreground">
              <AlertTriangle className="h-4 w-4 mt-0.5 shrink-0" />
              <span>Sélectionnez au moins un article à retourner.</span>
            </div>
          )}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onFermer} disabled={mutation.isPending}>Annuler</Button>
          <Button onClick={() => mutation.mutate()} disabled={!peutValider} className="gap-2">
            {mutation.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
            <RotateCcw className="h-4 w-4" />
            Créer l'avoir
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ── Composant principal exporté ──────────────────────────────────────────────

export function ScreenVentes() {
  const [recherche, setRecherche]       = useState("");
  const [filtreStatut, setFiltreStatut] = useState("");
  const [filtreDebut, setFiltreDebut]   = useState("");
  const [filtreFin, setFiltreFin]       = useState("");
  const [venteAvoir, setVenteAvoir]     = useState<Vente | null>(null);
  const [expanded, setExpanded]         = useState<string | null>(null);

  const params: Record<string, string> = {};
  if (filtreStatut) params.statut = filtreStatut;
  if (filtreDebut)  params.debut  = filtreDebut;
  if (filtreFin)    params.fin    = filtreFin;

  const { data, isLoading, isError } = useQuery({
    queryKey: ["ventes", params],
    queryFn: () => api.ventes.liste(params),
  });

  const ventes: Vente[] = data?.results ?? [];
  const ventesFiltrees  = recherche.trim()
    ? ventes.filter((v) =>
        v.numero.toLowerCase().includes(recherche.toLowerCase()) ||
        (v.client_nom ?? "").toLowerCase().includes(recherche.toLowerCase())
      )
    : ventes;

  return (
    <div className="flex flex-col gap-6 p-6 max-w-screen-xl mx-auto">
      <div>
        <h1 className="font-display text-2xl">Historique des ventes</h1>
        <p className="text-sm text-muted-foreground mt-1">Retrouvez toutes les ventes, annulations et avoirs.</p>
      </div>
      <Separator />

      {/* Filtres */}
      <div className="flex flex-wrap gap-3 items-end">
        <div className="flex-1 min-w-[180px]">
          <Label className="text-xs text-muted-foreground uppercase tracking-wide">Recherche</Label>
          <div className="relative mt-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input placeholder="N° vente, client…" value={recherche} onChange={(e) => setRecherche(e.target.value)} className="pl-9" />
          </div>
        </div>
        <div>
          <Label className="text-xs text-muted-foreground uppercase tracking-wide">Statut</Label>
          <select value={filtreStatut} onChange={(e) => setFiltreStatut(e.target.value)} className="mt-1 h-10 rounded-md border border-input bg-background px-3 text-sm">
            <option value="">Tous</option>
            <option value="validee">Validées</option>
            <option value="annulee">Annulées</option>
            <option value="avoir">Avoirs</option>
          </select>
        </div>
        <div>
          <Label className="text-xs text-muted-foreground uppercase tracking-wide">Du</Label>
          <Input type="date" value={filtreDebut} onChange={(e) => setFiltreDebut(e.target.value)} className="mt-1" />
        </div>
        <div>
          <Label className="text-xs text-muted-foreground uppercase tracking-wide">Au</Label>
          <Input type="date" value={filtreFin} onChange={(e) => setFiltreFin(e.target.value)} className="mt-1" />
        </div>
        {(filtreStatut || filtreDebut || filtreFin) && (
          <Button variant="outline" size="sm" onClick={() => { setFiltreStatut(""); setFiltreDebut(""); setFiltreFin(""); }} className="gap-1">
            <X className="h-3.5 w-3.5" /> Effacer
          </Button>
        )}
      </div>

      {isLoading && (
        <div className="flex items-center justify-center py-16 gap-2 text-muted-foreground">
          <Loader2 className="h-5 w-5 animate-spin" /> Chargement des ventes…
        </div>
      )}
      {isError && (
        <div className="rounded-xl border border-destructive/30 bg-destructive/10 p-6 text-center text-destructive">
          Impossible de charger les ventes.
        </div>
      )}
      {!isLoading && !isError && ventesFiltrees.length === 0 && (
        <div className="rounded-xl border bg-card p-12 text-center">
          <FileText className="h-10 w-10 text-muted-foreground mx-auto mb-3 opacity-40" />
          <p className="font-medium">Aucune vente trouvée</p>
        </div>
      )}
      {!isLoading && !isError && ventesFiltrees.length > 0 && (
        <div className="rounded-xl border overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-muted/20 text-muted-foreground text-xs uppercase tracking-wide">
                <th className="px-4 py-3 text-left">N° vente</th>
                <th className="px-4 py-3 text-left">Statut</th>
                <th className="px-4 py-3 text-left">Client</th>
                <th className="px-4 py-3 text-left">Mode</th>
                <th className="px-4 py-3 text-right">Montant</th>
                <th className="px-4 py-3 text-left">Date</th>
                <th className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {ventesFiltrees.map((v) => {
                const badge      = STATUT_BADGE[v.statut] ?? STATUT_BADGE.en_cours;
                const isExpanded = expanded === v.id;
                return (
                  <>
                    <tr key={v.id} className="hover:bg-muted/10 transition-colors cursor-pointer" onClick={() => setExpanded(isExpanded ? null : v.id)}>
                      <td className="px-4 py-3 font-mono text-xs">{v.numero}</td>
                      <td className="px-4 py-3">
                        <span className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium ${badge.cls}`}>{badge.label}</span>
                      </td>
                      <td className="px-4 py-3 text-muted-foreground">{v.client_nom ?? "—"}</td>
                      <td className="px-4 py-3 text-muted-foreground capitalize">{v.mode_paiement?.replace(/_/g, " ") ?? "—"}</td>
                      <td className="px-4 py-3 text-right tabular-nums font-medium">{fmtFCFA(Number(v.montant_total))}</td>
                      <td className="px-4 py-3 text-muted-foreground whitespace-nowrap">{new Date(v.cree_le).toLocaleDateString("fr-FR")}</td>
                      <td className="px-4 py-3 text-right">
                        {v.statut === "validee" && (
                          <Button size="sm" variant="outline" className="gap-1 text-xs" onClick={(e) => { e.stopPropagation(); setVenteAvoir(v); }}>
                            <RotateCcw className="h-3 w-3" /> Avoir
                          </Button>
                        )}
                      </td>
                    </tr>
                    {isExpanded && v.lignes && v.lignes.length > 0 && (
                      <tr key={`${v.id}-details`}>
                        <td colSpan={7} className="px-6 py-3 bg-muted/5">
                          <div className="rounded-lg border bg-card p-3">
                            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2">Détail des lignes</p>
                            <div className="space-y-1">
                              {v.lignes.map((l, i) => (
                                <div key={i} className="flex justify-between text-sm">
                                  <span>{l.medicament_nom ?? l.medicament}</span>
                                  <span className="tabular-nums text-muted-foreground">
                                    {l.quantite} × {fmtFCFA(Number(l.prix_unitaire))} =&nbsp;
                                    <strong>{fmtFCFA(Number(l.montant_total))}</strong>
                                  </span>
                                </div>
                              ))}
                            </div>
                          </div>
                        </td>
                      </tr>
                    )}
                  </>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {venteAvoir && (
        <DialogAvoir vente={venteAvoir} onFermer={() => setVenteAvoir(null)} onSuccess={() => setVenteAvoir(null)} />
      )}
    </div>
  );
}
