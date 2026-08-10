import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it, vi } from "vitest";

const mockMedicaments = vi.hoisted(() => vi.fn());
const mockLots = vi.hoisted(() => vi.fn());
const mockMouvements = vi.hoisted(() => vi.fn());
const mockAlertes = vi.hoisted(() => vi.fn());
const mockResoudre = vi.hoisted(() => vi.fn());
const mockAjuster = vi.hoisted(() => vi.fn());
const mockInventaire = vi.hoisted(() => vi.fn());
vi.mock("@/lib/api-client", () => ({
  api: {
    medicaments: { liste: mockMedicaments }, lots: { liste: mockLots },
    stocks: { mouvements: mockMouvements, ajuster: mockAjuster, demarrerInventaire: mockInventaire },
    alertes: { liste: mockAlertes, resoudre: mockResoudre },
  },
}));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

import { ScreenStock } from "./ScreenStock";

function renderScreen() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><ScreenStock /></QueryClientProvider>);
}

describe("ScreenStock — gestion réelle du stock", () => {
  it("affiche les médicaments et permet une recherche", async () => {
    const user = userEvent.setup();
    mockMedicaments.mockResolvedValue({ results: [{ id: "m1", nom: "Paracétamol", stock_total: 8, seuil_alerte_stock: 10 }], count: 1 });
    mockLots.mockResolvedValue({ results: [], count: 0 });
    mockMouvements.mockResolvedValue({ results: [], count: 0 });
    mockAlertes.mockResolvedValue({ results: [], count: 0 });
    renderScreen();
    expect(await screen.findByText("Paracétamol")).toBeInTheDocument();
    await user.type(screen.getByPlaceholderText("Rechercher un médicament…"), "Para");
    await waitFor(() => expect(mockMedicaments).toHaveBeenLastCalledWith(expect.objectContaining({ search: "Para" })));
  });

  it("affiche les mouvements et transmet leur filtre", async () => {
    const user = userEvent.setup();
    mockMedicaments.mockResolvedValue({ results: [], count: 0 });
    mockLots.mockResolvedValue({ results: [], count: 0 });
    mockMouvements.mockResolvedValue({ results: [{ id: "mv1", type_mouvement: "reception", type_mouvement_libelle: "Réception", medicament_nom: "Paracétamol", lot_nom: "LOT-1", quantite: 4, quantite_apres: 8, cree_le: "2026-08-01T10:00:00Z", reference_document: "REF-1" }], count: 1 });
    mockAlertes.mockResolvedValue({ results: [], count: 0 });
    renderScreen();
    await user.click(screen.getByRole("button", { name: "Mouvements" }));
    expect((await screen.findAllByText("Réception")).some((element) => element.tagName.toLowerCase() === "span")).toBe(true);
    await user.selectOptions(screen.getByRole("combobox"), "reception");
    await waitFor(() => expect(mockMouvements).toHaveBeenLastCalledWith(expect.objectContaining({ type_mouvement: "reception" })));
  });

  it("permet de résoudre une alerte non résolue", async () => {
    const user = userEvent.setup();
    mockMedicaments.mockResolvedValue({ results: [], count: 0 });
    mockLots.mockResolvedValue({ results: [], count: 0 });
    mockMouvements.mockResolvedValue({ results: [], count: 0 });
    mockAlertes.mockResolvedValue({ results: [{ id: "a1", medicament_nom: "Stock critique", niveau: "rupture", stock_au_moment_alerte: 0, seuil_depasse: 5, cree_le: "2026-08-01T10:00:00Z", est_resolue: false }], count: 1 });
    mockResoudre.mockResolvedValue({});
    renderScreen();
    await user.click(screen.getByRole("button", { name: "Alertes" }));
    expect(await screen.findByText("Stock critique")).toBeInTheDocument();
    await user.click(screen.getByTitle("Marquer comme résolue"));
    await waitFor(() => expect(mockResoudre).toHaveBeenCalledWith("a1"));
  });

  it("valide un ajustement de stock avec les champs requis", async () => {
    const user = userEvent.setup();
    mockMedicaments.mockResolvedValue({ results: [], count: 0 });
    mockLots.mockResolvedValue({ results: [], count: 0 });
    mockMouvements.mockResolvedValue({ results: [], count: 0 });
    mockAlertes.mockResolvedValue({ results: [], count: 0 });
    mockAjuster.mockResolvedValue({});
    renderScreen();
    await user.click(screen.getByRole("button", { name: /Ajuster un stock/ }));
    await user.type(screen.getByPlaceholderText(/xxxxxxxx/), "lot-1");
    await user.type(screen.getByPlaceholderText("0"), "12");
    await user.click(screen.getByRole("button", { name: "Valider l'ajustement" }));
    await waitFor(() => expect(mockAjuster).toHaveBeenCalledWith(expect.objectContaining({ lot_id: "lot-1", nouvelle_quantite: 12 })));
  });
});
