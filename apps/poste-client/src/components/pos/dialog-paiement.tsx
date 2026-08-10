/**
 * dialog-paiement.tsx — Étape 11 : Encaissement complet
 *
 * Onglets : Espèces | Mobile Money (réf. transaction) | Crédit (vérif. encours) | Assurance
 * Props étendues : clientId, onValider reçoit maintenant { mode, encaisse, referenceMobileMoney }
 */

import { useEffect, useState } from "react";
import { Loader2, AlertTriangle } from "lucide-react";

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogDescription,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { fmtFCFA, LIBELLES_MODE_PAIEMENT } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { ModePaiement, Client } from "@/lib/types";
import { api } from "@/lib/api-client";

export interface PayloadPaiement {
  mode: ModePaiement;
  encaisse: number;
  referenceMobileMoney?: string;
}

const MODES: ModePaiement[] = ["especes", "mobile_money", "credit", "assurance", "cheque"];

/**
 * Boîte d'encaissement — modes de paiement avec champs contextuels :
 * - Espèces : montant encaissé + rendu monnaie
 * - Mobile Money : référence transaction obligatoire
 * - Crédit : vérification encours vs plafond
 * - Assurance : taux prise en charge
 */
export function DialogPaiement({
  ouvert,
  onFermer,
  total,
  onValider,
  enCours,
  clientId,
}: {
  ouvert: boolean;
  onFermer: () => void;
  total: number;
  onValider: (payload: PayloadPaiement) => void;
  enCours: boolean;
  clientId?: string | null;
}) {
  const [mode, setMode] = useState<ModePaiement>("especes");
  const [encaisse, setEncaisse] = useState<string>("");
  const [referenceMobileMoney, setReferenceMobileMoney] = useState("");
  const [clientInfo, setClientInfo] = useState<Client | null>(null);
  const [loadingClient, setLoadingClient] = useState(false);

  // Charger les infos client (encours, plafond, assureur) quand nécessaire
  useEffect(() => {
    if (!ouvert || !clientId) {
      setClientInfo(null);
      return;
    }
    let actif = true;
    setLoadingClient(true);
    api.clients.detail(clientId)
      .then((c) => { if (actif) setClientInfo(c as Client); })
      .catch(() => { /* ignoré */ })
      .finally(() => { if (actif) setLoadingClient(false); });
    return () => { actif = false; };
  }, [ouvert, clientId]);

  useEffect(() => {
    if (ouvert) {
      setEncaisse(String(total));
      setMode("especes");
      setReferenceMobileMoney("");
    }
  }, [ouvert, total]);

  const montantEncaisse = Number(encaisse) || 0;
  const rendu = mode === "especes" ? montantEncaisse - total : 0;
  const insuffisant = mode === "especes" && montantEncaisse < total;

  // Calcul crédit : encours actuel + total > plafond → refus
  const encours = Number(clientInfo?.encours_credit ?? 0);
  const plafond = Number(clientInfo?.plafond_credit ?? 0);
  const creditAutorise = clientInfo?.credit_autorise ?? false;
  const depassePlafond = mode === "credit" && (encours + total > plafond);
  const creditInterdit = mode === "credit" && !creditAutorise;

  // Taux assurance
  const tauxAssurance = Number(clientInfo?.taux_prise_en_charge ?? 0);
  const montantAssurance = mode === "assurance" ? (total * tauxAssurance) / 100 : 0;
  const resteACharge = total - montantAssurance;

  const peutValider =
    !enCours &&
    !insuffisant &&
    !(mode === "mobile_money" && !referenceMobileMoney.trim()) &&
    !(creditInterdit || depassePlafond);

  function handleValider() {
    onValider({
      mode,
      encaisse: mode === "especes" ? montantEncaisse : total,
      referenceMobileMoney: mode === "mobile_money" ? referenceMobileMoney.trim() : undefined,
    });
  }

  return (
    <Dialog open={ouvert} onOpenChange={(v) => !v && onFermer()}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle className="font-display text-2xl">Encaissement</DialogTitle>
          <DialogDescription>
            Total à percevoir :{" "}
            <span className="numeric text-money font-medium">{fmtFCFA(total)}</span>
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-5">
          {/* Sélecteur mode */}
          <div>
            <Label className="text-xs uppercase tracking-wide text-muted-foreground">
              Mode de paiement
            </Label>
            <div className="mt-2 grid grid-cols-3 gap-2">
              {MODES.map((m) => (
                <button
                  key={m}
                  type="button"
                  onClick={() => setMode(m)}
                  className={cn(
                    "rounded-lg border px-3 py-3 text-sm font-medium transition-colors",
                    mode === m
                      ? "border-primary bg-primary/10 text-foreground"
                      : "border-border text-muted-foreground hover:bg-surface-strong",
                  )}
                >
                  {LIBELLES_MODE_PAIEMENT[m]}
                </button>
              ))}
            </div>
          </div>

          {/* ── Espèces ──────────────────────────────────────────────────── */}
          {mode === "especes" && (
            <div>
              <Label
                htmlFor="encaisse"
                className="text-xs uppercase tracking-wide text-muted-foreground"
              >
                Montant reçu (FCFA)
              </Label>
              <Input
                id="encaisse"
                type="number"
                inputMode="numeric"
                min={0}
                value={encaisse}
                onChange={(e) => setEncaisse(e.target.value)}
                className="numeric mt-2 h-14 text-2xl"
                autoFocus
              />
              <div
                className={cn(
                  "mt-3 flex items-baseline justify-between rounded-lg px-4 py-3",
                  insuffisant
                    ? "bg-destructive/10 text-destructive"
                    : "bg-success/10 text-success",
                )}
              >
                <span className="text-xs uppercase tracking-wide">
                  {insuffisant ? "Manque" : "Monnaie à rendre"}
                </span>
                <span className="numeric font-display text-2xl">
                  {fmtFCFA(Math.abs(rendu))}
                </span>
              </div>
            </div>
          )}

          {/* ── Mobile Money ─────────────────────────────────────────────── */}
          {mode === "mobile_money" && (
            <div className="space-y-3">
              <div className="rounded-lg bg-surface-strong p-3 text-sm">
                <p className="font-medium">Montant à envoyer</p>
                <p className="numeric text-2xl font-display mt-1">{fmtFCFA(total)}</p>
              </div>
              <div>
                <Label
                  htmlFor="ref-mobile"
                  className="text-xs uppercase tracking-wide text-muted-foreground"
                >
                  Référence transaction <span className="text-destructive">*</span>
                </Label>
                <Input
                  id="ref-mobile"
                  type="text"
                  placeholder="Ex : OM-2024-123456789"
                  value={referenceMobileMoney}
                  onChange={(e) => setReferenceMobileMoney(e.target.value)}
                  className="mt-2 font-mono"
                  autoFocus
                />
                {!referenceMobileMoney.trim() && (
                  <p className="mt-1 text-xs text-destructive">
                    La référence de transaction est obligatoire.
                  </p>
                )}
              </div>
            </div>
          )}

          {/* ── Crédit client ─────────────────────────────────────────────── */}
          {mode === "credit" && (
            <div className="space-y-3">
              {loadingClient && (
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Chargement infos crédit…
                </div>
              )}

              {!clientId && (
                <div className="flex items-start gap-2 rounded-lg bg-amber-50 border border-amber-200 p-3 text-sm text-amber-800">
                  <AlertTriangle className="h-4 w-4 mt-0.5 shrink-0" />
                  <span>
                    Aucun client sélectionné. Attachez un client pour activer le crédit.
                  </span>
                </div>
              )}

              {clientId && clientInfo && (
                <>
                  {creditInterdit && (
                    <div className="flex items-start gap-2 rounded-lg bg-destructive/10 border border-destructive/30 p-3 text-sm text-destructive">
                      <AlertTriangle className="h-4 w-4 mt-0.5 shrink-0" />
                      <span>Le crédit n'est pas autorisé pour ce client.</span>
                    </div>
                  )}
                  {!creditInterdit && (
                    <div className="rounded-lg border p-4 space-y-2">
                      <div className="flex justify-between text-sm">
                        <span className="text-muted-foreground">Encours actuel</span>
                        <span className="numeric font-medium">{fmtFCFA(encours)}</span>
                      </div>
                      <div className="flex justify-between text-sm">
                        <span className="text-muted-foreground">Plafond autorisé</span>
                        <span className="numeric font-medium">{fmtFCFA(plafond)}</span>
                      </div>
                      <div className="flex justify-between text-sm border-t pt-2">
                        <span className="text-muted-foreground">Encours après achat</span>
                        <span
                          className={cn(
                            "numeric font-medium",
                            depassePlafond ? "text-destructive" : "text-success",
                          )}
                        >
                          {fmtFCFA(encours + total)}
                        </span>
                      </div>
                      {depassePlafond && (
                        <div className="flex items-start gap-2 rounded-lg bg-destructive/10 border border-destructive/30 p-3 text-sm text-destructive mt-2">
                          <AlertTriangle className="h-4 w-4 mt-0.5 shrink-0" />
                          <span>
                            Dépassement du plafond de crédit (
                            {fmtFCFA(encours + total - plafond)} de dépassement).
                          </span>
                        </div>
                      )}
                    </div>
                  )}
                </>
              )}
            </div>
          )}

          {/* ── Assurance ─────────────────────────────────────────────────── */}
          {mode === "assurance" && (
            <div className="space-y-3">
              {!clientId && (
                <div className="flex items-start gap-2 rounded-lg bg-amber-50 border border-amber-200 p-3 text-sm text-amber-800">
                  <AlertTriangle className="h-4 w-4 mt-0.5 shrink-0" />
                  <span>
                    Aucun client sélectionné. Attachez un client assuré pour calculer la
                    prise en charge.
                  </span>
                </div>
              )}
              {clientInfo && (
                <div className="rounded-lg border p-4 space-y-2">
                  {clientInfo.assureur && (
                    <div className="flex justify-between text-sm">
                      <span className="text-muted-foreground">Assureur</span>
                      <span className="font-medium">{clientInfo.assureur}</span>
                    </div>
                  )}
                  <div className="flex justify-between text-sm">
                    <span className="text-muted-foreground">
                      Prise en charge ({tauxAssurance} %)
                    </span>
                    <span className="numeric font-medium text-success">
                      − {fmtFCFA(montantAssurance)}
                    </span>
                  </div>
                  <div className="flex justify-between text-sm border-t pt-2">
                    <span className="text-muted-foreground">Reste à charge</span>
                    <span className="numeric font-display text-xl font-medium">
                      {fmtFCFA(resteACharge)}
                    </span>
                  </div>
                </div>
              )}
              {!clientInfo && !loadingClient && clientId && (
                <div className="rounded-lg bg-surface-strong p-3 text-sm text-muted-foreground">
                  Montant total : <span className="numeric font-medium">{fmtFCFA(total)}</span>
                </div>
              )}
            </div>
          )}

          {/* ── Chèque ───────────────────────────────────────────────────── */}
          {mode === "cheque" && (
            <div className="rounded-lg bg-surface-strong p-4 text-sm">
              <p className="font-medium">Paiement par chèque</p>
              <p className="text-muted-foreground mt-1">
                Montant : <span className="numeric font-medium">{fmtFCFA(total)}</span>
              </p>
              <p className="text-muted-foreground mt-1 text-xs">
                Vérifiez la provision avant validation.
              </p>
            </div>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onFermer} disabled={enCours}>
            Retour
          </Button>
          <Button
            className="bg-money text-money-foreground hover:bg-money/90"
            onClick={handleValider}
            disabled={!peutValider}
          >
            {enCours && <Loader2 className="h-4 w-4 animate-spin" />}
            Valider la vente
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
