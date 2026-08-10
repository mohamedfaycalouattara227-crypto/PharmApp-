/**
 * PiedVersion — bandeau d'identité de build affiché en bas de l'écran.
 *
 * Objectif métier (ÉTAPE 00) : lorsqu'une officine appelle le support, la
 * première question est « quelle version exécutez-vous ? ». La réponse doit
 * être lisible à l'écran, sans naviguer, sans se connecter.
 *
 * Un clic copie l'identité complète (poste client + serveur local) dans le
 * presse-papier pour la coller dans un ticket d'incident.
 */

import { useEffect, useState } from "react";

import { API_BASE_URL } from "@/lib/api-client";
import { cn } from "@/lib/utils";
import { libelleSupport, libelleVersion, VERSION } from "@/lib/version";

type VersionServeur = {
  application: string;
  version: string;
  revision: string;
  environnement: string;
};

export function PiedVersion({ className }: { className?: string }) {
  const [serveur, setServeur] = useState<VersionServeur | null>(null);
  const [copie, setCopie] = useState(false);

  useEffect(() => {
    let annule = false;
    const racine = API_BASE_URL.replace(/\/api$/, "");
    fetch(`${racine}/api/v1/version/`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (!annule && d) setServeur(d as VersionServeur);
      })
      .catch(() => {
        /* serveur local injoignable : le poste reste utilisable hors-ligne */
      });
    return () => {
      annule = true;
    };
  }, []);

  const desaccord = serveur !== null && serveur.version !== VERSION;

  async function copier() {
    const texte = [
      libelleSupport(),
      serveur
        ? `Serveur local v${serveur.version} (build ${serveur.revision}, ${serveur.environnement})`
        : "Serveur local injoignable",
    ].join(" | ");
    try {
      await navigator.clipboard.writeText(texte);
      setCopie(true);
      window.setTimeout(() => setCopie(false), 2000);
    } catch {
      setCopie(false);
    }
  }

  return (
    <button
      type="button"
      onClick={copier}
      title="Cliquer pour copier l'identité de version à transmettre au support"
      className={cn(
        "w-full truncate px-4 py-2 text-left text-[11px] leading-tight text-muted-foreground transition-colors hover:text-foreground",
        className,
      )}
      data-testid="pied-version"
    >
      <span className="font-mono">{libelleVersion()}</span>
      {serveur && (
        <span className="font-mono"> · serveur v{serveur.version}</span>
      )}
      {desaccord && (
        <span className="ml-1 font-semibold text-warning">
          — versions poste/serveur différentes
        </span>
      )}
      {copie && <span className="ml-1 text-success">copié</span>}
    </button>
  );
}
