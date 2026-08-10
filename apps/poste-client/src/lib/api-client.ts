/**
 * Client API — parle exclusivement au backend Django local.
 *
 * Principes (§ Cahier des charges) :
 *  - Aucune dépendance cloud directe côté frontend.
 *  - Toute réponse ≥ 400 lève un `ApiError` typé.
 *  - En cas d'échec réseau, `NetworkError` est levée.
 *
 * ÉTAPES 4–10 : ajout de tous les endpoints manquants :
 *   api.catalogue.* (médic CRUD, catégories, lots, import CSV) — étape 4
 *   api.clients.* (CRUD complet) — étape 5
 *   api.fournisseurs.* (CRUD complet) — étape 6
 *   api.bonsCommande.* (création BC) — étape 6
 *   api.ventes.recu / avoir — étapes 7 & 7
 *   api.rapports.* (agrégats, export) — étape 8
 *   api.utilisateurs.* (CRUD + suspend) — étape 9
 *   api.ordonnances.* (upload multipart) — étape 10
 *
 * ÉTAPE 11 :
 *   api.ventes.annuler(id, motif) — POST /ventes/{id}/annuler/
 *   api.ventes.calculerMonnaie(id, montant) — POST /ventes/{id}/monnaie/
 *   api.clients.rechercher(q) — GET /clients/?search=q
 *   api.clients.creerRapide() — POST /clients/ (payload minimal)
 *   api.produitControle.* — CRUD registre + export PDF
 *   api.synchronisation.etat() — GET /synchronisation/etat/
 *
 * ÉTAPE 12 :
 *   Intercepteur 401 → clearSession + redirect /connexion
 *
 * ÉTAPE 15 :
 *   api.synchronisation.etat() enrichi avec supabase_accessible
 */

const RAW_BASE = (import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000").replace(/\/$/, "");
export const API_BASE_URL = `${RAW_BASE}/api`;

/**
 * Auth : depuis v5, plus AUCUN token n'est stocké côté JS.
 * Le backend émet des cookies httpOnly (`pharmapp_access`, `pharmapp_refresh`)
 * et un cookie CSRF lisible JS (`pharmapp_csrf`) qui doit être renvoyé dans
 * l'en-tête `X-CSRF-Token` sur toute requête non idempotente.
 */
const CSRF_COOKIE = "pharmapp_csrf";

function readCookie(nom: string): string | null {
  if (typeof document === "undefined") return null;
  const cible = `${nom}=`;
  for (const c of document.cookie.split(";")) {
    const s = c.trim();
    if (s.startsWith(cible)) return decodeURIComponent(s.slice(cible.length));
  }
  return null;
}

/** @deprecated conservé pour compatibilité, ne stocke plus rien. */
export function getToken(): string | null {
  return null;
}

/** @deprecated : no-op. Les tokens vivent en cookie httpOnly. */
export function setToken(_token: string | null): void {
  /* intentionnellement vide */
}

/** Efface la session côté JS et redirige vers /connexion. */
export function clearSession(raison = "session_expiree"): void {
  try {
    sessionStorage.clear();
  } catch {
    /* ignore */
  }
  if (typeof window !== "undefined") {
    window.location.href = `/connexion?raison=${raison}`;
  }
}

export class ApiError extends Error {
  status: number;
  body: unknown;
  detail: string;
  constructor(status: number, detail: string, body: unknown) {
    super(detail || `Erreur ${status}`);
    this.status = status;
    this.detail = detail;
    this.body = body;
  }
}

export class NetworkError extends Error {
  constructor(message = "Le serveur local n'est pas joignable.") {
    super(message);
  }
}

type Method = "GET" | "POST" | "PATCH" | "PUT" | "DELETE";

interface RequestOptions {
  method?: Method;
  body?: unknown;
  query?: Record<string, string | number | boolean | undefined | null>;
  signal?: AbortSignal;
  formData?: FormData;
}

function buildUrl(path: string, query?: RequestOptions["query"]): string {
  const url = new URL(`${API_BASE_URL}${path.startsWith("/") ? path : `/${path}`}`);
  if (query) {
    for (const [k, v] of Object.entries(query)) {
      if (v === undefined || v === null) continue;
      url.searchParams.set(k, String(v));
    }
  }
  return url.toString();
}

export async function apiFetch<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = {
    Accept: "application/json",
  };
  if (!opts.formData) {
    headers["Content-Type"] = "application/json";
  }
  const method: Method = opts.method ?? "GET";
  if (method !== "GET") {
    const csrf = readCookie(CSRF_COOKIE);
    if (csrf) headers["X-CSRF-Token"] = csrf;
  }

  let response: Response;
  try {
    response = await fetch(buildUrl(path, opts.query), {
      method,
      headers,
      body: opts.formData
        ? opts.formData
        : opts.body === undefined
        ? undefined
        : JSON.stringify(opts.body),
      signal: opts.signal,
      credentials: "include",
    });
  } catch (e) {
    throw new NetworkError();
  }

  // ── Étape 12 : intercepteur 401 → clearSession + redirect ────────────────
  if (response.status === 401) {
    // Éviter la redirection si on est déjà sur /connexion
    if (typeof window !== "undefined" && !window.location.pathname.startsWith("/connexion")) {
      clearSession("session_expiree");
    }
    throw new ApiError(401, "Session expirée. Veuillez vous reconnecter.", null);
  }

  const ct = response.headers.get("content-type") ?? "";
  let body: unknown = null;
  if (ct.includes("application/json")) {
    body = await response.json();
  } else if (!response.ok) {
    body = await response.text();
  }

  if (!response.ok) {
    const detail =
      typeof body === "object" && body !== null
        ? (body as Record<string, unknown>)["detail"] as string ||
          (body as Record<string, unknown>)["erreur"] as string ||
          JSON.stringify(body)
        : String(body || response.statusText);
    throw new ApiError(response.status, detail, body);
  }

  return body as T;
}

