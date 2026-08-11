/**
 * ScreenPOS — Point de vente, écran principal (§4.2 CDC, étapes 7/10/11).
 *
 * Extrait de _app.index.tsx lors du découpage modulaire (v2).
 * La route conserve uniquement la définition TanStack Router.
 *
 * Fonctionnalités :
 *  - Recherche médicament debounced + scanner code-barres HID
 *  - Raccourcis clavier : Ctrl+K / F2 = focus, F9 = encaisser
 *  - Sélection / création rapide de client
 *  - Ordonnances jointes (upload + recherche)
 *  - Badges stock bas / rupture / produit contrôlé / ordonnance requise
 *  - Dialog paiement multi-mode (espèces, mobile money, assurance, crédit)
 *  - Impression du reçu après validation
 *  - Dialog annulation avec motif obligatoire
 *  - File offline via Dexie (zéro perte en coupure réseau)
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Search, Plus, Minus, Trash2, Receipt, Loader2, Ban,
  Printer, FileText, X, CheckCircle, User, UserPlus,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle,
  DialogFooter, DialogDescription,
} from "@/components/ui/dialog";
import { toast } from "sonner";

import { api, ApiError, NetworkError } from "@/lib/api-client";
import { enfilerVente } from "@/lib/offline-queue";
import { fmtFCFA } from "@/lib/format";
import type { Medicament, ModePaiement, RecuDTO, Ordonnance, Client } from "@/lib/types";
import { DialogPaiement } from "@/components/pos/dialog-paiement";
import { DialogOrdonnance } from "@/components/pos/dialog-ordonnance";
import { ReceiptTemplate } from "@/components/print/ReceiptTemplate";
import { useCodeBarreScanner } from "@/hooks/use-barcode-scanner";

// ── Types internes ─────────────────────────────────────────────────────────────

interface LignePanier {
  cle: string;
  medicament_id: string;
  nom: string;
  prix_unitaire: number;
  quantite: number;
  stock_disponible: number;
  necessite_ordonnance: boolean;
  est_produit_controle?: boolean;
  taux_remise: number;
  lot_id?: string;
}

// ── Hook debounce ──────────────────────────────────────────────────────────────

function useDebounced<T>(value: T, delay = 300): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(t);
  }, [value, delay]);
  return debounced;
}

// ── Dialog Nouveau Client ──────────────────────────────────────────────────────

function DialogNouveauClient({ onFermer, onCreer }: {
  onFermer: () => void;
  onCreer: (client: Client) => void;
}) {
  const [nom, setNom]           = useState("");
  const [prenom, setPrenom]     = useState("");
  const [telephone, setTel]     = useState("");
  const [enCours, setEnCours]   = useState(false);

  async function creer() {
    if (!nom.trim()) return;
    setEnCours(true);
    try {
      const client = await api.clients.creer({ nom, prenom, telephone });
      toast.success(`Client ${client.nom_complet} créé.`);
      onCreer(client);
    } catch (e) {
      toast.error(e instanceof ApiError ? e.detail : "Erreur lors de la création du client.");
    } finally { setEnCours(false); }
  }

  return (
    <Dialog open onOpenChange={(v) => !v && onFermer()}>
      <DialogContent className="max-w-sm">
        <DialogHeader>
          <DialogTitle>Nouveau client</DialogTitle>
          <DialogDescription>Création rapide. Complétez la fiche plus tard.</DialogDescription>
        </DialogHeader>
        <div className="space-y-3 py-2">
          <div><Label>Nom <span className="text-destructive">*</span></Label><Input value={nom} onChange={(e) => setNom(e.target.value)} className="mt-1" autoFocus /></div>
          <div><Label>Prénom</Label><Input value={prenom} onChange={(e) => setPrenom(e.target.value)} className="mt-1" /></div>
          <div><Label>Téléphone</Label><Input value={telephone} onChange={(e) => setTel(e.target.value)} className="mt-1" /></div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onFermer} disabled={enCours}>Annuler</Button>
          <Button onClick={creer} disabled={!nom.trim() || enCours} className="gap-2">
            {enCours && <Loader2 className="h-4 w-4 animate-spin" />}
            <UserPlus className="h-4 w-4" />
            Créer
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ── Dialog Annulation ──────────────────────────────────────────────────────────

const MOTIFS_ANNULATION = [
  "Erreur de saisie",
  "Médicament non disponible en stock",
  "Client a changé d'avis",
  "Ordonnance incorrecte ou périmée",
  "Doublon de vente",
  "Autre (précisez dans les notes)",
];

function DialogAnnulation({ venteId, onFermer, onSuccess }: {
  venteId: string; onFermer: () => void; onSuccess: () => void;
}) {
  const [motif, setMotif]           = useState("");
  const [motifLibre, setMotifLibre] = useState("");
  const [enCours, setEnCours]       = useState(false);

  const motifFinal = motif === "Autre (précisez dans les notes)" ? motifLibre.trim() : motif;

  async function annuler() {
    if (!motifFinal) return;
    setEnCours(true);
    try {
      await api.ventes.annuler(venteId, motifFinal);
      toast.success("Vente annulée.", { description: motifFinal });
      onSuccess();
    } catch (e) {
      toast.error(e instanceof ApiError ? e.detail : "Erreur lors de l'annulation.");
    } finally { setEnCours(false); }
  }

  return (
    <Dialog open onOpenChange={(v) => !v && onFermer()}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2"><Ban className="h-5 w-5 text-destructive" />Annuler la vente</DialogTitle>
          <DialogDescription>Le stock sera restauré. L'annulation est irréversible.</DialogDescription>
        </DialogHeader>
        <div className="space-y-4 py-2">
          <div>
            <Label className="text-xs uppercase tracking-wide text-muted-foreground">Motif d'annulation <span className="text-destructive">*</span></Label>
            <div className="mt-2 space-y-2">
              {MOTIFS_ANNULATION.map((m) => (
                <label key={m} className={`flex items-center gap-3 rounded-lg border px-3 py-2.5 cursor-pointer transition-colors ${motif === m ? "border-destructive/50 bg-destructive/5" : "hover:bg-muted/30"}`}>
                  <input type="radio" name="motif" value={m} checked={motif === m} onChange={() => setMotif(m)} className="accent-destructive" />
                  <span className="text-sm">{m}</span>
                </label>
              ))}
            </div>
          </div>
          {motif === "Autre (précisez dans les notes)" && (
            <div>
              <Label className="text-xs uppercase tracking-wide text-muted-foreground">Précisez</Label>
              <Input className="mt-1" placeholder="Décrivez le motif…" value={motifLibre} onChange={(e) => setMotifLibre(e.target.value)} autoFocus />
            </div>
          )}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onFermer} disabled={enCours}>Conserver</Button>
          <Button variant="destructive" onClick={annuler} disabled={!motifFinal || enCours} className="gap-2">
            {enCours && <Loader2 className="h-4 w-4 animate-spin" />}
            <Ban className="h-4 w-4" />
            Annuler la vente
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ── Composant vide ─────────────────────────────────────────────────────────────

function VideAstuces() {
  return (
    <div className="py-12 text-center text-sm text-muted-foreground space-y-2">
      <Receipt className="h-10 w-10 mx-auto opacity-20 mb-4" />
      <p className="font-medium text-foreground">Prêt pour la vente</p>
      <p>Tapez le nom d'un médicament, son DCI ou son code.</p>
      <p className="text-xs opacity-60 mt-4">
        <kbd className="kbd">Ctrl</kbd>+<kbd className="kbd">K</kbd> · focus rapide
      </p>
    </div>
  );
}

// ── Composant principal exporté ────────────────────────────────────────────────

export function ScreenPOS() {
  // ── Recherche médicament ───────────────────────────────────────────────────
  const [recherche, setRecherche]   = useState("");
  const debounced                   = useDebounced(recherche, 280);
  const champRecherche              = useRef<HTMLInputElement>(null);

  // ── Panier ────────────────────────────────────────────────────────────────
  const [lignes, setLignes]         = useState<LignePanier[]>([]);

  // ── Client ────────────────────────────────────────────────────────────────
  const [clientSelectionne, setClientSelectionne]       = useState<Client | null>(null);
  const [rechercheClient, setRechercheClient]           = useState("");
  const [afficherNouveauClient, setAfficherNouveauClient] = useState(false);
  const debouncedClient                                   = useDebounced(rechercheClient, 350);

  // ── Ordonnance ────────────────────────────────────────────────────────────
  const [ordonnanceJointee, setOrdonnanceJointee]     = useState<Ordonnance | null>(null);
  const [dialogOrdoOuvert, setDialogOrdoOuvert]       = useState(false);

  // ── Paiement ─────────────────────────────────────────────────────────────
  const [dialogPaiementOuvert, setDialogPaiementOuvert] = useState(false);
  const [venteIdRecente, setVenteIdRecente]             = useState<string | null>(null);
  const [recuAImprimer, setRecuAImprimer]               = useState<RecuDTO | null>(null);
  const [dialogRecuOuvert, setDialogRecuOuvert]         = useState(false);

  // ── Annulation ────────────────────────────────────────────────────────────
  const [venteIdAnnuler, setVenteIdAnnuler] = useState<string | null>(null);

  // ── Requêtes API ──────────────────────────────────────────────────────────
  const { data: resultats, isFetching } = useQuery({
    queryKey: ["pos-recherche", debounced],
    queryFn: () => api.catalogue.medicaments.liste({ search: debounced, page_size: 12, est_actif: true }),
    enabled: debounced.length >= 2,
    staleTime: 30_000,
  });

  const { data: resultatsClient } = useQuery({
    queryKey: ["pos-clients", debouncedClient],
    queryFn: () => api.clients.rechercher(debouncedClient),
    enabled: debouncedClient.length >= 2,
    staleTime: 30_000,
  });

  // ── Scanner code-barres HID (DT-006) ─────────────────────────────────────
  useCodeBarreScanner({
    actif: true,
    onScan: useCallback(async (code: string) => {
      try {
        const res = await api.catalogue.medicaments.liste({ code_barre: code, page_size: 1 });
        if (res.results.length > 0) ajouterAuPanier(res.results[0]);
        else toast.warning("Code-barres inconnu", { description: code });
      } catch { toast.error("Erreur lors de la recherche par code-barres."); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []),
  });

  // ── Raccourcis clavier ────────────────────────────────────────────────────
  useEffect(() => {
    function handler(e: KeyboardEvent) {
      if ((e.ctrlKey || e.metaKey) && e.key === "k") { e.preventDefault(); champRecherche.current?.focus(); champRecherche.current?.select(); }
      if (e.key === "F2") { e.preventDefault(); champRecherche.current?.focus(); }
      if (e.key === "F9") { e.preventDefault(); if (lignes.length > 0) setDialogPaiementOuvert(true); }
    }
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [lignes.length]);

  // ── Total ─────────────────────────────────────────────────────────────────
  const total = useMemo(
    () => lignes.reduce((s, l) => s + l.prix_unitaire * l.quantite * (1 - l.taux_remise / 100), 0),
    [lignes],
  );

  // ── Panier — helpers ──────────────────────────────────────────────────────
  function ajouterAuPanier(m: Medicament) {
    setLignes((prev) => {
      const idx = prev.findIndex((l) => l.medicament_id === m.id);
      if (idx >= 0) {
        if (prev[idx].quantite >= prev[idx].stock_disponible) { toast.warning("Stock insuffisant", { description: `Disponible : ${prev[idx].stock_disponible}` }); return prev; }
        return prev.map((l, i) => i === idx ? { ...l, quantite: l.quantite + 1 } : l);
      }
      return [...prev, {
        cle: `${m.id}-${Date.now()}`, medicament_id: m.id, nom: m.nom,
        prix_unitaire: Number(m.prix_vente ?? m.prix_public ?? 0),
        quantite: 1, stock_disponible: m.stock_total_disponible ?? m.stock_total ?? 99,
        necessite_ordonnance: m.necessite_ordonnance ?? false,
        est_produit_controle: m.est_produit_controle ?? false, taux_remise: 0,
      }];
    });
    setRecherche("");
  }

  function modifierQuantite(cle: string, delta: number) {
    setLignes((prev) =>
      prev.map((l) => {
        if (l.cle !== cle) return l;
        const nv = l.quantite + delta;
        if (nv <= 0) return null as unknown as LignePanier;
        if (nv > l.stock_disponible) { toast.warning("Stock insuffisant", { description: `Disponible : ${l.stock_disponible}` }); return l; }
        return { ...l, quantite: nv };
      }).filter(Boolean) as LignePanier[]
    );
  }

  function supprimerLigne(cle: string) { setLignes((prev) => prev.filter((l) => l.cle !== cle)); }

  function viderPanier() { setLignes([]); setOrdonnanceJointee(null); setClientSelectionne(null); setRechercheClient(""); }

  // ── Validation paiement ───────────────────────────────────────────────────
  async function onPaiementValide(mode: ModePaiement, montantEncaisse: number, referenceMobileMoney?: string, tauxAssurance?: number) {
    const payload: Record<string, unknown> = {
      panier: lignes.map((l) => ({ medicament_id: l.medicament_id, quantite: l.quantite, prix_unitaire_demande: l.prix_unitaire, taux_remise: l.taux_remise })),
      mode_paiement: mode, montant_encaisse: montantEncaisse,
    };
    if (clientSelectionne) payload.client_id = clientSelectionne.id;
    if (ordonnanceJointee) payload.ordonnance_id = ordonnanceJointee.id;
    if (referenceMobileMoney) payload.reference_mobile_money = referenceMobileMoney;
    if (mode === "assurance" && tauxAssurance != null) payload.taux_assurance = tauxAssurance;

    try {
      const vente = await api.ventes.creer(payload);
      setVenteIdRecente(vente.id);
      toast.success("Vente enregistrée", { description: `Reçu ${vente.numero}` });
      viderPanier();
      const recu = await api.ventes.recu(vente.id);
      setRecuAImprimer(recu);
      setDialogRecuOuvert(true);
    } catch (e) {
      if (e instanceof NetworkError) {
        await enfilerVente(payload);
        toast.success("Vente mise en attente (hors-ligne). Elle sera synchronisée dès reprise du réseau.");
        viderPanier();
      } else {
        toast.error(e instanceof ApiError ? e.detail : "Erreur lors de la vente.");
      }
    } finally { setDialogPaiementOuvert(false); }
  }

  return (
    <div className="flex h-screen flex-col">
      {/* En-tête */}
      <header className="flex items-center justify-between border-b border-border/70 bg-surface/60 px-6 py-4 backdrop-blur">
        <div>
          <h1 className="font-display text-3xl leading-none">Point de vente</h1>
          <p className="text-xs text-muted-foreground mt-1">
            <span className="kbd">Ctrl+K</span> · recherche · <span className="kbd">F9</span> · encaisser
          </p>
        </div>
        <div className="flex items-center gap-3">
          {lignes.length > 0 && (
            <Badge className="bg-primary text-primary-foreground">{lignes.length} article{lignes.length > 1 ? "s" : ""}</Badge>
          )}
        </div>
      </header>

      {/* Corps principal */}
      <div className="grid flex-1 min-h-0 grid-cols-1 lg:grid-cols-[1fr_380px]">
        {/* Panneau gauche — recherche + résultats */}
        <section className="flex flex-col min-h-0 overflow-hidden border-r border-border/70">
          <div className="px-6 py-4 border-b border-border/50">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground pointer-events-none" />
              <Input
                ref={champRecherche}
                placeholder="Nom, DCI, code CIS ou code-barres…"
                value={recherche}
                onChange={(e) => setRecherche(e.target.value)}
                className="pl-9"
                autoFocus
              />
              {isFetching && <Loader2 className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 animate-spin text-muted-foreground" />}
            </div>
          </div>

          <div className="flex-1 overflow-y-auto px-6 py-3">
            {debounced.length < 2 ? (
              <VideAstuces />
            ) : resultats?.results?.length === 0 ? (
              <div className="text-center py-16 text-sm text-muted-foreground">Aucun résultat pour «&nbsp;{debounced}&nbsp;».</div>
            ) : (
              <ul className="space-y-2">
                {resultats?.results.map((m) => {
                  const stock   = m.stock_total_disponible ?? m.stock_total ?? 0;
                  const rupture = stock <= 0;
                  const stockBas = !rupture && stock <= (m.seuil_alerte_stock ?? 20);
                  return (
                    <li key={m.id}>
                      <button
                        onClick={() => ajouterAuPanier(m)}
                        disabled={rupture}
                        className={`w-full text-left rounded-xl border px-4 py-3 transition-all hover:shadow-sm ${rupture ? "opacity-50 cursor-not-allowed border-destructive/30 bg-destructive/5" : "border-border/60 hover:border-primary/40 hover:bg-surface/80"}`}
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div className="min-w-0 flex-1">
                            <div className="flex items-center gap-2 flex-wrap">
                              <span className="font-medium text-sm">{m.nom}</span>
                              {m.est_produit_controle && <Badge variant="outline" className="text-xs px-1.5 py-0 border-purple-300 text-purple-700">Contrôlé</Badge>}
                              {m.necessite_ordonnance && <Badge variant="outline" className="text-xs px-1.5 py-0 border-amber-300 text-amber-700">Sur ordo.</Badge>}
                            </div>
                            {(m.denomination_commune_internationale || m.dci) && (
                              <div className="text-xs text-muted-foreground mt-0.5">{m.denomination_commune_internationale ?? m.dci}</div>
                            )}
                            <div className="text-xs text-muted-foreground mt-0.5">{[m.forme_pharmaceutique ?? m.forme, m.dosage].filter(Boolean).join(" · ")}</div>
                          </div>
                          <div className="shrink-0 text-right">
                            <div className="font-mono font-medium text-sm">{fmtFCFA(m.prix_public ?? m.prix_vente)}</div>
                            <div className={`text-xs mt-0.5 ${rupture ? "text-destructive font-medium" : stockBas ? "text-amber-600 font-medium" : "text-muted-foreground"}`}>
                              {rupture ? "Rupture" : stockBas ? `Stock bas : ${stock}` : `Stock : ${stock}`}
                            </div>
                          </div>
                        </div>
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        </section>

        {/* Panneau droit — panier */}
        <aside className="flex flex-col min-h-0 bg-surface/40">
          {/* Sélection client */}
          <div className="px-4 pt-4 pb-2 border-b border-border/60">
            {clientSelectionne ? (
              <div className="flex items-center justify-between rounded-lg bg-primary/5 border border-primary/20 px-3 py-2 text-sm">
                <div className="flex items-center gap-2 min-w-0">
                  <User className="h-4 w-4 text-primary shrink-0" />
                  <div className="min-w-0">
                    <div className="font-medium truncate">{clientSelectionne.nom_complet}</div>
                    {clientSelectionne.telephone && <div className="text-xs text-muted-foreground">{clientSelectionne.telephone}</div>}
                  </div>
                </div>
                <button onClick={() => { setClientSelectionne(null); setRechercheClient(""); }} className="text-muted-foreground hover:text-foreground ml-2"><X className="h-4 w-4" /></button>
              </div>
            ) : (
              <div className="relative">
                <User className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground pointer-events-none" />
                <Input placeholder="Rechercher un client…" value={rechercheClient} onChange={(e) => setRechercheClient(e.target.value)} className="pl-9 pr-9 h-9 text-sm" />
                <button onClick={() => setAfficherNouveauClient(true)} className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-primary" title="Créer un nouveau client"><UserPlus className="h-4 w-4" /></button>
                {debouncedClient.length >= 2 && resultatsClient?.results && (
                  <div className="absolute z-20 mt-1 w-full rounded-lg border bg-popover shadow-lg">
                    {resultatsClient.results.length === 0 ? (
                      <div className="px-3 py-2 text-sm text-muted-foreground">Aucun client trouvé. <button className="ml-2 text-primary underline text-xs" onClick={() => setAfficherNouveauClient(true)}>Créer</button></div>
                    ) : (
                      resultatsClient.results.slice(0, 6).map((c) => (
                        <button key={c.id} onClick={() => { setClientSelectionne(c); setRechercheClient(""); }} className="w-full text-left px-3 py-2 text-sm hover:bg-accent transition-colors flex items-center gap-2">
                          <User className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                          <span>{c.nom_complet}{c.telephone && <span className="text-muted-foreground ml-1 text-xs">· {c.telephone}</span>}</span>
                        </button>
                      ))
                    )}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* En-tête panier + bouton ordonnance */}
          <div className="flex items-center justify-between px-4 py-2">
            <h2 className="font-display text-lg">Ticket en cours</h2>
            <button
              onClick={() => setDialogOrdoOuvert(true)}
              className={`flex items-center gap-1.5 text-xs rounded-lg px-2.5 py-1.5 transition-colors ${ordonnanceJointee ? "bg-success/10 text-success border border-success/30" : "text-muted-foreground hover:bg-surface-strong"}`}
            >
              <FileText className="h-3.5 w-3.5" />
              {ordonnanceJointee ? "Ord. jointe" : "Ordonnance"}
            </button>
          </div>

          {ordonnanceJointee && (
            <div className="mx-4 mb-1 flex items-center justify-between rounded-lg bg-success/10 border border-success/20 px-3 py-1.5 text-xs">
              <span className="text-success flex items-center gap-1">
                <CheckCircle className="h-3 w-3" />
                {ordonnanceJointee.numero_interne}{ordonnanceJointee.prescripteur_nom && ` — ${ordonnanceJointee.prescripteur_nom}`}
              </span>
              <button onClick={() => setOrdonnanceJointee(null)} className="text-muted-foreground hover:text-foreground"><X className="h-3 w-3" /></button>
            </div>
          )}

          {/* Lignes panier */}
          <div className="flex-1 overflow-y-auto px-4">
            {lignes.length === 0 ? (
              <div className="text-center py-12 text-sm text-muted-foreground">Aucun article. Scannez ou recherchez un médicament.</div>
            ) : (
              <ul className="space-y-2 pb-4 pt-1">
                {lignes.map((l) => {
                  const stockRestant = l.stock_disponible - l.quantite;
                  const enAlerte     = stockRestant <= 5 && stockRestant > 0;
                  const enRupture    = stockRestant <= 0;
                  return (
                    <li key={l.cle} className={`rounded-xl border p-3 flex items-start gap-3 transition-colors ${enRupture ? "border-destructive/40 bg-destructive/5" : enAlerte ? "border-amber-300/60 bg-amber-50/60" : "bg-card border-border/60"}`}>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-1.5 flex-wrap">
                          <span className="font-medium text-sm truncate">{l.nom}</span>
                          {enRupture && <Badge variant="destructive" className="text-xs px-1.5 py-0">Rupture !</Badge>}
                          {!enRupture && enAlerte && <Badge className="text-xs px-1.5 py-0 bg-amber-100 text-amber-800 border-amber-300">Stock bas</Badge>}
                          {l.est_produit_controle && <Badge variant="outline" className="text-xs px-1.5 py-0 border-purple-300 text-purple-700">Contrôlé</Badge>}
                          {l.necessite_ordonnance && !ordonnanceJointee && <Badge variant="outline" className="text-xs px-1.5 py-0 border-amber-300 text-amber-700">Ord. requise</Badge>}
                        </div>
                        <div className="text-xs text-muted-foreground numeric mt-0.5">
                          {fmtFCFA(l.prix_unitaire)} × {l.quantite} = <strong>{fmtFCFA(l.prix_unitaire * l.quantite)}</strong>
                        </div>
                        {stockRestant >= 0 && (
                          <div className={`text-xs mt-0.5 ${enRupture ? "text-destructive" : enAlerte ? "text-amber-600" : "text-muted-foreground"}`}>
                            {enRupture ? `Attention : ${l.stock_disponible} disponible(s)` : `Reste : ${stockRestant}`}
                          </div>
                        )}
                      </div>
                      <div className="flex items-center gap-1 shrink-0">
                        <Button size="icon" variant="ghost" className="h-7 w-7" onClick={() => modifierQuantite(l.cle, -1)}><Minus className="h-3.5 w-3.5" /></Button>
                        <span className="numeric w-6 text-center font-medium text-sm">{l.quantite}</span>
                        <Button size="icon" variant="ghost" className="h-7 w-7" onClick={() => modifierQuantite(l.cle, +1)} disabled={l.quantite >= l.stock_disponible}><Plus className="h-3.5 w-3.5" /></Button>
                        <Button size="icon" variant="ghost" className="h-7 w-7" onClick={() => supprimerLigne(l.cle)}><Trash2 className="h-3.5 w-3.5 text-destructive" /></Button>
                      </div>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>

          {/* Pied de panier */}
          {lignes.length > 0 && (
            <div className="border-t border-border/70 px-4 py-4 space-y-3 bg-surface/50">
              <div className="flex items-baseline justify-between">
                <span className="text-sm text-muted-foreground">Total</span>
                <span className="numeric font-display text-2xl">{fmtFCFA(total)}</span>
              </div>
              <div className="flex gap-2">
                <Button variant="outline" className="flex-1 gap-2" onClick={viderPanier}><X className="h-4 w-4" />Vider</Button>
                {venteIdRecente && (
                  <Button variant="outline" size="icon" onClick={() => setVenteIdAnnuler(venteIdRecente)} title="Annuler la dernière vente" className="text-destructive border-destructive/40 hover:bg-destructive/10">
                    <Ban className="h-4 w-4" />
                  </Button>
                )}
                <Button className="flex-1 gap-2" onClick={() => setDialogPaiementOuvert(true)} disabled={lignes.length === 0}>
                  <Receipt className="h-4 w-4" />Encaisser
                </Button>
              </div>
            </div>
          )}
        </aside>
      </div>

      {/* Dialogs */}
      {dialogPaiementOuvert && (
        <DialogPaiement
          ouvert={dialogPaiementOuvert}
          total={total}
          clientId={clientSelectionne?.id ?? null}
          enCours={false}
          onValider={(p) => onPaiementValide(p.mode, p.encaisse, p.referenceMobileMoney)}
          onFermer={() => setDialogPaiementOuvert(false)}
        />
      )}

      {dialogRecuOuvert && recuAImprimer && (
        <Dialog open onOpenChange={(v) => !v && setDialogRecuOuvert(false)}>
          <DialogContent className="max-w-sm">
            <DialogHeader><DialogTitle>Reçu de vente</DialogTitle></DialogHeader>
            <div className="py-2"><ReceiptTemplate recu={recuAImprimer} /></div>
            <DialogFooter>
              <Button onClick={() => window.print()} className="gap-2"><Printer className="h-4 w-4" />Imprimer</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      )}

      {afficherNouveauClient && (
        <DialogNouveauClient
          onFermer={() => setAfficherNouveauClient(false)}
          onCreer={(c) => { setClientSelectionne(c); setAfficherNouveauClient(false); setRechercheClient(""); }}
        />
      )}

      {venteIdAnnuler && (
        <DialogAnnulation
          venteId={venteIdAnnuler}
          onFermer={() => setVenteIdAnnuler(null)}
          onSuccess={() => { setVenteIdAnnuler(null); setVenteIdRecente(null); }}
        />
      )}

      {dialogOrdoOuvert && (
        <DialogOrdonnance
          onOrdonnanceJointee={(ord) => { setOrdonnanceJointee(ord); setDialogOrdoOuvert(false); }}
          onFermer={() => setDialogOrdoOuvert(false)}
        />
      )}
    </div>
  );
}
