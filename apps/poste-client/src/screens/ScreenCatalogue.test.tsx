import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ScreenCatalogue } from "./ScreenCatalogue";

const { apiMock } = vi.hoisted(() => ({ apiMock: {
  medicaments: { liste: vi.fn(), creer: vi.fn(), modifier: vi.fn(), importerCSV: vi.fn() },
  categories: { liste: vi.fn(), creer: vi.fn() },
} }));
vi.mock("@/lib/api-client", () => ({ api: apiMock, ApiError: class ApiError extends Error { detail = "Erreur API"; } }));

function renderScreen(role = "gestionnaire_stock") {
  window.sessionStorage.setItem("pharmapp.role", role);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><ScreenCatalogue /></QueryClientProvider>);
}

describe("ScreenCatalogue", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    apiMock.medicaments.liste.mockResolvedValue({ results: [{ id: "m1", nom: "Paracétamol", prix_public: "1500", stock_total: 12, categorie: null, code_cis: "", code_barre: "" }], count: 1 });
    apiMock.categories.liste.mockResolvedValue({ results: [{ id: "c1", nom: "Antalgiques", code: "ANT", description: "" }] });
    apiMock.medicaments.creer.mockResolvedValue({ id: "m2" });
    apiMock.categories.creer.mockResolvedValue({ id: "c2" });
  });

  it("affiche le catalogue et masque les actions d’écriture pour un caissier", async () => {
    renderScreen("caissier");
    expect(await screen.findByText("Catalogue")).toBeInTheDocument();
    expect(await screen.findByText("Paracétamol")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Nouveau médicament/i })).not.toBeInTheDocument();
  });

  it("affiche le formulaire, valide les champs obligatoires et crée un médicament", async () => {
    renderScreen();
    await screen.findByText("Paracétamol");
    fireEvent.click(screen.getByRole("button", { name: /Nouveau médicament/i }));
    expect(screen.getByRole("heading", { name: "Nouveau médicament" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Enregistrer" }));
    const champs = screen.getAllByRole("textbox");
    expect(champs[1]).toBeInvalid();
    fireEvent.change(champs[1], { target: { value: "Ibuprofène" } });
    fireEvent.click(screen.getByRole("button", { name: "Enregistrer" }));
    expect(screen.getAllByRole("spinbutton")[0]).toBeInvalid();
    fireEvent.change(screen.getAllByRole("spinbutton")[0], { target: { value: "2000" } });
    fireEvent.click(screen.getByRole("button", { name: "Enregistrer" }));
    await waitFor(() => expect(apiMock.medicaments.creer).toHaveBeenCalled());
  });

  it("filtre les résultats avec la recherche et change d’onglet", async () => {
    renderScreen();
    await screen.findByText("Paracétamol");
    const search = screen.getByPlaceholderText(/Rechercher/i);
    fireEvent.change(search, { target: { value: "para" } });
    await waitFor(() => expect(apiMock.medicaments.liste).toHaveBeenCalledWith(expect.objectContaining({ search: "para" })));
    fireEvent.click(screen.getByRole("button", { name: /Catégories/i }));
    expect(await screen.findByText("Antalgiques")).toBeInTheDocument();
  });
});
