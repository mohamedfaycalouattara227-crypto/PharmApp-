/**
 * Page de connexion — Route publique hors du layout _app.
 *
 * CORRECTION S2 : Crée la destination de la redirection effectuée par le
 * beforeLoad du layout `_app.tsx` lorsqu'aucun JWT n'est présent.
 *
 * Flux :
 *   1. L'utilisateur saisit son email + mot de passe.
 *   2. api.auth.connexion() POST { email, mot_de_passe } → Django VueConnexion.
 *   3. En cas de succès, l'access token est stocké via setToken() (sessionStorage).
 *      Le refresh token est stocké séparément pour permettre le renouvellement.
 *   4. Redirection immédiate vers "/" (point de vente).
 *   5. En cas d'erreur, le message Django (email invalide, compte verrouillé…)
 *      s'affiche directement — pas de message générique masquant la cause réelle.
 */

import { createFileRoute, useRouter } from "@tanstack/react-router";
import { useState, useRef } from "react";
import { Loader2, LogIn } from "lucide-react";

import { PiedVersion } from "@/components/pied-version";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api } from "@/lib/api-client";

const ROLE_KEY = "pharmapp.role";

export const Route = createFileRoute("/connexion")({
  // Plus de gate ici : le JWT est en cookie httpOnly, illisible côté JS.
  // La redirection "déjà connecté" se fait via un appel /auth/profil/ dans
  // le composant, non bloquant.
  component: PageConnexion,
  head: () => ({
    meta: [
      { title: "Connexion — PharmApp" },
      { name: "robots", content: "noindex, nofollow" },
    ],
  }),
});

function PageConnexion() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [motDePasse, setMotDePasse] = useState("");
  const [erreur, setErreur] = useState<string | null>(null);
  const [enCours, setEnCours] = useState(false);
  const emailRef = useRef<HTMLInputElement>(null);

  const seConnecter = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.trim() || !motDePasse) return;

    setEnCours(true);
    setErreur(null);

    try {
      // Depuis v5, la connexion pose des cookies httpOnly côté backend
      // et retourne uniquement { role, nom_complet }. Rien à stocker en JS
      // à part le rôle, qui reste un simple indicateur UI (le serveur
      // ré-évalue systématiquement les permissions).
      const { role } = await api.auth.connexion(email.trim(), motDePasse);
      window.sessionStorage.setItem(ROLE_KEY, role);
      await router.invalidate();
      await router.navigate({ to: "/" });
    } catch (err: unknown) {
      const detail =
        err instanceof Error ? err.message : "Erreur de connexion inattendue.";
      setErreur(detail);
      emailRef.current?.focus();
      emailRef.current?.select();
    } finally {
      setEnCours(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-background px-4">
      <div className="w-full max-w-sm space-y-8">

        {/* Logo / en-tête */}
        <div className="text-center space-y-3">
          <div className="mx-auto grid h-16 w-16 place-items-center rounded-2xl bg-primary text-primary-foreground shadow-elevated">
            <span className="font-display text-4xl leading-none">℞</span>
          </div>
          <div>
            <div className="font-display text-3xl">PharmApp</div>
            <div className="text-sm text-muted-foreground mt-1">Édition officine — Accès sécurisé</div>
          </div>
        </div>

        {/* Formulaire */}
        <form onSubmit={seConnecter} className="card-elevated p-6 space-y-5">
          <div className="space-y-2">
            <Label htmlFor="email">Adresse e-mail</Label>
            <Input
              id="email"
              ref={emailRef}
              type="email"
              autoComplete="email"
              autoFocus
              required
              placeholder="pharmacien@officine.bf"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              disabled={enCours}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="mot-de-passe">Mot de passe</Label>
            <Input
              id="mot-de-passe"
              type="password"
              autoComplete="current-password"
              required
              placeholder="••••••••••••"
              value={motDePasse}
              onChange={(e) => setMotDePasse(e.target.value)}
              disabled={enCours}
            />
          </div>

          {/* Message d'erreur — affiché uniquement en cas d'échec */}
          {erreur && (
            <div
              role="alert"
              className="rounded-lg border border-destructive/40 bg-destructive/10 px-4 py-3 text-sm text-destructive"
            >
              {erreur}
            </div>
          )}

          <Button type="submit" className="w-full" disabled={enCours || !email || !motDePasse}>
            {enCours ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <LogIn className="h-4 w-4" />
            )}
            {enCours ? "Connexion en cours…" : "Se connecter"}
          </Button>
        </form>

        <p className="text-center text-xs text-muted-foreground">
          Session active jusqu'à la fermeture de l'onglet.
          <br />
          En cas de verrouillage de compte, contactez l'administrateur.
        </p>

        {/* ÉTAPE 00 — version visible avant même l'authentification. */}
        <PiedVersion className="text-center" />
      </div>
    </div>
  );
}
