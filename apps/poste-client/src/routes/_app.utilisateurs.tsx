/**
 * _app.utilisateurs.tsx — Étape 9 : Gestion des utilisateurs
 *
 * Fonctionnalités :
 *  - Liste de tous les comptes (pharmaciens, caissiers, stagiaires…)
 *  - Créer / modifier un compte (titulaire uniquement)
 *  - Suspendre / réactiver un compte
 *  - Déverrouiller après blocage anti-brute-force
 *  - Afficher le rôle, statut actif/verrouillé, dernière connexion
 *
 * Accès : titulaire & administrateur uniquement (§4.1 CDC).
 */

import { createFileRoute } from "@tanstack/react-router";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { UserCog, Plus, Pencil, Lock, Unlock, UserX, UserCheck, X, Shield } from "lucide-react";

import { api, ApiError } from "@/lib/api-client";
import { fmtDate, LIBELLES_ROLE } from "@/lib/format";
import type { Utilisateur, RoleUtilisateur } from "@/lib/types";

export const Route = createFileRoute("/_app/utilisateurs")({
  component: UtilisateursPage,
});

const ROLES: RoleUtilisateur[] = [
  "stagiaire", "caissier", "assistant", "gestionnaire_stock",
  "pharmacien_adjoint", "titulaire", "administrateur",
];

// ── Formulaire utilisateur ───────────────────────────────────────────────────

type UtilisateurForm = {
  prenom: string; nom: string; email: string; telephone: string;
  role: RoleUtilisateur; numero_ordre: string; est_actif: boolean;
  mot_de_passe: string;
};

const FORM_VIDE: UtilisateurForm = {
  prenom: "", nom: "", email: "", telephone: "", role: "caissier",
  numero_ordre: "", est_actif: true, mot_de_passe: "",
};

