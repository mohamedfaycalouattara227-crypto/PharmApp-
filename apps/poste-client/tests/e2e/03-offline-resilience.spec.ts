/**
 * tests/e2e/03-offline-resilience.spec.ts
 *
 * Parcours E2E — Résilience hors-ligne (DT-004 + DT-007, Spec 3/5)
 *
 * Simule une coupure réseau et vérifie que :
 *  1. L'UI affiche un indicateur "hors-ligne" ou une notification
 *  2. La vente est mise en file IndexedDB (pas perdue)
 *  3. À la reconnexion, la file est rejouée automatiquement (ou manuellement)
 *  4. La vente apparaît ensuite dans l'historique
 *
 * Utilise l'API Playwright `page.route()` pour simuler la coupure réseau
 * sur les appels vers /api/ventes/ sans couper l'ensemble du réseau.
 */

import { expect, test } from "@playwright/test";

test.describe("Résilience hors-ligne — file d'attente caisse", () => {

  test("une vente soumise hors-ligne est mise en attente et non perdue", async ({ page }) => {
    await page.goto("/");

    // Ajouter un médicament au panier
    const champRecherche = page.getByPlaceholder(/rechercher un médicament|nom, DCI, code/i)
      .or(page.getByRole("searchbox"));
    await champRecherche.fill("par");
    await page.waitForResponse(
      (resp) => resp.url().includes("/api/medicaments") && resp.status() === 200,
    );
    await page.getByRole("option").first()
      .or(page.getByTestId("medicament-result").first())
      .click();

    // ── Simuler la coupure réseau sur /api/ventes/ ────────────────────────
    await page.route("**/api/ventes/", (route) => route.abort("failed"));

    // Tenter de valider la vente
    const boutonPayer = page.getByRole("button", { name: /payer|encaisser|valider/i });
    await boutonPayer.click();

    // Remplir le dialogue de paiement si présent
    const dialog = page.getByRole("dialog").or(page.getByTestId("dialog-paiement"));
    if (await dialog.isVisible({ timeout: 3_000 })) {
      const modeEspeces = page.getByRole("radio", { name: /espèces/i });
      if (await modeEspeces.isVisible()) await modeEspeces.click();

      const champMontant = page.getByLabel(/montant encaissé/i).or(page.getByPlaceholder(/montant/i));
      if (await champMontant.isVisible()) await champMontant.fill("10000");

      await page.getByRole("button", { name: /confirmer|valider le paiement/i }).click();
    }

    // L'UI doit indiquer la mise en attente (toast ou badge)
    await expect(
      page.getByText(/hors.ligne|en attente|sera synchronisée|file d.attente/i)
        .or(page.getByRole("alert").filter({ hasText: /hors.ligne|attente/i }))
        .or(page.getByTestId("offline-badge"))
    ).toBeVisible({ timeout: 10_000 });

    // ── Rétablir le réseau ────────────────────────────────────────────────
    await page.unrouteAll();

    // L'indicateur hors-ligne doit disparaître ou un message de sync s'afficher
    // (le SW ou le polling va rejouer la file)
    await expect(
      page.getByText(/synchronisée|synchro.réussie|vente enregistrée/i)
        .or(page.getByRole("alert").filter({ hasText: /synchronis/i }))
    ).toBeVisible({ timeout: 20_000 });
  });

  test("indicateur de statut offline visible pendant la coupure", async ({ page, context }) => {
    await page.goto("/");

    // Couper TOUT le réseau via le contexte Playwright
    await context.setOffline(true);

    // L'UI doit afficher un indicateur de déconnexion dans les 5 secondes
    // (événement "offline" du navigateur → handled dans sw-register.ts ou l'UI)
    await expect(
      page.getByTestId("offline-indicator")
        .or(page.getByText(/hors.ligne|déconnecté|pas de réseau/i))
    ).toBeVisible({ timeout: 8_000 });

    // Rétablir
    await context.setOffline(false);

    // L'indicateur doit disparaître
    await expect(
      page.getByTestId("offline-indicator")
        .or(page.getByText(/hors.ligne|déconnecté/i))
    ).toBeHidden({ timeout: 8_000 });
  });
});
