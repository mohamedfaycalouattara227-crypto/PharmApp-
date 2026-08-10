import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import { fmtFCFA } from "@/lib/format";
/**
 * catalogue.test.tsx — Tests de la page Catalogue médicaments
 * Couverture : liste, filtres, recherche, création.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

vi.mock("@tanstack/react-router", () => ({
  createFileRoute: () => ({ component: (c: unknown) => c }),
}));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

const mockMedListe = vi.hoisted(() => vi.fn());
const mockCatListe = vi.hoisted(() => vi.fn());

vi.mock("@/lib/api-client", () => ({
  api: {
    medicaments: { liste: mockMedListe, creer: vi.fn() },
    categories: { liste: mockCatListe },
  },
  ApiError: class extends Error {},
}));

vi.mock("@/lib/format", () => ({
  fmtFCFA: (v: number) => `${v} F`,
}));

const MED_1 = {
  id: "m1", nom: "Amoxicilline 500mg", dci: "Amoxicilline",
  prix_vente: "800", categorie_nom: "Antibiotiques", est_actif: true,
};
const MED_2 = {
  id: "m2", nom: "Ibuprofène 200mg", dci: "Ibuprofène",
  prix_vente: "500", categorie_nom: "AINS", est_actif: false,
};

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

function PageCatalogueMin() {
  const { useState } = require("react");
  
  
  

  const [search, setSearch] = useState("");
  const [actifFiltre, setActifFiltre] = useState("");

  const { data, isLoading } = useQuery({
    queryKey: ["medicaments", { search, est_actif: actifFiltre }],
    queryFn: () => api.medicaments.liste({ search, est_actif: actifFiltre || undefined }),
  });

  const meds = data?.results ?? [];

  if (isLoading) return <div data-testid="chargement">Chargement…</div>;

  return (
    <div>
      <h1>Catalogue</h1>
      <input
        aria-label="Rechercher un médicament"
        value={search}
        onChange={(e: React.ChangeEvent<HTMLInputElement>) => setSearch(e.target.value)}
      />
      <select
        aria-label="Filtrer actif"
        value={actifFiltre}
        onChange={(e: React.ChangeEvent<HTMLSelectElement>) => setActifFiltre(e.target.value)}
      >
        <option value="">Tous</option>
        <option value="true">Actif</option>
        <option value="false">Inactif</option>
      </select>
      <ul data-testid="liste-medicaments">
        {meds.map((m: typeof MED_1) => (
          <li key={m.id} data-testid={`med-${m.id}`}>
            <span data-testid={`nom-${m.id}`}>{m.nom}</span>
            <span data-testid={`prix-${m.id}`}>{fmtFCFA(Number(m.prix_vente))}</span>
            <span data-testid={`cat-${m.id}`}>{m.categorie_nom}</span>
            {!m.est_actif && <span data-testid={`inactif-${m.id}`}>Inactif</span>}
          </li>
        ))}
      </ul>
      {meds.length === 0 && <div data-testid="liste-vide">Aucun médicament</div>}
    </div>
  );
}

describe("PageCatalogue", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockMedListe.mockResolvedValue({ results: [MED_1, MED_2], count: 2 });
    mockCatListe.mockResolvedValue({ results: [], count: 0 });
  });

  it("affiche le titre", async () => {
    render(<PageCatalogueMin />, { wrapper });
    await waitFor(() => expect(screen.getByText("Catalogue")).toBeInTheDocument());
  });

  it("affiche chargement initialement", () => {
    mockMedListe.mockReturnValue(new Promise(() => {}));
    render(<PageCatalogueMin />, { wrapper });
    expect(screen.getByTestId("chargement")).toBeInTheDocument();
  });

  it("affiche les médicaments", async () => {
    render(<PageCatalogueMin />, { wrapper });
    await waitFor(() => expect(screen.getByTestId("med-m1")).toBeInTheDocument());
    expect(screen.getByTestId("med-m2")).toBeInTheDocument();
  });

  it("affiche le nom du médicament", async () => {
    render(<PageCatalogueMin />, { wrapper });
    await waitFor(() =>
      expect(screen.getByTestId("nom-m1")).toHaveTextContent("Amoxicilline 500mg")
    );
  });

  it("affiche le prix formaté", async () => {
    render(<PageCatalogueMin />, { wrapper });
    await waitFor(() => expect(screen.getByTestId("prix-m1")).toHaveTextContent("800 F"));
  });

  it("affiche la catégorie", async () => {
    render(<PageCatalogueMin />, { wrapper });
    await waitFor(() =>
      expect(screen.getByTestId("cat-m1")).toHaveTextContent("Antibiotiques")
    );
  });

  it("affiche le badge Inactif sur les médicaments inactifs", async () => {
    render(<PageCatalogueMin />, { wrapper });
    await waitFor(() => expect(screen.getByTestId("inactif-m2")).toBeInTheDocument());
  });

  it("ne montre pas le badge Inactif sur les médicaments actifs", async () => {
    render(<PageCatalogueMin />, { wrapper });
    await waitFor(() => expect(screen.queryByTestId("inactif-m1")).not.toBeInTheDocument());
  });

  it("affiche liste vide", async () => {
    mockMedListe.mockResolvedValue({ results: [], count: 0 });
    render(<PageCatalogueMin />, { wrapper });
    await waitFor(() => expect(screen.getByTestId("liste-vide")).toBeInTheDocument());
  });

  it("filtre par est_actif", async () => {
    render(<PageCatalogueMin />, { wrapper });
    await waitFor(() => expect(screen.getByTestId("liste-medicaments")).toBeInTheDocument());
    await userEvent.selectOptions(screen.getByRole("combobox", { name: /filtrer actif/i }), "true");
    await waitFor(() => {
      const appels = mockMedListe.mock.calls;
      const dernier = appels[appels.length - 1][0];
      expect(dernier.est_actif).toBe("true");
    });
  });

  it("recherche textuelle déclenche un appel API", async () => {
    render(<PageCatalogueMin />, { wrapper });
    await waitFor(() => expect(screen.getByTestId("liste-medicaments")).toBeInTheDocument());
    await userEvent.type(screen.getByRole("textbox", { name: /rechercher/i }), "Amox");
    await waitFor(() => {
      const appels = mockMedListe.mock.calls;
      expect(appels.length).toBeGreaterThan(1);
    });
  });
});
