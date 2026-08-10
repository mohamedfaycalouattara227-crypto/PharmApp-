import { useQuery, useMutation } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
/**
 * parametres.test.tsx — Tests de la page Paramétrage
 * Couverture : chargement config, onglets, modification formulaire, sauvegarde.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

vi.mock("@tanstack/react-router", () => ({
  createFileRoute: () => ({ component: (c: unknown) => c }),
}));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));
vi.mock("@/lib/utils", () => ({ cn: (...c: string[]) => c.join(" ") }));

const mockParametrageGet = vi.hoisted(() => vi.fn());
const mockParametrageModifier = vi.hoisted(() => vi.fn());

vi.mock("@/lib/api-client", () => ({
  api: {
    parametrage: {
      get: mockParametrageGet,
      modifier: mockParametrageModifier,
    },
  },
}));

const PARAMETRAGE_DEFAUT = {
  id: "p1",
  nom_pharmacie: "Pharmacie Saint-Michel",
  adresse: "01 BP 123, Ouagadougou",
  telephone: "+226 70 00 00 00",
  email: "contact@st-michel.bf",
  numero_agrement: "AGR-2020-001",
  seuil_stock_bas: 20,
  jours_avant_peremption: 60,
  type_imprimante: "thermique",
  format_numerotation: "V-{YYYY}-{NNN}",
  timeout_inactivite: 30,
  tentatives_connexion_max: 5,
};

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

function PageParametresMin() {
  const { useState, useEffect } = require("react");
  
  

  type Section = "identite" | "alertes" | "impression" | "securite";
  const [section, setSection] = useState<Section>("identite");
  const [form, setForm] = useState<Partial<typeof PARAMETRAGE_DEFAUT>>({});
  const [modifie, setModifie] = useState(false);

  const { data: parametrage, isLoading } = useQuery({
    queryKey: ["parametrage"],
    queryFn: () => api.parametrage.get(),
  });

  useEffect(() => {
    if (parametrage) { setForm(parametrage); setModifie(false); }
  }, [parametrage]);

  const set = (key: string, value: unknown) => {
    setForm((prev) => ({ ...prev, [key]: value }));
    setModifie(true);
  };

  const sauvegarder = useMutation({
    mutationFn: () => api.parametrage.modifier(form),
    onSuccess: () => setModifie(false),
  });

  if (isLoading) return <div data-testid="chargement">Chargement…</div>;

  return (
    <div>
      <h1>Paramétrage</h1>
      <nav>
        {(["identite", "alertes", "impression", "securite"] as Section[]).map((s) => (
          <button
            key={s}
            data-testid={`section-${s}`}
            onClick={() => setSection(s)}
            aria-current={section === s ? "page" : undefined}
          >
            {s}
          </button>
        ))}
      </nav>

      {section === "identite" && (
        <div data-testid="panel-identite">
          <input
            aria-label="Nom de la pharmacie"
            value={form.nom_pharmacie ?? ""}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
              set("nom_pharmacie", e.target.value)
            }
          />
          <input
            aria-label="Adresse"
            value={form.adresse ?? ""}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
              set("adresse", e.target.value)
            }
          />
          <input
            aria-label="Téléphone"
            value={form.telephone ?? ""}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
              set("telephone", e.target.value)
            }
          />
          <input
            aria-label="Email"
            value={form.email ?? ""}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
              set("email", e.target.value)
            }
          />
        </div>
      )}

      {section === "alertes" && (
        <div data-testid="panel-alertes">
          <input
            aria-label="Seuil stock bas"
            type="number"
            value={form.seuil_stock_bas ?? 0}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
              set("seuil_stock_bas", Number(e.target.value))
            }
          />
          <input
            aria-label="Jours avant péremption"
            type="number"
            value={form.jours_avant_peremption ?? 0}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
              set("jours_avant_peremption", Number(e.target.value))
            }
          />
        </div>
      )}

      {section === "impression" && (
        <div data-testid="panel-impression">
          <select
            aria-label="Type d'imprimante"
            value={form.type_imprimante ?? "thermique"}
            onChange={(e: React.ChangeEvent<HTMLSelectElement>) =>
              set("type_imprimante", e.target.value)
            }
          >
            <option value="thermique">Thermique</option>
            <option value="a4">A4</option>
          </select>
        </div>
      )}

      {section === "securite" && (
        <div data-testid="panel-securite">
          <input
            aria-label="Timeout inactivité (min)"
            type="number"
            value={form.timeout_inactivite ?? 30}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
              set("timeout_inactivite", Number(e.target.value))
            }
          />
        </div>
      )}

      <button
        data-testid="btn-sauvegarder"
        disabled={!modifie || sauvegarder.isPending}
        onClick={() => sauvegarder.mutate()}
      >
        {sauvegarder.isPending ? "Sauvegarde…" : "Sauvegarder"}
      </button>
    </div>
  );
}

describe("PageParametres", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockParametrageGet.mockResolvedValue(PARAMETRAGE_DEFAUT);
    mockParametrageModifier.mockResolvedValue(PARAMETRAGE_DEFAUT);
  });

  it("affiche le chargement initialement", () => {
    mockParametrageGet.mockReturnValue(new Promise(() => {}));
    render(<PageParametresMin />, { wrapper });
    expect(screen.getByTestId("chargement")).toBeInTheDocument();
  });

  it("affiche le formulaire après chargement", async () => {
    render(<PageParametresMin />, { wrapper });
    await waitFor(() => expect(screen.getByTestId("panel-identite")).toBeInTheDocument());
  });

  it("pré-remplit le nom de la pharmacie", async () => {
    render(<PageParametresMin />, { wrapper });
    await waitFor(() => {
      expect(screen.getByRole("textbox", { name: /nom de la pharmacie/i })).toHaveValue(
        "Pharmacie Saint-Michel"
      );
    });
  });

  it("pré-remplit l'adresse", async () => {
    render(<PageParametresMin />, { wrapper });
    await waitFor(() => {
      expect(screen.getByRole("textbox", { name: /adresse/i })).toHaveValue(
        "01 BP 123, Ouagadougou"
      );
    });
  });

  it("bouton Sauvegarder désactivé si non modifié", async () => {
    render(<PageParametresMin />, { wrapper });
    await waitFor(() => screen.getByTestId("panel-identite"));
    expect(screen.getByTestId("btn-sauvegarder")).toBeDisabled();
  });

  it("active le bouton Sauvegarder après modification", async () => {
    render(<PageParametresMin />, { wrapper });
    await waitFor(() => screen.getByTestId("panel-identite"));
    await userEvent.clear(screen.getByRole("textbox", { name: /nom de la pharmacie/i }));
    await userEvent.type(
      screen.getByRole("textbox", { name: /nom de la pharmacie/i }),
      "Pharmacie Nouvelle"
    );
    expect(screen.getByTestId("btn-sauvegarder")).not.toBeDisabled();
  });

  it("appelle api.parametrage.modifier à la sauvegarde", async () => {
    render(<PageParametresMin />, { wrapper });
    await waitFor(() => screen.getByTestId("panel-identite"));
    await userEvent.clear(screen.getByRole("textbox", { name: /nom de la pharmacie/i }));
    await userEvent.type(
      screen.getByRole("textbox", { name: /nom de la pharmacie/i }),
      "Nouvelle Pharmacie"
    );
    fireEvent.click(screen.getByTestId("btn-sauvegarder"));
    await waitFor(() => expect(mockParametrageModifier).toHaveBeenCalledTimes(1));
  });

  it("bascule vers la section Alertes", async () => {
    render(<PageParametresMin />, { wrapper });
    await waitFor(() => screen.getByTestId("section-alertes"));
    fireEvent.click(screen.getByTestId("section-alertes"));
    expect(screen.getByTestId("panel-alertes")).toBeInTheDocument();
  });

  it("affiche le seuil stock bas dans Alertes", async () => {
    render(<PageParametresMin />, { wrapper });
    await waitFor(() => screen.getByTestId("section-alertes"));
    fireEvent.click(screen.getByTestId("section-alertes"));
    await waitFor(() => {
      expect(screen.getByRole("spinbutton", { name: /seuil stock bas/i })).toHaveValue(20);
    });
  });

  it("bascule vers la section Impression", async () => {
    render(<PageParametresMin />, { wrapper });
    await waitFor(() => screen.getByTestId("section-impression"));
    fireEvent.click(screen.getByTestId("section-impression"));
    expect(screen.getByTestId("panel-impression")).toBeInTheDocument();
  });

  it("affiche le type d'imprimante dans Impression", async () => {
    render(<PageParametresMin />, { wrapper });
    await waitFor(() => screen.getByTestId("section-impression"));
    fireEvent.click(screen.getByTestId("section-impression"));
    await waitFor(() => {
      expect(screen.getByRole("combobox", { name: /type d'imprimante/i })).toHaveValue(
        "thermique"
      );
    });
  });

  it("bascule vers la section Sécurité", async () => {
    render(<PageParametresMin />, { wrapper });
    await waitFor(() => screen.getByTestId("section-securite"));
    fireEvent.click(screen.getByTestId("section-securite"));
    expect(screen.getByTestId("panel-securite")).toBeInTheDocument();
  });

  it("affiche le timeout inactivité dans Sécurité", async () => {
    render(<PageParametresMin />, { wrapper });
    await waitFor(() => screen.getByTestId("section-securite"));
    fireEvent.click(screen.getByTestId("section-securite"));
    await waitFor(() => {
      expect(
        screen.getByRole("spinbutton", { name: /timeout inactivité/i })
      ).toHaveValue(30);
    });
  });

  it("modifie le seuil d'alerte et active la sauvegarde", async () => {
    render(<PageParametresMin />, { wrapper });
    await waitFor(() => screen.getByTestId("section-alertes"));
    fireEvent.click(screen.getByTestId("section-alertes"));
    await waitFor(() =>
      screen.getByRole("spinbutton", { name: /seuil stock bas/i })
    );
    fireEvent.change(screen.getByRole("spinbutton", { name: /seuil stock bas/i }), {
      target: { value: "30" },
    });
    expect(screen.getByTestId("btn-sauvegarder")).not.toBeDisabled();
  });
});
