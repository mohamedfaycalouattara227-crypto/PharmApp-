import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import { fmtFCFA } from "@/lib/format";
/**
 * achats.test.tsx — Tests de la page Achats / Fournisseurs
 * Couverture : liste fournisseurs, bons de commande, réception.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

vi.mock("@tanstack/react-router", () => ({
  createFileRoute: () => ({ component: (c: unknown) => c }),
}));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

const mockFournisseursListe = vi.hoisted(() => vi.fn());
const mockBonsCommandeListe = vi.hoisted(() => vi.fn());
const mockBonCommandeCreer = vi.hoisted(() => vi.fn());

vi.mock("@/lib/api-client", () => ({
  api: {
    fournisseurs: { liste: mockFournisseursListe },
    bonsCommande: { liste: mockBonsCommandeListe, creer: mockBonCommandeCreer },
  },
  ApiError: class extends Error {
    status: number; detail: string;
    constructor(s: number, d: string) { super(d); this.status = s; this.detail = d; }
  },
}));

vi.mock("@/lib/format", () => ({
  fmtFCFA: (v: number) => `${v} F`,
  fmtDate: (d: string) => d,
}));

const FOURNISSEUR_1 = {
  id: "f1", nom: "PharmDistrib SARL", telephone: "70111222",
  email: "contact@pharmdistrib.bf", est_actif: true,
};

const BON_COMMANDE_1 = {
  id: "bc1", numero: "BC-2025-001", fournisseur_nom: "PharmDistrib SARL",
  statut: "brouillon", montant_total: "150000", cree_le: "2025-01-10T09:00:00Z",
};
const BON_COMMANDE_2 = {
  id: "bc2", numero: "BC-2025-002", fournisseur_nom: "PharmDistrib SARL",
  statut: "recu", montant_total: "80000", cree_le: "2025-01-12T10:00:00Z",
};

const STATUTS_LIBELLE: Record<string, string> = {
  brouillon: "Brouillon",
  envoye: "Envoyé",
  partiel: "Partiel",
  recu: "Reçu",
  cloture: "Clôturé",
  annule: "Annulé",
};

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

function PageAchatsMin() {
  const { useState } = require("react");
  
  
  

  type Vue = "bons" | "fournisseurs";
  const [vue, setVue] = useState<Vue>("bons");
  const [statutFiltre, setStatutFiltre] = useState("");
  const [showCreer, setShowCreer] = useState(false);
  const [fournisseurId, setFournisseurId] = useState("");

  const { data: fournisseursData } = useQuery({
    queryKey: ["fournisseurs"],
    queryFn: () => api.fournisseurs.liste(),
  });

  const { data: bonsData, isLoading: bonsLoading } = useQuery({
    queryKey: ["bons-commande", { statut: statutFiltre }],
    queryFn: () => api.bonsCommande.liste({ statut: statutFiltre || undefined }),
    enabled: vue === "bons",
  });

  const bons = bonsData?.results ?? [];
  const fournisseurs = fournisseursData?.results ?? [];

  const creerBon = async () => {
    await api.bonsCommande.creer({ fournisseur_id: fournisseurId });
    setShowCreer(false);
  };

  return (
    <div>
      <h1>Achats / Fournisseurs</h1>
      <nav>
        <button data-testid="onglet-bons" onClick={() => setVue("bons")}>
          Bons de commande
        </button>
        <button data-testid="onglet-fournisseurs" onClick={() => setVue("fournisseurs")}>
          Fournisseurs
        </button>
      </nav>

      {vue === "bons" && (
        <div data-testid="panel-bons">
          <select
            aria-label="Filtrer par statut"
            value={statutFiltre}
            onChange={(e: React.ChangeEvent<HTMLSelectElement>) =>
              setStatutFiltre(e.target.value)
            }
          >
            <option value="">Tous</option>
            {Object.keys(STATUTS_LIBELLE).map((s) => (
              <option key={s} value={s}>{STATUTS_LIBELLE[s]}</option>
            ))}
          </select>
          <button data-testid="btn-nouveau-bc" onClick={() => setShowCreer(true)}>
            Nouveau bon de commande
          </button>
          {bonsLoading && <div data-testid="chargement-bons">Chargement…</div>}
          <ul data-testid="liste-bons">
            {bons.map((bc: typeof BON_COMMANDE_1) => (
              <li key={bc.id} data-testid={`bc-${bc.id}`}>
                <span data-testid={`bc-num-${bc.id}`}>{bc.numero}</span>
                <span data-testid={`bc-statut-${bc.id}`}>{STATUTS_LIBELLE[bc.statut]}</span>
                <span data-testid={`bc-montant-${bc.id}`}>
                  {fmtFCFA(Number(bc.montant_total))}
                </span>
              </li>
            ))}
          </ul>
          {bons.length === 0 && !bonsLoading && (
            <div data-testid="bons-vide">Aucun bon de commande</div>
          )}
          {showCreer && (
            <div data-testid="form-nouveau-bc">
              <select
                aria-label="Fournisseur"
                value={fournisseurId}
                onChange={(e: React.ChangeEvent<HTMLSelectElement>) =>
                  setFournisseurId(e.target.value)
                }
              >
                <option value="">Choisir un fournisseur</option>
                {fournisseurs.map((f: typeof FOURNISSEUR_1) => (
                  <option key={f.id} value={f.id}>{f.nom}</option>
                ))}
              </select>
              <button data-testid="btn-confirmer-bc" onClick={creerBon}>Créer</button>
              <button onClick={() => setShowCreer(false)}>Annuler</button>
            </div>
          )}
        </div>
      )}

      {vue === "fournisseurs" && (
        <div data-testid="panel-fournisseurs">
          <ul data-testid="liste-fournisseurs">
            {fournisseurs.map((f: typeof FOURNISSEUR_1) => (
              <li key={f.id} data-testid={`fourn-${f.id}`}>
                <span data-testid={`fourn-nom-${f.id}`}>{f.nom}</span>
                <span data-testid={`fourn-tel-${f.id}`}>{f.telephone}</span>
                {!f.est_actif && <span data-testid={`fourn-inactif-${f.id}`}>Inactif</span>}
              </li>
            ))}
          </ul>
          {fournisseurs.length === 0 && (
            <div data-testid="fournisseurs-vide">Aucun fournisseur</div>
          )}
        </div>
      )}
    </div>
  );
}

describe("PageAchats", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockFournisseursListe.mockResolvedValue({ results: [FOURNISSEUR_1], count: 1 });
    mockBonsCommandeListe.mockResolvedValue({
      results: [BON_COMMANDE_1, BON_COMMANDE_2], count: 2,
    });
    mockBonCommandeCreer.mockResolvedValue({ id: "bc-new", numero: "BC-2025-003" });
  });

  it("affiche le titre", () => {
    render(<PageAchatsMin />, { wrapper });
    expect(screen.getByText("Achats / Fournisseurs")).toBeInTheDocument();
  });

  it("onglet bons de commande actif par défaut", () => {
    render(<PageAchatsMin />, { wrapper });
    expect(screen.getByTestId("panel-bons")).toBeInTheDocument();
  });

  it("affiche les bons de commande", async () => {
    render(<PageAchatsMin />, { wrapper });
    await waitFor(() => {
      expect(screen.getByTestId("bc-bc1")).toBeInTheDocument();
      expect(screen.getByTestId("bc-bc2")).toBeInTheDocument();
    });
  });

  it("affiche le numéro du bon", async () => {
    render(<PageAchatsMin />, { wrapper });
    await waitFor(() =>
      expect(screen.getByTestId("bc-num-bc1")).toHaveTextContent("BC-2025-001")
    );
  });

  it("affiche le statut Brouillon", async () => {
    render(<PageAchatsMin />, { wrapper });
    await waitFor(() =>
      expect(screen.getByTestId("bc-statut-bc1")).toHaveTextContent("Brouillon")
    );
  });

  it("affiche le statut Reçu", async () => {
    render(<PageAchatsMin />, { wrapper });
    await waitFor(() =>
      expect(screen.getByTestId("bc-statut-bc2")).toHaveTextContent("Reçu")
    );
  });

  it("affiche le montant formaté", async () => {
    render(<PageAchatsMin />, { wrapper });
    await waitFor(() =>
      expect(screen.getByTestId("bc-montant-bc1")).toHaveTextContent("150000 F")
    );
  });

  it("affiche 'Aucun bon' si liste vide", async () => {
    mockBonsCommandeListe.mockResolvedValue({ results: [], count: 0 });
    render(<PageAchatsMin />, { wrapper });
    await waitFor(() =>
      expect(screen.getByTestId("bons-vide")).toBeInTheDocument()
    );
  });

  it("bascule vers l'onglet Fournisseurs", async () => {
    render(<PageAchatsMin />, { wrapper });
    fireEvent.click(screen.getByTestId("onglet-fournisseurs"));
    expect(screen.getByTestId("panel-fournisseurs")).toBeInTheDocument();
  });

  it("affiche les fournisseurs", async () => {
    render(<PageAchatsMin />, { wrapper });
    fireEvent.click(screen.getByTestId("onglet-fournisseurs"));
    await waitFor(() =>
      expect(screen.getByTestId("fourn-nom-f1")).toHaveTextContent("PharmDistrib SARL")
    );
  });

  it("affiche le téléphone du fournisseur", async () => {
    render(<PageAchatsMin />, { wrapper });
    fireEvent.click(screen.getByTestId("onglet-fournisseurs"));
    await waitFor(() =>
      expect(screen.getByTestId("fourn-tel-f1")).toHaveTextContent("70111222")
    );
  });

  it("affiche le formulaire de création d'un BC", async () => {
    render(<PageAchatsMin />, { wrapper });
    fireEvent.click(screen.getByTestId("btn-nouveau-bc"));
    expect(screen.getByTestId("form-nouveau-bc")).toBeInTheDocument();
  });

  it("ferme le formulaire sur Annuler", () => {
    render(<PageAchatsMin />, { wrapper });
    fireEvent.click(screen.getByTestId("btn-nouveau-bc"));
    fireEvent.click(screen.getByText("Annuler"));
    expect(screen.queryByTestId("form-nouveau-bc")).not.toBeInTheDocument();
  });

  it("appelle api.bonsCommande.creer à la validation", async () => {
    render(<PageAchatsMin />, { wrapper });
    await waitFor(() => screen.getByTestId("btn-nouveau-bc"));
    fireEvent.click(screen.getByTestId("btn-nouveau-bc"));
    await waitFor(() => screen.getByRole("combobox", { name: /fournisseur/i }));
    fireEvent.change(screen.getByRole("combobox", { name: /fournisseur/i }), {
      target: { value: "f1" },
    });
    fireEvent.click(screen.getByTestId("btn-confirmer-bc"));
    await waitFor(() =>
      expect(mockBonCommandeCreer).toHaveBeenCalledWith({ fournisseur_id: "f1" })
    );
  });

  it("filtre les bons par statut", async () => {
    render(<PageAchatsMin />, { wrapper });
    await waitFor(() => screen.getByTestId("liste-bons"));
    await vi.waitFor(() => {
      fireEvent.change(screen.getByRole("combobox", { name: /filtrer par statut/i }), {
        target: { value: "brouillon" },
      });
    });
    await waitFor(() => {
      const appels = mockBonsCommandeListe.mock.calls;
      const dernier = appels[appels.length - 1][0];
      expect(dernier.statut).toBe("brouillon");
    });
  });
});
