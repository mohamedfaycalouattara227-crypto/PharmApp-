/**
 * src/components/pos/dialog-ordonnance.tsx
 * Dialog d'upload et d'attachement d'ordonnance dans le POS (DT-006 / ÉTAPE 10)
 *
 * Flux complet :
 *  1. Caissier clique "Ordonnance" dans le panier
 *  2. Ce dialog s'ouvre — deux onglets :
 *     a) "Uploader" : glisser-déposer ou sélection fichier → POST /api/ordonnances/ (multipart)
 *     b) "Rechercher" : chercher une ordonnance existante par numéro ou patient
 *  3. Après upload/sélection → onOrdonnanceJointee(ordonnance) est appelé
 *  4. Le panier affiche le badge "Ord. jointe" + numero_interne
 *
 * Sécurité : seuls JPEG, PNG, WebP, PDF sont acceptés côté client.
 *            Le backend valide les magic bytes — double protection.
 */

import { useCallback, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  CheckCircle,
  FileText,
  Loader2,
  Search,
  Upload,
  X,
} from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { api, ApiError } from "@/lib/api-client";
import type { Ordonnance } from "@/lib/types";

// ─── Types ────────────────────────────────────────────────────────────────────

interface DialogOrdonnanceProps {
  onOrdonnanceJointee: (ord: Ordonnance) => void;
  onFermer: () => void;
}

type Onglet = "uploader" | "rechercher";

const MIME_AUTORISES = ["image/jpeg", "image/png", "image/webp", "application/pdf"];
const TAILLE_MAX_MB = 5;
const TAILLE_MAX_OCTETS = TAILLE_MAX_MB * 1024 * 1024;

// ─── Utilitaires ─────────────────────────────────────────────────────────────

function validerFichierClient(fichier: File): string | null {
  if (!MIME_AUTORISES.includes(fichier.type)) {
    return `Type non autorisé : ${fichier.type}. Formats acceptés : JPEG, PNG, WebP, PDF.`;
  }
  if (fichier.size > TAILLE_MAX_OCTETS) {
    return `Fichier trop volumineux (${(fichier.size / 1024 / 1024).toFixed(1)} Mo). Maximum : ${TAILLE_MAX_MB} Mo.`;
  }
  if (fichier.size === 0) {
    return "Le fichier est vide.";
  }
  return null;
}

// ─── Sous-composant : onglet upload ──────────────────────────────────────────

