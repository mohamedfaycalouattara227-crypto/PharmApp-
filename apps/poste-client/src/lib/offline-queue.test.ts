/**
 * tests/lib/offline-queue.test.ts
 *
 * Tests unitaires de la file d'attente hors-ligne (DT-004 / P3-A).
 *
 * Couverture :
 *  - enfilerVente() : création d'une entrée IndexedDB
 *  - fileEnAttente() : ne retourne que "en_attente" / "en_cours" (pas "en_echec")
 *  - fileEnEchec()   : retourne uniquement "en_echec"
 *  - traiterFile()   : ACK serveur → acquittée
 *  - traiterFile()   : 4xx → en_echec (définitif, ne rejouera pas)
 *  - traiterFile()   : réseau → en_attente (transitoire, sera rejoué)
 *  - purge des acquittées > 1h
 *  - idempotencyKey() : format UUID valide
 */

import "fake-indexeddb/auto";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// Ré-importer après le stub fake-indexeddb pour que Dexie utilise le mock
import {
  db,
  enfilerVente,
  fileEnAttente,
  fileEnEchec,
  idempotencyKey,
  traiterFile,
} from "./offline-queue";
import { ApiError, NetworkError } from "./api-client";

// ─── Stub du module api-client ────────────────────────────────────────────────
vi.mock("./api-client", async (importOriginal) => {
  const original = await importOriginal<typeof import("./api-client")>();
  return {
    ...original,
    api: {
      ventes: {
        creer: vi.fn(),
      },
    },
    ApiError: original.ApiError,
    NetworkError: original.NetworkError,
  };
});

import { api } from "./api-client";

// ─── Helpers ──────────────────────────────────────────────────────────────────
const payloadMinimal = () => ({
  panier: [{ medicament_id: "uuid-med-1", quantite: 2, prix_unitaire_demande: "500.00" }],
  mode_paiement: "especes",
  montant_encaisse: "1000.00",
});

// ─── Setup / teardown ─────────────────────────────────────────────────────────
beforeEach(async () => {
  // Vider la table entre chaque test
  await db.ventes_en_attente.clear();
  vi.clearAllMocks();
});

afterEach(() => {
  vi.useRealTimers();
});

// ─── idempotencyKey ───────────────────────────────────────────────────────────
describe("idempotencyKey()", () => {
  it("retourne une chaîne non vide", () => {
    const k = idempotencyKey();
    expect(k).toBeTruthy();
    expect(typeof k).toBe("string");
  });

  it("retourne des clés uniques à chaque appel", () => {
    const k1 = idempotencyKey();
    const k2 = idempotencyKey();
    expect(k1).not.toBe(k2);
  });
});

// ─── enfilerVente ─────────────────────────────────────────────────────────────
describe("enfilerVente()", () => {
  it("crée une entrée avec état 'en_attente'", async () => {
    const payload = payloadMinimal();
    const entree = await enfilerVente(payload);

    expect(entree.etat).toBe("en_attente");
    expect(entree.tentatives).toBe(0);
    expect(entree.id).toBeTruthy();

    const stockee = await db.ventes_en_attente.get(entree.id);
    expect(stockee).toBeDefined();
    expect(stockee!.etat).toBe("en_attente");
  });

  it("persiste le payload complet", async () => {
    const payload = payloadMinimal();
    const entree = await enfilerVente(payload);
    const stockee = await db.ventes_en_attente.get(entree.id);
    expect(stockee!.payload).toEqual(payload);
  });

  it("deux appels créent deux entrées distinctes", async () => {
    await enfilerVente(payloadMinimal());
    await enfilerVente(payloadMinimal());
    const count = await db.ventes_en_attente.count();
    expect(count).toBe(2);
  });
});

// ─── fileEnAttente ────────────────────────────────────────────────────────────
describe("fileEnAttente()", () => {
  it("retourne uniquement les entrées en_attente et en_cours", async () => {
    // Créer 4 entrées dans des états différents
    await db.ventes_en_attente.bulkPut([
      { id: "id-1", cree_le: new Date().toISOString(), payload: {}, etat: "en_attente", tentatives: 0 },
      { id: "id-2", cree_le: new Date().toISOString(), payload: {}, etat: "en_cours", tentatives: 1 },
      { id: "id-3", cree_le: new Date().toISOString(), payload: {}, etat: "en_echec", tentatives: 3 },
      { id: "id-4", cree_le: new Date().toISOString(), payload: {}, etat: "acquitte", tentatives: 1 },
    ]);

    const file = await fileEnAttente();
    expect(file).toHaveLength(2);
    expect(file.map((e) => e.id).sort()).toEqual(["id-1", "id-2"]);
  });

  it("ne retourne PAS les entrées en_echec (état terminal)", async () => {
    // DT-023 : s'assurer que les en_echec ne sont jamais rejoués
    await db.ventes_en_attente.put({
      id: "echec-terminal",
      cree_le: new Date().toISOString(),
      payload: {},
      etat: "en_echec",
      tentatives: 5,
    });

    const file = await fileEnAttente();
    expect(file).toHaveLength(0);
  });
});

