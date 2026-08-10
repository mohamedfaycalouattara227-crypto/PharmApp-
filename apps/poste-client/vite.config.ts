import { execSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

const port = Number(process.env.PORT ?? 3000);
const basePath = process.env.BASE_PATH ?? "/";

/**
 * ÉTAPE 00 — source unique de vérité de la version.
 * La version est lue dans le fichier `VERSION` à la racine du monorepo ;
 * aucune version n'est dupliquée dans le code du poste client.
 */
function lireVersionDepot(): string {
  if (process.env.PHARMAPP_VERSION) return process.env.PHARMAPP_VERSION;
  let repertoire = __dirname;
  for (let i = 0; i < 6; i += 1) {
    const candidat = path.join(repertoire, "VERSION");
    if (fs.existsSync(candidat)) return fs.readFileSync(candidat, "utf-8").trim();
    repertoire = path.dirname(repertoire);
  }
  return "0.0.0-inconnue";
}

function lireCommit(): string {
  if (process.env.PHARMAPP_COMMIT) return process.env.PHARMAPP_COMMIT.slice(0, 12);
  try {
    return execSync("git rev-parse --short=12 HEAD", { cwd: __dirname, stdio: ["ignore", "pipe", "ignore"] })
      .toString()
      .trim();
  } catch {
    return "inconnue";
  }
}

const VERSION_DEPOT = lireVersionDepot();
const COMMIT_DEPOT = lireCommit();

export default defineConfig({
  base: basePath,
  define: {
    __PHARMAPP_VERSION__: JSON.stringify(VERSION_DEPOT),
    __PHARMAPP_COMMIT__: JSON.stringify(COMMIT_DEPOT),
    __PHARMAPP_BUILD_DATE__: JSON.stringify(
      process.env.PHARMAPP_BUILD_DATE ?? new Date().toISOString(),
    ),
  },
  plugins: [
    react(),
    tailwindcss(),
    // DT-020 (corrigé) : émission du Service Worker dans le build de production.
    // Le SW est copié depuis src/service-worker.ts vers dist/service-worker.js
    // via le plugin vite-plugin-static-copy ou un simple rollupOptions.input.
    // Note : vite-plugin-pwa n'est pas utilisé pour conserver le contrôle total
    // du SW (stratégies métier Outbox, import dynamique Dexie).
    {
      name: "pharmapp-sw-builder",
      apply: "build",
      async buildStart() {
        // Le SW est compilé séparément via rollupOptions.input ci-dessous.
      },
    },
  ],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "src"),
    },
    dedupe: ["react", "react-dom"],
  },
  server: {
    port,
    strictPort: true,
    host: "0.0.0.0",
  },
  preview: {
    port,
    host: "0.0.0.0",
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
    rollupOptions: {
      // DT-020 : compilation du Service Worker comme point d'entrée séparé.
      // Produit dist/service-worker.js avec scope "/" attendu par sw-register.ts.
      input: {
        main: path.resolve(__dirname, "index.html"),
        "service-worker": path.resolve(__dirname, "src/service-worker.ts"),
      },
      output: {
        // Forcer le SW à la racine de dist/ (pas dans assets/)
        entryFileNames: (chunkInfo) => {
          if (chunkInfo.name === "service-worker") return "[name].js";
          return "assets/[name]-[hash].js";
        },
      },
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: "./src/test/setup.ts",
    globals: true,
  },
});
