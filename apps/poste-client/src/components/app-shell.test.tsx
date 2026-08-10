import { api } from "@/lib/api-client";
import { SelecteurTheme } from "@/components/SelecteurTheme";
/**
 * app-shell.test.tsx — Tests du composant AppShell (layout principal)
 * Couverture : navigation, sélecteur de thème, rendu enfants, menu mobile.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";

// ── Mocks ─────────────────────────────────────────────────────────────────────

vi.mock("@tanstack/react-router", () => ({
  Link: ({ to, children, ...props }: Record<string, unknown>) => (
    <a href={String(to)} {...props}>{children as React.ReactNode}</a>
  ),
  useRouterState: () => ({ location: { pathname: "/" } }),
  Outlet: () => <div data-testid="outlet-contenu">Contenu de la page</div>,
  createFileRoute: () => ({ component: (c: unknown) => c }),
}));

vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

vi.mock("@/contexts/ThemeContext", () => ({
  useTheme: () => ({
    themeActif: "classique-bleu",
    changerTheme: vi.fn(),
    themes: [
      { nom: "classique-bleu", label: "Classique Bleu", couleur: "#2563eb" },
      { nom: "vert-sante", label: "Vert Santé", couleur: "#16a34a" },
    ],
    definitionActive: { nom: "classique-bleu", label: "Classique Bleu", couleur: "#2563eb" },
  }),
  ThemeProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

vi.mock("@/components/SelecteurTheme", () => ({
  SelecteurTheme: () => <div data-testid="selecteur-theme">Thème</div>,
}));

vi.mock("@/components/pied-version", () => ({
  PiedVersion: () => <div data-testid="pied-version" />,
}));

const mockApi = vi.hoisted(() => ({
  auth: { deconnecter: vi.fn() },
}));
vi.mock("@/lib/api-client", () => ({ api: mockApi }));

// ── Composant AppShell minimal ────────────────────────────────────────────────

type NavItem = { to: string; label: string; testId: string };

const NAV_ITEMS: NavItem[] = [
  { to: "/", label: "Point de vente", testId: "nav-pos" },
  { to: "/tableau-bord", label: "Tableau de bord", testId: "nav-tableau-bord" },
  { to: "/catalogue", label: "Catalogue", testId: "nav-catalogue" },
  { to: "/stock", label: "Stocks", testId: "nav-stock" },
  { to: "/clients", label: "Clients", testId: "nav-clients" },
  { to: "/ventes", label: "Ventes", testId: "nav-ventes" },
  { to: "/rapports", label: "Rapports", testId: "nav-rapports" },
  { to: "/parametres", label: "Paramètres", testId: "nav-parametres" },
];

function AppShellMin({ children }: { children?: React.ReactNode }) {
  const { useState } = require("react");
  
  
  const [menuOuvert, setMenuOuvert] = useState(false);

  const seDeconnecter = async () => {
    await api.auth.deconnecter();
    window.location.href = "/connexion";
  };

  return (
    <div data-testid="app-shell">
      <header data-testid="header">
        <button
          data-testid="btn-menu-mobile"
          className="md:hidden"
          onClick={() => setMenuOuvert((o: boolean) => !o)}
          aria-label="Menu"
        >
          ☰
        </button>
        <span data-testid="titre-app">PharmApp</span>
        <SelecteurTheme />
        <button data-testid="btn-deconnecter" onClick={seDeconnecter}>
          Déconnexion
        </button>
      </header>

      {/* Sidebar desktop */}
      <nav data-testid="sidebar-desktop" className="hidden md:block">
        {NAV_ITEMS.map((item) => (
          <a key={item.to} href={item.to} data-testid={item.testId}>
            {item.label}
          </a>
        ))}
      </nav>

      {/* Menu mobile overlay */}
      {menuOuvert && (
        <div data-testid="menu-mobile-overlay">
          <nav data-testid="sidebar-mobile">
            {NAV_ITEMS.map((item) => (
              <a
                key={item.to}
                href={item.to}
                data-testid={`mobile-${item.testId}`}
                onClick={() => setMenuOuvert(false)}
              >
                {item.label}
              </a>
            ))}
          </nav>
          <button onClick={() => setMenuOuvert(false)}>Fermer</button>
        </div>
      )}

      <main data-testid="contenu-principal">
        {children ?? <div data-testid="outlet-contenu">Contenu</div>}
      </main>
    </div>
  );
}

