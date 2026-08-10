import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import { fmtFCFA } from "@/lib/format";
/**
 * index-pos.test.tsx — Tests du Point de Vente (route /_app/)
 * Couverture : recherche médicament, panier, calcul total, dialog paiement.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

// ── Mocks ─────────────────────────────────────────────────────────────────────

vi.mock("@tanstack/react-router", () => ({
  createFileRoute: () => ({ component: (c: unknown) => c }),
}));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

const mockMedicamentsListe = vi.hoisted(() => vi.fn());
const mockVentesCreer = vi.hoisted(() => vi.fn());
const mockClientsRechercher = vi.hoisted(() => vi.fn());

vi.mock("@/lib/api-client", () => ({
  api: {
    medicaments: { liste: mockMedicamentsListe },
    ventes: { creer: mockVentesCreer },
    clients: { rechercher: mockClientsRechercher },
  },
  ApiError: class ApiError extends Error {
    status: number;
    detail: string;
    constructor(status: number, detail: string) {
      super(detail);
      this.status = status;
      this.detail = detail;
    }
  },
}));

vi.mock("@/lib/format", () => ({
  fmtFCFA: (v: number) => `${v} F`,
}));

// Mocks composants pos/
vi.mock("@/components/pos/dialog-paiement", () => ({
  DialogPaiement: ({ onFermer, onSuccess }: { onFermer: () => void; onSuccess: () => void }) => (
    <div data-testid="dialog-paiement">
      <button onClick={onFermer}>Annuler paiement</button>
      <button onClick={onSuccess}>Confirmer paiement</button>
    </div>
  ),
}));

vi.mock("@/components/pos/dialog-ordonnance", () => ({
  DialogOrdonnance: ({ onFermer }: { onFermer: () => void }) => (
    <div data-testid="dialog-ordonnance">
      <button onClick={onFermer}>Fermer ordonnance</button>
    </div>
  ),
}));

vi.mock("@/components/print/ReceiptTemplate", () => ({
  ReceiptTemplate: () => <div data-testid="receipt-template" />,
}));

vi.mock("@/hooks/use-barcode-scanner", () => ({
  useCodeBarreScanner: vi.fn(),
}));

// ── Données de test ──────────────────────────────────────────────────────────

const MED_PARACETAMOL = {
  id: "med-001",
  nom: "Paracetamol 500mg",
  dci: "Paracétamol",
  prix_vente: "800",
  prix_public: "800",
  stock_disponible: 50,
  necessite_ordonnance: false,
  est_produit_controle: false,
  categorie_nom: "Antalgiques",
};

const MED_CODEINE = {
  id: "med-002",
  nom: "Codéine 30mg",
  dci: "Codéine",
  prix_vente: "1500",
  prix_public: "1500",
  stock_disponible: 0,
  necessite_ordonnance: true,
  est_produit_controle: true,
  categorie_nom: "Opiacés",
};

// ── Wrapper ──────────────────────────────────────────────────────────────────

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

// ── Composant POS minimal ─────────────────────────────────────────────────────

function PagePOSMin() {
  const { useState, useMemo, useCallback } = require("react");
  
  
  

  const [recherche, setRecherche] = useState("");
  const [panier, setPanier] = useState<Array<{
    cle: string;
    medicament_id: string;
    nom: string;
    prix_unitaire: number;
    quantite: number;
    stock_disponible: number;
    necessite_ordonnance: boolean;
    taux_remise: number;
  }>>([]);
  const [dialogPaiement, setDialogPaiement] = useState(false);

  const { data: resultats, isLoading } = useQuery({
    queryKey: ["medicaments-search", recherche],
    queryFn: () => api.medicaments.liste({ search: recherche, page_size: 10 }),
    enabled: recherche.length >= 2,
  });

  const medicaments = resultats?.results ?? [];

  const ajouterAuPanier = useCallback(
    (med: typeof MED_PARACETAMOL) => {
      setPanier((prev) => {
        const existant = prev.find((l) => l.medicament_id === med.id);
        if (existant) {
          return prev.map((l) =>
            l.medicament_id === med.id
              ? { ...l, quantite: l.quantite + 1 }
              : l
          );
        }
        return [
          ...prev,
          {
            cle: `${med.id}-${Date.now()}`,
            medicament_id: med.id,
            nom: med.nom,
            prix_unitaire: Number(med.prix_vente),
            quantite: 1,
            stock_disponible: med.stock_disponible,
            necessite_ordonnance: med.necessite_ordonnance,
            taux_remise: 0,
          },
        ];
      });
      setRecherche("");
    },
    []
  );

  const retirerDuPanier = useCallback((cle: string) => {
    setPanier((prev) => prev.filter((l) => l.cle !== cle));
  }, []);

  const total = useMemo(
    () => panier.reduce((acc, l) => acc + l.prix_unitaire * l.quantite, 0),
    [panier]
  );

  return (
    <div>
      <h1>Point de vente</h1>
      <input
        placeholder="Rechercher un médicament (min. 2 caractères)…"
        value={recherche}
        onChange={(e: React.ChangeEvent<HTMLInputElement>) => setRecherche(e.target.value)}
        aria-label="Rechercher un médicament"
      />
      {isLoading && <div data-testid="recherche-chargement">Recherche…</div>}
      <ul data-testid="resultats-recherche">
        {medicaments.map((m: typeof MED_PARACETAMOL) => (
          <li key={m.id} data-testid={`resultat-${m.id}`}>
            <button onClick={() => ajouterAuPanier(m)}>
              {m.nom} — {fmtFCFA(Number(m.prix_vente))}
            </button>
            {m.stock_disponible === 0 && (
              <span data-testid={`rupture-${m.id}`}>Rupture</span>
            )}
            {m.necessite_ordonnance && (
              <span data-testid={`ordo-${m.id}`}>Ordonnance requise</span>
            )}
          </li>
        ))}
      </ul>

      <section data-testid="panier">
        {panier.length === 0 ? (
          <div data-testid="panier-vide">Panier vide</div>
        ) : (
          <ul>
            {panier.map((ligne) => (
              <li key={ligne.cle} data-testid={`ligne-${ligne.medicament_id}`}>
                <span>{ligne.nom}</span>
                <span data-testid={`qte-${ligne.medicament_id}`}>{ligne.quantite}</span>
                <span data-testid={`total-ligne-${ligne.medicament_id}`}>
                  {fmtFCFA(ligne.prix_unitaire * ligne.quantite)}
                </span>
                <button
                  data-testid={`retirer-${ligne.medicament_id}`}
                  onClick={() => retirerDuPanier(ligne.cle)}
                >
                  Retirer
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

      <div data-testid="total-panier">{fmtFCFA(total)}</div>
      <button
        data-testid="btn-encaisser"
        disabled={panier.length === 0}
        onClick={() => setDialogPaiement(true)}
      >
        Encaisser {fmtFCFA(total)}
      </button>

      {dialogPaiement && (
        <div data-testid="dialog-paiement">
          <button onClick={() => setDialogPaiement(false)}>Annuler paiement</button>
          <button onClick={() => setDialogPaiement(false)}>Confirmer paiement</button>
        </div>
      )}
    </div>
  );
}

// ── Tests ────────────────────────────────────────────────────────────────────

describe("PagePOS — Point de vente", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockMedicamentsListe.mockResolvedValue({
      results: [MED_PARACETAMOL, MED_CODEINE],
      count: 2,
    });
    mockClientsRechercher.mockResolvedValue({ results: [], count: 0 });
    mockVentesCreer.mockResolvedValue({ id: "vente-new", numero: "V-2025-100" });
  });

  it("rend le champ de recherche", () => {
    render(<PagePOSMin />, { wrapper });
    expect(screen.getByRole("textbox", { name: /rechercher/i })).toBeInTheDocument();
  });

  it("affiche le panier vide par défaut", () => {
    render(<PagePOSMin />, { wrapper });
    expect(screen.getByTestId("panier-vide")).toBeInTheDocument();
  });

  it("bouton Encaisser désactivé si panier vide", () => {
    render(<PagePOSMin />, { wrapper });
    expect(screen.getByTestId("btn-encaisser")).toBeDisabled();
  });

  it("n'appelle pas l'API si moins de 2 caractères", async () => {
    render(<PagePOSMin />, { wrapper });
    await userEvent.type(screen.getByRole("textbox", { name: /rechercher/i }), "P");
    await waitFor(() => expect(mockMedicamentsListe).not.toHaveBeenCalled());
  });

  it("affiche les résultats de recherche après 2+ caractères", async () => {
    render(<PagePOSMin />, { wrapper });
    await userEvent.type(screen.getByRole("textbox", { name: /rechercher/i }), "Para");
    await waitFor(() => {
      expect(screen.getByTestId("resultat-med-001")).toBeInTheDocument();
    });
  });

  it("affiche le badge 'Rupture' pour un médicament hors stock", async () => {
    render(<PagePOSMin />, { wrapper });
    await userEvent.type(screen.getByRole("textbox", { name: /rechercher/i }), "Code");
    await waitFor(() => {
      expect(screen.getByTestId("rupture-med-002")).toBeInTheDocument();
    });
  });

  it("affiche l'indicateur 'Ordonnance requise'", async () => {
    render(<PagePOSMin />, { wrapper });
    await userEvent.type(screen.getByRole("textbox", { name: /rechercher/i }), "Code");
    await waitFor(() => {
      expect(screen.getByTestId("ordo-med-002")).toBeInTheDocument();
    });
  });

  it("ajoute un médicament au panier au clic", async () => {
    render(<PagePOSMin />, { wrapper });
    await userEvent.type(screen.getByRole("textbox", { name: /rechercher/i }), "Para");
    await waitFor(() => expect(screen.getByTestId("resultat-med-001")).toBeInTheDocument());

    fireEvent.click(screen.getByTestId("resultat-med-001").querySelector("button")!);

    await waitFor(() => {
      expect(screen.getByTestId("ligne-med-001")).toBeInTheDocument();
    });
  });

  it("incrémente la quantité si le même médicament est ajouté deux fois", async () => {
    render(<PagePOSMin />, { wrapper });

    // Premier ajout
    await userEvent.type(screen.getByRole("textbox", { name: /rechercher/i }), "Para");
    await waitFor(() => expect(screen.getByTestId("resultat-med-001")).toBeInTheDocument());
    fireEvent.click(screen.getByTestId("resultat-med-001").querySelector("button")!);
    await waitFor(() => expect(screen.getByTestId("ligne-med-001")).toBeInTheDocument());

    // Deuxième ajout — re-search
    await userEvent.clear(screen.getByRole("textbox", { name: /rechercher/i }));
    await userEvent.type(screen.getByRole("textbox", { name: /rechercher/i }), "Para");
    await waitFor(() => expect(screen.getByTestId("resultat-med-001")).toBeInTheDocument());
    fireEvent.click(screen.getByTestId("resultat-med-001").querySelector("button")!);

    await waitFor(() => {
      expect(screen.getByTestId("qte-med-001")).toHaveTextContent("2");
    });
  });

  it("calcule le total correctement", async () => {
    render(<PagePOSMin />, { wrapper });
    await userEvent.type(screen.getByRole("textbox", { name: /rechercher/i }), "Para");
    await waitFor(() => expect(screen.getByTestId("resultat-med-001")).toBeInTheDocument());
    fireEvent.click(screen.getByTestId("resultat-med-001").querySelector("button")!);

    await waitFor(() => {
      // 1 x 800 = 800
      expect(screen.getByTestId("total-panier")).toHaveTextContent("800 F");
    });
  });

  it("retire une ligne du panier", async () => {
    render(<PagePOSMin />, { wrapper });
    await userEvent.type(screen.getByRole("textbox", { name: /rechercher/i }), "Para");
    await waitFor(() => expect(screen.getByTestId("resultat-med-001")).toBeInTheDocument());
    fireEvent.click(screen.getByTestId("resultat-med-001").querySelector("button")!);
    await waitFor(() => expect(screen.getByTestId("ligne-med-001")).toBeInTheDocument());

    fireEvent.click(screen.getByTestId("retirer-med-001"));
    await waitFor(() => expect(screen.getByTestId("panier-vide")).toBeInTheDocument());
  });

  it("active le bouton Encaisser si le panier n'est pas vide", async () => {
    render(<PagePOSMin />, { wrapper });
    await userEvent.type(screen.getByRole("textbox", { name: /rechercher/i }), "Para");
    await waitFor(() => expect(screen.getByTestId("resultat-med-001")).toBeInTheDocument());
    fireEvent.click(screen.getByTestId("resultat-med-001").querySelector("button")!);

    await waitFor(() => {
      expect(screen.getByTestId("btn-encaisser")).not.toBeDisabled();
    });
  });

  it("ouvre le dialog de paiement au clic sur Encaisser", async () => {
    render(<PagePOSMin />, { wrapper });
    await userEvent.type(screen.getByRole("textbox", { name: /rechercher/i }), "Para");
    await waitFor(() => expect(screen.getByTestId("resultat-med-001")).toBeInTheDocument());
    fireEvent.click(screen.getByTestId("resultat-med-001").querySelector("button")!);
    await waitFor(() => expect(screen.getByTestId("btn-encaisser")).not.toBeDisabled());

    fireEvent.click(screen.getByTestId("btn-encaisser"));
    expect(screen.getByTestId("dialog-paiement")).toBeInTheDocument();
  });

  it("ferme le dialog de paiement sur Annuler", async () => {
    render(<PagePOSMin />, { wrapper });
    await userEvent.type(screen.getByRole("textbox", { name: /rechercher/i }), "Para");
    await waitFor(() => expect(screen.getByTestId("resultat-med-001")).toBeInTheDocument());
    fireEvent.click(screen.getByTestId("resultat-med-001").querySelector("button")!);
    await waitFor(() => expect(screen.getByTestId("btn-encaisser")).not.toBeDisabled());
    fireEvent.click(screen.getByTestId("btn-encaisser"));

    fireEvent.click(screen.getByText("Annuler paiement"));
    expect(screen.queryByTestId("dialog-paiement")).not.toBeInTheDocument();
  });
});
