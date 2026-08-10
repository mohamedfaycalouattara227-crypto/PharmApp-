/**
 * tests/e2e/05-controle-acces-rbac.spec.ts
 *
 * Parcours E2E — Contrôle d'accès RBAC (DT-004, Spec 5/5)
 *
 * Couvre :
 *  - Un caissier ne peut pas accéder aux écrans admin (utilisateurs, rapports avancés)
 *  - Un caissier peut accéder à la caisse et à l'historique de ses ventes
 *  - Les URLs protégées redirigent vers /connexion si session invalide
 *  - Les menus inaccessibles ne sont pas affichés dans la navigation
 */

import { expect, test } from "@playwright/test";

test.describe("Contrôle d'accès RBAC — rôle Caissier", () => {
  // Utilise la session caissier (storageState configuré dans playwright.config.ts)

  test("un caissier peut accéder à la caisse (POS)", async ({ page }) => {
    await page.goto("/");
    await expect(page).toHaveURL(/\/|tableau-bord/);

    // La zone de recherche médicament doit être présente
    await expect(
      page.getByPlaceholder(/rechercher un médicament/i)
        .or(page.getByRole("searchbox"))
    ).toBeVisible({ timeout: 8_000 });
  });

  test("un caissier peut consulter ses ventes", async ({ page }) => {
    await page.goto("/ventes");
    // Pas de redirection → accès autorisé
    await expect(page).toHaveURL(/ventes/);
  });

  test("un caissier ne peut PAS accéder à la gestion des utilisateurs", async ({ page }) => {
    await page.goto("/utilisateurs");

    // Soit redirection, soit message d'interdiction (403 / accès refusé)
    const url = page.url();
    const estRedirige = url.includes("/connexion") || url.includes("/tableau-bord") || url.endsWith("/");
    const messageInterdit = page.getByText(/accès refusé|non autorisé|permissions insuffisantes/i)
      .or(page.getByRole("alert").filter({ hasText: /autoris|permiss/i }));

    const conditionRemplie = estRedirige || await messageInterdit.isVisible({ timeout: 5_000 });
    expect(conditionRemplie).toBeTruthy();
  });

  test("un caissier ne voit pas le lien 'Utilisateurs' dans la navigation", async ({ page }) => {
    await page.goto("/");

    // Le menu de navigation ne doit pas avoir de lien vers la gestion des utilisateurs
    const lienUtilisateurs = page.getByRole("link", { name: /utilisateurs|gestion des comptes/i });
    await expect(lienUtilisateurs).toBeHidden({ timeout: 5_000 });
  });

  test("un caissier ne peut PAS accéder aux rapports détaillés", async ({ page }) => {
    // Vérifier que les rapports de marges et exports (réservés titulaire/adjoint)
    // renvoient une interdiction
    const reponsesRapports = await Promise.all([
      page.request.get("/api/rapports/marges/"),
      page.request.get("/api/rapports/export-ventes/"),
    ]);

    for (const reponse of reponsesRapports) {
      expect([401, 403]).toContain(reponse.status());
    }
  });

  test("token expiré / cookie absent → redirection vers /connexion", async ({ browser }) => {
    // Ouvrir un contexte SANS storageState
    const context = await browser.newContext({ storageState: { cookies: [], origins: [] } });
    const page = await context.newPage();

    await page.goto("/");
    await page.waitForURL(/connexion/, { timeout: 8_000 });
    expect(page.url()).toContain("/connexion");

    await context.close();
  });
});