function OngletUpload({
  onSuccess,
}: {
  onSuccess: (ord: Ordonnance) => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [fichier, setFichier] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [prescripteur, setPrescripteur] = useState("");
  const [enCours, setEnCours] = useState(false);
  const [dragOver, setDragOver] = useState(false);

  const choisirFichier = useCallback((f: File) => {
    const erreur = validerFichierClient(f);
    if (erreur) {
      toast.error(erreur);
      return;
    }
    setFichier(f);
    if (f.type.startsWith("image/")) {
      const url = URL.createObjectURL(f);
      setPreview(url);
    } else {
      setPreview(null);
    }
  }, []);

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragOver(false);
      const f = e.dataTransfer.files[0];
      if (f) choisirFichier(f);
    },
    [choisirFichier]
  );

  const onInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (f) choisirFichier(f);
  };

  const effacer = () => {
    setFichier(null);
    if (preview) URL.revokeObjectURL(preview);
    setPreview(null);
    if (inputRef.current) inputRef.current.value = "";
  };

  const uploader = async () => {
    if (!fichier) return;
    setEnCours(true);
    try {
      const ordonnance = await api.ordonnances.creer({
        fichier,
        prescripteur_nom: prescripteur.trim() || undefined,
      });
      toast.success("Ordonnance enregistrée", {
        description: ordonnance.numero_interne,
      });
      onSuccess(ordonnance);
    } catch (e) {
      toast.error(
        e instanceof ApiError ? e.detail : "Erreur lors de l'upload de l'ordonnance."
      );
    } finally {
      setEnCours(false);
    }
  };

  return (
    <div className="space-y-4">
      {/* Zone drag & drop */}
      {!fichier ? (
        <div
          onDrop={onDrop}
          onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onClick={() => inputRef.current?.click()}
          className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-colors ${
            dragOver
              ? "border-primary bg-primary/5"
              : "border-border hover:border-primary/50 hover:bg-muted/30"
          }`}
        >
          <Upload className="h-10 w-10 mx-auto mb-3 text-muted-foreground" />
          <p className="font-medium text-sm">
            Glisser-déposer ou{" "}
            <span className="text-primary underline">cliquer pour choisir</span>
          </p>
          <p className="text-xs text-muted-foreground mt-1">
            JPEG, PNG, WebP, PDF — max {TAILLE_MAX_MB} Mo
          </p>
          <input
            ref={inputRef}
            type="file"
            accept={MIME_AUTORISES.join(",")}
            onChange={onInputChange}
            className="hidden"
          />
        </div>
      ) : (
        <div className="rounded-xl border bg-card p-4">
          <div className="flex items-start gap-3">
            {preview ? (
              <img
                src={preview}
                alt="Aperçu ordonnance"
                className="h-20 w-20 object-cover rounded-lg border shrink-0"
              />
            ) : (
              <div className="h-20 w-20 rounded-lg border bg-muted flex items-center justify-center shrink-0">
                <FileText className="h-8 w-8 text-muted-foreground" />
              </div>
            )}
            <div className="flex-1 min-w-0">
              <p className="font-medium text-sm truncate">{fichier.name}</p>
              <p className="text-xs text-muted-foreground mt-0.5">
                {(fichier.size / 1024).toFixed(0)} Ko — {fichier.type}
              </p>
              <Badge variant="outline" className="mt-2 text-xs text-green-700 border-green-300">
                <CheckCircle className="h-3 w-3 mr-1" />
                Fichier validé
              </Badge>
            </div>
            <button
              onClick={effacer}
              className="text-muted-foreground hover:text-destructive"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>
      )}

      {/* Prescripteur */}
      <div>
        <Label className="text-xs uppercase tracking-wide text-muted-foreground">
          Nom du prescripteur (optionnel)
        </Label>
        <Input
          value={prescripteur}
          onChange={(e) => setPrescripteur(e.target.value)}
          placeholder="Dr Coulibaly, Dr Sawadogo…"
          className="mt-1"
        />
      </div>

      <Button
        className="w-full gap-2"
        onClick={uploader}
        disabled={!fichier || enCours}
      >
        {enCours ? (
          <Loader2 className="h-4 w-4 animate-spin" />
        ) : (
          <Upload className="h-4 w-4" />
        )}
        {enCours ? "Envoi en cours…" : "Enregistrer l'ordonnance"}
      </Button>
    </div>
  );
}

// ─── Sous-composant : onglet recherche ───────────────────────────────────────

function OngletRecherche({
  onSuccess,
}: {
  onSuccess: (ord: Ordonnance) => void;
}) {
  const [recherche, setRecherche] = useState("");

  const { data, isFetching } = useQuery({
    queryKey: ["pos-ordonnances", recherche],
    queryFn: () =>
      api.ordonnances.liste({ search: recherche, statut: "en_attente", page_size: "10" }),
    enabled: recherche.length >= 2,
    staleTime: 15_000,
  });

  return (
    <div className="space-y-4">
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground pointer-events-none" />
        <Input
          value={recherche}
          onChange={(e) => setRecherche(e.target.value)}
          placeholder="Numéro ORD-… ou nom prescripteur…"
          className="pl-9"
          autoFocus
        />
        {isFetching && (
          <Loader2 className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 animate-spin text-muted-foreground" />
        )}
      </div>

      {recherche.length >= 2 && (
        <div className="max-h-60 overflow-y-auto space-y-1.5">
          {data?.results?.length === 0 && (
            <p className="text-center text-sm text-muted-foreground py-6">
              Aucune ordonnance trouvée.
            </p>
          )}
          {data?.results?.map((ord) => (
            <button
              key={ord.id}
              onClick={() => onSuccess(ord)}
              className="w-full text-left rounded-lg border px-3 py-2.5 hover:bg-accent hover:border-primary/40 transition-colors"
            >
              <div className="flex items-center justify-between gap-2">
                <div className="min-w-0">
                  <p className="font-medium text-sm truncate">{ord.numero_interne}</p>
                  {ord.prescripteur_nom && (
                    <p className="text-xs text-muted-foreground truncate">
                      {ord.prescripteur_nom}
                    </p>
                  )}
                </div>
                <Badge
                  variant="outline"
                  className="text-xs shrink-0 text-amber-700 border-amber-300"
                >
                  En attente
                </Badge>
              </div>
            </button>
          ))}
        </div>
      )}

      {recherche.length < 2 && (
        <p className="text-center text-xs text-muted-foreground py-4">
          Saisissez au moins 2 caractères pour chercher.
        </p>
      )}
    </div>
  );
}

// ─── Composant principal ──────────────────────────────────────────────────────

export function DialogOrdonnance({ onOrdonnanceJointee, onFermer }: DialogOrdonnanceProps) {
  const [onglet, setOnglet] = useState<Onglet>("uploader");

  const handleSuccess = (ord: Ordonnance) => {
    onOrdonnanceJointee(ord);
    onFermer();
  };

  return (
    <Dialog open onOpenChange={(v) => !v && onFermer()}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <FileText className="h-5 w-5 text-amber-600" />
            Attacher une ordonnance
          </DialogTitle>
          <DialogDescription>
            Uploadez le scan ou retrouvez une ordonnance déjà enregistrée.
          </DialogDescription>
        </DialogHeader>

        {/* Onglets */}
        <div className="flex border-b border-border mb-4">
          {(["uploader", "rechercher"] as Onglet[]).map((t) => (
            <button
              key={t}
              onClick={() => setOnglet(t)}
              className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                onglet === t
                  ? "border-primary text-primary"
                  : "border-transparent text-muted-foreground hover:text-foreground"
              }`}
            >
              {t === "uploader" ? "Uploader" : "Rechercher"}
            </button>
          ))}
        </div>

        {onglet === "uploader" ? (
          <OngletUpload onSuccess={handleSuccess} />
        ) : (
          <OngletRecherche onSuccess={handleSuccess} />
        )}

        <DialogFooter>
          <Button variant="outline" onClick={onFermer}>
            Annuler
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
