/**
 * tests/e2e/global.setup.ts
 *
 * Authentification globale pour les tests E2E Playwright (DT-004).
 * Exécuté UNE seule fois avant tous les projets.
 *
 * Crée les fichiers de session :
 *   - .auth/caissier.json  (rôle caissier — tests caisse)
 *   - .auth/adjoint.json   (rôle pharmacien_adjoint — tests catalogue/stocks)
 *
 * Prérequis : un compte de test doit exister dans la base de données de test
 * (créé par la fixture Django `tests/usine/usine_utilisateurs.py`).
 */

import { expect, test as setup } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const AUTH_DIR = path.join(__dirname, ".auth");

const CAISSIER_EMAIL   = process.env.E2E_CAISSIER_EMAIL   ?? "caissier-e2e@pharmapp-test.bf";
const CAISSIER_MDP     = process.env.E2E_CAISSIER_MDP     ?? "MotDePasse@E2E-2026!";
const ADJOINT_EMAIL    = process.env.E2E_ADJOINT_EMAIL    ?? "adjoint-e2e@pharmapp-test.bf";
const ADJOINT_MDP      = process.env.E2E_ADJOINT_MDP      ?? "MotDePasse@E2E-2026!";

/**
 * Connexion via le formulaire UI et sauvegarde du cookie de session.
 */
async function seConnecter(
  page: import("@playwright/test").Page,
  email: string,
  motDePasse: string,
  fichierSortie: string,
) {
  await page.goto("/connexion");
  await expect(page).toHaveTitle(/PharmApp/);

  // Remplir le formulaire de connexion
  await page.getByLabel(/adresse e-mail/i).fill(email);
  await page.getByLabel(/mot de passe/i).fill(motDePasse);
  await page.getByRole("button", { name: /se connecter/i }).click();

  // Attendre la fin de la navigation. Selon le routeur et le rôle,
  // l’application peut aboutir sur `/`, `/tableau-bord` ou `/caisse`.
  await page.waitForTimeout(1_000);

  // Vérifier qu'on est bien authentifié (pas de redirection retour connexion).
  expect(page.url()).not.toContain("/connexion");

  // Sauvegarder l'état de session (cookies httpOnly inclus)
  await page.context().storageState({ path: fichierSortie });
}

setup("Authentification caissier E2E", async ({ page }) => {
  await seConnecter(page, CAISSIER_EMAIL, CAISSIER_MDP, path.join(AUTH_DIR, "caissier.json"));
});

setup("Authentification adjoint E2E", async ({ page }) => {
  await seConnecter(page, ADJOINT_EMAIL, ADJOINT_MDP, path.join(AUTH_DIR, "adjoint.json"));
});
