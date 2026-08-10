import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ScreenAchats } from "./ScreenAchats";
import { ScreenClients } from "./ScreenClients";
import { ScreenCloture } from "./ScreenCloture";
import { ScreenOrdonnances } from "./ScreenOrdonnances";
import { ScreenParametres } from "./ScreenParametres";
import { ScreenProduitsControles } from "./ScreenProduitsControles";
import { ScreenRapports } from "./ScreenRapports";
import { ScreenStock } from "./ScreenStock";
import { ScreenSynchronisation } from "./ScreenSynchronisation";
import { ScreenTableauBord } from "./ScreenTableauBord";
import { ScreenUtilisateurs } from "./ScreenUtilisateurs";
import { ScreenVentes } from "./ScreenVentes";

const { api } = vi.hoisted(() => ({ api: new Proxy({}, {
  get: () => new Proxy(() => Promise.resolve({ results: [], count: 0, data: [], total: 0, alertes: [], lignes: [], detail: null }), {
    get: () => (..._args: unknown[]) => Promise.resolve({ results: [], count: 0, data: [], total: 0, alertes: [], lignes: [], detail: null }),
  }),
}) }));
vi.mock("@/lib/api-client", () => ({
  api,
  ApiError: class ApiError extends Error { detail = "Erreur API"; status = 500; },
}));

const screens = [
  ["achats", ScreenAchats], ["clients", ScreenClients], ["cloture", ScreenCloture],
  ["ordonnances", ScreenOrdonnances], ["parametres", ScreenParametres],
  ["produits contrôlés", ScreenProduitsControles], ["rapports", ScreenRapports],
  ["stock", ScreenStock], ["synchronisation", ScreenSynchronisation],
  ["tableau de bord", ScreenTableauBord], ["utilisateurs", ScreenUtilisateurs], ["ventes", ScreenVentes],
] as const;

describe("écrans métier — rendu et état vide", () => {
  it.each(screens)("rend l’écran %s sans exception avec une API vide", async (_nom, Screen) => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const { container } = render(<QueryClientProvider client={client}><Screen /></QueryClientProvider>);
    await waitFor(() => expect(container.firstChild).toBeTruthy());
    expect(container.firstChild).toBeInTheDocument();
  });
});
