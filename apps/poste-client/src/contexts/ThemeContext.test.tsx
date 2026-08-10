/**
 * Tests — contexts/ThemeContext.tsx
 *
 * Couvre : ThemeProvider, useTheme, changerTheme, persistance, valeurs initiales.
 */

import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, act, renderHook } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ThemeProvider, useTheme } from "@/contexts/ThemeContext";
import { THEMES, THEME_PAR_DEFAUT } from "@/lib/theme";
import type { ReactNode } from "react";

// ── Wrapper utilitaire ────────────────────────────────────────────────────────

function Wrapper({ children }: { children: ReactNode }) {
  return <ThemeProvider>{children}</ThemeProvider>;
}

// ── Composant de test simple ──────────────────────────────────────────────────

function ComposantTestTheme() {
  const { themeActif, changerTheme, themes, definitionActive } = useTheme();
  return (
    <div>
      <span data-testid="theme-actif">{themeActif}</span>
      <span data-testid="label-actif">{definitionActive.label}</span>
      <span data-testid="nb-themes">{themes.length}</span>
      {themes.map((t) => (
        <button
          key={t.nom}
          data-testid={`btn-${t.nom}`}
          onClick={() => changerTheme(t.nom)}
        >
          {t.label}
        </button>
      ))}
    </div>
  );
}

// ── localStorage simulé ───────────────────────────────────────────────────────

const storageSimule = (() => {
  let store: Record<string, string> = {};
  return {
    getItem: (k: string) => store[k] ?? null,
    setItem: (k: string, v: string) => { store[k] = v; },
    removeItem: (k: string) => { delete store[k]; },
    clear: () => { store = {}; },
  };
})();

beforeEach(() => {
  Object.defineProperty(window, "localStorage", { value: storageSimule, writable: true });
  storageSimule.clear();
  document.documentElement.className = "";
});

afterEach(() => {
  document.documentElement.className = "";
});

// ── Tests ─────────────────────────────────────────────────────────────────────

describe("ThemeProvider", () => {
  it("rend ses enfants sans erreur", () => {
    render(
      <ThemeProvider>
        <span data-testid="enfant">Contenu</span>
      </ThemeProvider>,
    );
    expect(screen.getByTestId("enfant")).toBeInTheDocument();
  });

  it("fournit le thème par défaut si rien n'est stocké", () => {
    render(<ComposantTestTheme />, { wrapper: Wrapper });
    expect(screen.getByTestId("theme-actif").textContent).toBe(THEME_PAR_DEFAUT);
  });

  it("fournit les 6 thèmes disponibles", () => {
    render(<ComposantTestTheme />, { wrapper: Wrapper });
    expect(screen.getByTestId("nb-themes").textContent).toBe("6");
  });

  it("affiche le bon label pour le thème actif", () => {
    render(<ComposantTestTheme />, { wrapper: Wrapper });
    const defaut = THEMES.find((t) => t.nom === THEME_PAR_DEFAUT)!;
    expect(screen.getByTestId("label-actif").textContent).toBe(defaut.label);
  });
});

describe("useTheme", () => {
  it("lève une erreur hors ThemeProvider", () => {
    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    expect(() => renderHook(() => useTheme())).toThrow(
      "useTheme doit être utilisé dans un ThemeProvider",
    );
    consoleSpy.mockRestore();
  });

  it("retourne le contexte complet dans un ThemeProvider", () => {
    const { result } = renderHook(() => useTheme(), { wrapper: Wrapper });
    expect(result.current.themeActif).toBe(THEME_PAR_DEFAUT);
    expect(result.current.themes).toHaveLength(6);
    expect(result.current.changerTheme).toBeTypeOf("function");
    expect(result.current.definitionActive).toBeTruthy();
  });
});

describe("changerTheme", () => {
  it("met à jour le thème actif", async () => {
    const user = userEvent.setup();
    render(<ComposantTestTheme />, { wrapper: Wrapper });

    await user.click(screen.getByTestId("btn-classique-bleu"));

    expect(screen.getByTestId("theme-actif").textContent).toBe("classique-bleu");
  });

  it("met à jour le label correspondant", async () => {
    const user = userEvent.setup();
    render(<ComposantTestTheme />, { wrapper: Wrapper });

    await user.click(screen.getByTestId("btn-violet-elegant"));

    expect(screen.getByTestId("label-actif").textContent).toBe("Violet Élégant");
  });

  it("applique la classe CSS sur <html>", async () => {
    const user = userEvent.setup();
    render(<ComposantTestTheme />, { wrapper: Wrapper });

    await user.click(screen.getByTestId("btn-sombre-moderne"));

    expect(document.documentElement.classList.contains("theme-sombre-moderne")).toBe(true);
  });

  it("persiste le thème dans localStorage", async () => {
    const user = userEvent.setup();
    render(<ComposantTestTheme />, { wrapper: Wrapper });

    await user.click(screen.getByTestId("btn-orange-dynamique"));

    expect(storageSimule.getItem("pharmapp.theme")).toBe("orange-dynamique");
  });

  it("changer de thème plusieurs fois fonctionne", async () => {
    const user = userEvent.setup();
    render(<ComposantTestTheme />, { wrapper: Wrapper });

    await user.click(screen.getByTestId("btn-classique-bleu"));
    await user.click(screen.getByTestId("btn-minimaliste-blanc"));
    await user.click(screen.getByTestId("btn-violet-elegant"));

    expect(screen.getByTestId("theme-actif").textContent).toBe("violet-elegant");
  });
});

describe("persistance au montage", () => {
  it("lit le thème depuis localStorage si disponible", () => {
    storageSimule.setItem("pharmapp.theme", "classique-bleu");
    render(<ComposantTestTheme />, { wrapper: Wrapper });
    expect(screen.getByTestId("theme-actif").textContent).toBe("classique-bleu");
  });
});
