/**
 * theme.ts — Système de 6 thèmes UI pour PharmApp.
 *
 * Chaque thème est une collection de variables CSS personnalisées.
 * Le thème actif est persisté dans localStorage sous la clé "pharmapp.theme".
 *
 * Thèmes disponibles :
 *  - classique-bleu   : bleu professionnel sobre (défaut)
 *  - vert-sante       : vert croix de pharmacie naturel (original)
 *  - sombre-moderne   : fond anthracite ultra-sombre, accents cyan
 *  - violet-elegant   : violet améthyste premium
 *  - orange-dynamique : orange vif énergique avec fond crème
 *  - minimaliste-blanc: blanc pur, gris clair, accents indigo
 */

export type NomTheme =
  | "classique-bleu"
  | "vert-sante"
  | "sombre-moderne"
  | "violet-elegant"
  | "orange-dynamique"
  | "minimaliste-blanc";

export interface DefinitionTheme {
  nom: NomTheme;
  label: string;
  description: string;
  /** Classe CSS appliquée sur <html> */
  classeHtml: string;
  /** Couleur d'aperçu (primary) pour le sélecteur */
  couleurPrimaire: string;
  couleurSecondaire: string;
  animation: "pulse-douce" | "glissement" | "rebond" | "fadeIn" | "aucune";
}

export const THEMES: DefinitionTheme[] = [
  {
    nom: "vert-sante",
    label: "Vert Santé",
    description: "Vert pharmacie, fond encre nuit — thème original PharmApp",
    classeHtml: "theme-vert-sante",
    couleurPrimaire: "oklch(0.760 0.140 170)",
    couleurSecondaire: "oklch(0.820 0.140 75)",
    animation: "fadeIn",
  },
  {
    nom: "classique-bleu",
    label: "Classique Bleu",
    description: "Bleu professionnel sobre, fond ardoise foncée",
    classeHtml: "theme-classique-bleu",
    couleurPrimaire: "oklch(0.650 0.150 240)",
    couleurSecondaire: "oklch(0.800 0.120 200)",
    animation: "glissement",
  },
  {
    nom: "sombre-moderne",
    label: "Sombre Moderne",
    description: "Fond anthracite profond, accents cyan néon",
    classeHtml: "theme-sombre-moderne",
    couleurPrimaire: "oklch(0.780 0.160 195)",
    couleurSecondaire: "oklch(0.720 0.180 185)",
    animation: "pulse-douce",
  },
  {
    nom: "violet-elegant",
    label: "Violet Élégant",
    description: "Améthyste premium, fond aubergine profond",
    classeHtml: "theme-violet-elegant",
    couleurPrimaire: "oklch(0.700 0.200 300)",
    couleurSecondaire: "oklch(0.750 0.150 280)",
    animation: "rebond",
  },
  {
    nom: "orange-dynamique",
    label: "Orange Dynamique",
    description: "Orange solaire énergique, fond sable chaud clair",
    classeHtml: "theme-orange-dynamique light",
    couleurPrimaire: "oklch(0.650 0.200 55)",
    couleurSecondaire: "oklch(0.720 0.180 65)",
    animation: "rebond",
  },
  {
    nom: "minimaliste-blanc",
    label: "Minimaliste Blanc",
    description: "Blanc pur et gris clair, accents indigo discrets",
    classeHtml: "theme-minimaliste-blanc light",
    couleurPrimaire: "oklch(0.500 0.180 260)",
    couleurSecondaire: "oklch(0.600 0.140 250)",
    animation: "fadeIn",
  },
];

export const THEME_PAR_DEFAUT: NomTheme = "vert-sante";
const CLE_STORAGE = "pharmapp.theme";

/** Lit le thème sauvegardé en localStorage (ou retourne le défaut). */
export function lireThemeSauvegarde(): NomTheme {
  if (typeof window === "undefined") return THEME_PAR_DEFAUT;
  try {
    const valeur = localStorage.getItem(CLE_STORAGE) as NomTheme | null;
    if (valeur && THEMES.some((t) => t.nom === valeur)) return valeur;
  } catch {
    /* ignore */
  }
  return THEME_PAR_DEFAUT;
}

/** Sauvegarde le thème dans localStorage. */
export function sauvegarderTheme(nom: NomTheme): void {
  if (typeof window === "undefined") return;
  try {
    localStorage.setItem(CLE_STORAGE, nom);
  } catch {
    /* ignore */
  }
}

/** Retourne la définition d'un thème par son nom. */
export function trouverTheme(nom: NomTheme): DefinitionTheme {
  return THEMES.find((t) => t.nom === nom) ?? THEMES[0];
}

/**
 * Applique le thème sur l'élément <html> en remplaçant les classes de thème.
 * L'animation d'entrée est appliquée via une classe temporaire.
 */
export function appliquerTheme(nom: NomTheme): void {
  if (typeof document === "undefined") return;
  const html = document.documentElement;
  const definition = trouverTheme(nom);

  // Supprimer toutes les classes de thème existantes
  const classesThemes = THEMES.flatMap((t) => t.classeHtml.split(" "));
  html.classList.remove(...classesThemes, "light");

  // Appliquer les nouvelles classes
  definition.classeHtml.split(" ").forEach((cls) => {
    if (cls) html.classList.add(cls);
  });

  // Animation d'entrée
  if (definition.animation !== "aucune") {
    html.classList.add(`anim-${definition.animation}`);
    setTimeout(() => html.classList.remove(`anim-${definition.animation}`), 600);
  }

  sauvegarderTheme(nom);
}
