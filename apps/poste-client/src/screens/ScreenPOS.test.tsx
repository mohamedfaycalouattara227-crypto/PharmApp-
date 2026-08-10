import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mockListe = vi.hoisted(() => vi.fn());
const mockClients = vi.hoisted(() => vi.fn());
const mockVente = vi.hoisted(() => vi.fn());
const mockRecu = vi.hoisted(() => vi.fn());
const mockToast = vi.hoisted(() => ({ success: vi.fn(), error: vi.fn(), warning: vi.fn() }));

vi.mock("@/lib/api-client", () => ({
  api: {
    catalogue: { medicaments: { liste: mockListe } },
    clients: { rechercher: mockClients, creer: vi.fn() },
    ventes: { creer: mockVente, recu: mockRecu, annuler: vi.fn() },
  },
  ApiError: class ApiError extends Error {
    detail: string;
    constructor(detail: string) { super(detail); this.detail = detail; }
  },
}));
vi.mock("sonner", () => ({ toast: mockToast }));
vi.mock("@/hooks/use-barcode-scanner", () => ({ useCodeBarreScanner: vi.fn() }));
vi.mock("@/components/pos/dialog-paiement", () => ({
  DialogPaiement: ({ onFermer, onValider }: { onFermer: () => void; onValider: (payload: { mode: string; encaisse: number }) => void }) => (
    <div data-testid="dialog-paiement">
      <button onClick={onFermer}>Fermer paiement</button>
      <button onClick={() => onValider({ mode: "especes", encaisse: 1000 })}>Valider paiement</button>
    </div>
  ),
}));
vi.mock("@/components/pos/dialog-ordonnance", () => ({
  DialogOrdonnance: ({ onFermer }: { onFermer: () => void }) => <div data-testid="dialog-ordonnance"><button onClick={onFermer}>Fermer ordonnance</button></div>,
}));
vi.mock("@/components/print/ReceiptTemplate", () => ({ ReceiptTemplate: () => <div data-testid="receipt-template" /> }));

import { ScreenPOS } from "./ScreenPOS";

const medicament = {
  id: "med-1", nom: "Paracétamol 500 mg", dci: "Paracétamol", prix_public: 800,
  prix_vente: 800, stock_total_disponible: 10, seuil_alerte_stock: 3,
  necessite_ordonnance: false, est_produit_controle: false,
};
const rupture = {
  ...medicament, id: "med-2", nom: "Codéine 30 mg", prix_public: 1500,
  stock_total_disponible: 0, necessite_ordonnance: true, est_produit_controle: true,
};

function renderScreen() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><ScreenPOS /></QueryClientProvider>);
}

describe("ScreenPOS — comportement métier du point de vente", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockListe.mockResolvedValue({ results: [medicament, rupture], count: 2 });
    mockClients.mockResolvedValue({ results: [], count: 0 });
    mockVente.mockResolvedValue({ id: "vente-1", numero: "V-001" });
    mockRecu.mockResolvedValue({ id: "recu-1", numero: "V-001", lignes: [] });
  });

  it("affiche l’état initial et n’interroge pas le catalogue sous deux caractères", async () => {
    const user = userEvent.setup();
    renderScreen();
    expect(screen.getByRole("heading", { name: "Point de vente" })).toBeInTheDocument();
    expect(screen.getByText(/Prêt pour la vente/)).toBeInTheDocument();
    await user.type(screen.getByPlaceholderText(/Nom, DCI/), "P");
    await new Promise((resolve) => setTimeout(resolve, 320));
    expect(mockListe).not.toHaveBeenCalled();
  });

  it("recherche les médicaments après le debounce et expose les états de stock", async () => {
    const user = userEvent.setup();
    renderScreen();
    await user.type(screen.getByPlaceholderText(/Nom, DCI/), "Para");
    await waitFor(() => expect(mockListe).toHaveBeenCalledWith(expect.objectContaining({ search: "Para", page_size: 12, est_actif: true })));
    const boutonParacetamol = (await screen.findByText("Paracétamol 500 mg")).closest("button");
    const boutonCodeine = (await screen.findByText("Codéine 30 mg")).closest("button");
    expect(boutonParacetamol).toBeInTheDocument();
    expect(boutonCodeine).toBeDisabled();
    expect(screen.getByText("Rupture")).toBeInTheDocument();
    expect(screen.getByText("Contrôlé")).toBeInTheDocument();
    expect(screen.getByText("Sur ordo.")).toBeInTheDocument();
  });

  it("ajoute, incrémente, décrémente et supprime une ligne du panier", async () => {
    const user = userEvent.setup();
    renderScreen();
    await user.type(screen.getByPlaceholderText(/Nom, DCI/), "Para");
    const resultat = (await screen.findByText("Paracétamol 500 mg")).closest("button")!;
    await user.click(resultat);
    expect(screen.getByText("1 article")).toBeInTheDocument();
    const ligne = screen.getAllByText("Paracétamol 500 mg")
      .map((element) => element.closest("li"))
      .find((li) => li?.querySelectorAll("button").length === 3)!;
    expect(ligne).toHaveTextContent(/× 1/);
    const boutons = ligne.querySelectorAll("button");
    await user.click(boutons[1] as HTMLElement);
    expect(ligne).toHaveTextContent(/× 2/);
    await user.click(boutons[0] as HTMLElement);
    expect(ligne).toHaveTextContent(/× 1/);
    await user.click(boutons[2] as HTMLElement);
    expect(screen.getByText(/Aucun article/)).toBeInTheDocument();
  });

  it("ouvre et ferme le dialogue ordonnance", async () => {
    const user = userEvent.setup();
    renderScreen();
    await user.click(screen.getByRole("button", { name: "Ordonnance" }));
    expect(screen.getByTestId("dialog-ordonnance")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Fermer ordonnance" }));
    expect(screen.queryByTestId("dialog-ordonnance")).not.toBeInTheDocument();
  });

  it("ouvre le paiement par F9 uniquement lorsque le panier n’est pas vide", async () => {
    const user = userEvent.setup();
    renderScreen();
    fireEvent.keyDown(window, { key: "F9" });
    expect(screen.queryByTestId("dialog-paiement")).not.toBeInTheDocument();
    await user.type(screen.getByPlaceholderText(/Nom, DCI/), "Para");
    await user.click((await screen.findByText("Paracétamol 500 mg")).closest("button")!);
    fireEvent.keyDown(window, { key: "F9" });
    expect(screen.getByTestId("dialog-paiement")).toBeInTheDocument();
  });

  it("valide un paiement, vide le panier et charge le reçu", async () => {
    const user = userEvent.setup();
    renderScreen();
    await user.type(screen.getByPlaceholderText(/Nom, DCI/), "Para");
    await user.click((await screen.findByText("Paracétamol 500 mg")).closest("button")!);
    await user.click(screen.getByRole("button", { name: /Encaisser/ }));
    await user.click(screen.getByRole("button", { name: "Valider paiement" }));
    await waitFor(() => expect(mockVente).toHaveBeenCalledWith(expect.objectContaining({ mode_paiement: "especes", montant_encaisse: 1000, panier: [expect.objectContaining({ medicament_id: "med-1", quantite: 1 })] })));
    await waitFor(() => expect(mockRecu).toHaveBeenCalledWith("vente-1"));
    expect(await screen.findByTestId("receipt-template")).toBeInTheDocument();
    expect(screen.getByText(/Aucun article/)).toBeInTheDocument();
  });
});
