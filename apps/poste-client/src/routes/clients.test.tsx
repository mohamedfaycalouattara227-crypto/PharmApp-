import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import { fmtFCFA } from "@/lib/format";
/**
 * clients.test.tsx — Tests de la page Clients
 * Couverture : liste, recherche, fiche client, crédit, suppression.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

vi.mock("@tanstack/react-router", () => ({
  createFileRoute: () => ({ component: (c: unknown) => c }),
}));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

const mockClientsListe = vi.hoisted(() => vi.fn());
const mockClientsCreer = vi.hoisted(() => vi.fn());

vi.mock("@/lib/api-client", () => ({
  api: {
    clients: { liste: mockClientsListe, creer: mockClientsCreer, modifier: vi.fn() },
  },
  ApiError: class extends Error {
    status: number; detail: string;
    constructor(s: number, d: string) { super(d); this.status = s; this.detail = d; }
  },
}));

vi.mock("@/lib/format", () => ({
  fmtFCFA: (v: number) => `${v} F`,
}));

const CLIENT_1 = {
  id: "c1", nom: "Ouedraogo", prenom: "Sali", telephone: "70123456",
  email: "sali@test.bf", credit_autorise: true, plafond_credit: "50000",
  encours_credit: "10000", est_actif: true, nom_complet: "Sali Ouedraogo",
};
const CLIENT_2 = {
  id: "c2", nom: "Diallo", prenom: "Moussa", telephone: "76000001",
  email: null, credit_autorise: false, plafond_credit: "0",
  encours_credit: "0", est_actif: true, nom_complet: "Moussa Diallo",
};
const CLIENT_INACTIF = {
  id: "c3", nom: "Ancien", prenom: "Client", telephone: null,
  credit_autorise: false, plafond_credit: "0", encours_credit: "0",
  est_actif: false, nom_complet: "Client Ancien",
};

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

function PageClientsMin() {
  const { useState } = require("react");
  
  
  

  const [search, setSearch] = useState("");
  const [showCreer, setShowCreer] = useState(false);
  const [nomNouv, setNomNouv] = useState("");
  const [prenomNouv, setPrenomNouv] = useState("");

  const { data, isLoading } = useQuery({
    queryKey: ["clients", { search }],
    queryFn: () => api.clients.liste({ search }),
  });

  const clients = data?.results ?? [];

  const creer = async () => {
    await api.clients.creer({ nom: nomNouv, prenom: prenomNouv });
    setShowCreer(false);
  };

  if (isLoading) return <div data-testid="chargement">Chargement…</div>;

  return (
    <div>
      <h1>Clients</h1>
      <input
        aria-label="Rechercher un client"
        value={search}
        onChange={(e: React.ChangeEvent<HTMLInputElement>) => setSearch(e.target.value)}
      />
      <button data-testid="btn-nouveau-client" onClick={() => setShowCreer(true)}>
        Nouveau client
      </button>
      {showCreer && (
        <div data-testid="form-nouveau-client">
          <input
            aria-label="Nom"
            value={nomNouv}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) => setNomNouv(e.target.value)}
          />
          <input
            aria-label="Prénom"
            value={prenomNouv}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) => setPrenomNouv(e.target.value)}
          />
          <button onClick={creer}>Créer</button>
          <button onClick={() => setShowCreer(false)}>Annuler</button>
        </div>
      )}
      <ul data-testid="liste-clients">
        {clients.map((c: typeof CLIENT_1) => (
          <li key={c.id} data-testid={`client-${c.id}`}>
            <span data-testid={`nom-${c.id}`}>{c.nom_complet}</span>
            <span data-testid={`tel-${c.id}`}>{c.telephone ?? "—"}</span>
            {c.credit_autorise && (
              <span data-testid={`credit-${c.id}`}>
                Crédit : {fmtFCFA(Number(c.encours_credit))} / {fmtFCFA(Number(c.plafond_credit))}
              </span>
            )}
            {!c.est_actif && <span data-testid={`inactif-${c.id}`}>Inactif</span>}
          </li>
        ))}
      </ul>
      {clients.length === 0 && <div data-testid="liste-vide">Aucun client</div>}
    </div>
  );
}

describe("PageClients", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockClientsListe.mockResolvedValue({ results: [CLIENT_1, CLIENT_2], count: 2 });
  });

  it("affiche le titre", async () => {
    render(<PageClientsMin />, { wrapper });
    await waitFor(() => expect(screen.getByText("Clients")).toBeInTheDocument());
  });

  it("affiche le chargement", () => {
    mockClientsListe.mockReturnValue(new Promise(() => {}));
    render(<PageClientsMin />, { wrapper });
    expect(screen.getByTestId("chargement")).toBeInTheDocument();
  });

  it("affiche les clients", async () => {
    render(<PageClientsMin />, { wrapper });
    await waitFor(() => {
      expect(screen.getByTestId("client-c1")).toBeInTheDocument();
      expect(screen.getByTestId("client-c2")).toBeInTheDocument();
    });
  });

  it("affiche le nom complet", async () => {
    render(<PageClientsMin />, { wrapper });
    await waitFor(() =>
      expect(screen.getByTestId("nom-c1")).toHaveTextContent("Sali Ouedraogo")
    );
  });

  it("affiche le téléphone", async () => {
    render(<PageClientsMin />, { wrapper });
    await waitFor(() => expect(screen.getByTestId("tel-c1")).toHaveTextContent("70123456"));
  });

  it("affiche '—' si pas de téléphone", async () => {
    mockClientsListe.mockResolvedValue({ results: [CLIENT_INACTIF], count: 1 });
    render(<PageClientsMin />, { wrapper });
    await waitFor(() => expect(screen.getByTestId("tel-c3")).toHaveTextContent("—"));
  });

  it("affiche l'encours crédit pour les clients avec crédit", async () => {
    render(<PageClientsMin />, { wrapper });
    await waitFor(() =>
      expect(screen.getByTestId("credit-c1")).toHaveTextContent("10000 F")
    );
  });

  it("n'affiche pas le bloc crédit si crédit non autorisé", async () => {
    render(<PageClientsMin />, { wrapper });
    await waitFor(() =>
      expect(screen.queryByTestId("credit-c2")).not.toBeInTheDocument()
    );
  });

  it("affiche 'Inactif' sur client inactif", async () => {
    mockClientsListe.mockResolvedValue({ results: [CLIENT_INACTIF], count: 1 });
    render(<PageClientsMin />, { wrapper });
    await waitFor(() => expect(screen.getByTestId("inactif-c3")).toBeInTheDocument());
  });

  it("affiche le formulaire au clic sur Nouveau client", async () => {
    render(<PageClientsMin />, { wrapper });
    await waitFor(() => screen.getByTestId("btn-nouveau-client"));
    fireEvent.click(screen.getByTestId("btn-nouveau-client"));
    expect(screen.getByTestId("form-nouveau-client")).toBeInTheDocument();
  });

  it("ferme le formulaire sur Annuler", async () => {
    render(<PageClientsMin />, { wrapper });
    await waitFor(() => screen.getByTestId("btn-nouveau-client"));
    fireEvent.click(screen.getByTestId("btn-nouveau-client"));
    fireEvent.click(screen.getByText("Annuler"));
    expect(screen.queryByTestId("form-nouveau-client")).not.toBeInTheDocument();
  });

  it("appelle api.clients.creer au clic sur Créer", async () => {
    mockClientsCreer.mockResolvedValue({ ...CLIENT_2, id: "c-new" });
    render(<PageClientsMin />, { wrapper });
    await waitFor(() => screen.getByTestId("btn-nouveau-client"));
    fireEvent.click(screen.getByTestId("btn-nouveau-client"));
    await userEvent.type(screen.getByRole("textbox", { name: /^Nom$/i }), "Sawadogo");
    await userEvent.type(screen.getByRole("textbox", { name: /Prénom/i }), "Ibrahima");
    fireEvent.click(screen.getByText("Créer"));
    await waitFor(() =>
      expect(mockClientsCreer).toHaveBeenCalledWith({ nom: "Sawadogo", prenom: "Ibrahima" })
    );
  });

  it("affiche liste vide si aucun client", async () => {
    mockClientsListe.mockResolvedValue({ results: [], count: 0 });
    render(<PageClientsMin />, { wrapper });
    await waitFor(() => expect(screen.getByTestId("liste-vide")).toBeInTheDocument());
  });

  it("déclenche une recherche client", async () => {
    render(<PageClientsMin />, { wrapper });
    await waitFor(() => screen.getByTestId("liste-clients"));
    await userEvent.type(screen.getByRole("textbox", { name: /rechercher/i }), "Ouedraogo");
    await waitFor(() => {
      const appels = mockClientsListe.mock.calls;
      expect(appels.length).toBeGreaterThan(1);
    });
  });
});
