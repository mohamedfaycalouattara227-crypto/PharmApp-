/**
 * Achats — Étape 6 : Fournisseurs + Cycle Bons de Commande.
 *
 * Deux onglets principaux :
 *  1. Bons de commande — liste, détail, envoi, réception
 *  2. Fournisseurs — CRUD complet
 *
 * Dans l'onglet BC : bouton "Nouveau BC" est désormais actif et ouvre un dialog
 * de création avec sélection du fournisseur + lignes de commande.
 */

import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Truck, Plus, Package, CheckCircle2, Send, Loader2, Building2, Pencil, X, Trash2 } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from "@/components/ui/dialog";
import { api, ApiError } from "@/lib/api-client";
import { fmtFCFA, fmtDate, LIBELLES_STATUT_BC } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { BonCommande, Fournisseur, StatutBonCommande, Medicament } from "@/lib/types";

export const Route = createFileRoute("/_app/achats")({
  component: PageAchats,
  head: () => ({
    meta: [
      { title: "Achats — PharmApp" },
      { name: "description", content: "Bons de commande fournisseur et réceptions de stock." },
    ],
  }),
});

const COULEUR_STATUT: Record<StatutBonCommande, string> = {
  brouillon: "bg-muted text-muted-foreground",
  envoye:    "bg-info/20 text-info",
  partiel:   "bg-warning/20 text-warning",
  recu:      "bg-success/20 text-success",
  cloture:   "bg-primary/20 text-primary",
  annule:    "bg-destructive/20 text-destructive",
};

// ── Dialog création BC ───────────────────────────────────────────────────────

type LigneBC = {
  medicament_id: string;
  medicament_nom: string;
  quantite_commandee: number;
  prix_unitaire_ht: string;
};