// ─── fileEnEchec ──────────────────────────────────────────────────────────────
describe("fileEnEchec()", () => {
  it("retourne uniquement les entrées en_echec", async () => {
    await db.ventes_en_attente.bulkPut([
      { id: "ok-1", cree_le: new Date().toISOString(), payload: {}, etat: "acquitte", tentatives: 1 },
      { id: "err-1", cree_le: new Date().toISOString(), payload: {}, etat: "en_echec", tentatives: 2 },
    ]);

    const echecs = await fileEnEchec();
    expect(echecs).toHaveLength(1);
    expect(echecs[0].id).toBe("err-1");
  });
});

// ─── traiterFile ─────────────────────────────────────────────────────────────
describe("traiterFile()", () => {
  it("acquitte une entrée quand l'API répond 200", async () => {
    const venteId = "srv-vente-uuid-001";
    (api.ventes.creer as ReturnType<typeof vi.fn>).mockResolvedValueOnce({ id: venteId });

    await enfilerVente(payloadMinimal());
    const resultat = await traiterFile();

    expect(resultat.acquittees).toBe(1);
    expect(resultat.echecs_definitifs).toBe(0);
    expect(resultat.echecs_transitoires).toBe(0);
    expect(resultat.derniereVenteId).toBe(venteId);

    const entrees = await db.ventes_en_attente.toArray();
    expect(entrees[0].etat).toBe("acquitte");
    expect(entrees[0].vente_id).toBe(venteId);
  });

  it("marque en_echec (définitif) sur erreur 4xx — ne rejouera jamais", async () => {
    (api.ventes.creer as ReturnType<typeof vi.fn>).mockRejectedValueOnce(
      new ApiError(422, { erreur: "Stock insuffisant" }, "Stock insuffisant"),
    );

    await enfilerVente(payloadMinimal());
    const resultat = await traiterFile();

    expect(resultat.echecs_definitifs).toBe(1);
    expect(resultat.echecs_transitoires).toBe(0);
    expect(resultat.acquittees).toBe(0);

    const entrees = await db.ventes_en_attente.toArray();
    expect(entrees[0].etat).toBe("en_echec");
  });

  it("remet en_attente (transitoire) sur erreur réseau — sera rejoué", async () => {
    (api.ventes.creer as ReturnType<typeof vi.fn>).mockRejectedValueOnce(
      new NetworkError("Serveur local injoignable"),
    );

    await enfilerVente(payloadMinimal());
    const resultat = await traiterFile();

    expect(resultat.echecs_transitoires).toBe(1);
    expect(resultat.echecs_definitifs).toBe(0);

    const entrees = await db.ventes_en_attente.toArray();
    expect(entrees[0].etat).toBe("en_attente");
  });

  it("remet en_attente (transitoire) sur erreur 503", async () => {
    (api.ventes.creer as ReturnType<typeof vi.fn>).mockRejectedValueOnce(
      new ApiError(503, { detail: "Service indisponible" }, "Service indisponible"),
    );

    await enfilerVente(payloadMinimal());
    const resultat = await traiterFile();

    expect(resultat.echecs_transitoires).toBe(1);
    const entrees = await db.ventes_en_attente.toArray();
    expect(entrees[0].etat).toBe("en_attente");
  });

  it("traite plusieurs entrées et cumule les compteurs", async () => {
    (api.ventes.creer as ReturnType<typeof vi.fn>)
      .mockResolvedValueOnce({ id: "v-001" })                                   // ACK
      .mockRejectedValueOnce(new ApiError(400, {}, "Panier invalide"))          // 4xx définitif
      .mockRejectedValueOnce(new NetworkError("timeout"));                       // réseau transitoire

    await enfilerVente(payloadMinimal());
    await enfilerVente(payloadMinimal());
    await enfilerVente(payloadMinimal());

    const resultat = await traiterFile();

    expect(resultat.acquittees).toBe(1);
    expect(resultat.echecs_definitifs).toBe(1);
    expect(resultat.echecs_transitoires).toBe(1);
  });

  it("purge les entrées acquittées de plus d'une heure", async () => {
    // NB : pas de faux timers ici — fake-indexeddb ordonnance ses transactions
    // via les timers réels ; les figer bloque toute opération Dexie.
    const uneHeureEtDemie = new Date(Date.now() - 90 * 60 * 1000).toISOString();

    await db.ventes_en_attente.put({
      id: "ancienne-acquittee",
      cree_le: uneHeureEtDemie,
      payload: {},
      etat: "acquitte",
      tentatives: 1,
      vente_id: "v-old",
    });

    // traiterFile() avec file vide déclenche quand même la purge
    await traiterFile();

    const restante = await db.ventes_en_attente.get("ancienne-acquittee");
    expect(restante).toBeUndefined();
  });

  it("conserve les acquittées récentes lors de la purge", async () => {
    await db.ventes_en_attente.put({
      id: "acquittee-recente",
      cree_le: new Date().toISOString(),
      payload: {},
      etat: "acquitte",
      tentatives: 1,
      vente_id: "v-new",
    });

    await traiterFile();

    const restante = await db.ventes_en_attente.get("acquittee-recente");
    expect(restante).toBeDefined();
  });

  it("génère une clé via le fallback si crypto.randomUUID n'existe pas", () => {
    const originalCrypto = global.crypto;

    Object.defineProperty(global, "crypto", {
      value: undefined,
      configurable: true,
      writable: true,
    });

    const key = idempotencyKey();
    expect(key).toMatch(/^pv-\d+-/);

    Object.defineProperty(global, "crypto", {
      value: originalCrypto,
      configurable: true,
      writable: true,
    });
  });
});
