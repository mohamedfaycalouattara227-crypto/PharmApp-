/**
 * Tests — lib/format.ts
 * Couvre : fmtFCFA, fmtNombre, fmtDate, fmtDateCourte, LIBELLES_*
 */

import { describe, it, expect } from "vitest";
import {
  fmtFCFA,
  fmtNombre,
  fmtDate,
  fmtDateCourte,
  LIBELLES_MODE_PAIEMENT,
  LIBELLES_STATUT_BC,
  LIBELLES_ROLE,
  LIBELLES_STATUT_ORDONNANCE,
  LIBELLES_TYPE_CLIENT,
} from "@/lib/format";

describe("fmtFCFA", () => {
  it("formate zéro", () => {
    expect(fmtFCFA(0)).toBe("0 FCFA");
  });

  it("formate un entier positif", () => {
    const res = fmtFCFA(1500);
    expect(res).toContain("1");
    expect(res).toContain("FCFA");
  });

  it("formate un grand nombre avec séparateurs", () => {
    const res = fmtFCFA(1500000);
    expect(res).toContain("FCFA");
    expect(res).toMatch(/1[\s\u00a0]?500[\s\u00a0]?000/);
  });

  it("formate une chaîne numérique", () => {
    expect(fmtFCFA("2500")).toContain("FCFA");
  });

  it("retourne '—' pour NaN", () => {
    expect(fmtFCFA(NaN)).toBe("—");
  });

  it("retourne '—' pour Infinity", () => {
    expect(fmtFCFA(Infinity)).toBe("—");
  });

  it("retourne '—' pour une chaîne invalide", () => {
    expect(fmtFCFA("abc")).toBe("—");
  });

  it("formate un montant négatif", () => {
    const res = fmtFCFA(-500);
    expect(res).toContain("FCFA");
    expect(res).toContain("-");
  });
});

describe("fmtNombre", () => {
  it("formate zéro", () => {
    expect(fmtNombre(0)).toBe("0");
  });

  it("formate un nombre positif", () => {
    const res = fmtNombre(1234);
    expect(res).toContain("1");
    expect(res).toContain("234");
  });

  it("formate une chaîne numérique", () => {
    const res = fmtNombre("9999");
    expect(res).toContain("9");
  });

  it("retourne '—' pour NaN", () => {
    expect(fmtNombre(NaN)).toBe("—");
  });

  it("retourne '—' pour chaîne invalide", () => {
    expect(fmtNombre("xyz")).toBe("—");
  });
});

describe("fmtDate", () => {
  it("formate une chaîne ISO", () => {
    const res = fmtDate("2024-01-15T10:30:00");
    expect(res).toContain("2024");
    expect(res).toContain("15");
  });

  it("formate un objet Date", () => {
    const d = new Date("2024-06-01T08:00:00");
    const res = fmtDate(d);
    expect(res).toContain("2024");
    expect(res).toContain("01");
  });

  it("inclut l'heure", () => {
    const res = fmtDate("2024-03-20T14:45:00");
    expect(res).toMatch(/\d{2}:\d{2}/);
  });
});

describe("fmtDateCourte", () => {
  it("formate en format court sans heure", () => {
    const res = fmtDateCourte("2024-12-25T00:00:00");
    expect(res).toContain("2024");
    expect(res).not.toMatch(/\d{2}:\d{2}:\d{2}/);
  });

  it("retourne une date au format jour/mois/année", () => {
    const res = fmtDateCourte("2024-04-10");
    expect(res).toContain("10");
    expect(res).toContain("04");
    expect(res).toContain("2024");
  });

  it("formate correctement un objet Date", () => {
    const d = new Date("2024-04-10T12:00:00");
    const res = fmtDateCourte(d);
    expect(res).toContain("2024");
    expect(res).toContain("04");
    expect(res).toContain("10");
  });
});

describe("LIBELLES_MODE_PAIEMENT", () => {
  it("contient les 5 modes de paiement", () => {
    expect(Object.keys(LIBELLES_MODE_PAIEMENT)).toHaveLength(5);
  });

  it("a les bons libellés français", () => {
    expect(LIBELLES_MODE_PAIEMENT.especes).toBe("Espèces");
    expect(LIBELLES_MODE_PAIEMENT.mobile_money).toBe("Mobile Money");
    expect(LIBELLES_MODE_PAIEMENT.assurance).toBe("Assurance");
    expect(LIBELLES_MODE_PAIEMENT.credit).toBe("Crédit client");
    expect(LIBELLES_MODE_PAIEMENT.cheque).toBe("Chèque");
  });
});

describe("LIBELLES_STATUT_BC", () => {
  it("contient les 6 statuts de bon de commande", () => {
    expect(Object.keys(LIBELLES_STATUT_BC)).toHaveLength(6);
  });

  it("a le libellé 'Brouillon' pour 'brouillon'", () => {
    expect(LIBELLES_STATUT_BC.brouillon).toBe("Brouillon");
  });

  it("a le libellé 'Annulé' pour 'annule'", () => {
    expect(LIBELLES_STATUT_BC.annule).toBe("Annulé");
  });
});

describe("LIBELLES_ROLE", () => {
  it("contient les 7 rôles", () => {
    expect(Object.keys(LIBELLES_ROLE)).toHaveLength(7);
  });

  it("a le libellé correct pour 'titulaire'", () => {
    expect(LIBELLES_ROLE.titulaire).toBe("Pharmacien(ne) titulaire");
  });

  it("a le libellé correct pour 'administrateur'", () => {
    expect(LIBELLES_ROLE.administrateur).toBe("Administrateur système");
  });

  it("a le libellé correct pour 'stagiaire'", () => {
    expect(LIBELLES_ROLE.stagiaire).toBe("Stagiaire");
  });
});

describe("LIBELLES_STATUT_ORDONNANCE", () => {
  it("contient les 5 statuts d'ordonnance", () => {
    expect(Object.keys(LIBELLES_STATUT_ORDONNANCE)).toHaveLength(5);
  });

  it("a 'Validée' pour 'validee'", () => {
    expect(LIBELLES_STATUT_ORDONNANCE.validee).toBe("Validée");
  });

  it("a 'Expirée' pour 'expiree'", () => {
    expect(LIBELLES_STATUT_ORDONNANCE.expiree).toBe("Expirée");
  });
});

describe("LIBELLES_TYPE_CLIENT", () => {
  it("contient les 3 types de clients", () => {
    expect(Object.keys(LIBELLES_TYPE_CLIENT)).toHaveLength(3);
  });

  it("a 'Particulier' pour 'particulier'", () => {
    expect(LIBELLES_TYPE_CLIENT.particulier).toBe("Particulier");
  });
});
