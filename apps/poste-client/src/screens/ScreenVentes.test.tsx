import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it, vi } from "vitest";

const mockListe = vi.hoisted(() => vi.fn());
const mockAvoir = vi.hoisted(() => vi.fn());
vi.mock("@/lib/api-client", () => ({
  api: { ventes: { liste: mockListe, avoir: mockAvoir } },
  ApiError: class ApiError extends Error { detail = this.message; },
}));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));
vi.mock("@/lib/format", () => ({ fmtFCFA: (value: number) => `${value} F` }));

import { ScreenVentes } from "./ScreenVentes";

const vente = {
  id: "v-1", numero: "V-001", statut: "validee", client_nom: "Awa Diop",
  mode_paiement: "mobile_money", montant_total: 1600, cree_le: "2026-08-01T10:00:00Z",
  lignes: [{ id: "l-1", medicament_nom: "Paracétamol", quantite: 2, prix_unitaire: 800 }],
};

function renderScreen() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><ScreenVentes /></QueryClientProvider>);
}

describe("ScreenVentes — historique réel", () => {
  it("affiche les ventes et son statut", async () => {
    mockListe.mockResolvedValue({ results: [vente], count: 1 });
    renderScreen();
    expect(await screen.findByText("V-001")).toBeInTheDocument();
    expect(screen.getByText("Validée")).toBeInTheDocument();
    expect(screen.getByText("Awa Diop")).toBeInTheDocument();
    expect(screen.getByText("1600 F")).toBeInTheDocument();
  });

  it("filtre localement par numéro ou client", async () => {
    const user = userEvent.setup();
    mockListe.mockResolvedValue({ results: [vente, { ...vente, id: "v-2", numero: "V-002", client_nom: "Moussa" }], count: 2 });
    renderScreen();
    await screen.findByText("V-001");
    await user.type(screen.getByPlaceholderText(/N° vente/), "Moussa");
    expect(screen.queryByText("V-001")).not.toBeInTheDocument();
    expect(screen.getByText("V-002")).toBeInTheDocument();
  });

  it("transmet le statut et les dates à l’API puis permet d’effacer", async () => {
    const user = userEvent.setup();
    mockListe.mockResolvedValue({ results: [], count: 0 });
    renderScreen();
    await screen.findByText("Aucune vente trouvée");
    await user.selectOptions(screen.getByRole("combobox"), "annulee");
    await waitFor(() => expect(mockListe).toHaveBeenCalledWith(expect.objectContaining({ statut: "annulee" })));
    expect(screen.getByRole("button", { name: /Effacer/ })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Effacer/ }));
    expect(screen.getByRole("combobox")).toHaveValue("");
  });

  it("déplie le détail puis ouvre le dialogue d’avoir", async () => {
    const user = userEvent.setup();
    mockListe.mockResolvedValue({ results: [vente], count: 1 });
    mockAvoir.mockResolvedValue({ total_avoir: 800 });
    renderScreen();
    await user.click(await screen.findByText("V-001"));
    expect(screen.getByText("Détail des lignes")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Avoir/ }));
    expect(screen.getByText(/Créer un avoir/)).toBeInTheDocument();
    const quantite = screen.getByDisplayValue("0");
    await user.clear(screen.getByPlaceholderText(/Ex : Produit/));
    await user.type(screen.getByPlaceholderText(/Ex : Produit/), "Produit endommagé");
    await user.clear(quantite);
    await user.type(quantite, "1");
    await user.click(screen.getByRole("button", { name: "Créer l'avoir" }));
    await waitFor(() => expect(mockAvoir).toHaveBeenCalledWith("v-1", expect.objectContaining({ motif: "Produit endommagé" })));
  });
});
