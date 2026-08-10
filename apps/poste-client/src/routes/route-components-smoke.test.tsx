import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { Route as Achats } from "./_app.achats";
import { Route as Catalogue } from "./_app.catalogue";
import { Route as Clients } from "./_app.clients";
import { Route as Cloture } from "./_app.cloture";
import { Route as Parametres } from "./_app.parametres";
import { Route as ProduitsControles } from "./_app.produits-controles";
import { Route as Rapports } from "./_app.rapports";
import { Route as Stock } from "./_app.stock";
import { Route as TableauBord } from "./_app.tableau-bord";
import { Route as Utilisateurs } from "./_app.utilisateurs";
import { Route as Ventes } from "./_app.ventes";

const { api } = vi.hoisted(() => ({ api: new Proxy({}, {
  get: () => new Proxy(() => Promise.resolve({ results: [], count: 0, data: [], total: 0, alertes: [], lignes: [], detail: null }), {
    get: () => (..._args: unknown[]) => Promise.resolve({ results: [], count: 0, data: [], total: 0, alertes: [], lignes: [], detail: null }),
  }),
}) }));
vi.mock("@/lib/api-client", () => ({ api, ApiError: class ApiError extends Error { detail = "Erreur API"; } }));

const routes = [
  ["achats", Achats], ["catalogue", Catalogue], ["clients", Clients], ["cloture", Cloture],
  ["parametres", Parametres], ["produits-controles", ProduitsControles], ["rapports", Rapports],
  ["stock", Stock], ["tableau-bord", TableauBord], ["utilisateurs", Utilisateurs], ["ventes", Ventes],
] as const;

describe("composants de routes métier", () => {
  it.each(routes)("rend la route %s avec des réponses API vides", async (_nom, route) => {
    const Component = (route as any).options.component as React.ComponentType;
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const { container } = render(<QueryClientProvider client={client}><Component /></QueryClientProvider>);
    await waitFor(() => expect(container.firstChild).toBeTruthy());
  });
});
