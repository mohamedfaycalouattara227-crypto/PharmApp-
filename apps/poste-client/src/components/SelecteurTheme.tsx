/**
 * SelecteurTheme.tsx — Composant sélecteur de thème pour PharmApp.
 *
 * Affiche un bouton avec dropdown listant les 6 thèmes disponibles.
 * Chaque thème est présenté avec sa couleur primaire et son label.
 */

import { Palette, Check } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useTheme } from "@/contexts/ThemeContext";

export function SelecteurTheme() {
  const { themeActif, changerTheme, themes } = useTheme();

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          title="Changer de thème"
          className="h-8 w-8 text-muted-foreground hover:text-foreground"
          aria-label="Sélecteur de thème"
        >
          <Palette className="h-4 w-4" />
        </Button>
      </DropdownMenuTrigger>

      <DropdownMenuContent align="end" className="w-56">
        <DropdownMenuLabel className="text-xs text-muted-foreground">
          Apparence
        </DropdownMenuLabel>
        <DropdownMenuSeparator />

        {themes.map((theme) => (
          <DropdownMenuItem
            key={theme.nom}
            onClick={() => changerTheme(theme.nom)}
            className="flex items-center gap-3 cursor-pointer"
          >
            {/* Pastille de couleur */}
            <span
              className="h-4 w-4 rounded-full border border-border shrink-0"
              style={{ background: theme.couleurPrimaire }}
              aria-hidden="true"
            />

            {/* Label + description */}
            <div className="flex-1 min-w-0">
              <div className="text-sm font-medium">{theme.label}</div>
              <div className="text-xs text-muted-foreground truncate">
                {theme.description}
              </div>
            </div>

            {/* Coche si actif */}
            {themeActif === theme.nom && (
              <Check className="h-3.5 w-3.5 text-primary shrink-0" />
            )}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
