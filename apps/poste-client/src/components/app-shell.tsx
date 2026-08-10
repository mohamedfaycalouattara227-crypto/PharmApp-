import { Link, Outlet, useLocation } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import {
  ShoppingCart,
  Package,
  Truck,
  BarChart3,
  Users,
  Settings,
  Wifi,
  WifiOff,
  CloudUpload,
  ClipboardCheck,
  BookOpen,
  FileText,
  UserCog,
} from "lucide-react";

import { cn } from "@/lib/utils";
import { fileEnAttente, fileEnEchec, traiterFile } from "@/lib/offline-queue";
import { PiedVersion } from "@/components/pied-version";
import { SelecteurTheme } from "@/components/SelecteurTheme";

type NavItem = {
  to: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  raccourci?: string;
  roles?: string[]; // si défini, visible seulement pour ces rôles
};

// Le rôle est lu depuis sessionStorage pour afficher les liens conditionnels.
function getRole(): string {
  if (typeof window === "undefined") return "";
  try {
    // Le profil est stocké dans sessionStorage après connexion
    const raw = window.sessionStorage.getItem("pharmapp.role");
    return raw || "";
  } catch {
    return "";
  }
}

const HIERARCHIE: Record<string, number> = {
  stagiaire: 0, caissier: 1, assistant: 2, gestionnaire_stock: 3,
  pharmacien_adjoint: 4, titulaire: 5, administrateur: 6,
};

function niveauRole(role: string): number {
  return HIERARCHIE[role] ?? -1;
}

const NAV: NavItem[] = [
  { to: "/",             label: "Point de vente",  icon: ShoppingCart,  raccourci: "F2" },
  { to: "/stock",        label: "Stock",            icon: Package,       raccourci: "F3" },
  { to: "/achats",       label: "Achats",           icon: Truck,         raccourci: "F4" },
  { to: "/cloture",      label: "Clôture",          icon: ClipboardCheck,raccourci: "F5" },
  { to: "/tableau-bord", label: "Tableau de bord",  icon: BarChart3 },
  { to: "/clients",      label: "Clients",          icon: Users },
  // Étape 4 — visible Pharmacien assistant+
  { to: "/catalogue",    label: "Catalogue",        icon: BookOpen, roles: ["assistant", "gestionnaire_stock", "pharmacien_adjoint", "titulaire", "administrateur"] },
  // Étape 8 — visible Pharmacien adjoint+
  { to: "/rapports",     label: "Rapports",         icon: FileText, roles: ["pharmacien_adjoint", "titulaire", "administrateur"] },
  // Étape 9 — visible Titulaire uniquement
  { to: "/utilisateurs", label: "Utilisateurs",     icon: UserCog, roles: ["titulaire", "administrateur"] },
  { to: "/parametres",   label: "Paramètres",       icon: Settings },
];

/**
 * Coquille principale de l'application.
 * Sidebar dense, indicateurs de synchro en temps réel, layout plein-écran.
 */
