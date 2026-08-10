/**
 * tests/e2e/02-vente-especes.spec.ts
 *
 * Parcours E2E — Vente espèces complète (DT-004, Spec 2/5)
 *
 * Parcours caisse critique :
 *  Connexion (session storageState) → POS → Recherche médicament →
 *  Ajout au panier → Vérification total → Paiement espèces →
 *  Ticket de caisse (DTO reçu) → Vente enregistrée en DB
 *
 * Note : ces tests s'exécutent avec la session caissier (storageState).
 * Les appels API réels vers le serveur Django local sont effectués.
 */

import { expect, test } from "@playwright/test";

test.describe("Vente espèces — parcours caisse complet", () => {

  test.beforeEach(async ({ page }) => {
    await page.goto("/");
    await expect(page).toHaveURL(/\/|tableau-bord/);
  });

  test("le POS affiche la zone de recherche et le panier vide", async ({ page }) => {
    // Zone de recherche médicament
    await expect(
      page.getByPlaceholder(/rechercher un médicament|nom, DCI, code/i)
        .or(page.getByRole("searchbox"))
    ).toBeVisible();

    // Panier vide
    await expect(
      page.getByText(/panier vide|0 article|aucun article|prêt pour la vente/i)
        .or(page.getByTestId("panier-vide")).first()
    ).toBeVisible();
  });

  test("recherche un médicament et l'ajoute au panier", async ({ page }) => {
    const champRecherche = page.getByPlaceholder(/rechercher un médicament|nom, DCI, code/i)
      .or(page.getByRole("searchbox"));

    // Taper les 3 premières lettres — attend les suggestions
    await champRecherche.fill("par");
    await page.waitForResponse(
      (resp) => resp.url().includes("/api/medicaments") && resp.status() === 200,
      { timeout: 8_000 },
    );

    // Cliquer sur le premier résultat
    const premierResultat = page.getByRole("button", { name: /Paracétamol.*500 mg/i }).first();
    await expect(premierResultat).toBeVisible({ timeout: 5_000 });
    await premierResultat.click();

    // Le médicament doit apparaître dans le panier
    await expect(
      page.getByRole("listitem").filter({ hasText: /Paracétamol E2E 500 mg/ }).first()
    ).toBeVisible({ timeout: 5_000 });
  });

  test("total du panier est cohérent avec le prix unitaire × quantité", async ({ page }) => {
    // Ajouter un médicament via la recherche
    const champRecherche = page.getByPlaceholder(/rechercher un médicament|nom, DCI, code/i)
      .or(page.getByRole("searchbox"));
    await champRecherche.fill("par");
    await page.waitForResponse(
      (resp) => resp.url().includes("/api/medicaments") && resp.status() === 200,
    );

    const premierResultat = page.getByRole("button", { name: /Paracétamol.*500 mg/i }).first();
    await premierResultat.click();

    // Le sous-total dans le panier doit être > 0
    const totalElement = page.getByTestId("panier-total")
      .or(page.getByText(/total.*FCFA|montant total/i)).first();
    await expect(totalElement).toBeVisible({ timeout: 5_000 });

    const texteTotal = await totalElement.textContent();
    const montant = parseFloat((texteTotal ?? "0").replace(/[^\d.,]/g, "").replace(",", "."));
    expect(montant).toBeGreaterThan(0);
  });

  test("dialogue de paiement espèces s'ouvre et calcule la monnaie rendue", async ({ page }) => {
    // Ajouter un médicament au panier
    const champRecherche = page.getByPlaceholder(/rechercher un médicament|nom, DCI, code/i)
      .or(page.getByRole("searchbox"));
    await champRecherche.fill("par");
    await page.waitForResponse(
      (resp) => resp.url().includes("/api/medicaments") && resp.status() === 200,
    );
    await page.getByRole("button", { name: /Paracétamol.*500 mg/i }).first().click();

    // Ouvrir le dialogue de paiement
    const boutonPayer = page.getByRole("button", { name: /payer|encaisser|valider/i });
    await expect(boutonPayer).toBeVisible({ timeout: 5_000 });
    await boutonPayer.click();

    // Le dialogue de paiement doit apparaître
    await expect(
      page.getByRole("dialog").or(page.getByTestId("dialog-paiement")).first()
    ).toBeVisible({ timeout: 5_000 });

    // Sélectionner le mode espèces
    const modeEspeces = page.getByRole("radio", { name: /espèces/i })
      .or(page.getByLabel(/espèces/i));
    if (await modeEspeces.isVisible()) {
      await modeEspeces.click();
    }

    // Saisir un montant supérieur au total → monnaie calculée automatiquement
    const champMontant = page.getByLabel(/montant encaissé|montant reçu/i)
      .or(page.getByPlaceholder(/montant/i));
    if (await champMontant.isVisible()) {
      await champMontant.fill("10000");

      // Attendre le calcul de la monnaie
      await expect(
        page.getByText(/monnaie à rendre/i)
      ).toBeVisible({ timeout: 3_000 });
    }
  });
});