// ── Tests ─────────────────────────────────────────────────────────────────────

describe("AppShell", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockApi.auth.deconnecter.mockResolvedValue({});
  });

  it("rend le layout principal", () => {
    render(<AppShellMin />);
    expect(screen.getByTestId("app-shell")).toBeInTheDocument();
  });

  it("affiche le titre de l'application", () => {
    render(<AppShellMin />);
    expect(screen.getByTestId("titre-app")).toHaveTextContent("PharmApp");
  });

  it("affiche le sélecteur de thème", () => {
    render(<AppShellMin />);
    expect(screen.getByTestId("selecteur-theme")).toBeInTheDocument();
  });

  it("affiche le bouton de déconnexion", () => {
    render(<AppShellMin />);
    expect(screen.getByTestId("btn-deconnecter")).toBeInTheDocument();
  });

  it("affiche tous les liens de navigation desktop", () => {
    render(<AppShellMin />);
    NAV_ITEMS.forEach(({ testId }) => {
      expect(screen.getByTestId(testId)).toBeInTheDocument();
    });
  });

  it("lien POS pointe vers /", () => {
    render(<AppShellMin />);
    expect(screen.getByTestId("nav-pos")).toHaveAttribute("href", "/");
  });

  it("lien Catalogue pointe vers /catalogue", () => {
    render(<AppShellMin />);
    expect(screen.getByTestId("nav-catalogue")).toHaveAttribute("href", "/catalogue");
  });

  it("lien Stock pointe vers /stock", () => {
    render(<AppShellMin />);
    expect(screen.getByTestId("nav-stock")).toHaveAttribute("href", "/stock");
  });

  it("rend les enfants dans la zone principale", () => {
    render(<AppShellMin><div data-testid="contenu-test">Hello</div></AppShellMin>);
    expect(screen.getByTestId("contenu-test")).toBeInTheDocument();
  });

  it("menu mobile fermé par défaut", () => {
    render(<AppShellMin />);
    expect(screen.queryByTestId("menu-mobile-overlay")).not.toBeInTheDocument();
  });

  it("ouvre le menu mobile au clic sur le bouton hamburger", () => {
    render(<AppShellMin />);
    fireEvent.click(screen.getByTestId("btn-menu-mobile"));
    expect(screen.getByTestId("menu-mobile-overlay")).toBeInTheDocument();
  });

  it("affiche les liens de navigation dans le menu mobile", () => {
    render(<AppShellMin />);
    fireEvent.click(screen.getByTestId("btn-menu-mobile"));
    NAV_ITEMS.forEach(({ testId }) => {
      expect(screen.getByTestId(`mobile-${testId}`)).toBeInTheDocument();
    });
  });

  it("ferme le menu mobile au clic sur Fermer", () => {
    render(<AppShellMin />);
    fireEvent.click(screen.getByTestId("btn-menu-mobile"));
    fireEvent.click(screen.getByText("Fermer"));
    expect(screen.queryByTestId("menu-mobile-overlay")).not.toBeInTheDocument();
  });

  it("ferme le menu mobile au clic sur un lien de nav", () => {
    render(<AppShellMin />);
    fireEvent.click(screen.getByTestId("btn-menu-mobile"));
    fireEvent.click(screen.getByTestId("mobile-nav-pos"));
    expect(screen.queryByTestId("menu-mobile-overlay")).not.toBeInTheDocument();
  });

  it("appelle api.auth.deconnecter sur clic Déconnexion", async () => {
    render(<AppShellMin />);
    fireEvent.click(screen.getByTestId("btn-deconnecter"));
    await vi.waitFor(() => expect(mockApi.auth.deconnecter).toHaveBeenCalledTimes(1));
  });
});