// ── API Object ──────────────────────────────────────────────────────────────

export const api = {

  // ── Auth ───────────────────────────────────────────────────────────────
  auth: {
    connexion: (email: string, mot_de_passe: string) =>
      apiFetch<{ role: string; nom_complet: string }>("/auth/connexion/", {
        method: "POST", body: { email, mot_de_passe },
      }),
    deconnexion: () =>
      apiFetch<{ message: string }>("/auth/deconnexion/", { method: "POST" }),
    profil: () =>
      apiFetch<import("./types").Utilisateur>("/auth/profil/"),
  },

  // ── Ventes ─────────────────────────────────────────────────────────────
  ventes: {
    creer: (payload: unknown) =>
      apiFetch<import("./types").Vente>("/ventes/", { method: "POST", body: payload }),
    liste: (params?: Record<string, string>) =>
      apiFetch<import("./types").Page<import("./types").Vente>>("/ventes/", { query: params }),
    detail: (id: string) =>
      apiFetch<import("./types").Vente>(`/ventes/${id}/`),
    recu: (id: string) =>
      apiFetch<import("./types").RecuDTO>(`/ventes/${id}/recu/`),

    /** Étape 11 — Annulation avec motif obligatoire */
    annuler: (id: string, motif: string) =>
      apiFetch<import("./types").Vente>(`/ventes/${id}/annuler/`, {
        method: "POST", body: { motif },
      }),

    /** Étape 11 — Calcul monnaie rendue en temps réel */
    calculerMonnaie: (id: string, montant_encaisse: number) =>
      apiFetch<{ montant_rendu: number; decomposition: Record<string, number> }>(
        `/ventes/${id}/monnaie/`,
        { method: "POST", body: { montant_encaisse } },
      ),

    /** Étape 14 — Créer un avoir (retour produit) */
    avoir: (
      id: string,
      payload: { lignes: Array<{ ligne_id: string; quantite: number }>; motif: string },
    ) =>
      apiFetch<{
        vente_origine: string;
        motif: string;
        lignes_retournees: Array<{ medicament_nom: string; quantite: number; montant: string }>;
        total_avoir: string;
        message: string;
      }>(`/ventes/${id}/avoir/`, { method: "POST", body: payload }),
  },

  // ── Clôtures ────────────────────────────────────────────────────────────
  clotures: {
    liste: () => apiFetch<import("./types").Page<import("./types").ClotureCaisse>>("/clotures/"),
    du_jour: () =>
      apiFetch<import("./types").ClotureCaisse[] | null>("/clotures/", {
        query: { date_today: "1" },
      }),
    creer: (payload: unknown) =>
      apiFetch<import("./types").ClotureCaisse>("/clotures/", { method: "POST", body: payload }),
  },

  // ── Étape 5 — Clients ───────────────────────────────────────────────────
  clients: {
    liste: (params?: Record<string, string | boolean>) =>
      apiFetch<import("./types").Page<import("./types").Client>>("/clients/", { query: params }),
    /** Étape 11 — Recherche autocomplete */
    rechercher: (q: string) =>
      apiFetch<import("./types").Page<import("./types").Client>>("/clients/", {
        query: { search: q, page_size: "10" },
      }),
    detail: (id: string) => apiFetch<import("./types").Client>(`/clients/${id}/`),
    /** Étape 11 — Création rapide depuis le POS */
    creer: (payload: unknown) =>
      apiFetch<import("./types").Client>("/clients/", { method: "POST", body: payload }),
    modifier: (id: string, payload: unknown) =>
      apiFetch<import("./types").Client>(`/clients/${id}/`, { method: "PATCH", body: payload }),
    supprimer: (id: string) =>
      apiFetch<void>(`/clients/${id}/`, { method: "DELETE" }),
    ventes: (id: string) =>
      apiFetch<import("./types").Page<import("./types").Vente>>("/ventes/", { query: { client: id } }),
  },

  // ── Étape 13 — Produits contrôlés ──────────────────────────────────────
  produitsControles: {
    liste: (params?: Record<string, string>) =>
      apiFetch<import("./types").Page<import("./types").RegistreProduitControle>>(
        "/produits-controles/",
        { query: params },
      ),
    exportRegistreUrl: (params?: {
      date_debut?: string;
      date_fin?: string;
      medicament?: string;
    }): string => {
      const url = new URL(`${API_BASE_URL}/produits-controles/export-registre/`);
      if (params?.date_debut) url.searchParams.set("date_debut", params.date_debut);
      if (params?.date_fin) url.searchParams.set("date_fin", params.date_fin);
      if (params?.medicament) url.searchParams.set("medicament", params.medicament);
      return url.toString();
    },
  },

  // ── Synchronisation (Étape 15) ──────────────────────────────────────────
  synchronisation: {
    etat: () =>
      apiFetch<{
        nb_en_attente: number;
        nb_en_echec: number;
        derniere_synchro_reussie: string | null;
        supabase_accessible: boolean;
        conflits_non_resolus: number;
      }>("/synchronisation/etat/"),
    rejouer: () =>
      apiFetch<{ rejoues: number }>("/synchronisation/rejouer/", { method: "POST" }),
  },

  // ── Étape 6 — Fournisseurs ──────────────────────────────────────────────
  fournisseurs: {
    liste: (params?: Record<string, string | boolean | number>) =>
      apiFetch<import("./types").Page<import("./types").Fournisseur>>("/fournisseurs/", {
        query: params,
      }),
    detail: (id: string) => apiFetch<import("./types").Fournisseur>(`/fournisseurs/${id}/`),
    creer: (payload: unknown) =>
      apiFetch<import("./types").Fournisseur>("/fournisseurs/", {
        method: "POST", body: payload,
      }),
    modifier: (id: string, payload: unknown) =>
      apiFetch<import("./types").Fournisseur>(`/fournisseurs/${id}/`, {
        method: "PATCH", body: payload,
      }),
    supprimer: (id: string) =>
      apiFetch<void>(`/fournisseurs/${id}/`, { method: "DELETE" }),
  },

  bonsCommande: {
    liste: (params?: Record<string, string>) =>
      apiFetch<import("./types").Page<import("./types").BonCommande>>("/bons-commande/", {
        query: params,
      }),
    detail: (id: string) => apiFetch<import("./types").BonCommande>(`/bons-commande/${id}/`),
    creer: (payload: unknown) =>
      apiFetch<import("./types").BonCommande>("/bons-commande/", {
        method: "POST", body: payload,
      }),
    envoyer: (id: string) =>
      apiFetch<import("./types").BonCommande>(`/bons-commande/${id}/envoyer/`, { method: "POST" }),
    annuler: (id: string, motif: string) =>
      apiFetch<import("./types").BonCommande>(`/bons-commande/${id}/annuler/`, {
        method: "POST", body: { motif },
      }),
    receptionner: (id: string, payload: unknown) =>
      apiFetch<unknown>(`/bons-commande/${id}/receptionner/`, {
        method: "POST", body: payload,
      }),
  },

  // ── Étape 1 — Tableau de bord ──────────────────────────────────────────
  rapports: {
    tableauBord: () =>
      apiFetch<import("./types").TableauBord>("/rapports/tableau-bord/"),
    ventes: (params?: Record<string, string>) =>
      apiFetch<import("./types").RapportVentes>("/rapports/ventes/", { query: params }),
    topProduits: (params?: { periode?: number; limit?: number }) =>
      apiFetch<import("./types").TopProduit[]>("/rapports/top-produits/", { query: params }),
    marges: (params?: Record<string, string>) =>
      apiFetch<import("./types").MargeProduit[]>("/rapports/marges/", { query: params }),
    ecartsInventaire: () =>
      apiFetch<unknown[]>("/rapports/ecarts-inventaire/"),
    exportVentesUrl: (debut?: string, fin?: string): string => {
      const q = new URLSearchParams();
      if (debut) q.set("debut", debut);
      if (fin) q.set("fin", fin);
      return `${API_BASE_URL}/rapports/export-ventes/?${q.toString()}`;
    },
  },

  // ── Étape 2 — Stocks ──────────────────────────────────────────────────
  stocks: {
    mouvements: (params?: Record<string, string | number | boolean>) =>
      apiFetch<import("./types").Page<import("./types").MouvementStock>>("/stocks/mouvements/", {
        query: params,
      }),
    ajuster: (payload: { lot_id: string; nouvelle_quantite: number; motif: string; notes?: string }) =>
      apiFetch<{ message: string; lot_id: string }>("/stocks/ajuster/", {
        method: "POST",
        body: payload,
      }),
    inventaires: () =>
      apiFetch<import("./types").Page<unknown>>("/stocks/inventaires/"),
    demarrerInventaire: (reference?: string) =>
      apiFetch<unknown>("/stocks/inventaires/", {
        method: "POST",
        body: reference ? { reference } : {},
      }),
    besoinsReappro: () =>
      apiFetch<unknown[]>("/stocks/besoins-reappro/"),
    /** Étape 11 — Vérifier stock disponible pour un médicament */
    stockMedicament: (medicamentId: string) =>
      apiFetch<import("./types").Page<import("./types").LotDetail>>("/lots/", {
        query: { medicament: medicamentId, quantite_disponible__gt: 0 },
      }),
  },

  alertes: {
    liste: (params?: Record<string, string | boolean>) =>
      apiFetch<import("./types").Page<import("./types").AlerteStock>>("/alertes/", { query: params }),
    resoudre: (id: string) =>
      apiFetch<import("./types").AlerteStock>(`/alertes/${id}/resoudre/`, { method: "POST" }),
  },

  lots: {
    liste: (params?: Record<string, string | number | boolean>) =>
      apiFetch<import("./types").Page<import("./types").LotDetail>>("/lots/", {
        query: params,
      }),
  },

  // ── Étape 3 — Paramétrage ─────────────────────────────────────────────
  parametrage: {
    get: () => apiFetch<import("./types").Parametrage>("/parametrage/"),
    modifier: (payload: Partial<import("./types").Parametrage>) =>
      apiFetch<import("./types").Parametrage>("/parametrage/", {
        method: "PATCH",
        body: payload,
      }),
  },

  // ── Étape 4 — Catalogue ───────────────────────────────────────────────
  catalogue: {
    medicaments: {
      liste: (params?: Record<string, string | boolean | number>) =>
        apiFetch<import("./types").Page<import("./types").Medicament>>("/medicaments/", {
          query: params,
        }),
      detail: (id: string) =>
        apiFetch<import("./types").Medicament>(`/medicaments/${id}/`),
      creer: (payload: unknown) =>
        apiFetch<import("./types").Medicament>("/medicaments/", {
          method: "POST", body: payload,
        }),
      modifier: (id: string, payload: unknown) =>
        apiFetch<import("./types").Medicament>(`/medicaments/${id}/`, {
          method: "PATCH", body: payload,
        }),
    },
    categories: {
      liste: () =>
        apiFetch<import("./types").Page<import("./types").CategorieProduit>>("/categories/"),
    },
    lots: {
      liste: (params?: Record<string, string | number | boolean>) =>
        apiFetch<import("./types").Page<import("./types").LotDetail>>("/lots/", {
          query: params,
        }),
      detail: (id: string) =>
        apiFetch<import("./types").LotDetail>(`/lots/${id}/`),
    },
  },

  // ── Étape 9 — Utilisateurs ─────────────────────────────────────────────
  utilisateurs: {
    liste: (params?: Record<string, string | boolean>) =>
      apiFetch<import("./types").Page<import("./types").Utilisateur>>("/auth/utilisateurs/", {
        query: params,
      }),
    detail: (id: string) => apiFetch<import("./types").Utilisateur>(`/auth/utilisateurs/${id}/`),
    creer: (payload: unknown) =>
      apiFetch<import("./types").Utilisateur>("/auth/utilisateurs/", {
        method: "POST", body: payload,
      }),
    modifier: (id: string, payload: unknown) =>
      apiFetch<import("./types").Utilisateur>(`/auth/utilisateurs/${id}/`, {
        method: "PATCH", body: payload,
      }),
    suspendre: (id: string) =>
      apiFetch<{ message: string; est_actif: boolean }>(`/auth/utilisateurs/${id}/suspendre/`, {
        method: "POST", body: { action: "suspendre" },
      }),
    reactiver: (id: string) =>
      apiFetch<{ message: string; est_actif: boolean }>(`/auth/utilisateurs/${id}/suspendre/`, {
        method: "POST", body: { action: "reactiver" },
      }),
    deverrouiller: (id: string) =>
      apiFetch<{ message: string }>(`/auth/utilisateurs/${id}/deverrouiller/`, {
        method: "POST",
      }),
  },

  // ── Shorthands (compat aliases for component imports) ──────────────────
  /** @alias catalogue.medicaments — used directly by stock/catalogue/achats pages */
  medicaments: {
    liste: (params?: Record<string, string | boolean | number>) =>
      apiFetch<import("./types").Page<import("./types").Medicament>>("/medicaments/", { query: params }),
    detail: (id: string) =>
      apiFetch<import("./types").Medicament>(`/medicaments/${id}/`),
    creer: (payload: unknown) =>
      apiFetch<import("./types").Medicament>("/medicaments/", { method: "POST", body: payload }),
    modifier: (id: string, payload: unknown) =>
      apiFetch<import("./types").Medicament>(`/medicaments/${id}/`, { method: "PATCH", body: payload }),
    rechercher: (q: string) =>
      apiFetch<import("./types").Page<import("./types").Medicament>>("/medicaments/", {
        query: { search: q, page_size: "20" },
      }),
    importerCSV: (file: File) => {
      const fd = new FormData();
      fd.append("fichier", file);
      return apiFetch<{ importe: number; erreurs: string[] }>("/medicaments/import-csv/", {
        method: "POST",
        formData: fd,
      });
    },
  },

  /** @alias catalogue.categories */
  categories: {
    liste: (params?: Record<string, string>) =>
      apiFetch<import("./types").Page<import("./types").CategorieProduit>>("/categories/", { query: params }),
    creer: (payload: unknown) =>
      apiFetch<import("./types").CategorieProduit>("/categories/", { method: "POST", body: payload }),
    modifier: (id: string, payload: unknown) =>
      apiFetch<import("./types").CategorieProduit>(`/categories/${id}/`, { method: "PATCH", body: payload }),
    supprimer: (id: string) => apiFetch<void>(`/categories/${id}/`, { method: "DELETE" }),
  },

  /** @alias synchronisation */
  sync: {
    etat: () => apiFetch<import("./types").EtatSync>("/synchronisation/etat/"),
    rejouer: () => apiFetch<{ rejoues: number }>("/synchronisation/rejouer/", { method: "POST" }),
  },

  // ── Étape 10 — Ordonnances ─────────────────────────────────────────────
  ordonnances: {
    liste: (params?: Record<string, string>) =>
      apiFetch<import("./types").Page<import("./types").Ordonnance>>("/ordonnances/", {
        query: params,
      }),
    detail: (id: string) => apiFetch<import("./types").Ordonnance>(`/ordonnances/${id}/`),
    creer: (payload: {
      fichier?: File;
      client_id?: string;
      prescripteur_nom?: string;
      prescripteur_etablissement?: string;
      date_prescription?: string;
      notes?: string;
    }) => {
      const fd = new FormData();
      if (payload.fichier) fd.append("fichier", payload.fichier);
      if (payload.client_id) fd.append("client_id", payload.client_id);
      if (payload.prescripteur_nom) fd.append("prescripteur_nom", payload.prescripteur_nom);
      if (payload.prescripteur_etablissement)
        fd.append("prescripteur_etablissement", payload.prescripteur_etablissement);
      if (payload.date_prescription) fd.append("date_prescription", payload.date_prescription);
      if (payload.notes) fd.append("notes", payload.notes);
      return apiFetch<import("./types").Ordonnance>("/ordonnances/", {
        method: "POST",
        formData: fd,
      });
    },
    valider: (id: string) =>
      apiFetch<import("./types").Ordonnance>(`/ordonnances/${id}/valider/`, { method: "POST" }),
  },
};
