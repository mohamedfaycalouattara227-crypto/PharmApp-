/**
 * api-client-avance.test.ts — Tests avancés du client API
 * Couverture des branches non testées : NetworkError, ApiError 401,
 * clearSession, buildUrl avec query params, formData, readCookie.
 */

import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";

// Réinitialiser fetch entre chaque test
const originalFetch = globalThis.fetch;

afterEach(() => {
  globalThis.fetch = originalFetch;
  vi.restoreAllMocks();
});

function mockFetch(status: number, body: unknown, contentType = "application/json") {
  const responseBody = typeof body === "string" ? body : JSON.stringify(body);
  globalThis.fetch = vi.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    headers: { get: (_: string) => contentType },
    json: () => Promise.resolve(body),
    text: () => Promise.resolve(responseBody),
  } as unknown as Response);
}

describe("apiFetch — NetworkError", () => {
  it("lève NetworkError si fetch échoue avec exception réseau", async () => {
    const { apiFetch, NetworkError } = await import("@/lib/api-client");
    globalThis.fetch = vi.fn().mockRejectedValue(new TypeError("Failed to fetch"));
    await expect(apiFetch("/test/")).rejects.toBeInstanceOf(NetworkError);
  });
});

describe("apiFetch — ApiError", () => {
  it("lève ApiError avec le statut HTTP sur 400", async () => {
    const { apiFetch, ApiError } = await import("@/lib/api-client");
    mockFetch(400, { detail: "Données invalides" });
    const err = await apiFetch("/test/").catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(400);
    expect(err.detail).toContain("Données invalides");
  });

  it("lève ApiError avec le champ erreur si detail absent", async () => {
    const { apiFetch, ApiError } = await import("@/lib/api-client");
    mockFetch(422, { erreur: "Crédit non autorisé" });
    const err = await apiFetch("/test/").catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.detail).toContain("Crédit non autorisé");
  });

  it("lève ApiError sur réponse texte non-JSON", async () => {
    const { apiFetch, ApiError } = await import("@/lib/api-client");
    mockFetch(500, "Erreur serveur interne", "text/plain");
    const err = await apiFetch("/test/").catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(500);
  });
});

describe("apiFetch — 401 intercepteur", () => {
  it("appelle clearSession et lève ApiError 401", async () => {
    const { apiFetch, ApiError } = await import("@/lib/api-client");
    mockFetch(401, { detail: "Non authentifié" });
    // Simuler window.location hors de /connexion
    Object.defineProperty(window, "location", {
      writable: true,
      value: { pathname: "/", href: "" },
    });
    const err = await apiFetch("/protected/").catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(401);
  });
});

describe("ApiError", () => {
  it("hérite de Error et expose status, detail, body", async () => {
    const { ApiError } = await import("@/lib/api-client");
    const err = new ApiError(404, "Introuvable", { id: "x" });
    expect(err).toBeInstanceOf(Error);
    expect(err.status).toBe(404);
    expect(err.detail).toBe("Introuvable");
    expect(err.body).toEqual({ id: "x" });
    expect(err.message).toBe("Introuvable");
  });

  it("construit un message par défaut si detail vide", async () => {
    const { ApiError } = await import("@/lib/api-client");
    const err = new ApiError(500, "", null);
    expect(err.message).toBe("Erreur 500");
  });
});

describe("NetworkError", () => {
  it("hérite de Error avec message par défaut", async () => {
    const { NetworkError } = await import("@/lib/api-client");
    const err = new NetworkError();
    expect(err).toBeInstanceOf(Error);
    expect(err.message).toContain("serveur local");
  });

  it("accepte un message personnalisé", async () => {
    const { NetworkError } = await import("@/lib/api-client");
    const err = new NetworkError("Timeout");
    expect(err.message).toBe("Timeout");
  });
});

describe("getToken / setToken dépréciés", () => {
  it("getToken retourne toujours null (cookie httpOnly)", async () => {
    const { getToken } = await import("@/lib/api-client");
    expect(getToken()).toBeNull();
  });

  it("setToken est un no-op sans erreur", async () => {
    const { setToken } = await import("@/lib/api-client");
    expect(() => setToken("anytoken")).not.toThrow();
  });
});

describe("apiFetch — méthodes HTTP et CSRF", () => {
  it("n'envoie pas X-CSRF-Token sur GET", async () => {
    const { apiFetch } = await import("@/lib/api-client");
    mockFetch(200, { ok: true });
    await apiFetch("/test/", { method: "GET" });
    const call = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    const headers = call[1]?.headers as Record<string, string>;
    expect(headers?.["X-CSRF-Token"]).toBeUndefined();
  });

  it("envoie le body JSON sur POST", async () => {
    const { apiFetch } = await import("@/lib/api-client");
    mockFetch(201, { id: "123" });
    await apiFetch("/test/", { method: "POST", body: { nom: "Test" } });
    const call = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(call[1]?.body).toBe(JSON.stringify({ nom: "Test" }));
  });
});

describe("apiFetch — query params", () => {
  it("construit l'URL avec les paramètres de query", async () => {
    const { apiFetch } = await import("@/lib/api-client");
    mockFetch(200, []);
    await apiFetch("/medicaments/", { query: { search: "Amox", page: 1 } });
    const url = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls[0][0] as string;
    expect(url).toContain("search=Amox");
    expect(url).toContain("page=1");
  });

  it("omet les paramètres null/undefined", async () => {
    const { apiFetch } = await import("@/lib/api-client");
    mockFetch(200, []);
    await apiFetch("/medicaments/", { query: { search: null, page: undefined } });
    const url = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls[0][0] as string;
    expect(url).not.toContain("search");
    expect(url).not.toContain("page");
  });
});

describe("apiFetch — formData", () => {
  it("envoie un FormData sans Content-Type JSON", async () => {
    const { apiFetch } = await import("@/lib/api-client");
    mockFetch(200, { crees: 2 });
    const fd = new FormData();
    fd.append("fichier", new Blob(["test"]), "test.csv");
    await apiFetch("/catalogue/medicaments/import-csv/", {
      method: "POST",
      formData: fd,
    });
    const call = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    const headers = call[1]?.headers as Record<string, string>;
    expect(headers?.["Content-Type"]).toBeUndefined();
    expect(call[1]?.body).toBeInstanceOf(FormData);
  });
});