function UtilisateurDialog({
  initial, onSave, onClose,
}: { initial?: Utilisateur | null; onSave: (d: Partial<UtilisateurForm>) => Promise<void>; onClose: () => void }) {
  const [form, setForm] = useState<UtilisateurForm>(
    initial
      ? {
          prenom: initial.prenom, nom: initial.nom, email: initial.email,
          telephone: initial.telephone ?? "", role: initial.role as RoleUtilisateur,
          numero_ordre: initial.numero_ordre ?? "", est_actif: initial.est_actif,
          mot_de_passe: "",
        }
      : FORM_VIDE
  );
  const [erreur, setErreur] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const champ = (k: keyof UtilisateurForm) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setForm((f) => ({ ...f, [k]: e.target.value }));
  const bool = (k: keyof UtilisateurForm) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((f) => ({ ...f, [k]: e.target.checked }));

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.nom.trim() || !form.email.trim()) { setErreur("Nom et email obligatoires."); return; }
    if (!initial && !form.mot_de_passe) { setErreur("Le mot de passe est obligatoire pour un nouveau compte."); return; }
    setLoading(true); setErreur(null);
    const payload: Partial<UtilisateurForm> = { ...form };
    if (!payload.mot_de_passe) delete payload.mot_de_passe;
    try {
      await onSave(payload);
      onClose();
    } catch (err) {
      setErreur(err instanceof ApiError ? err.detail : "Erreur inattendue.");
    } finally { setLoading(false); }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 overflow-y-auto">
      <div className="w-full max-w-lg rounded-xl bg-background shadow-xl p-6 my-4">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-display">{initial ? "Modifier le compte" : "Nouveau compte"}</h2>
          <button onClick={onClose} className="h-8 w-8 flex items-center justify-center rounded-lg hover:bg-surface-strong">
            <X className="h-4 w-4" />
          </button>
        </div>
        {erreur && <div className="mb-4 rounded-lg bg-destructive/10 px-4 py-2 text-sm text-destructive">{erreur}</div>}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div><label className="label">Prénom *</label><input className="input" value={form.prenom} onChange={champ("prenom")} required /></div>
            <div><label className="label">Nom *</label><input className="input" value={form.nom} onChange={champ("nom")} required /></div>
            <div><label className="label">Email *</label><input className="input" type="email" value={form.email} onChange={champ("email")} required /></div>
            <div><label className="label">Téléphone</label><input className="input" type="tel" value={form.telephone} onChange={champ("telephone")} /></div>
            <div>
              <label className="label">Rôle *</label>
              <select className="input" value={form.role} onChange={champ("role")}>
                {ROLES.map((r) => <option key={r} value={r}>{LIBELLES_ROLE[r] ?? r}</option>)}
              </select>
            </div>
            <div><label className="label">N° Ordre (pharmacien)</label><input className="input" value={form.numero_ordre} onChange={champ("numero_ordre")} /></div>
            <div className="col-span-2">
              <label className="label">{initial ? "Nouveau mot de passe (laisser vide pour conserver)" : "Mot de passe *"}</label>
              <input className="input" type="password" value={form.mot_de_passe} onChange={champ("mot_de_passe")} autoComplete="new-password" required={!initial} />
            </div>
          </div>
          {initial && (
            <div className="flex items-center gap-3">
              <input type="checkbox" id="est_actif" checked={form.est_actif} onChange={bool("est_actif")} className="checkbox" />
              <label htmlFor="est_actif" className="text-sm">Compte actif</label>
            </div>
          )}
          <div className="flex justify-end gap-3 pt-2">
            <button type="button" onClick={onClose} className="btn btn-ghost">Annuler</button>
            <button type="submit" disabled={loading} className="btn btn-primary">
              {loading ? "Enregistrement…" : "Enregistrer"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ── Page principale ──────────────────────────────────────────────────────────

function UtilisateursPage() {
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const [dialog, setDialog] = useState<{ open: boolean; item?: Utilisateur | null }>({ open: false });

  const { data, isLoading } = useQuery({
    queryKey: ["utilisateurs", search],
    queryFn: () => api.utilisateurs.liste({ ...(search ? { search } : {}) }),
    staleTime: 30_000,
  });
  const utilisateurs = data?.results ?? [];

  const creer = useMutation({
    mutationFn: (d: unknown) => api.utilisateurs.creer(d),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["utilisateurs"] }); },
  });
  const modifier = useMutation({
    mutationFn: ({ id, d }: { id: string; d: unknown }) => api.utilisateurs.modifier(id, d),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["utilisateurs"] }); },
  });
  const suspendre = useMutation({
    mutationFn: (id: string) => api.utilisateurs.suspendre(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["utilisateurs"] }),
  });
  const reactiver = useMutation({
    mutationFn: (id: string) => api.utilisateurs.reactiver(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["utilisateurs"] }),
  });
  const deverrouiller = useMutation({
    mutationFn: (id: string) => api.utilisateurs.deverrouiller(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["utilisateurs"] }),
  });

  const moi = window.sessionStorage.getItem("pharmapp.user_id") ?? "";

  return (
    <div className="flex h-screen flex-col overflow-hidden">
      <header className="flex items-center justify-between border-b border-border/70 bg-surface/80 px-6 py-4">
        <div className="flex items-center gap-3">
          <UserCog className="h-5 w-5 text-muted-foreground" />
          <h1 className="font-display text-2xl">Utilisateurs</h1>
          <span className="text-sm text-muted-foreground">({data?.count ?? 0})</span>
        </div>
        <button
          onClick={() => setDialog({ open: true, item: null })}
          className="btn btn-primary flex items-center gap-2"
        >
          <Plus className="h-4 w-4" /> Nouveau compte
        </button>
      </header>

      <div className="flex items-center gap-3 px-6 py-3 border-b border-border/40">
        <div className="relative max-w-md flex-1">
          <input
            className="input pl-4"
            placeholder="Rechercher nom, email…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
      </div>

      <div className="flex-1 overflow-auto px-6 py-4">
        {isLoading ? (
          <div className="flex justify-center py-16 text-muted-foreground">Chargement…</div>
        ) : utilisateurs.length === 0 ? (
          <div className="flex flex-col items-center gap-4 py-20 text-muted-foreground">
            <UserCog className="h-12 w-12" />
            <p>Aucun utilisateur trouvé.</p>
          </div>
        ) : (
          <div className="space-y-2">
            {utilisateurs.map((u) => {
              const estMoi = u.id === moi;
              return (
                <div
                  key={u.id}
                  className={`flex items-center gap-4 rounded-xl border ${u.est_actif ? "border-border/70 bg-surface/40" : "border-border/40 bg-surface/20 opacity-60"} px-5 py-4`}
                >
                  {/* Avatar initiales */}
                  <div className="h-10 w-10 rounded-full bg-primary/10 flex items-center justify-center flex-shrink-0">
                    <span className="text-sm font-semibold text-primary">
                      {(u.prenom[0] ?? "") + (u.nom[0] ?? "")}
                    </span>
                  </div>

                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-medium">{u.prenom} {u.nom}</span>
                      {estMoi && <span className="text-xs text-muted-foreground">(vous)</span>}
                      {u.est_verrouille && (
                        <span className="flex items-center gap-1 text-xs text-destructive">
                          <Lock className="h-3 w-3" /> Verrouillé
                        </span>
                      )}
                    </div>
                    <div className="text-sm text-muted-foreground">{u.email}</div>
                    <div className="flex items-center gap-3 mt-1">
                      <span className="rounded-full px-2 py-0.5 text-xs bg-primary/10 text-primary">
                        {LIBELLES_ROLE[u.role] ?? u.role}
                      </span>
                      {u.derniere_connexion_reussie && (
                        <span className="text-xs text-muted-foreground">
                          Dernière connexion : {fmtDate(u.derniere_connexion_reussie)}
                        </span>
                      )}
                    </div>
                  </div>

                  <div className="flex items-center gap-2 shrink-0">
                    {/* Déverrouiller */}
                    {u.est_verrouille && !estMoi && (
                      <button
                        onClick={() => deverrouiller.mutate(u.id)}
                        title="Déverrouiller le compte"
                        className="btn btn-ghost flex items-center gap-1.5 text-xs py-1.5"
                      >
                        <Unlock className="h-3.5 w-3.5" /> Déverrouiller
                      </button>
                    )}

                    {/* Suspendre / réactiver */}
                    {!estMoi && (
                      u.est_actif ? (
                        <button
                          onClick={() => { if (confirm(`Suspendre ${u.prenom} ${u.nom} ?`)) suspendre.mutate(u.id); }}
                          title="Suspendre le compte"
                          className="btn btn-ghost flex items-center gap-1.5 text-xs py-1.5 text-warning"
                        >
                          <UserX className="h-3.5 w-3.5" /> Suspendre
                        </button>
                      ) : (
                        <button
                          onClick={() => reactiver.mutate(u.id)}
                          title="Réactiver le compte"
                          className="btn btn-ghost flex items-center gap-1.5 text-xs py-1.5 text-success"
                        >
                          <UserCheck className="h-3.5 w-3.5" /> Réactiver
                        </button>
                      )
                    )}

                    {/* Modifier */}
                    <button
                      onClick={() => setDialog({ open: true, item: u })}
                      className="btn btn-ghost flex items-center gap-1.5 text-xs py-1.5"
                    >
                      <Pencil className="h-3.5 w-3.5" /> Modifier
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {dialog.open && (
        <UtilisateurDialog
          initial={dialog.item}
          onSave={async (d) => {
            if (dialog.item?.id) await modifier.mutateAsync({ id: dialog.item.id, d });
            else await creer.mutateAsync(d);
            setDialog({ open: false });
            qc.invalidateQueries({ queryKey: ["utilisateurs"] });
          }}
          onClose={() => setDialog({ open: false })}
        />
      )}
    </div>
  );
}
