/**
 * Registre des produits contrôlés — Route `/produits-controles`
 *
 * Étape 13 — CDC §4.10
 *
 * Tableau du registre ANRP : date, produit, acheteur, ordonnance, quantité, vendeur.
 * Filtres : par médicament et par période.
 * Export PDF du registre (bouton → GET /api/produits-controles/export-registre/).
 *
 * Accès : pharmacien_adjoint minimum (caissier redirigé).
 */

import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  FileText, Download, Filter, Search, ShieldAlert, Loader2,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";

import { api } from "@/lib/api-client";
import type { RegistreProduitControle } from "@/lib/types";

export const Route = createFileRoute("/_app/produits-controles")({
  component: PageProduitsControles,
  head: () => ({
    meta: [
      { title: "Registre produits contrôlés — PharmApp" },
      {
        name: "description",
        content:
          "Registre réglementaire des stupéfiants et psychotropes (ANRP — Burkina Faso).",
      },
    ],
  }),
});

const LIBELLES_MOUVEMENT: Record<string, string> = {
  entree: "Entrée",
  sortie_vente: "Sortie (vente)",
  retour: "Retour fournisseur",
  mise_au_rebut: "Rebut",
  controle_autorite: "Contrôle autorités",
};

const COULEURS_MOUVEMENT: Record<string, string> = {
  sortie_vente: "bg-red-100 text-red-800 border-red-200",
  entree: "bg-green-100 text-green-800 border-green-200",
  retour: "bg-blue-100 text-blue-800 border-blue-200",
  mise_au_rebut: "bg-gray-100 text-gray-700 border-gray-200",
  controle_autorite: "bg-purple-100 text-purple-800 border-purple-200",
};

