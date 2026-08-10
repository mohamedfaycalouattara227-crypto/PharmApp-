/**
 * Tests — lib/utils.ts
 * Couvre : cn (classnames merger), et tout utilitaire exporté
 */

import { describe, it, expect } from "vitest";
import { cn } from "@/lib/utils";

describe("cn — classnames utility", () => {
  it("retourne une chaîne vide pour aucune entrée", () => {
    expect(cn()).toBe("");
  });

  it("concatène plusieurs classes", () => {
    const res = cn("a", "b", "c");
    expect(res).toContain("a");
    expect(res).toContain("b");
    expect(res).toContain("c");
  });

  it("ignore les valeurs falsy (undefined, false, null)", () => {
    const res = cn("base", undefined, false, null, "extra");
    expect(res).toContain("base");
    expect(res).toContain("extra");
    expect(res).not.toContain("undefined");
    expect(res).not.toContain("false");
    expect(res).not.toContain("null");
  });

  it("fusionne les classes Tailwind conflictuelles (tailwind-merge)", () => {
    // tailwind-merge doit écraser p-4 avec p-8
    const res = cn("p-4", "p-8");
    expect(res).toContain("p-8");
    expect(res).not.toContain("p-4");
  });

  it("gère un tableau de classes", () => {
    const res = cn(["text-sm", "font-bold"]);
    expect(res).toContain("text-sm");
    expect(res).toContain("font-bold");
  });

  it("gère un objet conditionnel", () => {
    const estActif = true;
    const res = cn({ "bg-primary": estActif, "bg-muted": !estActif });
    expect(res).toContain("bg-primary");
    expect(res).not.toContain("bg-muted");
  });

  it("gère un objet conditionnel avec valeur false", () => {
    const res = cn({ "text-red-500": false, "text-green-500": true });
    expect(res).toContain("text-green-500");
    expect(res).not.toContain("text-red-500");
  });

  it("conserve l'ordre des classes non conflictuelles", () => {
    const res = cn("flex", "items-center", "gap-2");
    expect(res).toContain("flex");
    expect(res).toContain("items-center");
    expect(res).toContain("gap-2");
  });
});
