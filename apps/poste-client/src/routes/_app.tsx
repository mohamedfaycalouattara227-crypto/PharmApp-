import { createFileRoute, redirect, isRedirect } from "@tanstack/react-router";
import { useEffect, useRef } from "react";
import { AppShell } from "@/components/app-shell";

/**
 * Layout pathless : monte le shell (sidebar, statut synchro) et rend
 * l'Outlet des routes enfants `_app.*.tsx`.
 *
 * SÉCURITÉ v5 : le JWT est désormais en cookie httpOnly.
 * La garde effective est :
 *   1. Un ping /auth/profil/ dans beforeLoad — 401 ⇒ redirect /connexion.
 *   2. Le backend re-vérifie les permissions à chaque appel.
 *
 * ÉTAPE 12 — Déconnexion automatique par inactivité (CDC §4.1) :
 *   Hook useIdleTimer : écoute mousemove, keydown, click, scroll.
 *   Si aucun événement depuis `timeout` ms → déconnexion + redirect /connexion.
 *   Le timeout est lu depuis /api/parametrage/ (INACTIVITE_TIMEOUT_MINUTES).
 *   Par défaut : 15 minutes.
 *   L'intercepteur axios dans api-client.ts redirige aussi sur 401.
 */

const DEFAULT_IDLE_TIMEOUT_MS = 15 * 60 * 1000; // 15 minutes

/**
 * Hook useIdleTimer — détecte l'inactivité utilisateur.
 *
 * @param timeoutMs  Durée d'inactivité avant déconnexion (millisecondes).
 * @param onIdle     Callback appelé quand le timeout est atteint.
 */
function useIdleTimer(timeoutMs: number, onIdle: () => void): void {
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const onIdleRef = useRef(onIdle);
  onIdleRef.current = onIdle;

  useEffect(() => {
    if (timeoutMs <= 0) return;

    const reset = () => {
      if (timerRef.current) clearTimeout(timerRef.current);
      timerRef.current = setTimeout(() => {
        onIdleRef.current();
      }, timeoutMs);
    };

    const EVENTS = ["mousemove", "keydown", "click", "scroll", "touchstart"] as const;

    EVENTS.forEach((ev) => window.addEventListener(ev, reset, { passive: true }));
    reset(); // Démarre le timer dès le montage

    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
      EVENTS.forEach((ev) => window.removeEventListener(ev, reset));
    };
  }, [timeoutMs]);
}

/**
 * Composant wrapper qui monte AppShell + gère la déconnexion par inactivité.
 */
function AppLayoutWithIdleLogout() {
  // Lire le timeout depuis le parametrage (stocké lors du chargement initial)
  // Fallback sur la valeur par défaut si non disponible.
  const timeoutMs = (() => {
    try {
      const raw = sessionStorage.getItem("inactivite_timeout_minutes");
      if (raw) return parseInt(raw, 10) * 60 * 1000;
    } catch {
      /* ignore */
    }
    return DEFAULT_IDLE_TIMEOUT_MS;
  })();

  useIdleTimer(timeoutMs, async () => {
    try {
      const base = (import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000").replace(/\/$/, "");
      await fetch(`${base}/api/auth/deconnexion/`, {
        method: "POST",
        credentials: "include",
        headers: { Accept: "application/json" },
      });
    } catch {
      /* Déconnexion locale même si l'API est indisponible */
    }
    // Effacer les données de session côté JS
    try {
      sessionStorage.clear();
    } catch {
      /* ignore */
    }
    window.location.href = "/connexion?raison=inactivite";
  });

  return <AppShell />;
}

export const Route = createFileRoute("/_app")({
  beforeLoad: async () => {
    if (typeof window === "undefined") return; // SSR : cookies indispos ici
    const base = (import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000").replace(/\/$/, "");
    try {
      const r = await fetch(`${base}/api/auth/profil/`, {
        credentials: "include",
        headers: { Accept: "application/json" },
      });
      if (r.status === 401 || r.status === 403) {
        throw redirect({ to: "/connexion" });
      }
      if (r.ok) {
        const profil = await r.json();
        sessionStorage.setItem("pharmapp.role", profil.role);
        sessionStorage.setItem("pharmapp.user_id", profil.id);
      }
      // Lire le timeout depuis le parametrage et le stocker en session
      try {
        const pResp = await fetch(`${base}/api/parametrage/`, {
          credentials: "include",
          headers: { Accept: "application/json" },
        });
        if (pResp.ok) {
          const param = await pResp.json();
          const timeout = param.inactivite_timeout_minutes ?? 15;
          sessionStorage.setItem("inactivite_timeout_minutes", String(timeout));
        }
      } catch {
        /* Le parametrage n'est pas critique pour le boot */
      }
    } catch (e) {
      if (isRedirect(e)) throw e;
    }
  },
  component: AppLayoutWithIdleLogout,
});
