import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, apiFetch, clearSession } from "./api-client";

describe("apiFetch", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
    document.cookie = "pharmapp_csrf=;expires=Thu, 01 Jan 1970 00:00:00 GMT;path=/";
    sessionStorage.clear();
  });

  it("ajoute le header CSRF et credentials sur les requêtes mutantes", async () => {
    document.cookie = "pharmapp_csrf=token-csrf-test; path=/";
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const result = await apiFetch<{ ok: boolean }>("/ping/", {
      method: "POST",
      body: { hello: "world" },
    });

    expect(result.ok).toBe(true);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [, init] = fetchMock.mock.calls[0];
    expect(init.credentials).toBe("include");
    expect(init.headers).toMatchObject({
      Accept: "application/json",
      "Content-Type": "application/json",
      "X-CSRF-Token": "token-csrf-test",
    });
  });

  it("remonte une ApiError structurée sur réponse 401", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "Session expirée" }), {
        status: 401,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    window.history.replaceState({}, "", "/tableau-bord");

    await expect(apiFetch("/profil/")).rejects.toBeInstanceOf(ApiError);
  });
});

describe("clearSession", () => {
  afterEach(() => {
    sessionStorage.clear();
  });

  it("efface la session JS", () => {
    sessionStorage.setItem("pharmapp.role", "titulaire");
    clearSession("test");
    expect(sessionStorage.getItem("pharmapp.role")).toBeNull();
  });
});