function PageProduitsControles() {
  const [filtreDate1, setFiltreDate1] = useState("");
  const [filtreDate2, setFiltreDate2] = useState("");
  const [filtreProduit, setFiltreProduit] = useState("");
  const [filtresActifs, setFiltresActifs] = useState<{
    date_debut?: string;
    date_fin?: string;
    medicament?: string;
  }>({});

  const { data, isLoading, isError } = useQuery({
    queryKey: ["produits-controles", filtresActifs],
    queryFn: () =>
      api.produitsControles.liste({
        ...(filtresActifs.date_debut ? { date_debut: filtresActifs.date_debut } : {}),
        ...(filtresActifs.date_fin ? { date_fin: filtresActifs.date_fin } : {}),
        ...(filtresActifs.medicament ? { medicament: filtresActifs.medicament } : {}),
        page_size: "100",
      }),
  });

  const entrees: RegistreProduitControle[] = data?.results ?? [];

  function appliquerFiltres() {
    setFiltresActifs({
      ...(filtreDate1 ? { date_debut: filtreDate1 } : {}),
      ...(filtreDate2 ? { date_fin: filtreDate2 } : {}),
    });
  }

  function reinitialiserFiltres() {
    setFiltreDate1("");
    setFiltreDate2("");
    setFiltreProduit("");
    setFiltresActifs({});
  }

  function exporterPDF() {
    const url = api.produitsControles.exportRegistreUrl({
      date_debut: filtresActifs.date_debut,
      date_fin: filtresActifs.date_fin,
      medicament: filtresActifs.medicament,
    });
    window.open(url, "_blank");
  }

  return (
    <div className="flex flex-col gap-6 p-6 max-w-screen-xl mx-auto">
      {/* En-tête */}
      <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <ShieldAlert className="h-5 w-5 text-destructive" />
            <h1 className="font-display text-2xl">Registre produits contrôlés</h1>
          </div>
          <p className="text-sm text-muted-foreground mt-1">
            Registre réglementaire ANRP — Stupéfiants &amp; psychotropes.
            Ce registre est <strong>immuable</strong> (obligation légale de traçabilité).
          </p>
        </div>
        <Button onClick={exporterPDF} className="gap-2 shrink-0">
          <Download className="h-4 w-4" />
          Exporter PDF
        </Button>
      </div>

      <Separator />

      {/* Filtres */}
      <div className="rounded-xl border bg-card p-4">
        <div className="flex items-center gap-2 mb-3">
          <Filter className="h-4 w-4 text-muted-foreground" />
          <span className="text-sm font-medium">Filtres</span>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div>
            <Label className="text-xs text-muted-foreground uppercase tracking-wide">
              Date début
            </Label>
            <Input
              type="date"
              value={filtreDate1}
              onChange={(e) => setFiltreDate1(e.target.value)}
              className="mt-1"
            />
          </div>
          <div>
            <Label className="text-xs text-muted-foreground uppercase tracking-wide">
              Date fin
            </Label>
            <Input
              type="date"
              value={filtreDate2}
              onChange={(e) => setFiltreDate2(e.target.value)}
              className="mt-1"
            />
          </div>
          <div className="flex items-end gap-2">
            <Button
              onClick={appliquerFiltres}
              size="sm"
              className="gap-1"
            >
              <Search className="h-3.5 w-3.5" />
              Filtrer
            </Button>
            {Object.keys(filtresActifs).length > 0 && (
              <Button
                variant="outline"
                size="sm"
                onClick={reinitialiserFiltres}
              >
                Réinitialiser
              </Button>
            )}
          </div>
        </div>
      </div>

      {/* État */}
      {isLoading && (
        <div className="flex items-center justify-center py-16 text-muted-foreground gap-2">
          <Loader2 className="h-5 w-5 animate-spin" />
          Chargement du registre…
        </div>
      )}

      {isError && (
        <div className="rounded-xl border border-destructive/30 bg-destructive/10 p-6 text-center text-destructive">
          Impossible de charger le registre. Vérifiez vos droits d'accès.
        </div>
      )}

      {!isLoading && !isError && entrees.length === 0 && (
        <div className="rounded-xl border bg-card p-12 text-center">
          <ShieldAlert className="h-10 w-10 text-muted-foreground mx-auto mb-3 opacity-40" />
          <p className="font-medium">Aucun mouvement enregistré</p>
          <p className="text-sm text-muted-foreground mt-1">
            Aucun produit contrôlé n'a été délivré sur la période sélectionnée.
          </p>
        </div>
      )}

      {!isLoading && !isError && entrees.length > 0 && (
        <div className="rounded-xl border overflow-hidden">
          <div className="flex items-center justify-between px-4 py-3 bg-muted/30 border-b">
            <span className="text-sm text-muted-foreground">
              {entrees.length} mouvement{entrees.length > 1 ? "s" : ""}
            </span>
            <span className="text-xs text-muted-foreground">
              Registre immuable — aucune modification possible
            </span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-muted/20 text-muted-foreground text-xs uppercase tracking-wide">
                  <th className="px-4 py-3 text-left font-medium">Date</th>
                  <th className="px-4 py-3 text-left font-medium">Mouvement</th>
                  <th className="px-4 py-3 text-left font-medium">Produit</th>
                  <th className="px-4 py-3 text-left font-medium">Lot</th>
                  <th className="px-4 py-3 text-right font-medium">Qté</th>
                  <th className="px-4 py-3 text-left font-medium">Patient / Acheteur</th>
                  <th className="px-4 py-3 text-left font-medium">Ordonnance</th>
                  <th className="px-4 py-3 text-left font-medium">Prescripteur</th>
                  <th className="px-4 py-3 text-left font-medium">Vendeur</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {entrees.map((e) => (
                  <tr key={e.id} className="hover:bg-muted/10 transition-colors">
                    <td className="px-4 py-3 tabular-nums text-muted-foreground whitespace-nowrap">
                      {new Date(e.cree_le).toLocaleDateString("fr-FR", {
                        day: "2-digit",
                        month: "2-digit",
                        year: "numeric",
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${
                          COULEURS_MOUVEMENT[e.type_mouvement] ?? "bg-gray-100 text-gray-700"
                        }`}
                      >
                        {LIBELLES_MOUVEMENT[e.type_mouvement] ?? e.type_mouvement}
                      </span>
                    </td>
                    <td className="px-4 py-3 font-medium">
                      {e.medicament_nom ?? e.medicament}
                    </td>
                    <td className="px-4 py-3 font-mono text-xs text-muted-foreground">
                      {e.numero_lot_fabricant || "—"}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums font-medium">
                      {e.quantite_mouvement} {e.unite}
                    </td>
                    <td className="px-4 py-3 text-muted-foreground">
                      {e.patient_nom || "—"}
                    </td>
                    <td className="px-4 py-3">
                      {e.ordonnance_numero ? (
                        <span className="flex items-center gap-1 text-xs">
                          <FileText className="h-3 w-3 text-muted-foreground" />
                          {e.ordonnance_numero}
                        </span>
                      ) : (
                        <span className="text-muted-foreground">—</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-muted-foreground text-xs">
                      {e.prescripteur_nom || "—"}
                    </td>
                    <td className="px-4 py-3 text-muted-foreground text-xs">
                      {e.effectue_par_nom ?? e.effectue_par}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
