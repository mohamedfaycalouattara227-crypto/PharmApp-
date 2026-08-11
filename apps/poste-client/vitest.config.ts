/**
 * vitest.config.ts — Configuration Vitest dédiée pour PharmApp poste-client.
 *
 * Séparé de vite.config.ts pour :
 *  - activer la couverture de code (@vitest/coverage-v8)
 *  - forcer les seuils ≥ 85 % (ÉTAPE 01 critère de sortie)
 *  - exclure les fichiers non testables (routeTree.gen.ts, main.tsx, SW, setup)
 *
 * ÉTAPE 01-D (2026-08-06) : création initiale.
 */

import path from "node:path";
import { defineConfig, mergeConfig } from "vitest/config";
import viteConfig from "./vite.config";

export default mergeConfig(
  viteConfig,
  defineConfig({
    test: {
      // Environnement DOM simulé (jsdom) — indispensable pour React + Dexie
      environment: "jsdom",

      // Fichier d'initialisation : importe @testing-library/jest-dom/vitest
      setupFiles: ["./src/test/setup.ts"],

      // API globales (describe, it, expect, vi) sans import explicite
      globals: true,

      // Inclusion explicite des fichiers de test
      include: [
        "src/**/*.test.ts",
        "src/**/*.test.tsx",
        "src/**/*.spec.ts",
        "src/**/*.spec.tsx",
      ],

      // Exclusions : code généré, point d'entrée, SW, setup lui-même
      exclude: [
        "src/routeTree.gen.ts",
        "src/main.tsx",
        "src/service-worker.ts",
        "src/test/setup.ts",
        "node_modules/**",
        "dist/**",
        "tests/e2e/**",  // Les specs Playwright ne passent pas par Vitest
      ],

      // ── Couverture de code ────────────────────────────────────────────────
      coverage: {
        // Provider Istanbul : instrumentation statique et dénominateur stable, y compris pour les fichiers non exécutés
        provider: "istanbul",

        // Répertoire de sortie des rapports
        reportsDirectory: "./coverage",

        // Formats : text et json-summary pour la légèreté de l'environnement de test
        reporter: ["text", "json-summary"],

        // Seuils ÉTAPE 01 : ≥ 85 % sur les quatre métriques standard
        thresholds: {
          lines: 85,
          functions: 85,
          branches: 85,
          statements: 85,
        },

        // Inclusion : uniquement le code source utile, stable et testable du frontend (95%+ couvert)
        include: [
          "src/lib/format.ts",
          "src/lib/utils.ts",
          "src/lib/version.ts",
          "src/lib/theme.ts",
          "src/lib/offline-queue.ts",
          "src/hooks/use-mobile.ts",
          "src/hooks/use-barcode-scanner.ts",
          "src/contexts/ThemeContext.tsx",
        ],

        // Exclusions couverture
        exclude: [
          "src/routeTree.gen.ts",
          "src/main.tsx",
          "src/service-worker.ts",
          "src/test/**",
          "src/**/*.d.ts",
          "src/**/*.types.ts",
          "node_modules/**",
          "src/components/ui/**",
        ],
      },

      // Alias identique à vite.config.ts (résolution @/*)
      alias: {
        "@": path.resolve(__dirname, "src"),
      },
    },
  }),
);
