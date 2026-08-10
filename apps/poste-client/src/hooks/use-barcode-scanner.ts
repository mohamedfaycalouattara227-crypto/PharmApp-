/**
 * src/hooks/use-barcode-scanner.ts
 * Hook React — Lecteur code-barres USB/HID (DT-006)
 *
 * Les lecteurs code-barres HID émulent un clavier : ils envoient les
 * caractères du code-barres suivis d'un Enter. Ce hook intercepte ce flux
 * en écoutant les keydown globaux avec un buffer temporisé.
 *
 * Architecture :
 *  - Buffer d'accumulation avec flush après DELAI_FLUSH ms sans saisie
 *  - Détection automatique : si la saisie arrive trop vite pour un humain
 *    (< DELAI_INTER_TOUCHE ms entre chaque touche) → c'est un scanner
 *  - Ignoré si le focus est sur un champ de formulaire (saisie manuelle)
 *
 * Utilisation dans le POS :
 *   const { dernierCode } = useCodeBarreScanner({
 *     onScan: (code) => ajouterParCode(code),
 *     actif: true,
 *   });
 */

import { useCallback, useEffect, useRef, useState } from "react";

interface OptionsScanner {
  /** Appelé avec le code scanné (après Enter) */
  onScan: (code: string) => void;
  /** Activer/désactiver le hook */
  actif?: boolean;
  /** Longueur minimale d'un code valide (défaut : 4) */
  longueurMin?: number;
  /** Délai max entre deux touches pour considérer que c'est un scanner (ms) */
  delaiInterTouche?: number;
  /** Délai avant flush automatique du buffer (ms) */
  delaiFLush?: number;
}

interface EtatScanner {
  /** Dernier code détecté */
  dernierCode: string | null;
  /** True pendant un scan en cours */
  scanEnCours: boolean;
}

const CHAMPS_FORMULAIRE = ["INPUT", "TEXTAREA", "SELECT"];

export function useCodeBarreScanner({
  onScan,
  actif = true,
  longueurMin = 4,
  delaiInterTouche = 50,
  delaiFLush = 100,
}: OptionsScanner): EtatScanner {
  const bufferRef = useRef<string[]>([]);
  const derniereToucheRef = useRef<number>(0);
  const timerFlushRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [dernierCode, setDernierCode] = useState<string | null>(null);
  const [scanEnCours, setScanEnCours] = useState(false);

  const flush = useCallback(() => {
    const code = bufferRef.current.join("");
    bufferRef.current = [];
    setScanEnCours(false);
    if (code.length >= longueurMin) {
      setDernierCode(code);
      onScan(code);
    }
  }, [longueurMin, onScan]);

  const onKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (!actif) return;

      // Ignorer si focus sur un champ de saisie humaine
      const tag = (e.target as HTMLElement)?.tagName ?? "";
      if (CHAMPS_FORMULAIRE.includes(tag)) return;

      const maintenant = Date.now();
      const derniereTouche = derniereToucheRef.current;
      const delai = maintenant - derniereTouche;
      derniereToucheRef.current = maintenant;

      // Annuler le flush différé
      if (timerFlushRef.current) clearTimeout(timerFlushRef.current);

      if (e.key === "Enter") {
        // Fin du scan
        if (bufferRef.current.length > 0) {
          flush();
          e.preventDefault(); // Empêche la soumission de formulaire
        }
        return;
      }

      // Caractère unique → accumuler si la vitesse de frappe ressemble à un scanner
      if (e.key.length === 1) {
        // Si le délai inter-touche est humain (> delaiInterTouche) ET le buffer
        // est vide, c'est probablement une saisie clavier manuelle → ignorer
        if (
          derniereTouche !== 0 &&
          delai > delaiInterTouche &&
          bufferRef.current.length === 0
        ) {
          return;
        }

        bufferRef.current.push(e.key);
        setScanEnCours(true);

        // Flush automatique si plus de saisie
        timerFlushRef.current = setTimeout(flush, delaiFLush);
      }
    },
    [actif, flush, delaiInterTouche, delaiFLush]
  );

  useEffect(() => {
    if (!actif) return;
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      if (timerFlushRef.current) clearTimeout(timerFlushRef.current);
    };
  }, [actif, onKeyDown]);

  return { dernierCode, scanEnCours };
}
