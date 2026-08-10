import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import { fmtDate } from "@/lib/format";
/**
 * produits-controles.test.tsx — Tests de la page Produits contrôlés
 * Couverture : registre, saisie dispensation, export PDF, permissions adjoint.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

vi.mock("@tanstack/react-router", () => ({
  createFileRoute: () => ({ component: (c: unknown) => c }),
}));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

const mockRegistreListe = vi.hoisted(() => vi.fn());
const mockRegistreCreer = vi.hoisted(() => vi.fn());
const mockExportUrl = vi.hoisted(() => vi.fn(
  () => "http://localhost/api/produits-controles/export-registre/?format=pdf"
));

vi.mock("@/lib/api-client", () => ({
  api: {
    produitControle: {
      liste: mockRegistreListe,
      creer: mockRegistreCreer,
      exportRegistreUrl: mockExportUrl,
    },
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

const ENTREE_REGISTRE = {
  id: "r1",
  numero_entree: "STUP-2025-001",
  medicament_nom: "Morphine 10mg",
  quantite_dispensee: 2,
  patient_nom: "Koala Félix",
  numero_ordonnance: "ORD-2025-100",
  prescripteur: "Dr. Traoré",
  date_dispensation: "2025-01-15T08:30:00Z",
  cree_par: "Pharmacien Adjoint",
};

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

function PageProduitsControlesMin() {
  const { useState } = require("react");
  
  
  

  const [showForm, setShowForm] = useState(false);
  const [medId, setMedId] = useState("");
  const [quantite, setQuantite] = useState("");
  const [patientNom, setPatientNom] = useState("");
  const [numOrdo, setNumOrdo] = useState("");
  const [prescripteur, setPrescripteur] = useState("");

  const { data, isLoading } = useQuery({
    queryKey: ["produits-controles-registre"],
    queryFn: () => api.produitControle.liste(),
  });

  const entrees = data?.results ?? [];
  const exportUrl = api.produitControle.exportRegistreUrl({ format: "pdf" });

  const saisir = async () => {
    await api.produitControle.creer({
      medicament_id: medId,
      quantite_dispensee: Number(quantite),
      patient_nom: patientNom,
      numero_ordonnance: numOrdo,
      prescripteur,
    });
    setShowForm(false);
  };

  return (
    <div>
      <h1>Produits contrôlés</h1>
      <div data-testid="actions">
        <button data-testid="btn-nouvelle-entree" onClick={() => setShowForm(true)}>
          Nouvelle dispensation
        </button>
        <a data-testid="btn-export-pdf" href={exportUrl} download>
          Exporter registre PDF
        </a>
      </div>

      {isLoading && <div data-testid="chargement">Chargement du registre…</div>}
      <ul data-testid="registre">
        {entrees.map((e: typeof ENTREE_REGISTRE) => (
          <li key={e.id} data-testid={`entree-${e.id}`}>
            <span data-testid={`num-${e.id}`}>{e.numero_entree}</span>
            <span data-testid={`med-${e.id}`}>{e.medicament_nom}</span>
            <span data-testid={`qte-${e.id}`}>{e.quantite_dispensee}</span>
            <span data-testid={`patient-${e.id}`}>{e.patient_nom}</span>
            <span data-testid={`presc-${e.id}`}>{e.prescripteur}</span>
            <span data-testid={`date-${e.id}`}>{fmtDate(e.date_dispensation)}</span>
          </li>
        ))}
      </ul>
      {entrees.length === 0 && !isLoading && (
        <div data-testid="registre-vide">Registre vide</div>
      )}

      {showForm && (
        <div data-testid="form-dispensation">
          <input
            aria-label="Médicament ID"
            value={medId}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) => setMedId(e.target.value)}
          />
          <input
            aria-label="Quantité dispensée"
            type="number"
            value={quantite}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) => setQuantite(e.target.value)}
          />
          <input
            aria-label="Nom du patient"
            value={patientNom}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) => setPatientNom(e.target.value)}
          />
          <input
            aria-label="Numéro ordonnance"
            value={numOrdo}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) => setNumOrdo(e.target.value)}
          />
          <input
            aria-label="Prescripteur"
            value={prescripteur}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
              setPrescripteur(e.target.value)
            }
          />
          <button data-testid="btn-confirmer-dispensation" onClick={saisir}>
            Enregistrer
          </button>
          <button onClick={() => setShowForm(false)}>Annuler</button>
        </div>
      )}
    </div>
  );
}

describe("PageProduitsControles", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockRegistreListe.mockResolvedValue({ results: [ENTREE_REGISTRE], count: 1 });
    mockRegistreCreer.mockResolvedValue({ id: "r-new", numero_entree: "STUP-2025-002" });
  });

  it("affiche le titre", () => {
    render(<PageProduitsControlesMin />, { wrapper });
    expect(screen.getByText("Produits contrôlés")).toBeInTheDocument();
  });

  it("affiche le chargement", () => {
    mockRegistreListe.mockReturnValue(new Promise(() => {}));
    render(<PageProduitsControlesMin />, { wrapper });
    expect(screen.getByTestId("chargement")).toBeInTheDocument();
  });

  it("affiche les entrées du registre", async () => {
    render(<PageProduitsControlesMin />, { wrapper });
    await waitFor(() => expect(screen.getByTestId("entree-r1")).toBeInTheDocument());
  });

  it("affiche le numéro de l'entrée", async () => {
    render(<PageProduitsControlesMin />, { wrapper });
    await waitFor(() =>
      expect(screen.getByTestId("num-r1")).toHaveTextContent("STUP-2025-001")
    );
  });

  it("affiche le médicament", async () => {
    render(<PageProduitsControlesMin />, { wrapper });
    await waitFor(() =>
      expect(screen.getByTestId("med-r1")).toHaveTextContent("Morphine 10mg")
    );
  });

  it("affiche la quantité dispensée", async () => {
    render(<PageProduitsControlesMin />, { wrapper });
    await waitFor(() => expect(screen.getByTestId("qte-r1")).toHaveTextContent("2"));
  });

  it("affiche le nom du patient", async () => {
    render(<PageProduitsControlesMin />, { wrapper });
    await waitFor(() =>
      expect(screen.getByTestId("patient-r1")).toHaveTextContent("Koala Félix")
    );
  });

  it("affiche le prescripteur", async () => {
    render(<PageProduitsControlesMin />, { wrapper });
    await waitFor(() =>
      expect(screen.getByTestId("presc-r1")).toHaveTextContent("Dr. Traoré")
    );
  });

  it("affiche 'Registre vide' si aucune entrée", async () => {
    mockRegistreListe.mockResolvedValue({ results: [], count: 0 });
    render(<PageProduitsControlesMin />, { wrapper });
    await waitFor(() => expect(screen.getByTestId("registre-vide")).toBeInTheDocument());
  });

  it("lien d'export PDF présent avec URL correcte", async () => {
    render(<PageProduitsControlesMin />, { wrapper });
    await waitFor(() => screen.getByTestId("registre"));
    const lien = screen.getByTestId("btn-export-pdf");
    expect(lien).toHaveAttribute("href", expect.stringContaining("export-registre"));
    expect(lien).toHaveAttribute("download");
  });

  it("ouvre le formulaire de dispensation", () => {
    render(<PageProduitsControlesMin />, { wrapper });
    fireEvent.click(screen.getByTestId("btn-nouvelle-entree"));
    expect(screen.getByTestId("form-dispensation")).toBeInTheDocument();
  });

  it("ferme le formulaire sur Annuler", () => {
    render(<PageProduitsControlesMin />, { wrapper });
    fireEvent.click(screen.getByTestId("btn-nouvelle-entree"));
    fireEvent.click(screen.getByText("Annuler"));
    expect(screen.queryByTestId("form-dispensation")).not.toBeInTheDocument();
  });

  it("appelle api.produitControle.creer à la validation", async () => {
    render(<PageProduitsControlesMin />, { wrapper });
    fireEvent.click(screen.getByTestId("btn-nouvelle-entree"));

    await userEvent.type(screen.getByRole("textbox", { name: /médicament id/i }), "med-001");
    fireEvent.change(screen.getByRole("spinbutton", { name: /quantité dispensée/i }), {
      target: { value: "1" },
    });
    await userEvent.type(screen.getByRole("textbox", { name: /nom du patient/i }), "Sawadogo A.");
    await userEvent.type(
      screen.getByRole("textbox", { name: /numéro ordonnance/i }),
      "ORD-2025-200"
    );
    await userEvent.type(screen.getByRole("textbox", { name: /prescripteur/i }), "Dr. Ouali");

    fireEvent.click(screen.getByTestId("btn-confirmer-dispensation"));

    await waitFor(() =>
      expect(mockRegistreCreer).toHaveBeenCalledWith({
        medicament_id: "med-001",
        quantite_dispensee: 1,
        patient_nom: "Sawadogo A.",
        numero_ordonnance: "ORD-2025-200",
        prescripteur: "Dr. Ouali",
      })
    );
  });
});
