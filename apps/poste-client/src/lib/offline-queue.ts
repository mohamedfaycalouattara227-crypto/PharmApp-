/**
 * File d'attente hors-ligne (Principe n°1 & n°2 du cahier des charges).
 *
 * Toute vente validée dans l'UI est d'abord ENREGISTRÉE ICI (IndexedDB via
 * Dexie) puis rejouée vers l'API Django. Ce n'est qu'après un ACK explicite
 * de l'API que l'entrée est retirée. Ce mécanisme garantit qu'une coupure
 * réseau ne peut jamais faire perdre une vente.
 *
 * Le serveur local a lui-même une outbox vers le cloud — la présente file
 * est le miroir *poste-de-vente ↔ serveur local*, complémentaire.
 *
 * CORRECTION AUDIT v2 (P1 — faux succès en caisse) :
 *   traiterFile() retourne désormais un résumé en trois catégories :
 *     - acquittees        : ventes ACK serveur (succès réel)
 *     - echecs_definitifs : rejetées définitivement par le serveur (4xx) —
 *                           ne se resynchroniseront JAMAIS ; le caissier
 *                           doit en être informé immédiatement
 *     - echecs_transitoires : erreurs réseau / 5xx — seront rejouées au
 *                             prochain traiterFile()
 *
 *   L'ancienne signature { acquittees, echecs } fusionnait les deux types
 *   d'échec, ce qui permettait à validerVente() de montrer "sera synchronisée
 *   dès reprise du réseau" pour une vente définitivement rejetée (stock
 *   insuffisant, règle métier, etc.).
 */

import Dexie, { type Table } from "dexie";
import { api, ApiError, NetworkError } from "./api-client";

export type EtatEntree = "en_attente" | "en_cours" | "en_echec" | "acquitte";

export interface EntreeFileVente {
  id: string;                    // UUID client — idempotence
  cree_le: string;               // ISO date
  payload: unknown;              // corps POST /api/ventes/
  etat: EtatEntree;
  tentatives: number;
  derniere_erreur?: string;
  vente_id?: string;             // rempli après ACK
}

/** Résumé d'un appel à traiterFile(). */
export interface ResultatTraitement {
  acquittees: number;
  derniereVenteId?: string | null;
  /** Échecs définitifs (4xx) — ne seront jamais resynchronisés. */
  echecs_definitifs: number;
  /** Échecs transitoires (réseau, 5xx) — seront rejoués automatiquement. */
  echecs_transitoires: number;
}

class PharmAppDB extends Dexie {
  ventes_en_attente!: Table<EntreeFileVente, string>;

  constructor() {
    super("pharmapp");
    this.version(1).stores({
      ventes_en_attente: "id, etat, cree_le",
    });
  }
}

export const db = new PharmAppDB();

/** Génère un UUID v4 côté client (idempotence). */
export function idempotencyKey(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `pv-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

export async function fileEnAttente(): Promise<EntreeFileVente[]> {
  // CORRECTION BUG #2 : "en_echec" est un état TERMINAL — ces entrées ne doivent
  // jamais être rejouées automatiquement. Les inclure provoquait un cycle infini :
  // traiterFile() les retentait → 4xx → en_echec → retry 15 s → boucle.
  return db.ventes_en_attente
    .where("etat")
    .anyOf(["en_attente", "en_cours"])
    .toArray();
}

/** Retourne les entrées définitivement échouées (état terminal, jamais rejoué). */
export async function fileEnEchec(): Promise<EntreeFileVente[]> {
  return db.ventes_en_attente
    .where("etat")
    .equals("en_echec")
    .toArray();
}

export async function enfilerVente(payload: unknown): Promise<EntreeFileVente> {
  const entree: EntreeFileVente = {
    id: idempotencyKey(),
    cree_le: new Date().toISOString(),
    payload,
    etat: "en_attente",
    tentatives: 0,
  };
  await db.ventes_en_attente.put(entree);
  return entree;
}

/**
 * Tente d'acquitter toutes les entrées en attente.
 *
 * Retourne un résumé en trois catégories distinctes :
 *   - acquittees        : ACK serveur reçu — vente enregistrée côté serveur
 *   - echecs_definitifs : rejet 4xx — erreur métier définitive (stock, règle…)
 *   - echecs_transitoires : réseau / 5xx — sera rejoué
 *
 * Les erreurs 4xx sont marquées "en_echec" (état terminal).
 * Les erreurs réseau / 5xx sont remises "en_attente" pour retry.
 */
export async function traiterFile(): Promise<ResultatTraitement> {
  let acquittees = 0;
  let echecs_definitifs = 0;
  let echecs_transitoires = 0;
  let derniereVenteId: string | null = null;

  const entrees = await fileEnAttente();

  for (const entree of entrees) {
    await db.ventes_en_attente.update(entree.id, {
      etat: "en_cours",
      tentatives: entree.tentatives + 1,
    });

    try {
      const vente = await api.ventes.creer({
        ...(entree.payload as object),
        idempotency_key: entree.id,
      });
      await db.ventes_en_attente.update(entree.id, {
        etat: "acquitte",
        vente_id: (vente as { id: string }).id,
      });
      acquittees++;
      derniereVenteId = (vente as { id: string }).id ?? null;
    } catch (e) {
      const message =
        e instanceof ApiError
          ? `${e.status} — ${e.detail}`
          : e instanceof NetworkError
            ? "Serveur local injoignable"
            : String(e);

      // Erreur définitive : rejet 4xx (validation métier, stock insuffisant,
      // ordonnance manquante, règle pharmacie…). Ne JAMAIS rejouer.
      const definitif = e instanceof ApiError && e.status >= 400 && e.status < 500;

      await db.ventes_en_attente.update(entree.id, {
        etat: definitif ? "en_echec" : "en_attente",
        derniere_erreur: message,
      });

      if (definitif) {
        echecs_definitifs++;
      } else {
        echecs_transitoires++;
      }
    }
  }

  // Purge les acquittées vieilles de plus d'une heure
  const seuil = new Date(Date.now() - 60 * 60 * 1000).toISOString();
  await db.ventes_en_attente
    .where("etat").equals("acquitte")
    .and((e) => e.cree_le < seuil)
    .delete();

  return { acquittees, echecs_definitifs, echecs_transitoires, derniereVenteId };
}
