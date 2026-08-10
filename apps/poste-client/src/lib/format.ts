/** Formatage FCFA + dates FR-BF + libellés. */

export function fmtFCFA(montant: number | string): string {
  const n = typeof montant === "string" ? Number(montant) : montant;
  if (!Number.isFinite(n)) return "—";
  return new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 0 }).format(n) + " FCFA";
}

export function fmtNombre(n: number | string): string {
  const v = typeof n === "string" ? Number(n) : n;
  return Number.isFinite(v) ? new Intl.NumberFormat("fr-FR").format(v) : "—";
}

export function fmtDate(iso: string | Date): string {
  const d = typeof iso === "string" ? new Date(iso) : iso;
  return new Intl.DateTimeFormat("fr-FR", {
    day: "2-digit", month: "short", year: "numeric",
    hour: "2-digit", minute: "2-digit",
  }).format(d);
}

export function fmtDateCourte(iso: string | Date): string {
  const d = typeof iso === "string" ? new Date(iso) : iso;
  return new Intl.DateTimeFormat("fr-FR", {
    day: "2-digit", month: "2-digit", year: "numeric",
  }).format(d);
}

export const LIBELLES_MODE_PAIEMENT: Record<string, string> = {
  especes: "Espèces",
  mobile_money: "Mobile Money",
  assurance: "Assurance",
  credit: "Crédit client",
  cheque: "Chèque",
};

export const LIBELLES_STATUT_BC: Record<string, string> = {
  brouillon: "Brouillon",
  envoye: "Envoyé",
  partiel: "Partiel",
  recu: "Reçu",
  cloture: "Clôturé",
  annule: "Annulé",
};

export const LIBELLES_ROLE: Record<string, string> = {
  stagiaire:           "Stagiaire",
  caissier:            "Caissier(ère)",
  assistant:           "Pharmacien(ne) assistant(e)",
  gestionnaire_stock:  "Gestionnaire de stock",
  pharmacien_adjoint:  "Pharmacien(ne) adjoint(e)",
  titulaire:           "Pharmacien(ne) titulaire",
  administrateur:      "Administrateur système",
};

export const LIBELLES_STATUT_ORDONNANCE: Record<string, string> = {
  en_attente: "En attente",
  validee:    "Validée",
  utilisee:   "Utilisée",
  refusee:    "Refusée",
  expiree:    "Expirée",
};

export const LIBELLES_TYPE_CLIENT: Record<string, string> = {
  particulier: "Particulier",
  assurance:   "Assurance / Mutuelle",
  institution: "Institution",
};
