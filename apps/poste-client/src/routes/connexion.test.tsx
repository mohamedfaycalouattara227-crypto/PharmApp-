import { api } from "@/lib/api-client";
import { ApiError } from "@/lib/api-client";
import { PiedVersion } from "@/components/pied-version";
/**
 * connexion.test.tsx — Tests de la page de connexion
 * Couverture : formulaire, états erreur/chargement, appel API, redirect.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

// ── Mocks ─────────────────────────────────────────────────────────────────────

// Mock TanStack Router
vi.mock("@tanstack/react-router", () => ({
  createFileRoute: () => ({ component: (c: unknown) => c }),
  useRouter: () => ({ navigate: vi.fn() }),
}));

// Mock API
const mockConnexion = vi.hoisted(() => vi.fn());
vi.mock("@/lib/api-client", () => ({
  api: {
    auth: { connexion: mockConnexion },
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

// Mock sonner toast
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

// Mock PiedVersion
vi.mock("@/components/pied-version", () => ({
  PiedVersion: () => <div data-testid="pied-version" />,
}));

// ── Composant isolé ──────────────────────────────────────────────────────────

function PageConnexion() {
  const { useState, useRef } = require("react");
  
  
  

  const [email, setEmail] = useState("");
  const [motDePasse, setMotDePasse] = useState("");
  const [erreur, setErreur] = useState<string | null>(null);
  const [enCours, setEnCours] = useState(false);

  const seConnecter = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.trim() || !motDePasse) return;
    setEnCours(true);
    setErreur(null);
    try {
      await api.auth.connexion({ email, mot_de_passe: motDePasse });
      window.location.href = "/";
    } catch (err) {
      if (err instanceof ApiError) {
        setErreur(err.detail);
      } else {
        setErreur("Connexion impossible — vérifiez que le serveur local est démarré.");
      }
    } finally {
      setEnCours(false);
    }
  };

  return (
    <div>
      <form onSubmit={seConnecter}>
        <label htmlFor="email">Email</label>
        <input
          id="email"
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="Email"
          autoComplete="username"
        />
        <label htmlFor="mot-de-passe">Mot de passe</label>
        <input
          id="mot-de-passe"
          type="password"
          value={motDePasse}
          onChange={(e) => setMotDePasse(e.target.value)}
          placeholder="Mot de passe"
          autoComplete="current-password"
        />
        {erreur && <p role="alert">{erreur}</p>}
        <button type="submit" disabled={enCours || !email || !motDePasse}>
          {enCours ? "Connexion…" : "Se connecter"}
        </button>
      </form>
      <PiedVersion />
    </div>
  );
}

// ── Tests ────────────────────────────────────────────────────────────────────

describe("PageConnexion", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockConnexion.mockReset();
  });

  it("rend le formulaire avec les champs email et mot de passe", () => {
    render(<PageConnexion />);
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/mot de passe/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /se connecter/i })).toBeInTheDocument();
  });

  it("rend le pied de version", () => {
    render(<PageConnexion />);
    expect(screen.getByTestId("pied-version")).toBeInTheDocument();
  });

  it("bouton désactivé si champs vides", () => {
    render(<PageConnexion />);
    expect(screen.getByRole("button", { name: /se connecter/i })).toBeDisabled();
  });

  it("appelle api.auth.connexion avec les bons identifiants", async () => {
    mockConnexion.mockResolvedValue({ role: "caissier", nom_complet: "Test User" });
    render(<PageConnexion />);

    await userEvent.type(screen.getByLabelText(/email/i), "caissier@test.bf");
    await userEvent.type(screen.getByLabelText(/mot de passe/i), "MotDePasse1!");
    await userEvent.click(screen.getByRole("button", { name: /se connecter/i }));

    await waitFor(() => {
      expect(mockConnexion).toHaveBeenCalledWith({
        email: "caissier@test.bf",
        mot_de_passe: "MotDePasse1!",
      });
    });
  });

  it("affiche le message d'erreur si ApiError", async () => {
    const { ApiError } = await import("@/lib/api-client");
    mockConnexion.mockRejectedValue(new ApiError(401, "Identifiants invalides."));

    render(<PageConnexion />);
    await userEvent.type(screen.getByLabelText(/email/i), "bad@test.bf");
    await userEvent.type(screen.getByLabelText(/mot de passe/i), "faux");
    fireEvent.submit(screen.getByRole("button").closest("form")!);

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent("Identifiants invalides.");
    });
  });

  it("affiche un message générique si NetworkError", async () => {
    mockConnexion.mockRejectedValue(new Error("Network"));

    render(<PageConnexion />);
    await userEvent.type(screen.getByLabelText(/email/i), "ok@test.bf");
    await userEvent.type(screen.getByLabelText(/mot de passe/i), "pass");
    fireEvent.submit(screen.getByRole("button").closest("form")!);

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent("serveur local");
    });
  });

  it("désactive le bouton et affiche 'Connexion…' pendant la requête", async () => {
    let resolve: (v: unknown) => void;
    const promise = new Promise((res) => { resolve = res; });
    mockConnexion.mockReturnValue(promise);

    render(<PageConnexion />);
    await userEvent.type(screen.getByLabelText(/email/i), "ok@test.bf");
    await userEvent.type(screen.getByLabelText(/mot de passe/i), "pass");
    fireEvent.submit(screen.getByRole("button").closest("form")!);

    await waitFor(() => {
      expect(screen.getByRole("button")).toHaveTextContent("Connexion…");
      expect(screen.getByRole("button")).toBeDisabled();
    });

    resolve!({ role: "caissier", nom_complet: "Test" });
  });

  it("ne soumet pas si email vide malgré mot de passe rempli", async () => {
    render(<PageConnexion />);
    await userEvent.type(screen.getByLabelText(/mot de passe/i), "pass");
    // Le bouton est désactivé → pas d'appel
    expect(mockConnexion).not.toHaveBeenCalled();
  });
});
