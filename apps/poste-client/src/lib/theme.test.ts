/**
 * Tests — lib/theme.ts
 *
 * Couvre : lireThemeSauvegarde, sauvegarderTheme, trouverTheme, appliquerTheme,
 *          THEMES, THEME_PAR_DEFAUT
 */

import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import {
  THEMES,
  THEME_PAR_DEFAUT,
  lireThemeSauvegarde,
  sauvegarderTheme,
  trouverTheme,
  appliquerTheme,
  type NomTheme,
} from "@/lib/theme";

// ── Helpers localStorage simulé ───────────────────────────────────────────────

const localStorageSimule = (() => {
  let store: Record<string, string> = {};
  return {
    getItem: (key: string) => store[key] ?? null,
    setItem: (key: string, value: string) => { store[key] = value; },
    removeItem: (key: string) => { delete store[key]; },
    clear: () => { store = {}; },
  };
})();

// ── Tests ─────────────────────────────────────────────────────────────────────

describe("THEMES", () => {
  it("doit contenir exactement 6 thèmes", () => {
    expect(THEMES).toHaveLength(6);
  });

  it("doit contenir les 6 noms attendus", () => {
    const noms = THEMES.map((t) => t.nom);
    expect(noms).toContain("classique-bleu");
    expect(noms).toContain("vert-sante");
    expect(noms).toContain("sombre-moderne");
    expect(noms).toContain("violet-elegant");
    expect(noms).toContain("orange-dynamique");
    expect(noms).toContain("minimaliste-blanc");
  });

  it("chaque thème a label, description, classeHtml, couleurPrimaire", () => {
    THEMES.forEach((t) => {
      expect(t.label).toBeTruthy();
      expect(t.description).toBeTruthy();
      expect(t.classeHtml).toBeTruthy();
      expect(t.couleurPrimaire).toBeTruthy();
    });
  });
});

describe("THEME_PAR_DEFAUT", () => {
  it("doit être vert-sante", () => {
    expect(THEME_PAR_DEFAUT).toBe("vert-sante");
  });
});

describe("trouverTheme", () => {
  it("retourne la bonne définition pour un nom existant", () => {
    const t = trouverTheme("classique-bleu");
    expect(t.nom).toBe("classique-bleu");
    expect(t.label).toBe("Classique Bleu");
  });

  it("retourne le premier thème pour un nom inconnu", () => {
    const t = trouverTheme("inexistant" as NomTheme);
    expect(t).toBe(THEMES[0]);
  });

  it("retourne la bonne définition pour tous les thèmes connus", () => {
    THEMES.forEach((theme) => {
      expect(trouverTheme(theme.nom)).toBe(theme);
    });
  });
});

describe("lireThemeSauvegarde", () => {
  beforeEach(() => {
    Object.defineProperty(window, "localStorage", {
      value: localStorageSimule,
      writable: true,
    });
    localStorageSimule.clear();
  });

  it("retourne le thème par défaut si rien n'est stocké", () => {
    expect(lireThemeSauvegarde()).toBe(THEME_PAR_DEFAUT);
  });

  it("retourne le thème stocké s'il est valide", () => {
    localStorageSimule.setItem("pharmapp.theme", "violet-elegant");
    expect(lireThemeSauvegarde()).toBe("violet-elegant");
  });

  it("retourne le thème par défaut si la valeur stockée est invalide", () => {
    localStorageSimule.setItem("pharmapp.theme", "theme-bidon");
    expect(lireThemeSauvegarde()).toBe(THEME_PAR_DEFAUT);
  });

  it("retourne tous les thèmes valides correctement", () => {
    THEMES.forEach((t) => {
      localStorageSimule.setItem("pharmapp.theme", t.nom);
      expect(lireThemeSauvegarde()).toBe(t.nom);
    });
  });
});

describe("sauvegarderTheme", () => {
  beforeEach(() => {
    Object.defineProperty(window, "localStorage", {
      value: localStorageSimule,
      writable: true,
    });
    localStorageSimule.clear();
  });

  it("persiste le thème dans localStorage", () => {
    sauvegarderTheme("sombre-moderne");
    expect(localStorageSimule.getItem("pharmapp.theme")).toBe("sombre-moderne");
  });

  it("remplace la valeur précédente", () => {
    sauvegarderTheme("classique-bleu");
    sauvegarderTheme("orange-dynamique");
    expect(localStorageSimule.getItem("pharmapp.theme")).toBe("orange-dynamique");
  });
});

describe("appliquerTheme", () => {
  beforeEach(() => {
    // Réinitialiser les classes HTML
    document.documentElement.className = "";
  });

  afterEach(() => {
    document.documentElement.className = "";
  });

  it("ajoute la classe du thème sur <html>", () => {
    appliquerTheme("classique-bleu");
    expect(document.documentElement.classList.contains("theme-classique-bleu")).toBe(true);
  });

  it("retire les classes des thèmes précédents avant d'ajouter le nouveau", () => {
    appliquerTheme("violet-elegant");
    appliquerTheme("sombre-moderne");
    expect(document.documentElement.classList.contains("theme-violet-elegant")).toBe(false);
    expect(document.documentElement.classList.contains("theme-sombre-moderne")).toBe(true);
  });

  it("ajoute la classe 'light' pour les thèmes clairs", () => {
    appliquerTheme("orange-dynamique");
    expect(document.documentElement.classList.contains("light")).toBe(true);
  });

  it("n'ajoute pas 'light' pour les thèmes sombres", () => {
    appliquerTheme("sombre-moderne");
    expect(document.documentElement.classList.contains("light")).toBe(false);
  });

  it("appliquer tous les thèmes sans erreur", () => {
    THEMES.forEach((t) => {
      expect(() => appliquerTheme(t.nom)).not.toThrow();
    });
  });
});
