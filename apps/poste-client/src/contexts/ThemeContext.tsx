/**
 * ThemeContext.tsx — Contexte React pour la gestion des thèmes PharmApp.
 *
 * Fournit :
 *  - themeActif  : le nom du thème courant
 *  - changerTheme(nom) : change et persiste le thème
 *  - themes : liste des thèmes disponibles
 */

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import {
  type NomTheme,
  type DefinitionTheme,
  THEMES,
  lireThemeSauvegarde,
  appliquerTheme,
} from "@/lib/theme";

interface ThemeContextValue {
  themeActif: NomTheme;
  changerTheme: (nom: NomTheme) => void;
  themes: DefinitionTheme[];
  definitionActive: DefinitionTheme;
}

const ThemeContext = createContext<ThemeContextValue | null>(null);

/** Hook pour accéder au contexte de thème. */
export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext);
  if (!ctx) {
    throw new Error("useTheme doit être utilisé dans un ThemeProvider");
  }
  return ctx;
}

interface ThemeProviderProps {
  children: ReactNode;
}

/** Fournisseur de thème — à placer au plus haut niveau de l'arbre React. */
export function ThemeProvider({ children }: ThemeProviderProps) {
  const [themeActif, setThemeActif] = useState<NomTheme>(() => lireThemeSauvegarde());

  // Appliquer le thème initial au montage
  useEffect(() => {
    appliquerTheme(themeActif);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const changerTheme = (nom: NomTheme) => {
    setThemeActif(nom);
    appliquerTheme(nom);
  };

  const definitionActive = THEMES.find((t) => t.nom === themeActif) ?? THEMES[0];

  return (
    <ThemeContext.Provider
      value={{ themeActif, changerTheme, themes: THEMES, definitionActive }}
    >
      {children}
    </ThemeContext.Provider>
  );
}
