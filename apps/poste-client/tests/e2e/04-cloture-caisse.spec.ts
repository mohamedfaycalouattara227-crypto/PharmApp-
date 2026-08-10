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
    await page.goto("/cloture");
  });

  test("l'écran de clôture affiche le récapitulatif de la journée", async ({ page }) => {
    await expect(page).toHaveURL(/cloture/);

    // Titre de la page
    await expect(
      page.getByRole("heading", { name: /clôture|fermeture de caisse/i })
    ).toBeVisible({ timeout: 5_000 });

    // Récapitulatif des ventes (au moins les en-têtes)
    await expect(
      page.getByText(/espèces|mobile.money|crédit|total du jour/i)
    ).toBeVisible({ timeout: 8_000 });
  });

  test("le bouton de validation de clôture est présent et actif", async ({ page }) => {
    const boutonCloture = page.getByRole("button", { name: /clôturer la caisse|valider la clôture/i });
    await expect(boutonCloture).toBeVisible({ timeout: 8_000 });
    await expect(boutonCloture).toBeEnabled();
  });

  test("une clôture réussie affiche une confirmation", async ({ page }) => {
    // Intercepter l'appel POST /api/clotures/ et simuler un succès
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
        await route.continue();
      }
    });

    const boutonCloture = page.getByRole("button", {
      name: /clôturer la caisse|valider la clôture/i,
    });
    await expect(boutonCloture).toBeVisible({ timeout: 8_000 });
    await boutonCloture.click();

    // Dialogue de confirmation (si présent)
    const dialogConfirm = page.getByRole("dialog");
    if (await dialogConfirm.isVisible({ timeout: 2_000 })) {
      await page.getByRole("button", { name: /confirmer|oui, clôturer/i }).click();
    }

    // Toast ou message de succès
    await expect(
      page.getByRole("alert").filter({ hasText: /clôture.*réussie|caisse clôturée/i })
        .or(page.getByText(/clôture.*réussie|caisse clôturée/i))
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
        await route.continue();
      }
    });

    const boutonCloture = page.getByRole("button", {
      name: /clôturer la caisse|valider la clôture/i,
    });
    if (await boutonCloture.isVisible({ timeout: 5_000 })) {
      await boutonCloture.click();

      const dialogConfirm = page.getByRole("dialog");
      if (await dialogConfirm.isVisible({ timeout: 2_000 })) {
        await page.getByRole("button", { name: /confirmer|oui, clôturer/i }).click();
      }

      await expect(
        page.getByRole("alert").filter({ hasText: /déjà.*clôture|clôture.*existe/i })
          .or(page.getByText(/déjà.*clôture|clôture.*existe/i))
      ).toBeVisible({ timeout: 8_000 });
    }
  });
});
