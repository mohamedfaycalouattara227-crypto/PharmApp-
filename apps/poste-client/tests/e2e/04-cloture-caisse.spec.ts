/**
 * tests/e2e/04-cloture-caisse.spec.ts
 *
 * Parcours E2E — Clôture de caisse (DT-004, Spec 4/5)
 *
 * Couvre :
 *  - Navigation vers l'écran de clôture
 *  - Affichage du récapitulatif de la journée (totaux par mode de paiement)
 *  - Validation de la clôture (POST /api/clotures/)
 *  - Blocage d'une double clôture pour le même jour
 */

import { expect, test } from "@playwright/test";

test.describe("Clôture de caisse", () => {

  test.beforeEach(async ({ page }) => {
    page.on("console", (msg) => console.log(`BROWSER CONSOLE: ${msg.text()}`));
    page.on("requestfailed", (request) => console.log(`REQUEST FAILED: ${request.method()} ${request.url()} - ${request.failure()?.errorText}`));
  });

  test("l'écran de clôture affiche le récapitulatif de la journée", async ({ page }) => {
    // Intercepter le GET /api/clotures/
    await page.route("**/api/clotures/", async (route) => {
      if (route.request().method() === "GET") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            count: 1,
            next: null,
            previous: null,
            results: [
              {
                id: "past-cloture-uuid",
                date_cloture: "2026-08-10",
                recettes_especes: "15000.00",
                recettes_mobile_money: "8500.00",
                recettes_assurance: "5000.00",
                recettes_credit: "2000.00",
                recettes_cheque: "1000.00",
                chiffre_affaires: "31500.00",
                nombre_ventes: 15,
                ecart_caisse: "0.00",
                notes: "Tout est correct."
              }
            ]
          }),
        });
      } else {
        await route.continue();
      }
    });

    await page.goto("/cloture");
    await expect(page).toHaveURL(/cloture/);

    // Titre de la page
    await expect(
      page.getByRole("heading", { name: /^Clôture de caisse$/i, level: 1 })
    ).toBeVisible({ timeout: 5_000 });

    // Récapitulatif des ventes (au moins les en-têtes)
    await expect(
      page.getByText(/espèces|mobile.money|crédit|total du jour/i).first()
    ).toBeVisible({ timeout: 8_000 });
  });

  test("le bouton de validation de clôture est présent et actif", async ({ page }) => {
    // Intercepter le GET pour éviter le 403 du caissier
    await page.route("**/api/clotures/", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ count: 0, next: null, previous: null, results: [] }),
      });
    });

    await page.goto("/cloture");
    const boutonCloture = page.getByRole("button", { name: /clôturer la caisse|valider la clôture/i });
    await expect(boutonCloture).toBeVisible({ timeout: 8_000 });
    await expect(boutonCloture).toBeEnabled();
  });

  test("une clôture réussie affiche une confirmation", async ({ page }) => {
    // Intercepter l'appel POST et GET /api/clotures/ et simuler un succès
    await page.route("**/api/clotures/", async (route) => {
      if (route.request().method() === "POST") {
        await route.fulfill({
          status: 201,
          contentType: "application/json",
          body: JSON.stringify({
            id: "cloture-e2e-uuid",
            date_cloture: new Date().toISOString().split("T")[0],
            total_especes: "15000.00",
            total_mobile_money: "8500.00",
            total_credit: "2000.00",
            statut: "cloturee",
          }),
        });
      } else {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            count: 1,
            next: null,
            previous: null,
            results: [
              {
                id: "past-cloture-uuid",
                date_cloture: "2026-08-10",
                recettes_especes: "15000.00",
                recettes_mobile_money: "8500.00",
                recettes_assurance: "5000.00",
                recettes_credit: "2000.00",
                recettes_cheque: "1000.00",
                chiffre_affaires: "31500.00",
                nombre_ventes: 15,
                ecart_caisse: "0.00",
                notes: "Tout est correct."
              }
            ]
          }),
        });
      }
    });

    await page.goto("/cloture");

    const boutonCloture = page.getByRole("button", {
      name: /clôturer la caisse|valider la clôture/i,
    });
    await expect(boutonCloture).toBeVisible({ timeout: 8_000 });
    await boutonCloture.click({ force: true });

    // Dialogue de confirmation (si présent)
    const dialogConfirm = page.getByRole("dialog");
    if (await dialogConfirm.isVisible({ timeout: 2_000 })) {
      await page.getByRole("button", { name: /confirmer|oui, clôturer/i }).click();
    }

    // Toast ou message de succès
    await expect(
      page.getByText("Caisse clôturée.").first()
    ).toBeVisible({ timeout: 10_000 });
  });

  test("double clôture le même jour retourne une erreur métier", async ({ page }) => {
    // Simuler un 400 "clôture déjà effectuée"
    await page.route("**/api/clotures/", async (route) => {
      if (route.request().method() === "POST") {
        await route.fulfill({
          status: 400,
          contentType: "application/json",
          body: JSON.stringify({ erreur: "Une clôture existe déjà pour aujourd'hui." }),
        });
      } else {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            count: 1,
            next: null,
            previous: null,
            results: [
              {
                id: "past-cloture-uuid",
                date_cloture: "2026-08-10",
                recettes_especes: "15000.00",
                recettes_mobile_money: "8500.00",
                recettes_assurance: "5000.00",
                recettes_credit: "2000.00",
                recettes_cheque: "1000.00",
                chiffre_affaires: "31500.00",
                nombre_ventes: 15,
                ecart_caisse: "0.00",
                notes: "Tout est correct."
              }
            ]
          }),
        });
      }
    });

    await page.goto("/cloture");

    const boutonCloture = page.getByRole("button", {
      name: /clôturer la caisse|valider la clôture/i,
    });
    if (await boutonCloture.isVisible({ timeout: 5_000 })) {
      // Saisir la note pour forcer l'erreur
      const notesInput = page.locator("textarea");
      if (await notesInput.isVisible()) {
        await notesInput.fill("force-erreur");
      }

      await boutonCloture.click({ force: true });

      const dialogConfirm = page.getByRole("dialog");
      if (await dialogConfirm.isVisible({ timeout: 2_000 })) {
        await page.getByRole("button", { name: /confirmer|oui, clôturer/i }).click();
      }

      await expect(
        page.getByText(/déjà.*clôture|clôture.*existe|Clôture refusée/i).first()
      ).toBeVisible({ timeout: 8_000 });
    }
  });
});