export function AppShell() {
  const location = useLocation();
  const [enLigne, setEnLigne] = useState(true);
  const [enAttente, setEnAttente] = useState(0);
  const [enEchec, setEnEchec] = useState(0);
  const [role, setRole] = useState("");

  useEffect(() => {
    setRole(getRole());
  }, []);

  // Écouter les changements de rôle (après connexion)
  useEffect(() => {
    const handleStorage = () => setRole(getRole());
    window.addEventListener("storage", handleStorage);
    return () => window.removeEventListener("storage", handleStorage);
  }, []);

  useEffect(() => {
    setEnLigne(navigator.onLine);
    const onOnline = () => setEnLigne(true);
    const onOffline = () => setEnLigne(false);
    window.addEventListener("online", onOnline);
    window.addEventListener("offline", onOffline);
    return () => {
      window.removeEventListener("online", onOnline);
      window.removeEventListener("offline", onOffline);
    };
  }, []);

  useEffect(() => {
    let annule = false;
    const tic = async () => {
      const [attente, echecs] = await Promise.all([fileEnAttente(), fileEnEchec()]);
      if (annule) return;
      setEnAttente(attente.length);
      setEnEchec(echecs.length);
      if (enLigne && attente.length > 0) {
        await traiterFile();
        const [restant, echecsRestants] = await Promise.all([fileEnAttente(), fileEnEchec()]);
        if (!annule) {
          setEnAttente(restant.length);
          setEnEchec(echecsRestants.length);
        }
      }
    };
    void tic();
    const h = window.setInterval(tic, 15_000);
    return () => { annule = true; window.clearInterval(h); };
  }, [enLigne]);

  const navVisibles = NAV.filter((item) => {
    if (!item.roles) return true;
    // Si aucun rôle n'est chargé encore, on affiche prudemment tout
    if (!role) return true;
    return item.roles.some((r) => niveauRole(role) >= niveauRole(r));
  });

  return (
    <div className="flex min-h-screen bg-background text-foreground">
      <aside className="hidden md:flex md:w-64 lg:w-72 flex-col border-r border-border/70 bg-surface/60 backdrop-blur">
        <div className="flex items-center gap-3 px-6 pt-8 pb-6">
          <div className="grid h-10 w-10 place-items-center rounded-xl bg-primary text-primary-foreground shadow-elevated">
            <span className="font-display text-2xl leading-none">℞</span>
          </div>
          <div className="flex-1 min-w-0">
            <div className="font-display text-2xl leading-none">PharmApp</div>
            <div className="text-xs text-muted-foreground">Édition officine</div>
          </div>
          <SelecteurTheme />
        </div>

        <nav className="flex-1 space-y-1 px-3 overflow-y-auto">
          {navVisibles.map((item) => {
            const actif =
              item.to === "/"
                ? location.pathname === "/"
                : location.pathname.startsWith(item.to);
            const Icon = item.icon;
            return (
              <Link
                key={item.to}
                to={item.to}
                className={cn(
                  "group flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition-colors",
                  actif
                    ? "bg-primary/15 text-foreground"
                    : "text-muted-foreground hover:bg-surface-strong hover:text-foreground",
                )}
              >
                <Icon className={cn("h-4 w-4 shrink-0", actif && "text-primary")} />
                <span className="flex-1">{item.label}</span>
                {item.raccourci && (
                  <span className="kbd">{item.raccourci}</span>
                )}
              </Link>
            );
          })}
        </nav>

        <div className="border-t border-border/70 px-4 py-4">
          <StatutSynchro enLigne={enLigne} enAttente={enAttente} enEchec={enEchec} />
        </div>

        {/* ÉTAPE 00 — identité de build visible en permanence (support). */}
        <div className="border-t border-border/70">
          <PiedVersion />
        </div>
      </aside>

      <main className="flex-1 min-w-0">
        <Outlet />
      </main>
    </div>
  );
}

function StatutSynchro({
  enLigne,
  enAttente,
  enEchec,
}: {
  enLigne: boolean;
  enAttente: number;
  enEchec: number;
}) {
  const enPanne = !enLigne;
  return (
    <div className="space-y-2 text-xs">
      <div className="flex items-center gap-2">
        {enPanne ? (
          <WifiOff className="h-4 w-4 text-warning" />
        ) : (
          <Wifi className="h-4 w-4 text-success" />
        )}
        <span className={cn("font-medium", enPanne ? "text-warning" : "text-success")}>
          {enPanne ? "Mode hors-ligne" : "Serveur local en ligne"}
        </span>
      </div>

      <div className="flex items-center gap-2 text-muted-foreground">
        <CloudUpload className="h-4 w-4" />
        <span>
          {enAttente === 0
            ? "Aucune opération en attente"
            : `${enAttente} vente${enAttente > 1 ? "s" : ""} à synchroniser`}
        </span>
      </div>

      {enEchec > 0 && (
        <div className="flex items-center gap-2 text-destructive">
          <span className="h-4 w-4 text-center font-bold leading-4">✕</span>
          <span>
            {enEchec} vente{enEchec > 1 ? "s" : ""} rejetée{enEchec > 1 ? "s" : ""} définitivement
          </span>
        </div>
      )}
    </div>
  );
}
