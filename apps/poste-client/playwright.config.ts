/**
 * playwright.config.ts — Configuration E2E PharmApp (DT-004)
 *
 * Couvre les parcours critiques de la caisse d'officine :
 *  1. Connexion / déconnexion
 *  2. Vente espèces complète (recherche → panier → paiement → ticket)
 *  3. Vente hors-ligne + reprise automatique
 *  4. Clôture de caisse
 *  5. Contrôle d'accès (rôles RBAC)
 *
 * Prérequis : le serveur local Django doit tourner sur BASE_URL (défaut 8000).
 *             Le poste client Vite doit tourner sur VITE_PORT (défaut 3000).
 *
 * Lancer :
 *   npx playwright test               # tous les tests
 *   npx playwright test --headed      # avec fenêtre visible
 *   npx playwright test tests/e2e/vente-especes.spec.ts  # un seul fichier
 */

import { defineConfig, devices } from "@playwright/test";

const VITE_PORT = Number(process.env.VITE_PORT ?? 3000);
const BASE_URL  = process.env.PLAYWRIGHT_BASE_URL ?? `http://localhost:${VITE_PORT}`;
const API_URL   = process.env.VITE_API_BASE_URL    ?? "http://localhost:8000";

export default defineConfig({
  // ── Répertoire des specs ──────────────────────────────────────────────────
  testDir: "./tests/e2e",

  // ── Exécution ─────────────────────────────────────────────────────────────
  fullyParallel: false,     // les tests caisse sont séquentiels (données partagées)
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: process.env.CI ? 1 : undefined,

  // ── Rapports ──────────────────────────────────────────────────────────────
  reporter: process.env.CI
    ? [["github"], ["html", { open: "never", outputFolder: "playwright-report" }]]
    : [["list"], ["html", { open: "on-failure" }]],

  // ── Timeout global ────────────────────────────────────────────────────────
  timeout: 45_000,
  expect: { timeout: 10_000 },

  // ── Configuration commune à tous les projets ──────────────────────────────
  use: {
    baseURL: BASE_URL,
    // Cookies httpOnly JWT — credentials nécessaires
    storageState: undefined,

    // Captures automatiques en cas d'échec
    screenshot: "only-on-failure",
    video: "retain-on-failure",
    trace: "on-first-retry",

    // En-têtes standards
    extraHTTPHeaders: {
      Accept: "application/json",
    },

    // Ignorer les erreurs HTTPS en dev (certificat auto-signé)
    ignoreHTTPSErrors: true,
  },

  // ── Projets (navigateurs cibles) ──────────────────────────────────────────
  projects: [
    // Setup global : connexion et sauvegarde du cookie de session
    {
      name: "setup",
      testMatch: /global\.setup\.ts/,
    },

    // Tests caisse (Chrome — navigateur principal en officine)
    {
      name: "chromium-caisse",
      use: {
        ...devices["Desktop Chrome"],
        storageState: "tests/e2e/.auth/caissier.json",
      },
      dependencies: ["setup"],
    },

    // Tests lecture seule (compatibilité pharmacien adjoint) via Chrome
    {
      name: "chromium-adjoint",
      use: {
        ...devices["Desktop Chrome"],
        storageState: "tests/e2e/.auth/adjoint.json",
      },
      dependencies: ["setup"],
    },
  ],

  // ── Seed idempotent puis serveur web de développement ─────────────────────
  webServer: {
    command: `python ../serveur-local/manage.py seed_e2e && VITE_API_BASE_URL=${API_URL} npm run dev`,
    url: BASE_URL,
    reuseExistingServer: !process.env.CI,
    timeout: 60_000,
    stdout: "pipe",
    stderr: "pipe",
  },
});
