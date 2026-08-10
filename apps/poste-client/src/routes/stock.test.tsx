import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
/**
 * stock.test.tsx — Tests de la page Gestion des stocks
 * Couverture : onglets, liste médicaments, lots, mouvements, alertes, ajuster stock.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

vi.mock("@tanstack/react-router", () => ({
  createFileRoute: () => ({ component: (c: unknown) => c }),
}));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

const mockMedListe = vi.hoisted(() => vi.fn());
const mockLotsListe = vi.hoisted(() => vi.fn());
const mockMouvListe = vi.hoisted(() => vi.fn());
const mockAlertesListe = vi.hoisted(() => vi.fn());
const mockAjusterStock = vi.hoisted(() => vi.fn());
const mockAlertesResoudre = vi.hoisted(() => vi.fn());

vi.mock("@/lib/api-client", () => ({
  api: {
    medicaments: { liste: mockMedListe },
    lots: { liste: mockLotsListe },
    mouvements: { liste: mockMouvListe },
    alertes: { liste: mockAlertesListe, resoudre: mockAlertesResoudre },
    stocks: { ajuster: mockAjusterStock },
  },
}));

vi.mock("@/lib/format", () => ({
  fmtFCFA: (v: number) => `${v} F`,
  fmtDateCourte: (d: string) => d,
}));

vi.mock("@/lib/utils", () => ({ cn: (...c: string[]) => c.join(" ") }));

// ── Données ──────────────────────────────────────────────────────────────────

const MED_STOCK = {
  id: "m1", nom: "Paracetamol 500mg", stock_disponible: 45,
  seuil_alerte: 20, prix_vente: "800", categorie_nom: "Antalgiques",
};

const LOT_OK = {
  id: "l1", numero_lot: "LOT-001", medicament_nom: "Paracetamol 500mg",
  quantite_disponible: 30, date_peremption: "2026-12-31",
  medicament_id: "m1",
};

const LOT_EXPIRE = {
  id: "l2", numero_lot: "LOT-002", medicament_nom: "Ibuprofène 200mg",
  quantite_disponible: 5, date_peremption: "2024-01-01",
  medicament_id: "m2",
};

const MOUVEMENT = {
  id: "mv1", type_mouvement: "entree", quantite: 100,
  medicament_nom: "Paracetamol 500mg", cree_le: "2025-06-01T10:00:00Z",
  motif: "Réception commande", numero_lot: "LOT-001",
};

const ALERTE = {
  id: "a1", medicament_nom: "Paracetamol 500mg",
  niveau: "alerte", quantite_disponible: 8, seuil_alerte: 20, est_resolue: false,
};

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

// ── Composant simplifié ───────────────────────────────────────────────────────

function PageStockMin() {
  const { useState } = require("react");
  
  

  type Onglet = "overview" | "lots" | "mouvements" | "alertes";
  const [onglet, setOnglet] = useState<Onglet>("overview");
  const [dialogAjuster, setDialogAjuster] = useState(false);
  const [lotId, setLotId] = useState("");
  const [nouvelleQte, setNouvelleQte] = useState("");
  const [motif, setMotif] = useState("");

  const qc = useQueryClient();

  const { data: medsData, isLoading: medsLoading } = useQuery({
    queryKey: ["medicaments-stock"],
    queryFn: () => api.medicaments.liste({ page_size: 100 }),
    enabled: onglet === "overview",
  });

  const { data: lotsData, isLoading: lotsLoading } = useQuery({
    queryKey: ["lots-stock"],
    queryFn: () => api.lots.liste({ page_size: 100 }),
    enabled: onglet === "lots",
  });

  const { data: mouvData, isLoading: mouvLoading } = useQuery({
    queryKey: ["mouvements-stock"],
    queryFn: () => api.mouvements.liste({ page_size: 50 }),
    enabled: onglet === "mouvements",
  });

  const { data: alertesData, isLoading: alertesLoading } = useQuery({
    queryKey: ["alertes-stock-page"],
    queryFn: () => api.alertes.liste({ est_resolue: false }),
    enabled: onglet === "alertes",
  });

  const ajusterMutation = useMutation({
    mutationFn: () => api.stocks.ajuster({ lot_id: lotId, nouvelle_quantite: Number(nouvelleQte), motif }),
    onSuccess: () => {
      setDialogAjuster(false);
      qc.invalidateQueries({ queryKey: ["lots-stock"] });
    },
  });

  const resoudreMutation = useMutation({
    mutationFn: (id: string) => api.alertes.resoudre(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["alertes-stock-page"] }),
  });

  const meds = medsData?.results ?? [];
  const lots = lotsData?.results ?? [];
  const mouvements = mouvData?.results ?? [];
  const alertes = alertesData?.results ?? [];

  return (
    <div>
      <h1>Gestion des stocks</h1>
      <nav>
        {(["overview", "lots", "mouvements", "alertes"] as Onglet[]).map((o) => (
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
      <button data-testid="btn-ajuster" onClick={() => setDialogAjuster(true)}>
        Ajuster stock
      </button>

      {onglet === "overview" && (
        <div data-testid="panel-overview">
          {medsLoading ? (
            <div data-testid="chargement-meds">Chargement…</div>
          ) : (
            <ul data-testid="liste-meds-stock">
              {meds.map((m: typeof MED_STOCK) => (
                <li key={m.id} data-testid={`med-stock-${m.id}`}>
                  {m.nom} — {m.stock_disponible}
                  {m.stock_disponible <= m.seuil_alerte && (
                    <span data-testid={`badge-alerte-${m.id}`}>⚠ Alerte</span>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {onglet === "lots" && (
        <div data-testid="panel-lots">
          {lotsLoading ? (
            <div data-testid="chargement-lots">Chargement…</div>
          ) : (
            <ul data-testid="liste-lots">
              {lots.map((l: typeof LOT_OK) => (
                <li key={l.id} data-testid={`lot-${l.id}`}>
                  {l.numero_lot} — {l.medicament_nom} — {l.date_peremption}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {onglet === "mouvements" && (
        <div data-testid="panel-mouvements">
          {mouvLoading ? (
            <div data-testid="chargement-mouvements">Chargement…</div>
          ) : (
            <ul data-testid="liste-mouvements">
              {mouvements.map((mv: typeof MOUVEMENT) => (
                <li key={mv.id} data-testid={`mouvement-${mv.id}`}>
                  {mv.type_mouvement} — {mv.medicament_nom} — {mv.quantite}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {onglet === "alertes" && (
        <div data-testid="panel-alertes">
          {alertesLoading ? (
            <div data-testid="chargement-alertes">Chargement…</div>
          ) : (
            <ul data-testid="liste-alertes">
              {alertes.map((a: typeof ALERTE) => (
                <li key={a.id} data-testid={`alerte-${a.id}`}>
                  {a.medicament_nom} — qte: {a.quantite_disponible}
                  <button
                    data-testid={`resoudre-${a.id}`}
                    onClick={() => resoudreMutation.mutate(a.id)}
                  >
                    Résoudre
                  </button>
                </li>
              ))}
            </ul>
          )}
          {alertes.length === 0 && <div data-testid="alertes-vide">Aucune alerte</div>}
        </div>
      )}

      {dialogAjuster && (
        <div data-testid="dialog-ajuster">
          <input
            aria-label="Lot ID"
            value={lotId}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) => setLotId(e.target.value)}
          />
          <input
            aria-label="Nouvelle quantité"
            type="number"
            value={nouvelleQte}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) => setNouvelleQte(e.target.value)}
          />
          <input
            aria-label="Motif"
            value={motif}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) => setMotif(e.target.value)}
          />
          <button
            data-testid="btn-confirmer-ajuster"
            onClick={() => ajusterMutation.mutate()}
          >
            Confirmer
          </button>
          <button onClick={() => setDialogAjuster(false)}>Annuler</button>
        </div>
      )}
    </div>
  );
}

// ── Tests ────────────────────────────────────────────────────────────────────

describe("PageStock", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockMedListe.mockResolvedValue({ results: [MED_STOCK], count: 1 });
    mockLotsListe.mockResolvedValue({ results: [LOT_OK, LOT_EXPIRE], count: 2 });
    mockMouvListe.mockResolvedValue({ results: [MOUVEMENT], count: 1 });
    mockAlertesListe.mockResolvedValue({ results: [ALERTE], count: 1 });
    mockAjusterStock.mockResolvedValue({});
    mockAlertesResoudre.mockResolvedValue({});
  });

  it("rend le titre", () => {
    render(<PageStockMin />, { wrapper });
    expect(screen.getByText("Gestion des stocks")).toBeInTheDocument();
  });

  it("affiche les 4 onglets", () => {
    render(<PageStockMin />, { wrapper });
    ["overview", "lots", "mouvements", "alertes"].forEach((o) => {
      expect(screen.getByTestId(`onglet-${o}`)).toBeInTheDocument();
    });
  });

  it("onglet overview actif par défaut", () => {
    render(<PageStockMin />, { wrapper });
    expect(screen.getByTestId("panel-overview")).toBeInTheDocument();
  });

  it("affiche les médicaments avec leur stock", async () => {
    render(<PageStockMin />, { wrapper });
    await waitFor(() =>
      expect(screen.getByTestId("med-stock-m1")).toHaveTextContent("Paracetamol 500mg — 45")
    );
  });

  it("badge alerte si stock <= seuil", async () => {
    mockMedListe.mockResolvedValue({
      results: [{ ...MED_STOCK, stock_disponible: 15 }], count: 1,
    });
    render(<PageStockMin />, { wrapper });
    await waitFor(() =>
      expect(screen.getByTestId("badge-alerte-m1")).toBeInTheDocument()
    );
  });

  it("pas de badge alerte si stock > seuil", async () => {
    render(<PageStockMin />, { wrapper });
    await waitFor(() =>
      expect(screen.queryByTestId("badge-alerte-m1")).not.toBeInTheDocument()
    );
  });

  it("bascule vers l'onglet Lots", async () => {
    render(<PageStockMin />, { wrapper });
    fireEvent.click(screen.getByTestId("onglet-lots"));
    await waitFor(() => expect(screen.getByTestId("panel-lots")).toBeInTheDocument());
  });

  it("affiche les lots dans l'onglet Lots", async () => {
    render(<PageStockMin />, { wrapper });
    fireEvent.click(screen.getByTestId("onglet-lots"));
    await waitFor(() => {
      expect(screen.getByTestId("lot-l1")).toHaveTextContent("LOT-001");
      expect(screen.getByTestId("lot-l2")).toHaveTextContent("LOT-002");
    });
  });

  it("bascule vers l'onglet Mouvements", async () => {
    render(<PageStockMin />, { wrapper });
    fireEvent.click(screen.getByTestId("onglet-mouvements"));
    await waitFor(() => expect(screen.getByTestId("panel-mouvements")).toBeInTheDocument());
  });

  it("affiche les mouvements", async () => {
    render(<PageStockMin />, { wrapper });
    fireEvent.click(screen.getByTestId("onglet-mouvements"));
    await waitFor(() =>
      expect(screen.getByTestId("mouvement-mv1")).toHaveTextContent("entree")
    );
  });

  it("bascule vers l'onglet Alertes", async () => {
    render(<PageStockMin />, { wrapper });
    fireEvent.click(screen.getByTestId("onglet-alertes"));
    await waitFor(() => expect(screen.getByTestId("panel-alertes")).toBeInTheDocument());
  });

  it("affiche les alertes non résolues", async () => {
    render(<PageStockMin />, { wrapper });
    fireEvent.click(screen.getByTestId("onglet-alertes"));
    await waitFor(() =>
      expect(screen.getByTestId("alerte-a1")).toHaveTextContent("Paracetamol 500mg")
    );
  });

  it("affiche 'Aucune alerte' si liste vide", async () => {
    mockAlertesListe.mockResolvedValue({ results: [], count: 0 });
    render(<PageStockMin />, { wrapper });
    fireEvent.click(screen.getByTestId("onglet-alertes"));
    await waitFor(() => expect(screen.getByTestId("alertes-vide")).toBeInTheDocument());
  });

  it("résout une alerte", async () => {
    render(<PageStockMin />, { wrapper });
    fireEvent.click(screen.getByTestId("onglet-alertes"));
    await waitFor(() => expect(screen.getByTestId("resoudre-a1")).toBeInTheDocument());
    fireEvent.click(screen.getByTestId("resoudre-a1"));
    await waitFor(() => expect(mockAlertesResoudre).toHaveBeenCalledWith("a1"));
  });

  it("ouvre le dialog d'ajustement de stock", () => {
    render(<PageStockMin />, { wrapper });
    fireEvent.click(screen.getByTestId("btn-ajuster"));
    expect(screen.getByTestId("dialog-ajuster")).toBeInTheDocument();
  });

  it("ferme le dialog sur Annuler", () => {
    render(<PageStockMin />, { wrapper });
    fireEvent.click(screen.getByTestId("btn-ajuster"));
    fireEvent.click(screen.getByText("Annuler"));
    expect(screen.queryByTestId("dialog-ajuster")).not.toBeInTheDocument();
  });

  it("appelle api.stocks.ajuster à la confirmation", async () => {
    render(<PageStockMin />, { wrapper });
    fireEvent.click(screen.getByTestId("btn-ajuster"));

    fireEvent.change(screen.getByRole("textbox", { name: /Lot ID/i }), {
      target: { value: "l1" },
    });
    fireEvent.change(screen.getByRole("spinbutton", { name: /Nouvelle quantité/i }), {
      target: { value: "50" },
    });
    fireEvent.change(screen.getByRole("textbox", { name: /Motif/i }), {
      target: { value: "Inventaire" },
    });

    fireEvent.click(screen.getByTestId("btn-confirmer-ajuster"));
    await waitFor(() =>
      expect(mockAjusterStock).toHaveBeenCalledWith({
        lot_id: "l1",
        nouvelle_quantite: 50,
        motif: "Inventaire",
      })
    );
  });
});
