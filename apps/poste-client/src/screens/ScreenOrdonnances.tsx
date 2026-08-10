/**
 * ScreenOrdonnances — Gestion des ordonnances (§4.2 CDC, étape 10).
 *
 * Ce module n'avait pas de route dédiée dans la v1 (la gestion était
 * intégrée au POS via DialogOrdonnance). Il est exposé ici comme écran
 * autonome pour consultation, validation et upload hors-vente.
 *
 * Fonctionnalités :
 *  - Liste paginée avec recherche (client, prescripteur, numéro interne)
 *  - Upload d'une nouvelle ordonnance (fichier optionnel + métadonnées)
 *  - Action « Valider » sur les ordonnances en attente
 *  - Affichage de l'image si fichier joint
 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";
import {
  FileText, Plus, UploadCloud, CheckCircle2,
  Loader2, Search, X, Eye,
} from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { api, ApiError } from "@/lib/api-client";
import { fmtDate } from "@/lib/format";
import type { Ordonnance } from "@/lib/types";

// ── Formulaire upload ordonnance ──────────────────────────────────────────────

function DialogUploadOrdonnance({ onFermer }: { onFermer: () => void }) {
  const qc                            = useQueryClient();
  const fileRef                       = useRef<HTMLInputElement>(null);
  const [fichier, setFichier]         = useState<File | null>(null);
  const [prescripteur, setPrescripteur] = useState("");
  const [etablissement, setEtabl]     = useState("");
  const [datePrescription, setDate]   = useState("");
  const [clientSearch, setClientSearch] = useState("");
  const [notes, setNotes]             = useState("");
  const [erreur, setErreur]           = useState<string | null>(null);

  const creer = useMutation({
    mutationFn: () =>
      api.ordonnances.creer({
        fichier: fichier ?? undefined,
        prescripteur_nom: prescripteur || undefined,
        prescripteur_etablissement: etablissement || undefined,
        date_prescription: datePrescription || undefined,
        notes: notes || undefined,
      }),
    onSuccess: () => {
      toast.success("Ordonnance enregistrée.");
      qc.invalidateQueries({ queryKey: ["ordonnances"] });
      onFermer();
    },
    onError: (e) => setErreur(e instanceof ApiError ? e.detail : "Erreur lors de l'enregistrement."),
  });

  return (
    <Dialog open onOpenChange={(v) => !v && onFermer()}>
      <DialogContent className="max-w-lg">
        <DialogHeader><DialogTitle>Nouvelle ordonnance</DialogTitle></DialogHeader>
        <div className="space-y-4 py-2">
          {/* Fichier */}
          <div>
            <Label>Fichier (photo ou scan, optionnel)</Label>
            <div
              onClick={() => fileRef.current?.click()}
              className="mt-2 flex flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed border-border/60 py-8 cursor-pointer hover:border-primary/40 hover:bg-surface/60 transition-colors"
            >
              {fichier ? (
                <div className="text-sm text-center">
                  <CheckCircle2 className="h-6 w-6 text-success mx-auto mb-1" />
                  <span className="font-medium">{fichier.name}</span>
                  <div className="text-xs text-muted-foreground">{(fichier.size / 1024).toFixed(0)} Ko</div>
                </div>
              ) : (
                <>
                  <UploadCloud className="h-8 w-8 text-muted-foreground/50" />
                  <span className="text-sm text-muted-foreground">Cliquer pour sélectionner un fichier</span>
                  <span className="text-xs text-muted-foreground">JPG, PNG, PDF acceptés</span>
                </>
              )}
            </div>
            <input ref={fileRef} type="file" accept="image/*,.pdf" className="hidden" onChange={(e) => setFichier(e.target.files?.[0] ?? null)} />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div><Label>Nom du prescripteur</Label><Input className="mt-1" value={prescripteur} onChange={(e) => setPrescripteur(e.target.value)} placeholder="Dr. Koné" /></div>
            <div><Label>Établissement</Label><Input className="mt-1" value={etablissement} onChange={(e) => setEtabl(e.target.value)} placeholder="CHU Yalgado" /></div>
            <div><Label>Date de prescription</Label><Input type="date" className="mt-1" value={datePrescription} onChange={(e) => setDate(e.target.value)} /></div>
          </div>

          <div><Label>Notes</Label><Input className="mt-1" value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Observations…" /></div>

          {erreur && <div className="rounded-lg bg-destructive/10 px-4 py-2 text-sm text-destructive">{erreur}</div>}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onFermer}>Annuler</Button>
          <Button onClick={() => creer.mutate()} disabled={creer.isPending} className="gap-2">
            {creer.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
            Enregistrer
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ── Composant principal exporté ────────────────────────────────────────────────

export function ScreenOrdonnances() {
  const qc                            = useQueryClient();
  const [search, setSearch]           = useState("");
  const [dialogUpload, setDialogUpload] = useState(false);
  const [visualisee, setVisualisee]   = useState<Ordonnance | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["ordonnances", search],
    queryFn: () => api.ordonnances.liste(search ? { search } : undefined),
    staleTime: 30_000,
  });
  const ordonnances: Ordonnance[] = data?.results ?? [];

  const valider = useMutation({
    mutationFn: (id: string) => api.ordonnances.valider(id),
    onSuccess: () => { toast.success("Ordonnance validée."); qc.invalidateQueries({ queryKey: ["ordonnances"] }); },
    onError: (e) => toast.error("Erreur", { description: e instanceof ApiError ? e.detail : String(e) }),
  });

  const STATUT_CLASSES: Record<string, string> = {
    en_attente: "bg-warning/15 text-warning",
    valide:     "bg-success/15 text-success",
    expire:     "bg-destructive/15 text-destructive",
    utilise:    "bg-muted text-muted-foreground",
  };
  const STATUT_LIBELLE: Record<string, string> = {
    en_attente: "En attente",
    valide:     "Validée",
    expire:     "Expirée",
    utilise:    "Utilisée",
  };

  return (
    <div className="flex h-screen flex-col overflow-hidden">
      <header className="flex items-center justify-between border-b border-border/70 bg-surface/80 px-6 py-4">
        <div className="flex items-center gap-3">
          <FileText className="h-5 w-5 text-muted-foreground" />
          <h1 className="font-display text-2xl">Ordonnances</h1>
          <span className="text-sm text-muted-foreground">({data?.count ?? 0})</span>
        </div>
        <Button onClick={() => setDialogUpload(true)} className="gap-2">
          <Plus className="h-4 w-4" /> Nouvelle ordonnance
        </Button>
      </header>

      <div className="flex items-center gap-3 px-6 py-3 border-b border-border/40">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input className="pl-9" placeholder="Rechercher numéro, prescripteur, client…" value={search} onChange={(e) => setSearch(e.target.value)} />
        </div>
        {isLoading && <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />}
      </div>

      <div className="flex-1 overflow-auto px-6 py-4">
        {ordonnances.length === 0 && !isLoading ? (
          <div className="flex flex-col items-center gap-4 py-20 text-muted-foreground">
            <FileText className="h-12 w-12" />
            <p>{search ? "Aucune ordonnance correspondante." : "Aucune ordonnance enregistrée."}</p>
          </div>
        ) : (
          <div className="card-elevated overflow-hidden">
            <table className="w-full text-sm">
              <thead className="border-b border-border/70 bg-surface-strong/50">
                <tr>
                  <th className="text-left px-4 py-3 font-medium text-muted-foreground">N° interne</th>
                  <th className="text-left px-4 py-3 font-medium text-muted-foreground">Prescripteur</th>
                  <th className="text-left px-4 py-3 font-medium text-muted-foreground">Client</th>
                  <th className="text-left px-4 py-3 font-medium text-muted-foreground">Date prescription</th>
                  <th className="text-center px-4 py-3 font-medium text-muted-foreground">Statut</th>
                  <th className="text-right px-4 py-3 font-medium text-muted-foreground">Actions</th>
                </tr>
              </thead>
              <tbody>
                {ordonnances.map((ord, i) => (
                  <tr key={ord.id} className={`border-b border-border/40 hover:bg-surface-strong/30 ${i % 2 !== 0 ? "bg-surface/30" : ""}`}>
                    <td className="px-4 py-3 font-mono text-xs">{ord.numero_interne}</td>
                    <td className="px-4 py-3">
                      <div className="font-medium">{ord.prescripteur_nom ?? "—"}</div>
                      {ord.prescripteur_etablissement && <div className="text-xs text-muted-foreground">{ord.prescripteur_etablissement}</div>}
                    </td>
                    <td className="px-4 py-3 text-muted-foreground">{ord.client_nom ?? "—"}</td>
                    <td className="px-4 py-3 text-muted-foreground">{ord.date_prescription ? fmtDate(ord.date_prescription) : "—"}</td>
                    <td className="px-4 py-3 text-center">
                      <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${STATUT_CLASSES[ord.statut ?? "en_attente"] ?? "bg-muted text-muted-foreground"}`}>
                        {STATUT_LIBELLE[ord.statut ?? "en_attente"] ?? ord.statut}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <div className="flex items-center justify-end gap-2">
                        {ord.fichier && (
                          <Button size="sm" variant="ghost" onClick={() => setVisualisee(ord)} title="Voir le fichier">
                            <Eye className="h-4 w-4" />
                          </Button>
                        )}
                        {(ord.statut === "en_attente" || !ord.statut) && (
                          <Button size="sm" variant="ghost" onClick={() => valider.mutate(ord.id)} disabled={valider.isPending} className="text-success hover:text-success">
                            <CheckCircle2 className="h-4 w-4" />
                          </Button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Dialog upload */}
      {dialogUpload && <DialogUploadOrdonnance onFermer={() => setDialogUpload(false)} />}

      {/* Dialog visualisation fichier */}
      {visualisee && visualisee.fichier && (
        <Dialog open onOpenChange={(v) => !v && setVisualisee(null)}>
          <DialogContent className="max-w-2xl">
            <DialogHeader>
              <DialogTitle className="flex items-center justify-between">
                <span>Ordonnance — {visualisee.numero_interne}</span>
                <Button size="sm" variant="ghost" onClick={() => setVisualisee(null)}><X className="h-4 w-4" /></Button>
              </DialogTitle>
            </DialogHeader>
            <div className="py-2 max-h-[70vh] overflow-auto">
              {visualisee.fichier.match(/\.(jpg|jpeg|png|webp)$/i)
                ? <img src={visualisee.fichier} alt="Ordonnance" className="w-full rounded-lg" />
                : <iframe src={visualisee.fichier} className="w-full h-[60vh] rounded-lg border" title="Ordonnance PDF" />}
            </div>
          </DialogContent>
        </Dialog>
      )}
    </div>
  );
}
