/**
 * src/lib/sw-register.ts
 * Enregistrement du Service Worker et gestion du cycle de vie (DT-007)
 *
 * - Enregistre le SW uniquement en production (évite la confusion en dev)
 * - Expose useSWStatus() hook React pour l'UI de mise à jour
 * - Écoute les messages SW pour notifier l'UI de la synchronisation
 * - Enregistre background sync dès qu'une entrée est ajoutée à la file
 */

export type SWStatus =
  | "inactif"
  | "installation"
  | "attente_mise_a_jour"
  | "actif"
  | "erreur";

let _status: SWStatus = "inactif";
let _registration: ServiceWorkerRegistration | null = null;
const _listeners: Array<(s: SWStatus) => void> = [];

function notify(s: SWStatus) {
  _status = s;
  _listeners.forEach((fn) => fn(s));
}

/** Enregistre le Service Worker. Appelé depuis main.tsx. */
export async function enregistrerServiceWorker(): Promise<void> {
  if (!("serviceWorker" in navigator)) return;

  // En développement, ne pas enregistrer (Vite HMR incompatible)
  if (import.meta.env.DEV) {
    console.info("[SW] Mode développement — Service Worker désactivé.");
    return;
  }

  try {
    notify("installation");
    _registration = await navigator.serviceWorker.register(
      "/service-worker.js",
      { scope: "/" }
    );

    _registration.addEventListener("updatefound", () => {
      const newWorker = _registration!.installing;
      newWorker?.addEventListener("statechange", () => {
        if (
          newWorker.state === "installed" &&
          navigator.serviceWorker.controller
        ) {
          notify("attente_mise_a_jour");
        }
      });
    });

    navigator.serviceWorker.addEventListener("message", handleSWMessage);

    if (_registration.active) {
      notify("actif");
    }

    // Vérifier les mises à jour toutes les 60 secondes
    setInterval(() => _registration?.update(), 60_000);

    console.info("[SW] Service Worker enregistré avec succès.");
  } catch (err) {
    console.error("[SW] Échec enregistrement:", err);
    notify("erreur");
  }
}

/** Demande au SW d'appliquer immédiatement la mise à jour en attente. */
export function appliquerMiseAJour(): void {
  const waiting = _registration?.waiting;
  if (waiting) {
    waiting.postMessage({ type: "SKIP_WAITING" });
    window.location.reload();
  }
}

/** Déclenche manuellement la synchronisation de la file hors-ligne. */
export function declencherSync(): void {
  if (_registration?.active) {
    _registration.active.postMessage({ type: "SYNC_NOW" });
  }
}

/** Demande un Background Sync au navigateur (si supporté). */
export async function demanderBackgroundSync(): Promise<void> {
  if (_registration && "sync" in _registration) {
    try {
      await (_registration as any).sync.register("pharmapp-sync-ventes");
    } catch {
      // Fallback : synchronisation directe
      declencherSync();
    }
  } else {
    declencherSync();
  }
}

/** Retourne le statut actuel du SW. */
export function getSwStatus(): SWStatus {
  return _status;
}

/** Abonnement aux changements de statut. */
export function onSwStatusChange(fn: (s: SWStatus) => void): () => void {
  _listeners.push(fn);
  return () => {
    const i = _listeners.indexOf(fn);
    if (i >= 0) _listeners.splice(i, 1);
  };
}

// ─── Gestion des messages SW → UI ────────────────────────────────────────────

type SWMessage =
  | { type: "VENTE_SYNC_OK"; venteId: string }
  | { type: "VENTE_SYNC_ECHEC_DEFINITIF"; entreeId: string };

const _msgListeners: Array<(m: SWMessage) => void> = [];

function handleSWMessage(event: MessageEvent<SWMessage>) {
  _msgListeners.forEach((fn) => fn(event.data));
}

/** Abonnement aux messages SW (sync OK/ECHEC). */
export function onSWMessage(fn: (m: SWMessage) => void): () => void {
  _msgListeners.push(fn);
  return () => {
    const i = _msgListeners.indexOf(fn);
    if (i >= 0) _msgListeners.splice(i, 1);
  };
}
