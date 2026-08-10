/**
 * Clôture de caisse (§4.7 du cahier des charges).
 *
 * Le titulaire renseigne le fond de caisse à l'ouverture et à la clôture ;
 * l'API calcule les recettes par mode de paiement, le CA de la journée et
 * l'écart de caisse. La clôture est atomique : impossible d'encaisser
 * pendant sa validation côté serveur.
 */

import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Loader2, ClipboardCheck } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Separator } from "@/components/ui/separator";
import { api } from "@/lib/api-client";
import { fmtFCFA, fmtDate } from "@/lib/format";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/_app/cloture")({
  component: PageCloture,
  head: () => ({
    meta: [
      { title: "Clôture de caisse — PharmApp" },
      { name: "description", content: "Fond de caisse, recettes par mode de paiement, écart et notes." },
    ],
  }),
});

function PageCloture() {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["clotures"],
    queryFn: () => api.clotures.liste(),
  });

  const [fondOuverture, setFondOuverture] = useState("0");
  const [fondCloture, setFondCloture] = useState("0");
  const [notes, setNotes] = useState("");

  const cloturer = useMutation({
    mutationFn: () =>
      api.clotures.creer({
        fond_caisse_ouverture: fondOuverture,
        fond_caisse_cloture: fondCloture,
        notes,
      }),
    onSuccess: () => {
      toast.success("Caisse clôturée.");
      void qc.invalidateQueries({ queryKey: ["clotures"] });
      setNotes("");
    },
    onError: (e) => toast.error("Clôture refusée", { description: String(e) }),
  });

  const derniere = data?.results?.[0];

  return (
    <div className="flex h-screen flex-col">
      <header className="border-b border-border/70 bg-surface/60 px-6 py-4 backdrop-blur">
        <h1 className="font-display text-3xl leading-none">Clôture de caisse</h1>
        <p className="text-xs text-muted-foreground mt-1">
          Journée courante — l'écart doit être expliqué s'il dépasse le seuil autorisé.
        </p>
      </header>

      <div className="grid flex-1 min-h-0 grid-cols-1 lg:grid-cols-2 overflow-y-auto">
        <section className="p-8 space-y-6 border-r border-border/70">
          <h2 className="font-display text-2xl">Formulaire de clôture</h2>

          <div className="space-y-4">
            <div>
              <Label>Fond de caisse à l'ouverture</Label>
              <Input
                type="number" className="numeric mt-2 h-12 text-lg"
                value={fondOuverture} onChange={(e) => setFondOuverture(e.target.value)}
              />
            </div>
            <div>
              <Label>Fond de caisse compté à la clôture</Label>
              <Input
                type="number" className="numeric mt-2 h-12 text-lg"
                value={fondCloture} onChange={(e) => setFondCloture(e.target.value)}
              />
            </div>
            <div>
              <Label>Notes & justification d'écart</Label>
              <Textarea
                className="mt-2 min-h-[100px]" value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Exemple : différence de −250 FCFA due à un rendu-monnaie non tracé."
              />
            </div>
            <Button
              size="lg" className="w-full bg-primary text-primary-foreground"
              onClick={() => cloturer.mutate()}
              disabled={cloturer.isPending}
            >
              {cloturer.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <ClipboardCheck className="h-4 w-4" />}
              Clôturer la caisse
            </Button>
          </div>
        </section>

        <section className="p-8 space-y-4">
          <h2 className="font-display text-2xl">Dernière clôture</h2>
          {isLoading ? (
            <div className="text-sm text-muted-foreground flex items-center gap-2">
              <Loader2 className="h-4 w-4 animate-spin" /> Chargement…
            </div>
          ) : derniere ? (
            <div className="card-elevated p-6 space-y-4">
              <div className="flex items-baseline justify-between">
                <span className="text-xs uppercase tracking-wide text-muted-foreground">Date</span>
                <span className="font-medium">{fmtDate(derniere.date_cloture)}</span>
              </div>
              <Separator />
              <LigneStat libelle="Espèces" valeur={derniere.recettes_especes} />
              <LigneStat libelle="Mobile Money" valeur={derniere.recettes_mobile_money} />
              <LigneStat libelle="Assurance" valeur={derniere.recettes_assurance} />
              <LigneStat libelle="Crédit client" valeur={derniere.recettes_credit} />
              <LigneStat libelle="Chèque" valeur={derniere.recettes_cheque} />
              <Separator />
              <LigneStat libelle="Chiffre d'affaires" valeur={derniere.chiffre_affaires} fort />
              <LigneStat libelle="Nombre de ventes" valeur={derniere.nombre_ventes} unite="ventes" />
              <LigneStat libelle="Écart de caisse" valeur={derniere.ecart_caisse} alerte={Number(derniere.ecart_caisse) !== 0} />
              {derniere.notes && (
                <div className="text-xs text-muted-foreground bg-surface-strong rounded-md p-3 mt-2">
                  {derniere.notes}
                </div>
              )}
            </div>
          ) : (
            <div className="text-sm text-muted-foreground">Aucune clôture pour l'instant.</div>
          )}
        </section>
      </div>
    </div>
  );
}

function LigneStat({
  libelle, valeur, fort, alerte, unite,
}: { libelle: string; valeur: string | number; fort?: boolean; alerte?: boolean; unite?: string }) {
  return (
    <div className="flex items-baseline justify-between">
      <span className="text-sm text-muted-foreground">{libelle}</span>
      <span className={cn(
        "numeric",
        fort && "font-display text-money text-2xl",
        alerte && "text-destructive",
      )}>
        {unite ? `${valeur} ${unite}` : fmtFCFA(valeur)}
      </span>
    </div>
  );
}
