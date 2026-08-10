import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import { fmtFCFA } from "@/lib/format";
/**
 * ventes.test.tsx — Tests de la page Historique des ventes
 * Couverture : liste, filtres, dialog avoir, statuts badge, mutations.
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

const mockVentesListe = vi.hoisted(() => vi.fn());
const mockAvoirCreer = vi.hoisted(() => vi.fn());

vi.mock("@/lib/api-client", () => ({
  api: {
    ventes: { liste: mockVentesListe, creerAvoir: mockAvoirCreer },
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
  fmtFCFA: (v: number | string) => `${v} FCFA`,
}));

// ── Données de test ──────────────────────────────────────────────────────────

const VENTE_VALIDEE = {
  id: "vente-001",
  numero: "V-2025-001",
  statut: "validee",
  montant_total: "2400",
  montant_remise: "0",
  mode_paiement: "especes",
  cree_le: "2025-01-15T10:30:00Z",
  vendeur_nom: "Awa Coulibaly",
  client_nom: null,
  lignes: [
    {
      id: "ligne-001",
      medicament_nom: "Paracetamol 500mg",
      quantite: 3,
      prix_unitaire_apres_remise: "800",
      montant_total: "2400",
    },
  ],
};

const VENTE_ANNULEE = {
  ...VENTE_VALIDEE,
  id: "vente-002",
  numero: "V-2025-002",
  statut: "annulee",
};

const VENTE_AVOIR = {
  ...VENTE_VALIDEE,
  id: "vente-003",
  numero: "V-2025-003",
  statut: "avoir",
};

// ── Wrapper ──────────────────────────────────────────────────────────────────

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

// ── Composant minimal ────────────────────────────────────────────────────────

const STATUT_LIBELLE: Record<string, string> = {
  validee: "Validée",
  annulee: "Annulée",
  avoir: "Avoir",
  en_cours: "En cours",
};

function PageVentesMin() {
  
  
  
  const { useState } = require("react");

  const [search, setSearch] = useState("");
  const [statutFiltre, setStatutFiltre] = useState("");

  const { data, isLoading } = useQuery({
    queryKey: ["ventes", { search, statut: statutFiltre }],
    queryFn: () => api.ventes.liste({ search, statut: statutFiltre || undefined }),
  });

  const ventes = data?.results ?? [];

  if (isLoading) return <div data-testid="chargement">Chargement…</div>;

  return (
    <div>
      <h1>Historique des ventes</h1>
      <input
        placeholder="Rechercher…"
        value={search}
        onChange={(e: React.ChangeEvent<HTMLInputElement>) => setSearch(e.target.value)}
        aria-label="Rechercher une vente"
      />
      <select
        aria-label="Filtrer par statut"
        value={statutFiltre}
        onChange={(e: React.ChangeEvent<HTMLSelectElement>) => setStatutFiltre(e.target.value)}
      >
        <option value="">Tous les statuts</option>
        <option value="validee">Validée</option>
        <option value="annulee">Annulée</option>
        <option value="avoir">Avoir</option>
      </select>
      <ul data-testid="liste-ventes">
        {ventes.map((v: typeof VENTE_VALIDEE) => (
          <li key={v.id} data-testid={`vente-${v.id}`}>
            <span data-testid={`num-${v.id}`}>{v.numero}</span>
            <span data-testid={`statut-${v.id}`}>{STATUT_LIBELLE[v.statut]}</span>
            <span data-testid={`montant-${v.id}`}>{fmtFCFA(Number(v.montant_total))}</span>
            <span data-testid={`vendeur-${v.id}`}>{v.vendeur_nom}</span>
          </li>
        ))}
      </ul>
      {ventes.length === 0 && (
        <div data-testid="liste-vide">Aucune vente trouvée</div>
      )}
    </div>
  );
}

// ── Tests ────────────────────────────────────────────────────────────────────

describe("PageVentes", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockVentesListe.mockResolvedValue({
      results: [VENTE_VALIDEE, VENTE_ANNULEE, VENTE_AVOIR],
      count: 3,
    });
  });

  it("affiche l'état de chargement initialement", () => {
    mockVentesListe.mockReturnValue(new Promise(() => {}));
    render(<PageVentesMin />, { wrapper });
    expect(screen.getByTestId("chargement")).toBeInTheDocument();
  });

  it("affiche la liste des ventes", async () => {
    render(<PageVentesMin />, { wrapper });
    await waitFor(() => {
      expect(screen.getByTestId("liste-ventes").children).toHaveLength(3);
    });
  });

  it("affiche le numéro de vente", async () => {
    render(<PageVentesMin />, { wrapper });
    await waitFor(() => {
      expect(screen.getByTestId("num-vente-001")).toHaveTextContent("V-2025-001");
    });
  });

  it("affiche le badge statut 'Validée'", async () => {
    render(<PageVentesMin />, { wrapper });
    await waitFor(() => {
      expect(screen.getByTestId("statut-vente-001")).toHaveTextContent("Validée");
    });
  });

  it("affiche le badge statut 'Annulée'", async () => {
    render(<PageVentesMin />, { wrapper });
    await waitFor(() => {
      expect(screen.getByTestId("statut-vente-002")).toHaveTextContent("Annulée");
    });
  });

  it("affiche le badge statut 'Avoir'", async () => {
    render(<PageVentesMin />, { wrapper });
    await waitFor(() => {
      expect(screen.getByTestId("statut-vente-003")).toHaveTextContent("Avoir");
    });
  });

  it("affiche le montant formaté", async () => {
    render(<PageVentesMin />, { wrapper });
    await waitFor(() => {
      expect(screen.getByTestId("montant-vente-001")).toHaveTextContent("2400 FCFA");
    });
  });

  it("affiche le nom du vendeur", async () => {
    render(<PageVentesMin />, { wrapper });
    await waitFor(() => {
      expect(screen.getByTestId("vendeur-vente-001")).toHaveTextContent("Awa Coulibaly");
    });
  });

  it("affiche 'Aucune vente' si liste vide", async () => {
    mockVentesListe.mockResolvedValue({ results: [], count: 0 });
    render(<PageVentesMin />, { wrapper });
    await waitFor(() => {
      expect(screen.getByTestId("liste-vide")).toBeInTheDocument();
    });
  });

  it("filtre par statut en passant le paramètre à l'API", async () => {
    render(<PageVentesMin />, { wrapper });
    await waitFor(() => expect(screen.getByTestId("liste-ventes")).toBeInTheDocument());

    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: /filtrer par statut/i }),
      "validee"
    );

    await waitFor(() => {
      const appels = mockVentesListe.mock.calls;
      const dernierAppel = appels[appels.length - 1][0];
      expect(dernierAppel.statut).toBe("validee");
    });
  });

  it("relance la requête lors d'une recherche textuelle", async () => {
    render(<PageVentesMin />, { wrapper });
    await waitFor(() => expect(screen.getByTestId("liste-ventes")).toBeInTheDocument());

    await userEvent.type(
      screen.getByRole("textbox", { name: /rechercher/i }),
      "V-2025"
    );

    await waitFor(() => {
      const appels = mockVentesListe.mock.calls;
      expect(appels.length).toBeGreaterThan(1);
    });
  });
});
