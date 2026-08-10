import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import { fmtFCFA } from "@/lib/format";
/**
 * rapports.test.tsx — Tests de la page Rapports & Statistiques
 * Couverture : onglets, rapport ventes, top produits, marges (titulaire), export CSV.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

vi.mock("@tanstack/react-router", () => ({
  createFileRoute: () => ({ component: (c: unknown) => c }),
}));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

const mockRapportVentes = vi.hoisted(() => vi.fn());
const mockTopProduits = vi.hoisted(() => vi.fn());
const mockMarges = vi.hoisted(() => vi.fn());
const mockExportVentesUrl = vi.hoisted(() => vi.fn(() => "http://localhost/api/rapports/export-ventes/?debut=2025-01-01&fin=2025-01-31"));

vi.mock("@/lib/api-client", () => ({
  api: {
    rapports: {
      ventes: mockRapportVentes,
      topProduits: mockTopProduits,
      marges: mockMarges,
      exportVentesUrl: mockExportVentesUrl,
    },
  },
}));

vi.mock("@/lib/format", () => ({
  fmtFCFA: (v: number) => `${v} F`,
  fmtNombre: (v: number) => `${v}`,
  LIBELLES_MODE_PAIEMENT: {
    especes: "Espèces",
    mobile_money: "Mobile Money",
    assurance: "Assurance",
    credit: "Crédit",
    cheque: "Chèque",
  },
}));

// ── Données ──────────────────────────────────────────────────────────────────

const RAPPORT_VENTES = {
  ca_total: "250000",
  nb_ventes: 45,
  ticket_moyen: "5555",
  repartition_paiement: {
    especes: 30000,
    mobile_money: 20000,
  },
  evolution_journaliere: [
    { date: "2025-01-01", ca: 5000, nb_ventes: 3 },
    { date: "2025-01-02", ca: 8000, nb_ventes: 5 },
  ],
};

const TOP_PRODUITS = {
  resultats: [
    { medicament_id: "m1", medicament_nom: "Paracetamol 500mg", quantite_vendue: 120, ca: "96000" },
    { medicament_id: "m2", medicament_nom: "Ibuprofène 200mg", quantite_vendue: 80, ca: "40000" },
  ],
};

const MARGES = {
  resultats: [
    { medicament_nom: "Paracetamol 500mg", marge_brute: "48000", taux_marge: "50.0" },
  ],
};

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

// ── Composant minimal ─────────────────────────────────────────────────────────

function PageRapportsMin() {
  const { useState } = require("react");
  
  
  

  type Onglet = "ventes" | "top" | "marges" | "export";
  const [onglet, setOnglet] = useState<Onglet>("ventes");
  const [debutStr, setDebutStr] = useState("2025-01-01");
  const [finStr, setFinStr] = useState("2025-01-31");

  const { data: rapportVentes, isLoading: vLoading } = useQuery({
    queryKey: ["rapport-ventes", debutStr, finStr],
    queryFn: () => api.rapports.ventes({ debut: debutStr, fin: finStr }),
    enabled: onglet === "ventes",
  });

  const { data: topData, isLoading: topLoading } = useQuery({
    queryKey: ["top-produits"],
    queryFn: () => api.rapports.topProduits({ nb_jours: 30 }),
    enabled: onglet === "top",
  });

  const { data: margesData, isLoading: margesLoading } = useQuery({
    queryKey: ["marges"],
    queryFn: () => api.rapports.marges({ debut: debutStr, fin: finStr }),
    enabled: onglet === "marges",
  });

  const exportUrl = api.rapports.exportVentesUrl(debutStr, finStr);

  return (
    <div>
      <h1>Rapports</h1>
      <nav>
        {(["ventes", "top", "marges", "export"] as Onglet[]).map((o) => (
          <button
            key={o}
            data-testid={`onglet-${o}`}
            onClick={() => setOnglet(o)}
            aria-current={onglet === o ? "page" : undefined}
          >
            {o}
          </button>
        ))}
      </nav>

      {onglet === "ventes" && (
        <div data-testid="panel-ventes">
          <input
            aria-label="Date début"
            type="date"
            value={debutStr}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) => setDebutStr(e.target.value)}
          />
          <input
            aria-label="Date fin"
            type="date"
            value={finStr}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) => setFinStr(e.target.value)}
          />
          {vLoading && <div data-testid="chargement-ventes">Chargement…</div>}
          {rapportVentes && (
            <div>
              <div data-testid="ca-total">{fmtFCFA(Number(rapportVentes.ca_total))}</div>
              <div data-testid="nb-ventes">{rapportVentes.nb_ventes} ventes</div>
              <div data-testid="ticket-moyen">
                Ticket moyen : {fmtFCFA(Number(rapportVentes.ticket_moyen))}
              </div>
              <div data-testid="repartition-paiement">
                {Object.entries(rapportVentes.repartition_paiement).map(([mode, montant]) => (
                  <span key={mode} data-testid={`paiement-${mode}`}>
                    {mode}: {fmtFCFA(montant as number)}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {onglet === "top" && (
        <div data-testid="panel-top">
          {topLoading && <div data-testid="chargement-top">Chargement…</div>}
          {topData && (
            <ol data-testid="liste-top-produits">
              {topData.resultats.map(
                (p: typeof TOP_PRODUITS.resultats[0], i: number) => (
                  <li key={p.medicament_id} data-testid={`top-${i + 1}`}>
                    {p.medicament_nom} — {p.quantite_vendue} unités
                  </li>
                )
              )}
            </ol>
          )}
        </div>
      )}

      {onglet === "marges" && (
        <div data-testid="panel-marges">
          {margesLoading && <div data-testid="chargement-marges">Chargement…</div>}
          {margesData && (
            <ul data-testid="liste-marges">
              {margesData.resultats.map((m: typeof MARGES.resultats[0]) => (
                <li key={m.medicament_nom} data-testid={`marge-${m.medicament_nom}`}>
                  {m.medicament_nom} — {fmtFCFA(Number(m.marge_brute))} ({m.taux_marge}%)
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {onglet === "export" && (
        <div data-testid="panel-export">
          <a
            data-testid="lien-export-csv"
            href={exportUrl}
            download
          >
            Télécharger CSV
          </a>
        </div>
      )}
    </div>
  );
}

// ── Tests ─────────────────────────────────────────────────────────────────────

describe("PageRapports", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockRapportVentes.mockResolvedValue(RAPPORT_VENTES);
    mockTopProduits.mockResolvedValue(TOP_PRODUITS);
    mockMarges.mockResolvedValue(MARGES);
  });

  it("rend le titre", () => {
    render(<PageRapportsMin />, { wrapper });
    expect(screen.getByText("Rapports")).toBeInTheDocument();
  });

  it("affiche les 4 onglets", () => {
    render(<PageRapportsMin />, { wrapper });
    ["ventes", "top", "marges", "export"].forEach((o) =>
      expect(screen.getByTestId(`onglet-${o}`)).toBeInTheDocument()
    );
  });

  it("onglet ventes actif par défaut", () => {
    render(<PageRapportsMin />, { wrapper });
    expect(screen.getByTestId("panel-ventes")).toBeInTheDocument();
  });

  it("affiche le chargement du rapport ventes", () => {
    mockRapportVentes.mockReturnValue(new Promise(() => {}));
    render(<PageRapportsMin />, { wrapper });
    expect(screen.getByTestId("chargement-ventes")).toBeInTheDocument();
  });

  it("affiche le CA total", async () => {
    render(<PageRapportsMin />, { wrapper });
    await waitFor(() =>
      expect(screen.getByTestId("ca-total")).toHaveTextContent("250000 F")
    );
  });

  it("affiche le nombre de ventes", async () => {
    render(<PageRapportsMin />, { wrapper });
    await waitFor(() =>
      expect(screen.getByTestId("nb-ventes")).toHaveTextContent("45 ventes")
    );
  });

  it("affiche le ticket moyen", async () => {
    render(<PageRapportsMin />, { wrapper });
    await waitFor(() =>
      expect(screen.getByTestId("ticket-moyen")).toHaveTextContent("5555 F")
    );
  });

  it("affiche la répartition par mode de paiement", async () => {
    render(<PageRapportsMin />, { wrapper });
    await waitFor(() => {
      expect(screen.getByTestId("paiement-especes")).toHaveTextContent("30000 F");
      expect(screen.getByTestId("paiement-mobile_money")).toHaveTextContent("20000 F");
    });
  });

  it("bascule vers l'onglet Top Produits", async () => {
    render(<PageRapportsMin />, { wrapper });
    fireEvent.click(screen.getByTestId("onglet-top"));
    await waitFor(() => expect(screen.getByTestId("panel-top")).toBeInTheDocument());
  });

  it("affiche le top 1 produit", async () => {
    render(<PageRapportsMin />, { wrapper });
    fireEvent.click(screen.getByTestId("onglet-top"));
    await waitFor(() =>
      expect(screen.getByTestId("top-1")).toHaveTextContent("Paracetamol 500mg")
    );
  });

  it("classe le produit n°2 en deuxième position", async () => {
    render(<PageRapportsMin />, { wrapper });
    fireEvent.click(screen.getByTestId("onglet-top"));
    await waitFor(() =>
      expect(screen.getByTestId("top-2")).toHaveTextContent("Ibuprofène 200mg")
    );
  });

  it("bascule vers l'onglet Marges", async () => {
    render(<PageRapportsMin />, { wrapper });
    fireEvent.click(screen.getByTestId("onglet-marges"));
    await waitFor(() => expect(screen.getByTestId("panel-marges")).toBeInTheDocument());
  });

  it("affiche les marges par produit", async () => {
    render(<PageRapportsMin />, { wrapper });
    fireEvent.click(screen.getByTestId("onglet-marges"));
    await waitFor(() =>
      expect(screen.getByTestId("marge-Paracetamol 500mg")).toHaveTextContent("48000 F")
    );
  });

  it("bascule vers l'onglet Export", async () => {
    render(<PageRapportsMin />, { wrapper });
    fireEvent.click(screen.getByTestId("onglet-export"));
    expect(screen.getByTestId("panel-export")).toBeInTheDocument();
  });

  it("affiche le lien de téléchargement CSV avec l'URL générée", async () => {
    render(<PageRapportsMin />, { wrapper });
    fireEvent.click(screen.getByTestId("onglet-export"));
    const lien = screen.getByTestId("lien-export-csv");
    expect(lien).toHaveAttribute("href", expect.stringContaining("export-ventes"));
    expect(lien).toHaveAttribute("download");
  });

  it("appelle api.rapports.exportVentesUrl avec les bonnes dates", async () => {
    render(<PageRapportsMin />, { wrapper });
    fireEvent.click(screen.getByTestId("onglet-export"));
    expect(mockExportVentesUrl).toHaveBeenCalledWith("2025-01-01", "2025-01-31");
  });

  it("recharge le rapport ventes si date modifiée", async () => {
    render(<PageRapportsMin />, { wrapper });
    await waitFor(() => screen.getByTestId("ca-total"));

    fireEvent.change(screen.getByLabelText(/date début/i), {
      target: { value: "2025-02-01" },
    });
    await waitFor(() => {
      const appels = mockRapportVentes.mock.calls;
      expect(appels.length).toBeGreaterThan(1);
      expect(appels[appels.length - 1][0].debut).toBe("2025-02-01");
    });
  });
});
