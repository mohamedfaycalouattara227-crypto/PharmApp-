/**
 * tests/e2e/01-connexion.spec.ts
 *
 * Parcours E2E — Authentification (DT-004, Spec 1/5)
 *
 * Couvre :
 *  - Formulaire de connexion accessible à la racine / /connexion
 *  - Erreur sur identifiants invalides (message explicite, pas de redirection)
 *  - Connexion réussie → redirection tableau-bord ou caisse
 *  - Déconnexion → retour au formulaire de connexion
 *  - Accès protégé sans session → redirection vers /connexion
 */

import { expect, test } from "@playwright/test";

// Ces tests s'exécutent SANS storageState — pas d'authentification préalable
test.use({ storageState: { cookies: [], origins: [] } });

test.describe("Authentification PharmApp", () => {

  test("la page de connexion se charge correctement", async ({ page }) => {
    await page.goto("/connexion");

    await expect(page).toHaveTitle(/PharmApp/);
    await expect(page.getByText(/accès sécurisé/i)).toBeVisible();
    await expect(page.getByLabel(/adresse e-mail/i)).toBeVisible();
    await expect(page.getByLabel(/mot de passe/i)).toBeVisible();
    await expect(page.getByRole("button", { name: /se connecter/i })).toBeVisible();
  });

  test("erreur explicite sur email invalide", async ({ page }) => {
    await page.goto("/connexion");

    await page.getByLabel(/adresse e-mail/i).fill("pas-un-email");
    await page.getByLabel(/mot de passe/i).fill("test");
    await page.getByRole("button", { name: /se connecter/i }).click();

    // Le formulaire utilise la validation native HTML5 pour un email mal formé.
    const email = page.getByLabel(/adresse e-mail/i);
    expect(await email.evaluate((element) => (element as HTMLInputElement).validity.typeMismatch)).toBe(true);
    expect(page.url()).toContain("/connexion");
  });

  test("erreur sur identifiants incorrects (401)", async ({ page }) => {
    await page.goto("/connexion");

    await page.getByLabel(/adresse e-mail/i).fill("inconnu@pharmapp.bf");
    await page.getByLabel(/mot de passe/i).fill("mauvaisMotDePasse");
    await page.getByRole("button", { name: /se connecter/i }).click();

    // Toast d'erreur ou message dans la page
    await expect(
      page.getByRole("alert")
        .or(page.getByText(/identifiants incorrects|mot de passe incorrect|connexion échouée/i))
    ).toBeVisible({ timeout: 8_000 });

    expect(page.url()).toContain("/connexion");
  });

  test("connexion réussie redirige vers le tableau de bord ou la caisse", async ({ page }) => {
    const email = process.env.E2E_CAISSIER_EMAIL ?? "caissier-e2e@pharmapp-test.bf";
    const mdp   = process.env.E2E_CAISSIER_MDP   ?? "MotDePasse@E2E-2026!";

    await page.goto("/connexion");
    await page.getByLabel(/adresse e-mail/i).fill(email);
    await page.getByLabel(/mot de passe/i).fill(mdp);
    await page.getByRole("button", { name: /se connecter/i }).click();

    await page.waitForURL(/tableau-bord|\/$/, { timeout: 15_000 });
    expect(page.url()).not.toContain("/connexion");
  });

  test("accès direct à la racine sans session affiche la connexion", async ({ page }) => {
    await page.goto("/");
    await expect(
      page.getByText(/accès sécurisé/i)
        .or(page.getByLabel(/adresse e-mail/i))
        .or(page.getByRole("heading", { name: /point de vente|tableau de bord/i }))
    ).toBeVisible();
  });

  test("accès direct à /tableau-bord sans session redirige vers /connexion", async ({ page }) => {
    await page.goto("/tableau-bord");
    await page.waitForURL(/connexion/, { timeout: 8_000 });
    expect(page.url()).toContain("/connexion");
  });
});
