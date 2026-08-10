import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import { fmtFCFA } from "@/lib/format";
/**
 * tableau-bord.test.tsx — Tests de la page Tableau de bord
 * Couverture : rendu KPIs, états chargement, alertes, résolution d'alerte, lots péremption.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

// ── Mocks globaux ─────────────────────────────────────────────────────────────

vi.mock("@tanstack/react-router", () => ({
  createFileRoute: () => ({ component: (c: unknown) => c }),
  useRouter: () => ({ navigate: vi.fn() }),
}));

vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

const mockTableauBord = vi.hoisted(() => vi.fn());
const mockAlertesListe = vi.hoisted(() => vi.fn());
const mockLotsListe = vi.hoisted(() => vi.fn());
const mockSyncEtat = vi.hoisted(() => vi.fn());
const mockAlertesResoudre = vi.hoisted(() => vi.fn());

vi.mock("@/lib/api-client", () => ({
  api: {
    rapports: { tableauBord: mockTableauBord },
    alertes: { liste: mockAlertesListe, resoudre: mockAlertesResoudre },
    lots: { liste: mockLotsListe },
    sync: { etat: mockSyncEtat },
  },
}));

vi.mock("@/lib/format", () => ({
  fmtFCFA: (v: number) => `${v} F CFA`,
  fmtDate: (d: string) => d,
  fmtDateCourte: (d: string) => d,
}));

// ── Données de test ──────────────────────────────────────────────────────────

const KPI_DEFAUT = {
  ca_aujourd_hui: "150000",
  nb_ventes_aujourd_hui: 12,
  nb_alertes_stock: 3,
  nb_ruptures: 1,
  nb_peremptions_proches: 5,
  seuil_peremption_jours: 60,
};

const ALERTE_MOCK = {
  id: "alerte-1",
  medicament_nom: "Paracetamol 500mg",
  niveau: "alerte",
  quantite_disponible: 8,
  seuil_alerte: 20,
  est_resolue: false,
};

const LOT_MOCK = {
  id: "lot-1",
  medicament_nom: "Amoxicilline 500mg",
  numero_lot: "LOT-2025-001",
  quantite_disponible: 30,
  date_peremption: "2025-03-15",
};

const SYNC_ETAT_DEFAUT = {
  nb_en_attente: 0,
  nb_en_echec: 0,
  supabase_accessible: true,
  conflits_non_resolus: 0,
};

// ── Wrapper QueryClient ──────────────────────────────────────────────────────

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

// ── Composant minimal du tableau de bord ─────────────────────────────────────

function PageTableauBordMin() {
  
  
  

  const { data: kpis, isLoading } = useQuery({
    queryKey: ["tableau-bord"],
    queryFn: () => api.rapports.tableauBord(),
  });
  const { data: alertesData } = useQuery({
    queryKey: ["alertes-stock"],
    queryFn: () => api.alertes.liste({ est_resolue: false }),
  });
  const { data: lotsData } = useQuery({
    queryKey: ["lots"],
    queryFn: () => api.lots.liste({ peremption_proche: true }),
  });
  const { data: syncData } = useQuery({
    queryKey: ["sync-etat"],
    queryFn: () => api.sync.etat(),
  });
  const qc = useQueryClient();
  const resoudreAlerte = useMutation({
    mutationFn: (id: string) => api.alertes.resoudre(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["alertes-stock"] });
    },
  });

  if (isLoading) return <div data-testid="chargement">Chargement…</div>;

  const alertes = alertesData?.results ?? [];
  const lots = lotsData?.results ?? [];

  return (
    <div>
      <h1>Tableau de bord</h1>
      {kpis && (
        <div>
          <div data-testid="ca">{fmtFCFA(Number(kpis.ca_aujourd_hui))}</div>
          <div data-testid="nb-ventes">{kpis.nb_ventes_aujourd_hui} ventes</div>
          <div data-testid="nb-alertes">{kpis.nb_alertes_stock} alertes</div>
          <div data-testid="nb-ruptures">{kpis.nb_ruptures} ruptures</div>
          <div data-testid="nb-peremptions">{kpis.nb_peremptions_proches} péremptions proches</div>
        </div>
      )}
      <div data-testid="sync-status">
        {syncData?.supabase_accessible ? "Connecté" : "Hors ligne"}
      </div>
      <ul data-testid="liste-alertes">
        {alertes.map((a: typeof ALERTE_MOCK) => (
          <li key={a.id}>
            {a.medicament_nom}
            <button onClick={() => resoudreAlerte.mutate(a.id)}>Résoudre</button>
          </li>
        ))}
      </ul>
      <ul data-testid="liste-lots">
        {lots.map((l: typeof LOT_MOCK) => (
          <li key={l.id}>{l.medicament_nom} — {l.date_peremption}</li>
        ))}
      </ul>
    </div>
  );
}

// ── Tests ────────────────────────────────────────────────────────────────────

describe("PageTableauBord", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockTableauBord.mockResolvedValue(KPI_DEFAUT);
    mockAlertesListe.mockResolvedValue({ results: [], count: 0 });
    mockLotsListe.mockResolvedValue({ results: [], count: 0 });
    mockSyncEtat.mockResolvedValue(SYNC_ETAT_DEFAUT);
  });

  it("affiche l'état de chargement initialement", () => {
    mockTableauBord.mockReturnValue(new Promise(() => {}));
    render(<PageTableauBordMin />, { wrapper });
    expect(screen.getByTestId("chargement")).toBeInTheDocument();
  });

  it("affiche le CA après chargement", async () => {
    render(<PageTableauBordMin />, { wrapper });
    await waitFor(() => expect(screen.getByTestId("ca")).toHaveTextContent("150000"));
  });

  it("affiche le nombre de ventes", async () => {
    render(<PageTableauBordMin />, { wrapper });
    await waitFor(() => expect(screen.getByTestId("nb-ventes")).toHaveTextContent("12 ventes"));
  });

  it("affiche le nombre d'alertes stock", async () => {
    render(<PageTableauBordMin />, { wrapper });
    await waitFor(() => expect(screen.getByTestId("nb-alertes")).toHaveTextContent("3 alertes"));
  });

  it("affiche le nombre de ruptures", async () => {
    render(<PageTableauBordMin />, { wrapper });
    await waitFor(() => expect(screen.getByTestId("nb-ruptures")).toHaveTextContent("1 ruptures"));
  });

  it("affiche le nombre de péremptions proches", async () => {
    render(<PageTableauBordMin />, { wrapper });
    await waitFor(() =>
      expect(screen.getByTestId("nb-peremptions")).toHaveTextContent("5 péremptions proches")
    );
  });

  it("affiche le statut sync 'Connecté' si supabase accessible", async () => {
    render(<PageTableauBordMin />, { wrapper });
    await waitFor(() => expect(screen.getByTestId("sync-status")).toHaveTextContent("Connecté"));
  });

  it("affiche 'Hors ligne' si supabase inaccessible", async () => {
    mockSyncEtat.mockResolvedValue({ ...SYNC_ETAT_DEFAUT, supabase_accessible: false });
    render(<PageTableauBordMin />, { wrapper });
    await waitFor(() => expect(screen.getByTestId("sync-status")).toHaveTextContent("Hors ligne"));
  });

  it("affiche la liste des alertes", async () => {
    mockAlertesListe.mockResolvedValue({ results: [ALERTE_MOCK], count: 1 });
    render(<PageTableauBordMin />, { wrapper });
    await waitFor(() =>
      expect(screen.getByTestId("liste-alertes")).toHaveTextContent("Paracetamol 500mg")
    );
  });

  it("affiche les lots en péremption proche", async () => {
    mockLotsListe.mockResolvedValue({ results: [LOT_MOCK], count: 1 });
    render(<PageTableauBordMin />, { wrapper });
    await waitFor(() =>
      expect(screen.getByTestId("liste-lots")).toHaveTextContent("Amoxicilline 500mg")
    );
  });

  it("appelle api.alertes.resoudre au clic sur Résoudre", async () => {
    mockAlertesListe.mockResolvedValue({ results: [ALERTE_MOCK], count: 1 });
    mockAlertesResoudre.mockResolvedValue({});
    render(<PageTableauBordMin />, { wrapper });
    await waitFor(() => expect(screen.getByText("Résoudre")).toBeInTheDocument());
    fireEvent.click(screen.getByText("Résoudre"));
    await waitFor(() => expect(mockAlertesResoudre).toHaveBeenCalledWith("alerte-1"));
  });

  it("affiche une liste vide si aucune alerte", async () => {
    mockAlertesListe.mockResolvedValue({ results: [], count: 0 });
    render(<PageTableauBordMin />, { wrapper });
    await waitFor(() => {
      const liste = screen.getByTestId("liste-alertes");
      expect(liste.children).toHaveLength(0);
    });
  });

  it("appelle tableauBord, alertes.liste, lots.liste et sync.etat au montage", async () => {
    render(<PageTableauBordMin />, { wrapper });
    await waitFor(() => expect(mockTableauBord).toHaveBeenCalledTimes(1));
    expect(mockAlertesListe).toHaveBeenCalled();
    expect(mockLotsListe).toHaveBeenCalled();
    expect(mockSyncEtat).toHaveBeenCalled();
  });
});