function DialogCreerBC({
  fournisseurs,
  onCreer,
  onFermer,
}: {
  fournisseurs: Fournisseur[];
  onCreer: (payload: unknown) => Promise<void>;
  onFermer: () => void;
}) {
  const [fournisseurId, setFournisseurId] = useState("");
  const [dateLivraison, setDateLivraison] = useState("");
  const [notes, setNotes] = useState("");
  const [lignes, setLignes] = useState<LigneBC[]>([]);
  const [rechercheMed, setRechercheMed] = useState("");
  const [loading, setLoading] = useState(false);
  const [erreur, setErreur] = useState<string | null>(null);

  const [debouncedMed, setDebouncedMed] = useState("");
  const timerRef = useState<ReturnType<typeof setTimeout> | null>(null);

  const handleSearchMed = (v: string) => {
    setRechercheMed(v);
    if (timerRef[0]) clearTimeout(timerRef[0]);
    timerRef[1](setTimeout(() => setDebouncedMed(v.trim()), 250));
  };

  const { data: medsData } = useQuery({
    queryKey: ["med-search-bc", debouncedMed],
    queryFn: () => api.medicaments.rechercher(debouncedMed),
    enabled: debouncedMed.length >= 2,
    staleTime: 30_000,
  });

  const ajouterLigne = (m: Medicament) => {
    if (lignes.some((l) => l.medicament_id === m.id)) return;
    setLignes((cur) => [
      ...cur,
      { medicament_id: m.id, medicament_nom: m.nom, quantite_commandee: 1, prix_unitaire_ht: "0" },
    ]);
    setRechercheMed(""); setDebouncedMed("");
  };

  const mettreAJourLigne = (idx: number, champ: keyof LigneBC, val: string | number) => {
    setLignes((cur) => cur.map((l, i) => i === idx ? { ...l, [champ]: val } : l));
  };

  const supprimerLigne = (idx: number) => setLignes((cur) => cur.filter((_, i) => i !== idx));

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!fournisseurId) { setErreur("Sélectionnez un fournisseur."); return; }
    if (lignes.length === 0) { setErreur("Ajoutez au moins un médicament."); return; }
    setLoading(true); setErreur(null);
    try {
      await onCreer({
        fournisseur: fournisseurId,
        date_livraison_prevue: dateLivraison || null,
        notes,
        lignes: lignes.map((l) => ({
          medicament: l.medicament_id,
          quantite_commandee: Number(l.quantite_commandee),
          prix_unitaire_ht: l.prix_unitaire_ht || "0",
        })),
      });
      toast.success("Bon de commande créé.");
      onFermer();
    } catch (err) {
      setErreur(err instanceof ApiError ? err.detail : "Erreur lors de la création.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 overflow-y-auto">
      <div className="w-full max-w-2xl rounded-xl bg-background shadow-xl p-6 my-4">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-display">Nouveau bon de commande</h2>
          <button onClick={onFermer} className="h-8 w-8 flex items-center justify-center rounded-lg hover:bg-surface-strong">
            <X className="h-4 w-4" />
          </button>
        </div>
        {erreur && <div className="mb-4 rounded-lg bg-destructive/10 px-4 py-2 text-sm text-destructive">{erreur}</div>}
        <form onSubmit={handleSubmit} className="space-y-5">
          {/* Fournisseur */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label>Fournisseur *</Label>
              <select className="input mt-1" value={fournisseurId} onChange={(e) => setFournisseurId(e.target.value)} required>
                <option value="">— Sélectionner —</option>
                {fournisseurs.map((f) => (
                  <option key={f.id} value={f.id}>{f.nom}</option>
                ))}
              </select>
            </div>
            <div>
              <Label>Date de livraison prévue</Label>
              <Input type="date" className="mt-1" value={dateLivraison} onChange={(e) => setDateLivraison(e.target.value)} />
            </div>
            <div className="col-span-2">
              <Label>Notes</Label>
              <Input className="mt-1" value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Instructions spéciales…" />
            </div>
          </div>

          {/* Lignes de commande */}
          <div>
            <Label>Médicaments à commander</Label>
            <div className="relative mt-1">
              <Input
                value={rechercheMed}
                onChange={(e) => handleSearchMed(e.target.value)}
                placeholder="Rechercher un médicament à ajouter…"
                className="mb-2"
              />
              {medsData?.results && medsData.results.length > 0 && rechercheMed && (
                <div className="absolute z-10 w-full bg-background border border-border/70 rounded-lg shadow-xl max-h-48 overflow-y-auto">
                  {medsData.results.map((m) => (
                    <button
                      key={m.id}
                      type="button"
                      onClick={() => ajouterLigne(m)}
                      className="w-full text-left px-4 py-2.5 hover:bg-surface-strong text-sm border-b border-border/40 last:border-0"
                    >
                      <span className="font-medium">{m.nom}</span>
                      <span className="text-muted-foreground ml-2 text-xs">{m.dosage}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>

            {lignes.length > 0 && (
              <div className="space-y-2">
                <div className="grid grid-cols-[2fr_1fr_1fr_auto] gap-2 text-xs text-muted-foreground px-1">
                  <span>Médicament</span><span>Quantité</span><span>Prix HT (FCFA)</span><span></span>
                </div>
                {lignes.map((l, i) => (
                  <div key={i} className="grid grid-cols-[2fr_1fr_1fr_auto] gap-2 items-center">
                    <span className="text-sm truncate">{l.medicament_nom}</span>
                    <Input
                      type="number" min="1" value={l.quantite_commandee} className="h-8"
                      onChange={(e) => mettreAJourLigne(i, "quantite_commandee", Number(e.target.value))}
                    />
                    <Input
                      type="number" min="0" value={l.prix_unitaire_ht} className="h-8"
                      onChange={(e) => mettreAJourLigne(i, "prix_unitaire_ht", e.target.value)}
                    />
                    <button type="button" onClick={() => supprimerLigne(i)} className="h-8 w-8 flex items-center justify-center hover:bg-surface-strong rounded">
                      <Trash2 className="h-3.5 w-3.5 text-destructive" />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="flex justify-end gap-3">
            <button type="button" onClick={onFermer} className="btn btn-ghost">Annuler</button>
            <button type="submit" disabled={loading} className="btn btn-primary flex items-center gap-2">
              {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
              Créer le BC
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ── Dialog création/modification Fournisseur ─────────────────────────────────

type FournisseurForm = {
  code: string; nom: string; contact_principal: string; telephone: string;
  email: string; adresse: string; ville: string; pays: string;
  numero_agrement: string; delai_livraison_jours: string;
  conditions_paiement: string; actif: boolean; notes: string;
};

const FOURNISSEUR_VIDE: FournisseurForm = {
  code: "", nom: "", contact_principal: "", telephone: "", email: "",
  adresse: "", ville: "", pays: "BF", numero_agrement: "",
  delai_livraison_jours: "7", conditions_paiement: "", actif: true, notes: "",
};

function DialogFournisseur({
  initial,
  onSave,
  onFermer,
}: {
  initial?: Fournisseur | null;
  onSave: (d: Partial<FournisseurForm>) => Promise<void>;
  onFermer: () => void;
}) {
  const [form, setForm] = useState<FournisseurForm>(
    initial
      ? {
          code: initial.code ?? "", nom: initial.nom,
          contact_principal: initial.contact_principal ?? "", telephone: initial.telephone ?? "",
          email: initial.email ?? "", adresse: initial.adresse ?? "", ville: initial.ville ?? "",
          pays: initial.pays ?? "BF", numero_agrement: initial.numero_agrement ?? "",
          delai_livraison_jours: String(initial.delai_livraison_jours ?? 7),
          conditions_paiement: initial.conditions_paiement ?? "", actif: initial.actif ?? initial.est_actif,
          notes: initial.notes ?? "",
        }
      : FOURNISSEUR_VIDE
  );
  const [erreur, setErreur] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const champ = (k: keyof FournisseurForm) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
    setForm((f) => ({ ...f, [k]: e.target.value }));
  const bool = (k: keyof FournisseurForm) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((f) => ({ ...f, [k]: e.target.checked }));

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.nom.trim()) { setErreur("Le nom est obligatoire."); return; }
    setLoading(true); setErreur(null);
    try {
      await onSave({ ...form, delai_livraison_jours: String(form.delai_livraison_jours) });
      onFermer();
    } catch (err) {
      setErreur(err instanceof ApiError ? err.detail : "Erreur inattendue.");
    } finally { setLoading(false); }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 overflow-y-auto">
      <div className="w-full max-w-lg rounded-xl bg-background shadow-xl p-6 my-4">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-display">{initial ? "Modifier le fournisseur" : "Nouveau fournisseur"}</h2>
          <button onClick={onFermer} className="h-8 w-8 flex items-center justify-center rounded-lg hover:bg-surface-strong">
            <X className="h-4 w-4" />
          </button>
        </div>
        {erreur && <div className="mb-4 rounded-lg bg-destructive/10 px-4 py-2 text-sm text-destructive">{erreur}</div>}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div><Label>Code</Label><Input className="mt-1" value={form.code} onChange={champ("code")} placeholder="ex: CAMEG-01" /></div>
            <div><Label>Nom *</Label><Input className="mt-1" value={form.nom} onChange={champ("nom")} required /></div>
            <div><Label>Contact principal</Label><Input className="mt-1" value={form.contact_principal} onChange={champ("contact_principal")} /></div>
            <div><Label>Téléphone</Label><Input className="mt-1" type="tel" value={form.telephone} onChange={champ("telephone")} /></div>
            <div><Label>Email</Label><Input className="mt-1" type="email" value={form.email} onChange={champ("email")} /></div>
            <div><Label>Ville</Label><Input className="mt-1" value={form.ville} onChange={champ("ville")} /></div>
            <div><Label>N° Agrément</Label><Input className="mt-1" value={form.numero_agrement} onChange={champ("numero_agrement")} /></div>
            <div><Label>Délai livraison (jours)</Label><Input className="mt-1" type="number" min="1" value={form.delai_livraison_jours} onChange={champ("delai_livraison_jours")} /></div>
            <div className="col-span-2"><Label>Conditions de paiement</Label><Input className="mt-1" value={form.conditions_paiement} onChange={champ("conditions_paiement")} placeholder="ex: 30 jours fin de mois" /></div>
          </div>
          {initial && (
            <div className="flex items-center gap-3">
              <input type="checkbox" id="actif_f" checked={form.actif} onChange={bool("actif")} className="checkbox" />
              <label htmlFor="actif_f" className="text-sm">Fournisseur actif</label>
            </div>
          )}
          <div className="flex justify-end gap-3">
            <button type="button" onClick={onFermer} className="btn btn-ghost">Annuler</button>
            <button type="submit" disabled={loading} className="btn btn-primary">
              {loading ? "Enregistrement…" : "Enregistrer"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ── Détail BC + Dialog réception ─────────────────────────────────────────────

function DetailBonCommande({ bc, onReceptionner }: { bc: BonCommande; onReceptionner: () => void }) {
  const qc = useQueryClient();
  const envoyer = useMutation({
    mutationFn: () => api.bonsCommande.envoyer(bc.id),
    onSuccess: () => { toast.success("Bon de commande envoyé au fournisseur."); qc.invalidateQueries({ queryKey: ["bons-commande"] }); },
    onError: (e) => toast.error("Envoi impossible", { description: String(e) }),
  });

  const annuler = useMutation({
    mutationFn: () => api.bonsCommande.annuler(bc.id, "Annulé depuis l'interface"),
    onSuccess: () => { toast.success("Bon de commande annulé."); qc.invalidateQueries({ queryKey: ["bons-commande"] }); },
  });

  const receptionnable = bc.statut === "envoye" || bc.statut === "partiel";

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="text-xs text-muted-foreground uppercase tracking-wide">Bon de commande</div>
          <h2 className="font-display text-3xl numeric">{bc.numero}</h2>
          <div className="text-sm text-muted-foreground mt-1">
            {bc.fournisseur_nom} · {fmtDate(bc.date_commande)}
          </div>
        </div>
        <Badge className={cn("text-sm", COULEUR_STATUT[bc.statut])}>{LIBELLES_STATUT_BC[bc.statut]}</Badge>
      </div>

      <div className="flex gap-2">
        {bc.statut === "brouillon" && (
          <Button onClick={() => envoyer.mutate()} disabled={envoyer.isPending} size="sm">
            {envoyer.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
            Envoyer au fournisseur
          </Button>
        )}
        {receptionnable && (
          <Button variant="secondary" onClick={onReceptionner} size="sm">
            <Package className="h-4 w-4" /> Réceptionner
          </Button>
        )}
        {(bc.statut === "brouillon" || bc.statut === "envoye") && (
          <Button variant="ghost" size="sm" onClick={() => { if (confirm("Annuler ce BC ?")) annuler.mutate(); }} className="text-destructive hover:text-destructive">
            Annuler le BC
          </Button>
        )}
      </div>

      <Separator />

      {/* Lignes */}
      <div className="space-y-2">
        <h3 className="text-sm font-medium text-muted-foreground uppercase tracking-wide">Lignes de commande</h3>
        {bc.lignes?.length ? (
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="border-b border-border/70 text-muted-foreground text-left">
                <th className="pb-2 pr-4 font-medium">Médicament</th>
                <th className="pb-2 pr-4 font-medium text-right">Commandé</th>
                <th className="pb-2 pr-4 font-medium text-right">Reçu</th>
                <th className="pb-2 font-medium text-right">PU HT</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/40">
              {bc.lignes.map((l) => (
                <tr key={l.id}>
                  <td className="py-2 pr-4">{l.medicament_nom ?? l.medicament}</td>
                  <td className="py-2 pr-4 text-right numeric">{l.quantite_commandee}</td>
                  <td className="py-2 pr-4 text-right numeric text-success">{l.quantite_recue ?? 0}</td>
                  <td className="py-2 text-right numeric">{fmtFCFA(l.prix_unitaire_ht ?? l.prix_unitaire ?? 0)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className="text-sm text-muted-foreground">Aucune ligne.</div>
        )}
      </div>

      <Separator />

      <div className="space-y-1 text-sm">
        <div className="flex justify-between">
          <span className="text-muted-foreground">Total HT</span>
          <span className="numeric">{fmtFCFA(bc.total_ht ?? 0)}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-muted-foreground">TVA</span>
          <span className="numeric">{fmtFCFA(bc.total_tva ?? 0)}</span>
        </div>
        <div className="flex justify-between font-semibold text-base">
          <span>Total TTC</span>
          <span className="numeric">{fmtFCFA(bc.total_ttc ?? bc.montant_total)}</span>
        </div>
      </div>
    </div>
  );
}

function DialogReception({
  bc, ouvert, onFermer,
}: { bc: BonCommande; ouvert: boolean; onFermer: () => void }) {
  const qc = useQueryClient();
  const [quantites, setQuantites] = useState<Record<string, number>>(
    Object.fromEntries((bc.lignes ?? []).map((l) => [l.id as string, l.quantite_restante ?? (l.quantite_commandee ?? l.quantite) - (l.quantite_recue ?? 0)]))
  );

  const receptionner = useMutation({
    mutationFn: () =>
      api.bonsCommande.receptionner(bc.id, {
        lignes: Object.entries(quantites)
          .filter(([, q]) => q > 0)
          .map(([ligne_id, quantite_recue]) => ({ ligne_id, quantite_recue })),
      }),
    onSuccess: () => {
      toast.success("Réception enregistrée.", { description: "Le stock a été mis à jour." });
      qc.invalidateQueries({ queryKey: ["bons-commande"] });
      onFermer();
    },
    onError: (e) => toast.error("Erreur de réception", { description: String(e) }),
  });

  return (
    <Dialog open={ouvert} onOpenChange={(v) => !v && onFermer()}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Réceptionner — {bc.numero}</DialogTitle>
        </DialogHeader>
        <div className="space-y-3 py-2 max-h-[50vh] overflow-y-auto">
          {(bc.lignes ?? []).map((l) => (
            <div key={l.id} className="flex items-center gap-4">
              <span className="flex-1 text-sm truncate">{l.medicament_nom}</span>
              <div className="flex items-center gap-2 shrink-0">
                <span className="text-xs text-muted-foreground numeric">/ {l.quantite_commandee ?? l.quantite}</span>
                <Input
                  type="number"
                  min="0"
                  max={l.quantite_commandee ?? l.quantite}
                  value={quantites[l.id as string] ?? 0}
                  onChange={(e) =>
                    setQuantites((cur) => ({ ...cur, [l.id as string]: Number(e.target.value) }))
                  }
                  className="w-20 h-8 text-right numeric"
                />
              </div>
            </div>
          ))}
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={onFermer}>Annuler</Button>
          <Button onClick={() => receptionner.mutate()} disabled={receptionner.isPending}>
            {receptionner.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckCircle2 className="h-4 w-4" />}
            Valider la réception
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ── Onglet Fournisseurs ──────────────────────────────────────────────────────

function OngletFournisseurs() {
  const qc = useQueryClient();
  const [dialog, setDialog] = useState<{ open: boolean; item?: Fournisseur | null }>({ open: false });

  const { data, isLoading } = useQuery({
    queryKey: ["fournisseurs"],
    queryFn: () => api.fournisseurs.liste(),
    staleTime: 60_000,
  });
  const fournisseurs = data?.results ?? [];

  const creer = useMutation({
    mutationFn: (d: unknown) => api.fournisseurs.creer(d),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["fournisseurs"] }); setDialog({ open: false }); toast.success("Fournisseur créé."); },
    onError: (e: ApiError) => toast.error("Erreur", { description: e.detail }),
  });
  const modifier = useMutation({
    mutationFn: ({ id, d }: { id: string; d: unknown }) => api.fournisseurs.modifier(id, d),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["fournisseurs"] }); setDialog({ open: false }); toast.success("Fournisseur mis à jour."); },
    onError: (e: ApiError) => toast.error("Erreur", { description: e.detail }),
  });

  return (
    <div className="flex-1 overflow-auto px-6 py-4">
      <div className="flex justify-end mb-4">
        <Button onClick={() => setDialog({ open: true, item: null })} className="flex items-center gap-2">
          <Plus className="h-4 w-4" /> Nouveau fournisseur
        </Button>
      </div>

      {isLoading ? (
        <div className="flex justify-center py-12 text-muted-foreground">
          <Loader2 className="h-6 w-6 animate-spin" />
        </div>
      ) : fournisseurs.length === 0 ? (
        <div className="text-center py-16 text-muted-foreground">
          <Building2 className="h-12 w-12 mx-auto mb-3" />
          <p>Aucun fournisseur enregistré.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {fournisseurs.map((f) => (
            <div
              key={f.id}
              className={`rounded-xl border ${f.actif ? "border-border/70 bg-surface/40" : "border-border/40 bg-surface/20 opacity-60"} p-5`}
            >
              <div className="flex items-start justify-between">
                <div>
                  <div className="font-semibold text-base">{f.nom}</div>
                  {f.code && <div className="text-xs text-muted-foreground">{f.code}</div>}
                </div>
                <button
                  onClick={() => setDialog({ open: true, item: f })}
                  className="h-8 w-8 flex items-center justify-center rounded-lg hover:bg-surface-strong"
                >
                  <Pencil className="h-3.5 w-3.5 text-muted-foreground" />
                </button>
              </div>
              <div className="mt-3 space-y-1 text-sm text-muted-foreground">
                {f.contact_principal && <div>{f.contact_principal}</div>}
                {f.telephone && <div>📞 {f.telephone}</div>}
                {f.ville && <div>📍 {f.ville}</div>}
                <div>Délai livraison : {f.delai_livraison_jours} j.</div>
              </div>
              <div className={`mt-3 inline-block rounded-full px-2 py-0.5 text-xs ${f.actif ? "bg-success/10 text-success" : "bg-muted text-muted-foreground"}`}>
                {f.actif ? "Actif" : "Inactif"}
              </div>
            </div>
          ))}
        </div>
      )}

      {dialog.open && (
        <DialogFournisseur
          initial={dialog.item}
          onSave={async (d) => {
            if (dialog.item?.id) await modifier.mutateAsync({ id: dialog.item.id, d });
            else await creer.mutateAsync(d);
          }}
          onFermer={() => setDialog({ open: false })}
        />
      )}
    </div>
  );
}

// ── Page principale ──────────────────────────────────────────────────────────

function PageAchats() {
  const [onglet, setOnglet] = useState<"bc" | "fournisseurs">("bc");
  const [selection, setSelection] = useState<string | null>(null);
  const [receptionOuverte, setReceptionOuverte] = useState(false);
  const [dialogNouveauBC, setDialogNouveauBC] = useState(false);

  const qc = useQueryClient();

  const { data: bcsData, isLoading: bcsLoading } = useQuery({
    queryKey: ["bons-commande"],
    queryFn: () => api.bonsCommande.liste(),
    staleTime: 30_000,
  });

  const { data: fournisseursData } = useQuery({
    queryKey: ["fournisseurs"],
    queryFn: () => api.fournisseurs.liste({ actif: true, page_size: 200 }),
    staleTime: 60_000,
  });

  const fournisseurs = fournisseursData?.results ?? [];
  const bcs = bcsData?.results ?? [];
  const bcActif = bcs.find((b) => b.id === selection) ?? bcs[0];

  const creerBC = useMutation({
    mutationFn: (payload: unknown) => api.bonsCommande.creer(payload),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["bons-commande"] }); },
    onError: (e: ApiError) => toast.error("Erreur création BC", { description: e.detail }),
  });

  return (
    <div className="flex h-screen flex-col">
      <header className="flex items-center justify-between border-b border-border/70 bg-surface/60 px-6 py-4 backdrop-blur">
        <div>
          <h1 className="font-display text-3xl leading-none">Achats & réceptions</h1>
          <p className="text-xs text-muted-foreground mt-1">
            Bons de commande, réceptions partielles ou totales, gestion des fournisseurs.
          </p>
        </div>
        {onglet === "bc" && (
          <Button onClick={() => setDialogNouveauBC(true)} className="flex items-center gap-2">
            <Plus className="h-4 w-4" /> Nouveau BC
          </Button>
        )}
      </header>

      {/* Onglets */}
      <div className="border-b border-border/70 px-6 flex gap-4">
        <button
          onClick={() => setOnglet("bc")}
          className={`py-3 text-sm font-medium border-b-2 transition-colors flex items-center gap-1.5 ${onglet === "bc" ? "border-primary text-primary" : "border-transparent text-muted-foreground hover:text-foreground"}`}
        >
          <Truck className="h-4 w-4" /> Bons de commande ({bcs.length})
        </button>
        <button
          onClick={() => setOnglet("fournisseurs")}
          className={`py-3 text-sm font-medium border-b-2 transition-colors flex items-center gap-1.5 ${onglet === "fournisseurs" ? "border-primary text-primary" : "border-transparent text-muted-foreground hover:text-foreground"}`}
        >
          <Building2 className="h-4 w-4" /> Fournisseurs ({fournisseurs.length})
        </button>
      </div>

      {onglet === "bc" ? (
        <div className="grid flex-1 min-h-0 grid-cols-1 lg:grid-cols-[420px_1fr]">
          {/* Liste BC */}
          <section className="flex flex-col min-h-0 border-r border-border/70">
            <div className="flex-1 overflow-y-auto">
              {bcsLoading ? (
                <div className="p-6 text-sm text-muted-foreground flex items-center gap-2">
                  <Loader2 className="h-4 w-4 animate-spin" /> Chargement…
                </div>
              ) : bcs.length === 0 ? (
                <div className="p-10 text-center text-sm text-muted-foreground">
                  Aucun bon de commande. Cliquez sur "Nouveau BC" pour en créer un.
                </div>
              ) : (
                <ul>
                  {bcs.map((bc) => (
                    <li key={bc.id}>
                      <button
                        onClick={() => setSelection(bc.id)}
                        className={cn(
                          "w-full text-left px-4 py-3 border-b border-border/50 hover:bg-surface-strong transition-colors",
                          bcActif?.id === bc.id && "bg-surface-strong",
                        )}
                      >
                        <div className="flex items-center justify-between">
                          <span className="font-medium numeric">{bc.numero}</span>
                          <span className={cn("rounded-full px-2 py-0.5 text-xs", COULEUR_STATUT[bc.statut])}>
                            {LIBELLES_STATUT_BC[bc.statut]}
                          </span>
                        </div>
                        <div className="text-sm mt-1 truncate text-muted-foreground">{bc.fournisseur_nom ?? "—"}</div>
                        <div className="flex justify-between text-xs text-muted-foreground mt-1">
                          <span>{fmtDate(bc.date_commande)}</span>
                          <span className="numeric">{fmtFCFA(bc.total_ttc ?? bc.montant_total)}</span>
                        </div>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </section>

          {/* Détail BC */}
          <section className="flex flex-col min-h-0 overflow-y-auto">
            {bcActif ? (
              <DetailBonCommande bc={bcActif} onReceptionner={() => setReceptionOuverte(true)} />
            ) : (
              <div className="m-auto text-sm text-muted-foreground">
                Sélectionnez un bon de commande pour voir le détail.
              </div>
            )}
          </section>
        </div>
      ) : (
        <OngletFournisseurs />
      )}

      {/* Dialog réception */}
      {bcActif && (
        <DialogReception
          bc={bcActif}
          ouvert={receptionOuverte}
          onFermer={() => setReceptionOuverte(false)}
        />
      )}

      {/* Dialog nouveau BC */}
      {dialogNouveauBC && (
        <DialogCreerBC
          fournisseurs={fournisseurs}
          onCreer={async (payload) => { await creerBC.mutateAsync(payload); }}
          onFermer={() => setDialogNouveauBC(false)}
        />
      )}
    </div>
  );
}
