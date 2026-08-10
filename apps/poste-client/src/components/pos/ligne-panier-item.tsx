/**
 * src/components/pos/ligne-panier-item.tsx
 * Composant atomique — une ligne du panier (DT-005)
 * Extrait de PagePOS pour isoler la logique d'affichage d'une ligne.
 */

import { Minus, Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { fmtFCFA } from "@/lib/format";
import type { LignePanier } from "./panier-sidebar";

interface LignePanierItemProps {
  ligne: LignePanier;
  ordonnanceJointee: boolean;
  onModifierQuantite: (cle: string, delta: number) => void;
  onSupprimer: (cle: string) => void;
}

export function LignePanierItem({
  ligne: l,
  ordonnanceJointee,
  onModifierQuantite,
  onSupprimer,
}: LignePanierItemProps) {
  const stockRestant = l.stock_disponible - l.quantite;
  const enAlerte  = stockRestant <= 5 && stockRestant > 0;
  const enRupture = stockRestant <= 0;

  return (
    <li
      className={`rounded-xl border p-3 flex items-start gap-3 transition-colors ${
        enRupture
          ? "border-destructive/40 bg-destructive/5"
          : enAlerte
          ? "border-amber-300/60 bg-amber-50/60"
          : "bg-card border-border/60"
      }`}
    >
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-1.5 flex-wrap">
          <span className="font-medium text-sm truncate">{l.nom}</span>
          {enRupture && (
            <Badge variant="destructive" className="text-xs px-1.5 py-0">Rupture !</Badge>
          )}
          {!enRupture && enAlerte && (
            <Badge className="text-xs px-1.5 py-0 bg-amber-100 text-amber-800 border-amber-300">
              Stock bas
            </Badge>
          )}
          {l.est_produit_controle && (
            <Badge variant="outline" className="text-xs px-1.5 py-0 border-purple-300 text-purple-700">
              Contrôlé
            </Badge>
          )}
          {l.necessite_ordonnance && !ordonnanceJointee && (
            <Badge variant="outline" className="text-xs px-1.5 py-0 border-amber-300 text-amber-700">
              Ord. requise
            </Badge>
          )}
        </div>

        <div className="text-xs text-muted-foreground numeric mt-0.5">
          {fmtFCFA(l.prix_unitaire)} × {l.quantite} ={" "}
          <strong>{fmtFCFA(l.prix_unitaire * l.quantite * (1 - l.taux_remise / 100))}</strong>
          {l.taux_remise > 0 && (
            <span className="ml-1 text-success">(−{l.taux_remise}%)</span>
          )}
        </div>

        {stockRestant >= 0 && (
          <div
            className={`text-xs mt-0.5 ${
              enRupture ? "text-destructive" : enAlerte ? "text-amber-600" : "text-muted-foreground"
            }`}
          >
            {enRupture
              ? `Attention : ${l.stock_disponible} dispo en stock`
              : `Reste en stock : ${stockRestant}`}
          </div>
        )}
      </div>

      <div className="flex items-center gap-1 shrink-0">
        <Button
          size="icon" variant="ghost" className="h-7 w-7"
          onClick={() => onModifierQuantite(l.cle, -1)}
        >
          <Minus className="h-3.5 w-3.5" />
        </Button>
        <span className="numeric w-6 text-center font-medium text-sm">{l.quantite}</span>
        <Button
          size="icon" variant="ghost" className="h-7 w-7"
          onClick={() => onModifierQuantite(l.cle, +1)}
          disabled={l.quantite >= l.stock_disponible}
        >
          <Plus className="h-3.5 w-3.5" />
        </Button>
        <Button
          size="icon" variant="ghost" className="h-7 w-7"
          onClick={() => onSupprimer(l.cle)}
        >
          <Trash2 className="h-3.5 w-3.5 text-destructive" />
        </Button>
      </div>
    </li>
  );
}
