/**
 * ScreenClients — Gestion des clients (§4.5 CDC, étape 5).
 *
 * Extrait de _app.clients.tsx lors du découpage modulaire (v2).
 * La route conserve uniquement la définition TanStack Router.
 *
 * Liste paginée + recherche + fiche détaillée + CRUD + droit à l'oubli.
 * Allergies et crédit conditionnels selon le rôle (§7.2 CDC).
 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import {
  Users, Plus, Search, Pencil, ChevronRight, Phone, Mail,
  CreditCard, Shield, AlertTriangle, History, X,
} from "lucide-react";

import { api, ApiError } from "@/lib/api-client";
import { fmtFCFA, fmtDateCourte, LIBELLES_TYPE_CLIENT } from "@/lib/format";
import type { Client, Vente } from "@/lib/types";

const HIERARCHIE: Record<string, number> = {
  stagiaire: 0, caissier: 1, assistant: 2, gestionnaire_stock: 3,
  pharmacien_adjoint: 4, titulaire: 5, administrateur: 6,
};
function getRole(): string { return window.sessionStorage.getItem("pharmapp.role") ?? ""; }
function niveau(): number  { return HIERARCHIE[getRole()] ?? -1; }
function peutVoirAllergies(): boolean { return niveau() >= 4; }
function peutGererCredit():   boolean { return niveau() >= 4; }
function peutAnonimiser():    boolean { return niveau() >= 5; }

// ── Formulaire client ────────────────────────────────────────────────────────

type ClientForm = {
  prenom: string; nom: string; telephone: string; email: string; adresse: string;
  date_naissance: string; type_client: string; assureur: string;
  numero_assurance: string; taux_prise_en_charge: string;
  credit_autorise: boolean; plafond_credit: string;
  allergies: string; notes: string; est_actif: boolean;
};
const FORM_VIDE: ClientForm = {
  prenom: "", nom: "", telephone: "", email: "", adresse: "", date_naissance: "",
  type_client: "particulier", assureur: "", numero_assurance: "", taux_prise_en_charge: "0",
  credit_autorise: false, plafond_credit: "0", allergies: "", notes: "", est_actif: true,
};

function ClientDialog({ initial, onSave, onClose }: {
  initial?: Client | null;
  onSave: (d: Partial<ClientForm>) => Promise<void>;
  onClose: () => void;
}) {
  const [form, setForm] = useState<ClientForm>(
    initial ? {
      prenom: initial.prenom ?? "", nom: initial.nom, telephone: initial.telephone ?? "",
      email: initial.email ?? "", adresse: initial.adresse ?? "", date_naissance: initial.date_naissance ?? "",
      type_client: initial.type_client ?? "particulier", assureur: initial.assureur ?? "",
      numero_assurance: initial.numero_assurance ?? "", taux_prise_en_charge: initial.taux_prise_en_charge ?? "0",
      credit_autorise: initial.credit_autorise ?? false, plafond_credit: initial.plafond_credit ?? "0",
      allergies: initial.allergies ?? "", notes: initial.notes ?? "", est_actif: initial.est_actif ?? true,
    } : FORM_VIDE
  );
  const [erreur, setErreur]   = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const champ = (k: keyof ClientForm) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => setForm((f) => ({ ...f, [k]: e.target.value }));
  const bool  = (k: keyof ClientForm) => (e: React.ChangeEvent<HTMLInputElement>) => setForm((f) => ({ ...f, [k]: e.target.checked }));

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.nom.trim()) { setErreur("Le nom est obligatoire."); return; }
    setLoading(true); setErreur(null);
    try { await onSave(form); onClose(); }
    catch (err) { setErreur(err instanceof ApiError ? err.detail : "Erreur inattendue."); }
    finally { setLoading(false); }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 overflow-y-auto">
      <div className="w-full max-w-2xl rounded-xl bg-background shadow-xl p-6 my-4">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-display">{initial ? "Modifier le client" : "Nouveau client"}</h2>
          <button onClick={onClose} className="h-8 w-8 flex items-center justify-center rounded-lg hover:bg-surface-strong"><X className="h-4 w-4" /></button>
        </div>
        {erreur && <div className="mb-4 rounded-lg bg-destructive/10 px-4 py-2 text-sm text-destructive">{erreur}</div>}
        <form onSubmit={handleSubmit} className="space-y-5">
          <div>
            <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3">Identité</div>
            <div className="grid grid-cols-2 gap-3">
              <div><label className="label">Prénom</label><input className="input" value={form.prenom} onChange={champ("prenom")} /></div>
              <div><label className="label">Nom *</label><input className="input" value={form.nom} onChange={champ("nom")} required /></div>
              <div><label className="label">Téléphone</label><input className="input" type="tel" value={form.telephone} onChange={champ("telephone")} /></div>
              <div><label className="label">Email</label><input className="input" type="email" value={form.email} onChange={champ("email")} /></div>
              <div><label className="label">Date de naissance</label><input className="input" type="date" value={form.date_naissance} onChange={champ("date_naissance")} /></div>
              <div>
                <label className="label">Type</label>
                <select className="input" value={form.type_client} onChange={champ("type_client")}>
                  <option value="particulier">Particulier</option>
                  <option value="assurance">Assurance / Mutuelle</option>
                  <option value="institution">Institution</option>
                </select>
              </div>
              <div className="col-span-2"><label className="label">Adresse</label><input className="input" value={form.adresse} onChange={champ("adresse")} /></div>
            </div>
          </div>
          {form.type_client === "assurance" && (
            <div>
              <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3">Assurance</div>
              <div className="grid grid-cols-2 gap-3">
                <div><label className="label">Assureur</label><input className="input" value={form.assureur} onChange={champ("assureur")} /></div>
                <div><label className="label">N° contrat</label><input className="input" value={form.numero_assurance} onChange={champ("numero_assurance")} /></div>
                <div><label className="label">Taux prise en charge (%)</label><input className="input" type="number" min="0" max="100" value={form.taux_prise_en_charge} onChange={champ("taux_prise_en_charge")} /></div>
              </div>
            </div>
          )}
          {peutGererCredit() && (
            <div>
              <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3">Crédit</div>
              <div className="space-y-3">
                <div className="flex items-center gap-3">
                  <input type="checkbox" id="credit" checked={form.credit_autorise} onChange={bool("credit_autorise")} className="checkbox" />
                  <label htmlFor="credit" className="text-sm">Crédit autorisé</label>
                </div>
                {form.credit_autorise && <div><label className="label">Plafond (FCFA)</label><input className="input" type="number" min="0" value={form.plafond_credit} onChange={champ("plafond_credit")} /></div>}
              </div>
            </div>
          )}
          {peutVoirAllergies() && (
            <div>
              <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3 flex items-center gap-2"><Shield className="h-3.5 w-3.5" />Données médicales sensibles</div>
              <div>
                <label className="label">Allergies connues</label>
                <textarea className="input min-h-[80px]" value={form.allergies} onChange={champ("allergies")} placeholder="ex: Pénicilline, sulfamides…" />
                <p className="text-xs text-muted-foreground mt-1">Visible uniquement par les pharmaciens adjoints et supérieurs (§7.2 CDC).</p>
              </div>
            </div>
          )}
          <div><label className="label">Notes</label><textarea className="input min-h-[60px]" value={form.notes} onChange={champ("notes")} /></div>
          <div className="flex justify-end gap-3">
            <button type="button" onClick={onClose} className="btn btn-ghost">Annuler</button>
            <button type="submit" disabled={loading} className="btn btn-primary">{loading ? "Enregistrement…" : "Enregistrer"}</button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ── Fiche client ─────────────────────────────────────────────────────────────

function FicheClient({ client, onEdit, onClose }: { client: Client; onEdit: () => void; onClose: () => void }) {
  const { data: ventesData } = useQuery({
    queryKey: ["client-ventes", client.id],
    queryFn: () => api.clients.ventes(client.id),
    staleTime: 30_000,
  });
  const qc         = useQueryClient();
  const ventes     = ventesData?.results ?? [];
  const credit     = client.encours_credit ?? "0";

  function apiAnonymiser(id: string) {
    const csrf = document.cookie.split("; ").find((c) => c.startsWith("pharmapp_csrf="))?.split("=")[1] ?? "";
    return fetch(`${import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000"}/api/clients/${id}/anonymiser/`, {
      method: "POST", credentials: "include",
      headers: csrf ? { "X-CSRF-Token": decodeURIComponent(csrf) } : {},
    });
  }

  const anonymiser = useMutation({
    mutationFn: () => apiAnonymiser(client.id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["clients"] }); onClose(); },
  });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 overflow-y-auto">
      <div className="w-full max-w-2xl rounded-xl bg-background shadow-xl my-4">
        <div className="flex items-center justify-between p-6 border-b border-border/70">
          <div>
            <h2 className="text-xl font-display">{client.nom_complet ?? `${client.prenom ?? ""} ${client.nom}`.trim()}</h2>
            <div className="text-sm text-muted-foreground">{LIBELLES_TYPE_CLIENT[client.type_client ?? "particulier"]}</div>
          </div>
          <div className="flex gap-2">
            <button onClick={onEdit} className="btn btn-ghost flex items-center gap-2 text-sm"><Pencil className="h-4 w-4" /> Modifier</button>
            <button onClick={onClose} className="h-9 w-9 flex items-center justify-center rounded-lg hover:bg-surface-strong"><X className="h-4 w-4" /></button>
          </div>
        </div>
        <div className="p-6 space-y-6">
          <div className="grid grid-cols-2 gap-4">
            {client.telephone && <div className="flex items-center gap-2 text-sm"><Phone className="h-4 w-4 text-muted-foreground" /><span>{client.telephone}</span></div>}
            {client.email     && <div className="flex items-center gap-2 text-sm"><Mail  className="h-4 w-4 text-muted-foreground" /><span>{client.email}</span></div>}
          </div>
          {client.type_client === "assurance" && (
            <div className="rounded-lg bg-surface/40 p-4">
              <div className="flex items-center gap-2 mb-2"><Shield className="h-4 w-4 text-primary" /><span className="font-medium text-sm">Assurance</span></div>
              <div className="grid grid-cols-2 gap-2 text-sm text-muted-foreground">
                <span>Assureur : <span className="text-foreground">{client.assureur || "—"}</span></span>
                <span>Contrat : <span className="text-foreground">{client.numero_assurance || "—"}</span></span>
                <span>Taux PC : <span className="text-foreground">{client.taux_prise_en_charge ?? "0"} %</span></span>
              </div>
            </div>
          )}
          {client.credit_autorise && (
            <div className="rounded-lg bg-surface/40 p-4">
              <div className="flex items-center gap-2 mb-2"><CreditCard className="h-4 w-4 text-primary" /><span className="font-medium text-sm">Crédit</span></div>
              <div className="grid grid-cols-2 gap-2 text-sm">
                <span className="text-muted-foreground">Plafond : <span className="text-foreground">{fmtFCFA(client.plafond_credit ?? "0")}</span></span>
                <span className={Number(credit) > 0 ? "text-warning" : "text-muted-foreground"}>Encours : <span className="font-medium">{fmtFCFA(credit)}</span></span>
              </div>
            </div>
          )}
          {peutVoirAllergies() && client.allergies && (
            <div className="rounded-lg bg-amber-50 dark:bg-amber-950/20 border border-amber-200 dark:border-amber-900/40 p-4">
              <div className="flex items-center gap-2 mb-2"><AlertTriangle className="h-4 w-4 text-amber-600" /><span className="font-medium text-sm text-amber-700 dark:text-amber-400">Allergies connues</span></div>
              <p className="text-sm text-amber-800 dark:text-amber-300">{client.allergies}</p>
            </div>
          )}
          <div>
            <div className="flex items-center gap-2 mb-3"><History className="h-4 w-4 text-muted-foreground" /><span className="font-medium text-sm">Historique des achats ({ventes.length})</span></div>
            {ventes.length === 0 ? <p className="text-sm text-muted-foreground">Aucun achat enregistré.</p> : (
              <div className="space-y-2">
                {ventes.slice(0, 5).map((v: Vente) => (
                  <div key={v.id} className="flex items-center justify-between rounded-lg bg-surface/40 px-3 py-2 text-sm">
                    <span className="text-muted-foreground">{fmtDateCourte(v.cree_le)}</span>
                    <span className="text-muted-foreground">{v.numero}</span>
                    <span className="font-medium">{fmtFCFA(v.montant_total)}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
          {peutAnonimiser() && !client.est_anonymise && (
            <div className="border-t border-border/70 pt-4">
              <button onClick={() => { if (confirm("Anonymiser les données de ce client ? Cette action est irréversible.")) anonymiser.mutate(); }} className="text-sm text-destructive hover:underline">
                Anonymiser (droit à l'oubli RGPD)
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Composant principal exporté ──────────────────────────────────────────────

export function ScreenClients() {
  const qc = useQueryClient();
  const [search, setSearch]   = useState("");
  const [ficheId, setFicheId] = useState<string | null>(null);
  const [dialog, setDialog]   = useState<{ open: boolean; item?: Client | null }>({ open: false });

  const { data, isLoading } = useQuery({
    queryKey: ["clients", search],
    queryFn: () => api.clients.liste({ ...(search ? { search } : {}) }),
    staleTime: 30_000,
  });
  const clients     = data?.results ?? [];
  const ficheClient = ficheId ? clients.find((c) => c.id === ficheId) ?? null : null;

  const creer   = useMutation({ mutationFn: (d: unknown) => api.clients.creer(d), onSuccess: () => { qc.invalidateQueries({ queryKey: ["clients"] }); setDialog({ open: false }); } });
  const modifier = useMutation({ mutationFn: ({ id, d }: { id: string; d: unknown }) => api.clients.modifier(id, d), onSuccess: () => { qc.invalidateQueries({ queryKey: ["clients"] }); setDialog({ open: false }); } });

  return (
    <div className="flex h-screen flex-col overflow-hidden">
      <header className="flex items-center justify-between border-b border-border/70 bg-surface/80 px-6 py-4">
        <div className="flex items-center gap-3">
          <Users className="h-5 w-5 text-muted-foreground" />
          <h1 className="font-display text-2xl">Clients</h1>
          <span className="text-sm text-muted-foreground">({data?.count ?? 0})</span>
        </div>
        <button onClick={() => setDialog({ open: true, item: null })} className="btn btn-primary flex items-center gap-2">
          <Plus className="h-4 w-4" /> Nouveau client
        </button>
      </header>
      <div className="flex items-center gap-3 px-6 py-3 border-b border-border/40">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <input className="input pl-9" placeholder="Rechercher nom, prénom, téléphone…" value={search} onChange={(e) => setSearch(e.target.value)} />
        </div>
      </div>
      <div className="flex-1 overflow-auto px-6 py-4">
        {isLoading ? <div className="flex justify-center py-16 text-muted-foreground">Chargement…</div>
          : clients.length === 0 ? (
            <div className="flex flex-col items-center gap-4 py-20 text-muted-foreground">
              <Users className="h-12 w-12" />
              <p>{search ? "Aucun client trouvé." : "Aucun client enregistré."}</p>
            </div>
          ) : (
            <table className="w-full border-collapse text-sm">
              <thead>
                <tr className="border-b border-border/70 text-muted-foreground text-left">
                  <th className="pb-2 pr-4 font-medium">Nom</th>
                  <th className="pb-2 pr-4 font-medium">Téléphone</th>
                  <th className="pb-2 pr-4 font-medium">Type</th>
                  <th className="pb-2 pr-4 font-medium text-right">Encours</th>
                  {peutVoirAllergies() && <th className="pb-2 pr-4 font-medium text-center">Allergies</th>}
                  <th className="pb-2 font-medium text-center">Statut</th>
                  <th></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/40">
                {clients.map((c) => (
                  <tr key={c.id} className="hover:bg-surface/60 cursor-pointer" onClick={() => setFicheId(c.id)}>
                    <td className="py-2.5 pr-4"><div className="font-medium">{c.nom_complet ?? `${c.prenom ?? ""} ${c.nom}`.trim()}</div>{c.email && <div className="text-xs text-muted-foreground">{c.email}</div>}</td>
                    <td className="py-2.5 pr-4 text-muted-foreground">{c.telephone ?? "—"}</td>
                    <td className="py-2.5 pr-4 text-muted-foreground">{LIBELLES_TYPE_CLIENT[c.type_client ?? "particulier"]}</td>
                    <td className="py-2.5 pr-4 text-right">{c.credit_autorise ? <span className={Number(c.encours_credit ?? 0) > 0 ? "text-warning font-medium" : "text-muted-foreground"}>{fmtFCFA(c.encours_credit ?? "0")}</span> : <span className="text-muted-foreground">—</span>}</td>
                    {peutVoirAllergies() && <td className="py-2.5 pr-4 text-center">{c.allergies ? <span title={c.allergies}><AlertTriangle className="h-4 w-4 text-amber-500 inline" /></span> : "—"}</td>}
                    <td className="py-2.5 text-center"><span className={`rounded-full px-2 py-0.5 text-xs ${c.est_actif ? "bg-success/10 text-success" : "bg-muted text-muted-foreground"}`}>{c.est_actif ? "Actif" : "Inactif"}</span></td>
                    <td className="py-2.5 pl-2"><ChevronRight className="h-4 w-4 text-muted-foreground" /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
      </div>
      {ficheClient && <FicheClient client={ficheClient} onEdit={() => { setFicheId(null); setDialog({ open: true, item: ficheClient }); }} onClose={() => setFicheId(null)} />}
      {dialog.open && (
        <ClientDialog
          initial={dialog.item}
          onSave={async (d) => { if (dialog.item?.id) await modifier.mutateAsync({ id: dialog.item.id, d }); else await creer.mutateAsync(d); }}
          onClose={() => setDialog({ open: false })}
        />
      )}
    </div>
  );
}
