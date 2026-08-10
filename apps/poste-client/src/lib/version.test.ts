import { describe, expect, it } from "vitest";

import { COMMIT, libelleSupport, libelleVersion, VERSION } from "./version";

describe("identité de build du poste client", () => {
  it("expose une version sémantique injectée au build", () => {
    expect(VERSION).toMatch(/^\d+\.\d+\.\d+(-[0-9A-Za-z.-]+)?$/);
    expect(VERSION).not.toBe("0.0.0-inconnue");
  });

  it("compose un libellé lisible en pied de page", () => {
    expect(libelleVersion()).toContain(`PharmApp v${VERSION}`);
  });

  it("compose une chaîne exhaustive pour le support", () => {
    const texte = libelleSupport();
    expect(texte).toContain(VERSION);
    expect(texte).toContain(COMMIT);
  });
});
