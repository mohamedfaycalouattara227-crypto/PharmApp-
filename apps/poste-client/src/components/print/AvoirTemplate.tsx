/**
 * AvoirTemplate.tsx — Étape 7 : Modèle d'avoir imprimable
 *
 * Affiche le récapitulatif d'un retour client (avoir).
 * Répond à l'endpoint POST /api/ventes/{id}/avoir/ et affiche sa réponse.
 *
 * Usage similaire à ReceiptTemplate : fenêtre de retour → print().
 */

import { fmtFCFA, fmtDate } from "@/lib/format";

interface AvoirData {
  vente_origine: string;
  motif: string;
  lignes_retournees: Array<{
    medicament_nom: string;
    quantite: number;
    montant: string;
  }>;
  total_avoir: string;
  message: string;
  pharmacie?: {
    nom: string;
    adresse: string;
    telephone: string;
  };
  date?: string;
}

interface AvoirTemplateProps {
  avoir: AvoirData;
  format?: "thermique" | "a4";
}

export function AvoirTemplate({ avoir, format = "thermique" }: AvoirTemplateProps) {
  const isThermique = format === "thermique";
  const widthClass = isThermique ? "w-72" : "w-full max-w-2xl";
  const sep = "─".repeat(isThermique ? 32 : 64);

  return (
    <>
      <style>{`
        @media print {
          body > * { display: none !important; }
          #avoir-print-root { display: block !important; }
          @page { margin: 0; size: ${isThermique ? "80mm auto" : "A4"}; }
        }
        #avoir-print-root { display: none; }
        #avoir-preview-root { display: block; }
      `}</style>

      <div id="avoir-preview-root" className={`${widthClass} font-mono text-xs mx-auto bg-white text-black p-4 shadow-lg border border-border/70`}>
        <AvoirContent avoir={avoir} sep={sep} />
      </div>
      <div id="avoir-print-root" aria-hidden>
        <div className={`${widthClass} font-mono text-xs mx-auto bg-white text-black p-2`}>
          <AvoirContent avoir={avoir} sep={sep} />
        </div>
      </div>
    </>
  );
}

function AvoirContent({ avoir, sep }: { avoir: AvoirData; sep: string }) {
  return (
    <div className="space-y-1">
      {/* En-tête */}
      {avoir.pharmacie && (
        <div className="text-center space-y-0.5">
          <div className="text-sm font-bold uppercase tracking-wider">{avoir.pharmacie.nom}</div>
          <div>{avoir.pharmacie.adresse}</div>
          <div>Tél : {avoir.pharmacie.telephone}</div>
        </div>
      )}
      <div className="text-center text-[10px] text-gray-500">{sep}</div>

      <div className="text-center">
        <div className="text-sm font-bold uppercase">AVOIR / RETOUR CLIENT</div>
        {avoir.date && <div>Date : {fmtDate(avoir.date)}</div>}
        <div>Vente origine : {avoir.vente_origine}</div>
      </div>

      <div className="text-center text-[10px] text-gray-500">{sep}</div>

      <div className="space-y-0.5">
        <div className="font-medium">Motif :</div>
        <div className="text-[10px]">{avoir.motif}</div>
      </div>

      <div className="text-center text-[10px] text-gray-500">{sep}</div>

      <div>
        <div className="font-medium mb-1">Articles retournés :</div>
        {avoir.lignes_retournees.map((l, i) => (
          <div key={i} className="flex justify-between">
            <span>{l.medicament_nom} × {l.quantite}</span>
            <span>{fmtFCFA(l.montant)}</span>
          </div>
        ))}
      </div>

      <div className="text-center text-[10px] text-gray-500">{sep}</div>

      <div className="flex justify-between font-bold text-sm">
        <span>TOTAL AVOIR</span>
        <span>{fmtFCFA(avoir.total_avoir)}</span>
      </div>

      <div className="text-center text-[10px] text-gray-500">{sep}</div>
      <div className="text-center text-[10px] text-gray-400">
        Le stock a été remis à jour.
      </div>
    </div>
  );
}
