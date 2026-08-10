/**
 * src/components/pos/recherche-section.tsx
 * Composant atomique — zone de recherche médicament du POS (DT-005)
 * Extrait de PagePOS : champ de recherche + grille de résultats.
 */

import { Search, Loader2, AlertTriangle } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import type { Medicament } from "@/lib/types";
import { fmtFCFA } from "@/lib/format";

interface RechercheSectionProps {
  recherche: string;
  isFetching: boolean;
  resultats?: Medicament[];
  inputRef: React.RefObject<HTMLInputElement>;
  onRechercheChange: (v: string) => void;
  onAjouter: (m: Medicament) => void;
}

export function RechercheSection({
  recherche,
  isFetching,
  resultats,
  inputRef,
  onRechercheChange,
  onAjouter,
}: RechercheSectionProps) {
  return (
    <div className="flex flex-col h-full">
      {/* Champ de recherche */}
      <div className="relative p-4 pb-2">
        <Search className="absolute left-7 top-1/2 -translate-y-1/2 mt-1 h-4 w-4 text-muted-foreground pointer-events-none" />
        {isFetching && (
          <Loader2 className="absolute right-7 top-1/2 -translate-y-1/2 mt-1 h-4 w-4 animate-spin text-muted-foreground pointer-events-none" />
        )}
        <Input
          ref={inputRef}
          value={recherche}
          onChange={(e) => onRechercheChange(e.target.value)}
          placeholder="Médicament, DCI, code-barres… (Ctrl+K)"
          className="pl-9 pr-9 h-11 text-base"
          autoFocus
          autoComplete="off"
        />
      </div>

      {/* Grille de résultats */}
      <div className="flex-1 overflow-y-auto px-4 pb-4">
        {recherche.length < 2 ? (
          <div className="flex flex-col items-center justify-center h-full text-center text-muted-foreground">
            <Search className="h-12 w-12 opacity-10 mb-4" />
            <p className="text-sm">Saisissez au moins 2 caractères</p>
            <p className="text-xs mt-1 opacity-70">ou scannez un code-barres</p>
          </div>
        ) : resultats?.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-40 text-center text-muted-foreground">
            <p className="text-sm">Aucun médicament trouvé pour «&nbsp;{recherche}&nbsp;»</p>
          </div>
        ) : (
          <div className="grid grid-cols-2 xl:grid-cols-3 gap-3">
            {resultats?.map((m) => {
              const rupture = (m.stock_total_disponible ?? m.stock_total ?? 0) <= 0;
              return (
                <button
                  key={m.id}
                  disabled={rupture}
                  onClick={() => !rupture && onAjouter(m)}
                  className={`rounded-xl border p-3 text-left transition-all ${
                    rupture
                      ? "opacity-50 cursor-not-allowed border-border/40 bg-muted/30"
                      : "hover:border-primary/60 hover:shadow-sm hover:bg-accent/30 bg-card"
                  }`}
                >
                  <p className="font-medium text-sm leading-tight line-clamp-2">{m.nom}</p>
                  {m.forme_pharmaceutique && (
                    <p className="text-xs text-muted-foreground mt-0.5 line-clamp-1">
                      {m.forme_pharmaceutique}
                      {m.dosage && ` — ${m.dosage}`}
                    </p>
                  )}
                  <div className="flex items-center justify-between mt-2 gap-1 flex-wrap">
                    <span className="numeric text-sm font-semibold">
                      {fmtFCFA(Number(m.prix_vente ?? m.prix_public ?? 0))}
                    </span>
                    <div className="flex gap-1 flex-wrap">
                      {rupture ? (
                        <Badge variant="destructive" className="text-xs px-1.5 py-0">
                          Rupture
                        </Badge>
                      ) : (
                        <Badge variant="outline" className="text-xs px-1.5 py-0">
                          {m.stock_total_disponible ?? m.stock_total ?? 0}
                        </Badge>
                      )}
                      {m.necessite_ordonnance && (
                        <Badge
                          variant="outline"
                          className="text-xs px-1.5 py-0 border-amber-300 text-amber-700"
                          title="Nécessite une ordonnance"
                        >
                          <AlertTriangle className="h-2.5 w-2.5" />
                        </Badge>
                      )}
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
