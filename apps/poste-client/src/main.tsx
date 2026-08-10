import { RouterProvider } from "@tanstack/react-router";
import { createRoot } from "react-dom/client";
import { getRouter } from "./router";
import { enregistrerServiceWorker } from "./lib/sw-register";
import { ThemeProvider } from "./contexts/ThemeContext";
import "./styles.css";

const router = getRouter();

// Register router type for devtools / type inference
declare module "@tanstack/react-router" {
  interface Register {
    router: ReturnType<typeof getRouter>;
  }
}

createRoot(document.getElementById("root")!).render(
  <ThemeProvider>
    <RouterProvider router={router} />
  </ThemeProvider>,
);

// DT-020 (corrigé) : enregistrement du Service Worker PWA.
// Activé uniquement en production (sw-register.ts le vérifie via import.meta.env.DEV).
// Fournit : cache offline NetworkFirst/CacheFirst, Background Sync des ventes hors-ligne,
// notification UI de mise à jour disponible.
enregistrerServiceWorker();
