/**
 * src/lib/version.ts — Identité de build du poste client.
 *
 * ÉTAPE 00, tâche 04 : la version n'est JAMAIS écrite en dur ici. Elle est
 * injectée au build par Vite (`define`) depuis le fichier `VERSION` unique
 * situé à la racine du monorepo. Le contrôle `outils/verifier_version.py`
 * échoue en CI si une version littérale réapparaît dans le code.
 */

declare const __PHARMAPP_VERSION__: string;
declare const __PHARMAPP_COMMIT__: string;
declare const __PHARMAPP_BUILD_DATE__: string;

export const VERSION: string =
  typeof __PHARMAPP_VERSION__ !== "undefined" ? __PHARMAPP_VERSION__ : "0.0.0-inconnue";

export const COMMIT: string =
  typeof __PHARMAPP_COMMIT__ !== "undefined" ? __PHARMAPP_COMMIT__ : "inconnue";

export const DATE_BUILD: string =
  typeof __PHARMAPP_BUILD_DATE__ !== "undefined" ? __PHARMAPP_BUILD_DATE__ : "inconnue";

/** Libellé compact affiché en pied de page : « PharmApp v1.0.0 · a1b2c3d ». */
export function libelleVersion(): string {
  const revision = COMMIT === "inconnue" ? "" : ` · ${COMMIT.slice(0, 7)}`;
  return `PharmApp v${VERSION}${revision}`;
}

/** Chaîne exhaustive à dicter au support téléphonique. */
export function libelleSupport(): string {
  return `PharmApp poste client v${VERSION} (build ${COMMIT}, ${DATE_BUILD})`;
}
