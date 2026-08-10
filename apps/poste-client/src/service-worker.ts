/**
 * src/service-worker.ts
 * Service Worker PharmApp — PWA offline-first (DT-007)
 *
 * Stratégies :
 *  - API Django (/api/*) : NetworkFirst, fallback cache 5 min
 *  - Assets statiques (JS/CSS/images) : CacheFirst, stale-while-revalidate
 *  - Navigation HTML : NetworkFirst, fallback vers /index.html (SPA)
 *  - Background Sync : rejoue la file des ventes hors-ligne dès reconnexion
 *
 * Compatibilité : Chrome 80+, Firefox 88+, Edge 88+
 *
 * Enregistrement : voir src/main.tsx (registerSW())
 */

/// <reference lib="webworker" />

type PharmappSyncEvent = ExtendableEvent & { tag: string };
const sw = globalThis as unknown as ServiceWorkerGlobalScope;

const CACHE_APP   = "pharmapp-app-v1";
const CACHE_API   = "pharmapp-api-v1";
const SYNC_TAG    = "pharmapp-sync-ventes";
const API_PREFIX  = "/api/";
const MAX_API_AGE = 5 * 60 * 1000; // 5 minutes

// ─── Installation : précache des assets critiques ────────────────────────────

sw.addEventListener("install", (event: ExtendableEvent) => {
  event.waitUntil(
    caches.open(CACHE_APP).then((cache) =>
      cache.addAll([
        "/",
        "/index.html",
        // Les assets Vite sont ajoutés dynamiquement via stale-while-revalidate
      ])
    ).then(() => sw.skipWaiting())
  );
});

// ─── Activation : nettoyer les anciens caches ─────────────────────────────────

sw.addEventListener("activate", (event: ExtendableEvent) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((k) => k !== CACHE_APP && k !== CACHE_API)
          .map((k) => caches.delete(k))
      )
    ).then(() => sw.clients.claim())
  );
});

// ─── Interception des requêtes ────────────────────────────────────────────────

sw.addEventListener("fetch", (event: FetchEvent) => {
  const { request } = event;
  const url = new URL(request.url);

  // Ignorer les requêtes non-GET sauf les API (gérées par background sync)
  if (request.method !== "GET" && !url.pathname.startsWith(API_PREFIX)) {
    return;
  }

  // Navigation SPA → NetworkFirst, fallback /index.html
  if (request.mode === "navigate") {
    event.respondWith(networkFirstNavigation(request));
    return;
  }

  // API Django → NetworkFirst + cache court terme
  if (url.pathname.startsWith(API_PREFIX)) {
    event.respondWith(networkFirstAPI(request));
    return;
  }

  // Assets statiques → CacheFirst (Vite génère des hashes immuables)
  if (
    url.pathname.match(/\.(js|css|woff2?|png|svg|ico|webp)$/) ||
    url.pathname.startsWith("/assets/")
  ) {
    event.respondWith(cacheFirstAsset(request));
    return;
  }
});

// ─── Stratégie : NetworkFirst navigation (SPA) ───────────────────────────────

async function networkFirstNavigation(request: Request): Promise<Response> {
  try {
    const response = await fetch(request);
    const cache = await caches.open(CACHE_APP);
    cache.put(request, response.clone());
    return response;
  } catch {
    const cached = await caches.match("/index.html");
    return cached ?? new Response("PharmApp hors ligne", { status: 503 });
  }
}

// ─── Stratégie : NetworkFirst API avec cache de secours ──────────────────────

async function networkFirstAPI(request: Request): Promise<Response> {
  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(CACHE_API);
      cache.put(request, addTimestamp(response.clone()));
    }
    return response;
  } catch {
    // Réseau indisponible → chercher dans le cache API
    const cached = await caches.match(request, { cacheName: CACHE_API });
    if (cached) {
      const age = Date.now() - (Number(cached.headers.get("x-sw-cached-at")) || 0);
      if (age < MAX_API_AGE) return cached;
    }
    return new Response(
      JSON.stringify({ erreur: "Hors ligne — données non disponibles." }),
      { status: 503, headers: { "Content-Type": "application/json" } }
    );
  }
}

// ─── Stratégie : CacheFirst assets statiques ─────────────────────────────────

async function cacheFirstAsset(request: Request): Promise<Response> {
  const cached = await caches.match(request, { cacheName: CACHE_APP });
  if (cached) return cached;
  try {
    const response = await fetch(request);
    const cache = await caches.open(CACHE_APP);
    cache.put(request, response.clone());
    return response;
  } catch {
    return new Response("Asset indisponible hors ligne", { status: 503 });
  }
}

// ─── Utilitaire : ajouter horodatage au cache ─────────────────────────────────

function addTimestamp(response: Response): Response {
  const headers = new Headers(response.headers);
  headers.set("x-sw-cached-at", String(Date.now()));
  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers,
  });
}

// ─── Background Sync : rejouer file des ventes ───────────────────────────────

sw.addEventListener("sync" as any, ((event: PharmappSyncEvent) => {
  if (event.tag === SYNC_TAG) {
    event.waitUntil(rejouerFileVentes());
  }
}) as EventListener);

async function rejouerFileVentes(): Promise<void> {
  // Import dynamique de Dexie depuis le contexte SW
  // La DB est accessible car même origine
  try {
    const { db } = await import("./lib/offline-queue");
    const entrees = await db.ventes_en_attente
      .where("etat")
      .anyOf(["en_attente", "en_cours"])
      .toArray();

    for (const entree of entrees) {
      try {
        await db.ventes_en_attente.update(entree.id, { etat: "en_cours" });
        const response = await fetch("/api/ventes/", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            // Le cookie CSRF est transmis automatiquement (même origine)
          },
          credentials: "include",
          body: JSON.stringify(entree.payload),
        });

        if (response.ok) {
          const data = await response.json();
          await db.ventes_en_attente.update(entree.id, {
            etat: "acquitte",
            vente_id: data.id,
          });
          // Notifier les clients ouverts
          await notifierClients({ type: "VENTE_SYNC_OK", venteId: data.id });
        } else if (response.status >= 400 && response.status < 500) {
          // Erreur définitive (règle métier)
          const detail = await response.json().catch(() => ({}));
          await db.ventes_en_attente.update(entree.id, {
            etat: "en_echec",
            derniere_erreur: detail?.detail || `HTTP ${response.status}`,
          });
          await notifierClients({ type: "VENTE_SYNC_ECHEC_DEFINITIF", entreeId: entree.id });
        }
        // 5xx → rester en en_cours, sera rejoué
      } catch {
        // Réseau toujours indisponible — on laisse en en_cours
      }
    }
  } catch (err) {
    console.error("[SW] Erreur rejouerFileVentes:", err);
  }
}

// ─── Notification aux onglets ouverts ────────────────────────────────────────

async function notifierClients(message: unknown): Promise<void> {
  const clients = await sw.clients.matchAll({ type: "window" });
  for (const client of clients) {
    client.postMessage(message);
  }
}

// ─── Message handler : forcer mise à jour ────────────────────────────────────

sw.addEventListener("message", (event: ExtendableMessageEvent) => {
  if (event.data?.type === "SKIP_WAITING") {
    sw.skipWaiting();
  }
  if (event.data?.type === "SYNC_NOW") {
    // Déclenchement manuel de la synchronisation (bouton dans l'UI)
    rejouerFileVentes();
  }
});
