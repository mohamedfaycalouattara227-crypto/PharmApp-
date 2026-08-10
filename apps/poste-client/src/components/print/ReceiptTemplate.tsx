/**
 * ReceiptTemplate.tsx — Étape 7 : Modèle de reçu imprimable
 *
 * Deux modes de rendu :
 *  - format="thermique" : 80 mm (POS thermique standard)
 *  - format="a4"        : feuille A4 (courrier/archivage)
 */

import type { RecuDTO } from "@/lib/types";
import { fmtFCFA, LIBELLES_MODE_PAIEMENT } from "@/lib/format";

interface ReceiptProps {
  recu: RecuDTO;
  format?: "thermique" | "a4";
}

export function ReceiptTemplate({ recu, format = "thermique" }: ReceiptProps) {
  const isThermique = format === "thermique";
  const widthClass = isThermique ? "w-72" : "w-full max-w-2xl";

  return (
    <>
      <style>{`
        @media print {
          body > * { display: none !important; }
          #receipt-print-root { display: block !important; }
          #receipt-print-root * { display: block; }
          @page { margin: 0; size: ${isThermique ? "80mm auto" : "A4"}; }
        }
        #receipt-print-root { display: none; }
        #receipt-preview-root { display: block; }
      `}</style>

      {/* Aperçu (visible dans l'UI) */}
      <div
        id="receipt-preview-root"
        className={`${widthClass} font-mono text-xs mx-auto bg-white text-black p-4 shadow-lg border border-border/70`}
      >
        <ReceiptContent recu={recu} isThermique={isThermique} />
      </div>

      {/* Version impression (masquée sauf pendant print) */}
      <div id="receipt-print-root" aria-hidden>
        <div className={`${widthClass} font-mono text-xs mx-auto bg-white text-black p-2`}>
          <ReceiptContent recu={recu} isThermique={isThermique} />
        </div>
      </div>
    </>
  );
}

function ReceiptContent({ recu, isThermique }: { recu: RecuDTO; isThermique: boolean }) {
  const sep = "─".repeat(isThermique ? 32 : 64);

  return (
    <div className="space-y-1">
      {/* En-tête pharmacie */}
      <div className="text-center space-y-0.5">
        <div className="text-sm font-bold uppercase tracking-wider">{recu.pharmacie.nom}</div>
        {recu.pharmacie.adresse && <div>{recu.pharmacie.adresse}</div>}
        {recu.pharmacie.telephone && <div>Tél : {recu.pharmacie.telephone}</div>}
        {recu.pharmacie.numero_agrement && (
          <div>Agrément : {recu.pharmacie.numero_agrement}</div>
        )}
      </div>

      <div className="text-center text-[10px] text-gray-500">{sep}</div>

      {/* Info vente */}
      <div className="flex justify-between">
        <span>Reçu n° {recu.numero}</span>
        {recu.reimprime && <span className="font-bold">[DUPLICATA]</span>}
      </div>
      <div>Date : {recu.date}</div>
      <div>Caissier : {recu.vendeur_nom}</div>
      {recu.client_nom && <div>Client : {recu.client_nom}</div>}
      {recu.est_avoir && recu.vente_origine_numero && (
        <div className="font-bold">AVOIR — Vente origine : {recu.vente_origine_numero}</div>
      )}

      <div className="text-center text-[10px] text-gray-500">{sep}</div>

      {/* Lignes */}
      <div className="space-y-1">
        {recu.lignes.map((l, i) => (
          <div key={i} className="space-y-0.5">
            <div className="font-medium">{l.nom}</div>
            <div className="flex justify-between text-[10px] text-gray-600">
              <span>
                {l.quantite} × {fmtFCFA(l.prix_unitaire)}
              </span>
              <span>{fmtFCFA(l.montant_total)}</span>
            </div>
            {Number(l.taux_remise) > 0 && (
              <div className="text-[10px] text-gray-500">
                Remise {l.taux_remise}%
              </div>
            )}
          </div>
        ))}
      </div>

      <div className="text-center text-[10px] text-gray-500">{sep}</div>

      {/* Totaux */}
      <div className="space-y-0.5">
        <div className="flex justify-between font-bold text-sm border-t border-black pt-1 mt-1">
          <span>TOTAL</span>
          <span>{fmtFCFA(recu.montant_total)}</span>
        </div>
        <div className="flex justify-between text-[10px] text-gray-600">
          <span>
            Payé ({LIBELLES_MODE_PAIEMENT[recu.mode_paiement] ?? recu.mode_paiement})
          </span>
          <span>{fmtFCFA(recu.montant_encaisse)}</span>
        </div>
        {Number(recu.montant_rendu) > 0 && (
          <div className="flex justify-between text-[10px] text-gray-600">
            <span>Monnaie rendue</span>
            <span>{fmtFCFA(recu.montant_rendu)}</span>
          </div>
        )}
      </div>

      <div className="text-center text-[10px] text-gray-500">{sep}</div>

      <div className="text-center text-[10px] text-gray-500 space-y-0.5">
        <div>Merci pour votre confiance.</div>
        <div>Conservez ce reçu — non échangeable.</div>
      </div>
    </div>
  );
}
