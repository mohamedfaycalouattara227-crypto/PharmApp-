/**
 * src/components/pos/panier-sidebar.tsx
 * Sidebar panier du POS — composant atomique extrait de _app.index.tsx (DT-005)
 *
 * Gère l'affichage et les interactions du panier :
 *  - Sélection client
 *  - Badge ordonnance jointée
 *  - Liste des lignes avec quantités, alertes stock, badges contrôlé/ordonnance
 *  - Pied : total, boutons Vider / Annuler / Encaisser
 */

import { X, FileText, CheckCircle, User, UserPlus, Receipt, Ban } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { fmtFCFA } from "@/lib/format";
import type { Client, Ordonnance } from "@/lib/types";
import { LignePanierItem } from "./ligne-panier-item";

export interface LignePanier {
  cle: string;
  medicament_id: string;
  nom: string;
  prix_unitaire: number;
  quantite: number;
  stock_disponible: number;
  necessite_ordonnance: boolean;
  est_produit_controle: boolean;
  taux_remise: number;
}

interface PanierSidebarProps {
  lignes: LignePanier[];
  total: number;
  clientSelectionne: Client | null;
  rechercheClient: string;
  resultatsClient?: Client[];
  afficherNouveauClient: boolean;
  ordonnanceJointee: Ordonnance | null;
  venteIdRecente: string | null;
  scanEnCours?: boolean;
  onRechercheClientChange: (v: string) => void;
  onClientSelectionne: (c: Client) => void;
  onClientEfface: () => void;
  onNouveauClientClick: () => void;
  onOrdonnanceClick: () => void;
  onOrdonnanceEffacee: () => void;
  onModifierQuantite: (cle: string, delta: number) => void;
  onSupprimerLigne: (cle: string) => void;
  onViderPanier: () => void;
  onAnnulerVente: () => void;
  onEncaisser: () => void;
}

export function PanierSidebar({
  lignes,
  total,
  clientSelectionne,
  rechercheClient,
  resultatsClient,
  ordonnanceJointee,
  venteIdRecente,
  scanEnCours,
  onRechercheClientChange,
  onClientSelectionne,
  onClientEfface,
  onNouveauClientClick,
  onOrdonnanceClick,
  onOrdonnanceEffacee,
  onModifierQuantite,
  onSupprimerLigne,
  onViderPanier,
  onAnnulerVente,
  onEncaisser,
}: PanierSidebarProps) {
  return (
    <aside className="w-[26rem] shrink-0 flex flex-col border-l border-border/60 bg-surface h-full">

      {/* ── Sélection client ──────────────────────────────────────────── */}
      <div className="px-4 pt-4 pb-2 border-b border-border/50">
        {clientSelectionne ? (
          <div className="flex items-center justify-between rounded-lg bg-primary/5 border border-primary/20 px-3 py-2">
            <div className="flex items-center gap-2 min-w-0">
              <User className="h-4 w-4 text-primary shrink-0" />
              <span className="text-sm font-medium truncate">{clientSelectionne.nom_complet}</span>
            </div>
            <button onClick={onClientEfface} className="text-muted-foreground hover:text-foreground shrink-0 ml-2">
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        ) : (
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <div className="relative flex-1">
                <User className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground pointer-events-none" />
                <Input
                  value={rechercheClient}
                  onChange={(e) => onRechercheClientChange(e.target.value)}
                  placeholder="Client (optionnel)…"
                  className="pl-8 h-8 text-sm"
                />
              </div>
              <Button
                size="icon"
                variant="ghost"
                className="h-8 w-8 shrink-0"
                onClick={onNouveauClientClick}
                title="Créer un nouveau client"
              >
                <UserPlus className="h-4 w-4" />
              </Button>
            </div>
            {resultatsClient && resultatsClient.length > 0 && rechercheClient.length >= 2 && (
              <div className="rounded-lg border bg-card shadow-md max-h-36 overflow-y-auto z-20">
                {resultatsClient.map((c) => (
                  <button
                    key={c.id}
                    onClick={() => onClientSelectionne(c)}
                    className="w-full text-left px-3 py-2 text-sm hover:bg-accent transition-colors flex items-center gap-2"
                  >
                    <User className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                    <span>
                      {c.nom_complet}
                      {c.telephone && (
                        <span className="text-muted-foreground ml-1 text-xs">· {c.telephone}</span>
                      )}
                    </span>
                  </button>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* ── En-tête ticket + bouton ordonnance ───────────────────────── */}
      <div className="flex items-center justify-between px-4 py-2">
        <h2 className="font-display text-lg">
          Ticket en cours
          {scanEnCours && (
            <span className="ml-2 text-xs text-primary animate-pulse">● Scan…</span>
          )}
        </h2>
        <button
          onClick={onOrdonnanceClick}
          className={`flex items-center gap-1.5 text-xs rounded-lg px-2.5 py-1.5 transition-colors ${
            ordonnanceJointee
              ? "bg-success/10 text-success border border-success/30"
              : "text-muted-foreground hover:bg-surface-strong"
          }`}
          title="Attacher une ordonnance à cette vente"
        >
          <FileText className="h-3.5 w-3.5" />
          {ordonnanceJointee ? "Ord. jointe" : "Ordonnance"}
        </button>
      </div>

      {/* Badge ordonnance jointée */}
      {ordonnanceJointee && (
        <div className="mx-4 mb-1 flex items-center justify-between rounded-lg bg-success/10 border border-success/20 px-3 py-1.5 text-xs">
          <span className="text-success flex items-center gap-1">
            <CheckCircle className="h-3 w-3" />
            {ordonnanceJointee.numero_interne}
            {ordonnanceJointee.prescripteur_nom && ` — ${ordonnanceJointee.prescripteur_nom}`}
          </span>
          <button onClick={onOrdonnanceEffacee} className="text-muted-foreground hover:text-foreground">
            <X className="h-3 w-3" />
          </button>
        </div>
      )}

      {/* ── Lignes panier ────────────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto px-4">
        {lignes.length === 0 ? (
          <div className="text-center py-12 text-sm text-muted-foreground">
            Aucun article. Scannez ou recherchez un médicament.
          </div>
        ) : (
          <ul className="space-y-2 pb-4 pt-1">
            {lignes.map((l) => (
              <LignePanierItem
                key={l.cle}
                ligne={l}
                ordonnanceJointee={!!ordonnanceJointee}
                onModifierQuantite={onModifierQuantite}
                onSupprimer={onSupprimerLigne}
              />
            ))}
          </ul>
        )}
      </div>

      {/* ── Pied de panier ───────────────────────────────────────────── */}
      {lignes.length > 0 && (
        <div className="border-t border-border/70 px-4 py-4 space-y-3 bg-surface/50">
          <div className="flex items-baseline justify-between">
            <span className="text-sm text-muted-foreground">Total</span>
            <span className="numeric font-display text-2xl">{fmtFCFA(total)}</span>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" className="flex-1 gap-2" onClick={onViderPanier}>
              <X className="h-4 w-4" />
              Vider
            </Button>
            {venteIdRecente && (
              <Button
                variant="outline"
                size="icon"
                onClick={onAnnulerVente}
                title="Annuler la dernière vente"
                className="text-destructive border-destructive/40 hover:bg-destructive/10"
              >
                <Ban className="h-4 w-4" />
              </Button>
            )}
            <Button className="flex-1 gap-2" onClick={onEncaisser} disabled={lignes.length === 0}>
              <Receipt className="h-4 w-4" />
              Encaisser
            </Button>
          </div>
        </div>
      )}
    </aside>
  );
}
