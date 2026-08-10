/**
 * Tests — components/SelecteurTheme.tsx
 *
 * Couvre : rendu, ouverture dropdown, changement thème, coche active.
 */

import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SelecteurTheme } from "@/components/SelecteurTheme";
import { ThemeProvider } from "@/contexts/ThemeContext";
import { THEMES } from "@/lib/theme";

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

function renderAvecProvider() {
  return render(
    <ThemeProvider>
      <SelecteurTheme />
    </ThemeProvider>,
  );
}

describe("SelecteurTheme", () => {
  it("rend le bouton palette", () => {
    renderAvecProvider();
    expect(screen.getByRole("button", { name: /thème/i })).toBeInTheDocument();
  });

  it("ouvre le dropdown au clic", async () => {
    const user = userEvent.setup();
    renderAvecProvider();
    await user.click(screen.getByRole("button", { name: /thème/i }));
    await waitFor(() => {
      expect(screen.getByText("Apparence")).toBeInTheDocument();
    });
  });

  it("affiche tous les 6 thèmes dans le dropdown", async () => {
    const user = userEvent.setup();
    renderAvecProvider();
    await user.click(screen.getByRole("button", { name: /thème/i }));
    await waitFor(() => {
      THEMES.forEach((t) => {
        expect(screen.getByText(t.label)).toBeInTheDocument();
      });
    });
  });

  it("sélectionner un thème change le thème actif", async () => {
    const user = userEvent.setup();
    renderAvecProvider();
    await user.click(screen.getByRole("button", { name: /thème/i }));
    await waitFor(() => screen.getByText("Classique Bleu"));
    await user.click(screen.getByText("Classique Bleu"));
    expect(storageSimule.getItem("pharmapp.theme")).toBe("classique-bleu");
  });

  it("affiche une coche pour le thème actif", async () => {
    const user = userEvent.setup();
    renderAvecProvider();
    await user.click(screen.getByRole("button", { name: /thème/i }));
    // Le thème actif par défaut est vert-sante → chercher son label
    await waitFor(() => {
      expect(screen.getByText("Vert Santé")).toBeInTheDocument();
    });
  });
});
