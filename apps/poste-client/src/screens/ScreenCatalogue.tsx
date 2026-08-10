/**
 * ScreenCatalogue — Catalogue médicaments & catégories (§4.4 CDC, étape 4).
 *
 * Extrait de _app.catalogue.tsx lors du découpage modulaire (v2).
 * La route conserve uniquement la définition TanStack Router.
 *
 * Onglets : Médicaments (liste + CRUD + import CSV CAMEG), Catégories (CRUD).
 * Écriture réservée aux gestionnaires de stock et au-dessus.
 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { Plus, Pencil, UploadCloud, Search, Filter, Package, Tag, BookOpen, X } from "lucide-react";

import { api, ApiError } from "@/lib/api-client";
import { fmtFCFA } from "@/lib/format";
import type { Medicament, CategorieProduit } from "@/lib/types";

const ROLES_ECRITURE = ["gestionnaire_stock", "pharmacien_adjoint", "titulaire", "administrateur"];
function getRole(): string { return window.sessionStorage.getItem("pharmapp.role") ?? ""; }
function peutEcrire(): boolean { return ROLES_ECRITURE.includes(getRole()); }

// ── Formulaire médicament ────────────────────────────────────────────────────

type MedForm = {
  nom: string; denomination_commune_internationale: string;
  forme_pharmaceutique: string; dosage: string; conditionnement: string;
  categorie: string; code_cis: string; code_barre: string;
  prix_public: string; prix_reglemente: boolean; prix_reference: string;
  hors_nomenclature: boolean; necessite_ordonnance: boolean;
  seuil_alerte_stock: string; seuil_rupture_stock: string; est_actif: boolean;
};

const FORM_VIDE: MedForm = {
  nom: "", denomination_commune_internationale: "", forme_pharmaceutique: "",
  dosage: "", conditionnement: "", categorie: "", code_cis: "", code_barre: "",
  prix_public: "", prix_reglemente: false, prix_reference: "", hors_nomenclature: false,
  necessite_ordonnance: false, seuil_alerte_stock: "20", seuil_rupture_stock: "5", est_actif: true,
};

function MedicamentDialog({ initial, categories, onSave, onClose }: {
  initial?: Medicament | null;
  categories: CategorieProduit[];
  onSave: (data: Partial<MedForm>) => Promise<void>;
  onClose: () => void;
}) {
  const [form, setForm] = useState<MedForm>(initial ? {
    nom: initial.nom,
    denomination_commune_internationale: initial.denomination_commune_internationale ?? "",
    forme_pharmaceutique: initial.forme_pharmaceutique ?? "",
    dosage: initial.dosage ?? "", conditionnement: initial.conditionnement ?? "",
    categorie: (initial.categorie as string) ?? "", code_cis: initial.code_cis ?? "",
    code_barre: initial.code_barre ?? "",
    prix_public: initial.prix_public ?? initial.prix_vente ?? "",
    prix_reglemente: initial.prix_reglemente ?? false,
    prix_reference: initial.prix_reference ?? "",
    hors_nomenclature: initial.hors_nomenclature ?? false,
    necessite_ordonnance: initial.necessite_ordonnance ?? false,
    seuil_alerte_stock: String(initial.seuil_alerte_stock ?? 20),
    seuil_rupture_stock: String(initial.seuil_rupture_stock ?? 5),
    est_actif: initial.est_actif ?? true,
  } : FORM_VIDE);
  const [erreur, setErreur]   = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const champ = (k: keyof MedForm) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => setForm((f) => ({ ...f, [k]: e.target.value }));
  const bool  = (k: keyof MedForm) => (e: React.ChangeEvent<HTMLInputElement>) => setForm((f) => ({ ...f, [k]: e.target.checked }));

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.nom.trim()) { setErreur("Le nom est obligatoire."); return; }
    if (!form.prix_public) { setErreur("Le prix public est obligatoire."); return; }
    if (form.prix_reglemente && !form.prix_reference) { setErreur("Le prix de référence est obligatoire quand le prix est réglementé."); return; }
    setLoading(true); setErreur(null);
    try {
      await onSave({ ...form, prix_public: form.prix_public || undefined, prix_reference: form.prix_reglemente ? form.prix_reference || undefined : null, categorie: form.categorie || undefined } as Partial<MedForm>);
      onClose();
    } catch (err) { setErreur(err instanceof ApiError ? err.detail : "Erreur inattendue."); }
    finally { setLoading(false); }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 overflow-y-auto">
      <div className="w-full max-w-2xl rounded-xl bg-background shadow-xl p-6 my-4">
        <h2 className="text-xl font-display mb-4">{initial ? "Modifier le médicament" : "Nouveau médicament"}</h2>
        {erreur && <div className="mb-4 rounded-lg bg-destructive/10 px-4 py-2 text-sm text-destructive">{erreur}</div>}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="col-span-2"><label className="label">Nom commercial *</label><input className="input" value={form.nom} onChange={champ("nom")} required /></div>
            <div><label className="label">DCI</label><input className="input" value={form.denomination_commune_internationale} onChange={champ("denomination_commune_internationale")} placeholder="ex: Paracétamol" /></div>
            <div><label className="label">Forme pharmaceutique</label><input className="input" value={form.forme_pharmaceutique} onChange={champ("forme_pharmaceutique")} placeholder="Comprimé, Sirop..." /></div>
            <div><label className="label">Dosage</label><input className="input" value={form.dosage} onChange={champ("dosage")} placeholder="500 mg" /></div>
            <div><label className="label">Conditionnement</label><input className="input" value={form.conditionnement} onChange={champ("conditionnement")} placeholder="Boîte de 24" /></div>
            <div>
              <label className="label">Catégorie</label>
              <select className="input" value={form.categorie} onChange={champ("categorie")}>
                <option value="">— Aucune —</option>
                {categories.map((c) => <option key={c.id} value={c.id}>{c.nom}</option>)}
              </select>
            </div>
            <div><label className="label">Prix public (FCFA) *</label><input className="input" type="number" min="0" value={form.prix_public} onChange={champ("prix_public")} required /></div>
            <div><label className="label">Code CIS</label><input className="input" value={form.code_cis} onChange={champ("code_cis")} /></div>
            <div><label className="label">Code-barre</label><input className="input" value={form.code_barre} onChange={champ("code_barre")} /></div>
            <div><label className="label">Seuil alerte</label><input className="input" type="number" min="0" value={form.seuil_alerte_stock} onChange={champ("seuil_alerte_stock")} /></div>
            <div><label className="label">Seuil rupture</label><input className="input" type="number" min="0" value={form.seuil_rupture_stock} onChange={champ("seuil_rupture_stock")} /></div>
          </div>
          <div className="rounded-lg border border-border/70 p-4 space-y-3">
            <div className="flex items-center gap-3">
              <input type="checkbox" id="px_reg" checked={form.prix_reglemente} onChange={bool("prix_reglemente")} className="checkbox" />
              <label htmlFor="px_reg" className="text-sm">Prix réglementé (CAMEG/OHADA)</label>
            </div>
            {form.prix_reglemente && (
              <div><label className="label">Prix de référence plafonné (FCFA) *</label><input className="input" type="number" min="0" value={form.prix_reference} onChange={champ("prix_reference")} required={form.prix_reglemente} /></div>
            )}
            <div className="flex items-center gap-3"><input type="checkbox" id="hors_n" checked={form.hors_nomenclature} onChange={bool("hors_nomenclature")} className="checkbox" /><label htmlFor="hors_n" className="text-sm">Hors nomenclature nationale (prix libre)</label></div>
            <div className="flex items-center gap-3"><input type="checkbox" id="ordo" checked={form.necessite_ordonnance} onChange={bool("necessite_ordonnance")} className="checkbox" /><label htmlFor="ordo" className="text-sm">Médicament sur ordonnance</label></div>
            {initial && (<div className="flex items-center gap-3"><input type="checkbox" id="actif" checked={form.est_actif} onChange={bool("est_actif")} className="checkbox" /><label htmlFor="actif" className="text-sm">Actif dans le catalogue</label></div>)}
          </div>
          <div className="flex justify-end gap-3">
            <button type="button" onClick={onClose} className="btn btn-ghost">Annuler</button>
            <button type="submit" disabled={loading} className="btn btn-primary">{loading ? "Enregistrement…" : "Enregistrer"}</button>
          </div>
        </form>
      </div>
    </div>
  );
}

function CategorieDialog({ initial, onSave, onClose }: { initial?: CategorieProduit | null; onSave: (d: unknown) => Promise<void>; onClose: () => void }) {
  const [nom, setNom]               = useState(initial?.nom ?? "");
  const [code, setCode]             = useState(initial?.code ?? "");
  const [description, setDesc]      = useState(initial?.description ?? "");
  const [erreur, setErreur]         = useState<string | null>(null);
  const [loading, setLoading]       = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!nom.trim()) { setErreur("Le nom est obligatoire."); return; }
    setLoading(true); setErreur(null);
    try { await onSave({ nom, code, description, est_active: true }); onClose(); }
    catch (err) { setErreur(err instanceof ApiError ? err.detail : "Erreur inattendue."); }
    finally { setLoading(false); }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="w-full max-w-md rounded-xl bg-background shadow-xl p-6">
        <h2 className="text-xl font-display mb-4">{initial ? "Modifier la catégorie" : "Nouvelle catégorie"}</h2>
        {erreur && <div className="mb-4 rounded-lg bg-destructive/10 px-4 py-2 text-sm text-destructive">{erreur}</div>}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div><label className="label">Nom *</label><input className="input" value={nom} onChange={(e) => setNom(e.target.value)} required /></div>
          <div><label className="label">Code</label><input className="input" value={code} onChange={(e) => setCode(e.target.value)} placeholder="ex: ANTIB" /></div>
          <div><label className="label">Description</label><input className="input" value={description} onChange={(e) => setDesc(e.target.value)} /></div>
          <div className="flex justify-end gap-3">
            <button type="button" onClick={onClose} className="btn btn-ghost">Annuler</button>
            <button type="submit" disabled={loading} className="btn btn-primary">{loading ? "Enregistrement…" : "Enregistrer"}</button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ── Composant principal exporté ──────────────────────────────────────────────

export function ScreenCatalogue() {
  const qc = useQueryClient();
  const [search, setSearch]         = useState("");
  const [catFiltre, setCatFiltre]   = useState("");
  const [onglet, setOnglet]         = useState<"medicaments" | "categories">("medicaments");
  const [dialogMed, setDialogMed]   = useState<{ open: boolean; item?: Medicament | null }>({ open: false });
  const [dialogCat, setDialogCat]   = useState<{ open: boolean; item?: CategorieProduit | null }>({ open: false });
  const [importMsg, setImportMsg]   = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const { data: medicamentsData, isLoading } = useQuery({
    queryKey: ["medicaments", search, catFiltre],
    queryFn: () => api.medicaments.liste({ ...(search ? { search } : {}), ...(catFiltre ? { categorie: catFiltre } : {}), page_size: 100 }),
    staleTime: 30_000,
  });
  const { data: categoriesData } = useQuery({ queryKey: ["categories"], queryFn: () => api.categories.liste(), staleTime: 60_000 });

  const categories  = categoriesData?.results ?? [];
  const medicaments = medicamentsData?.results ?? [];

  const creerMed   = useMutation({ mutationFn: (d: unknown) => api.medicaments.creer(d), onSuccess: () => qc.invalidateQueries({ queryKey: ["medicaments"] }) });
  const modifierMed = useMutation({ mutationFn: ({ id, data }: { id: string; data: unknown }) => api.medicaments.modifier(id, data), onSuccess: () => qc.invalidateQueries({ queryKey: ["medicaments"] }) });
  const creerCat    = useMutation({ mutationFn: (d: unknown) => api.categories.creer(d), onSuccess: () => qc.invalidateQueries({ queryKey: ["categories"] }) });

  const handleImportCSV = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]; if (!file) return;
    setImportMsg("Import en cours…");
    try {
      const r = await api.medicaments.importerCSV(file);
      setImportMsg(`${r.importe} lignes importées` + (r.erreurs.length > 0 ? ` (${r.erreurs.length} erreur(s))` : ""));
      qc.invalidateQueries({ queryKey: ["medicaments"] });
    } catch (err) { setImportMsg(`Erreur import : ${err instanceof ApiError ? err.detail : "Inconnu"}`); }
    if (fileRef.current) fileRef.current.value = "";
  };

  return (
    <div className="flex h-screen flex-col overflow-hidden">
      <header className="flex items-center justify-between border-b border-border/70 bg-surface/80 px-6 py-4">
        <div className="flex items-center gap-3"><BookOpen className="h-5 w-5 text-muted-foreground" /><h1 className="font-display text-2xl">Catalogue</h1></div>
        {peutEcrire() && (
          <div className="flex items-center gap-2">
            <button onClick={() => fileRef.current?.click()} className="btn btn-ghost flex items-center gap-2 text-sm" title="Importer depuis un fichier CSV CAMEG">
              <UploadCloud className="h-4 w-4" /> Import CSV
            </button>
            <input ref={fileRef} type="file" accept=".csv" className="hidden" onChange={handleImportCSV} />
            <button onClick={() => setDialogMed({ open: true, item: null })} className="btn btn-primary flex items-center gap-2">
              <Plus className="h-4 w-4" /> Nouveau médicament
            </button>
          </div>
        )}
      </header>

      {importMsg && (
        <div className="mx-6 mt-3 rounded-lg bg-info/10 px-4 py-2 text-sm text-info-foreground">
          {importMsg}
          <button onClick={() => setImportMsg(null)} className="ml-3 underline text-xs">Fermer</button>
        </div>
      )}

      <div className="border-b border-border/70 px-6 flex gap-4">
        <button onClick={() => setOnglet("medicaments")} className={`py-3 text-sm font-medium border-b-2 transition-colors ${onglet === "medicaments" ? "border-primary text-primary" : "border-transparent text-muted-foreground hover:text-foreground"}`}>
          <Package className="inline h-4 w-4 mr-1" /> Médicaments ({medicamentsData?.count ?? 0})
        </button>
        <button onClick={() => setOnglet("categories")} className={`py-3 text-sm font-medium border-b-2 transition-colors ${onglet === "categories" ? "border-primary text-primary" : "border-transparent text-muted-foreground hover:text-foreground"}`}>
          <Tag className="inline h-4 w-4 mr-1" /> Catégories ({categories.length})
        </button>
      </div>

      {onglet === "medicaments" && (
        <>
          <div className="flex items-center gap-3 px-6 py-3 border-b border-border/40">
            <div className="relative flex-1 max-w-md">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <input className="input pl-9" placeholder="Rechercher nom, DCI, code…" value={search} onChange={(e) => setSearch(e.target.value)} />
            </div>
            <div className="flex items-center gap-2">
              <Filter className="h-4 w-4 text-muted-foreground" />
              <select className="input w-48" value={catFiltre} onChange={(e) => setCatFiltre(e.target.value)}>
                <option value="">Toutes catégories</option>
                {categories.map((c) => <option key={c.id} value={c.id}>{c.nom}</option>)}
              </select>
            </div>
          </div>
          <div className="flex-1 overflow-auto px-6 py-4">
            {isLoading ? <div className="flex justify-center py-16 text-muted-foreground">Chargement…</div>
              : medicaments.length === 0 ? <div className="flex flex-col items-center gap-4 py-20 text-muted-foreground"><Package className="h-12 w-12" /><p>Aucun médicament trouvé.</p></div>
              : (
                <table className="w-full border-collapse text-sm">
                  <thead>
                    <tr className="border-b border-border/70 text-muted-foreground text-left">
                      <th className="pb-2 pr-4 font-medium">Nom / DCI</th>
                      <th className="pb-2 pr-4 font-medium">Forme</th>
                      <th className="pb-2 pr-4 font-medium">Catégorie</th>
                      <th className="pb-2 pr-4 font-medium text-right">Prix public</th>
                      <th className="pb-2 pr-4 font-medium text-center">Stock</th>
                      <th className="pb-2 pr-4 font-medium text-center">Statut</th>
                      {peutEcrire() && <th className="pb-2 font-medium text-center">Actions</th>}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border/40">
                    {medicaments.map((m) => (
                      <tr key={m.id} className="hover:bg-surface/60 transition-colors">
                        <td className="py-2.5 pr-4">
                          <div className="font-medium">{m.nom}</div>
                          {(m.dci || m.denomination_commune_internationale) && <div className="text-xs text-muted-foreground">{m.dci || m.denomination_commune_internationale}</div>}
                          {m.necessite_ordonnance && <span className="text-xs text-amber-600 font-medium">Sur ordonnance</span>}
                        </td>
                        <td className="py-2.5 pr-4 text-muted-foreground">{[m.forme || m.forme_pharmaceutique, m.dosage].filter(Boolean).join(" ")}</td>
                        <td className="py-2.5 pr-4 text-muted-foreground">{m.categorie_nom ?? "—"}</td>
                        <td className="py-2.5 pr-4 text-right font-mono">{fmtFCFA(m.prix_public ?? m.prix_vente)}{m.prix_reglemente && <div className="text-xs text-blue-600">Réglementé</div>}</td>
                        <td className="py-2.5 pr-4 text-center">
                          <span className={`font-mono text-sm ${(m.stock_total_disponible ?? 0) <= (m.seuil_rupture_stock ?? 5) ? "text-destructive" : (m.stock_total_disponible ?? 0) <= (m.seuil_alerte_stock ?? 20) ? "text-warning" : "text-success"}`}>{m.stock_total_disponible ?? "—"}</span>
                        </td>
                        <td className="py-2.5 pr-4 text-center"><span className={`rounded-full px-2 py-0.5 text-xs ${m.est_actif ? "bg-success/15 text-success" : "bg-muted/60 text-muted-foreground"}`}>{m.est_actif ? "Actif" : "Inactif"}</span></td>
                        {peutEcrire() && <td className="py-2.5 text-center"><button onClick={() => setDialogMed({ open: true, item: m })} className="inline-flex h-8 w-8 items-center justify-center rounded-lg hover:bg-surface-strong"><Pencil className="h-4 w-4 text-muted-foreground" /></button></td>}
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
          </div>
        </>
      )}

      {onglet === "categories" && (
        <div className="flex-1 overflow-auto px-6 py-4">
          {peutEcrire() && <div className="mb-4 flex justify-end"><button onClick={() => setDialogCat({ open: true, item: null })} className="btn btn-primary flex items-center gap-2"><Plus className="h-4 w-4" /> Nouvelle catégorie</button></div>}
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
            {categories.map((cat) => (
              <div key={cat.id} className="rounded-xl border border-border/70 bg-surface/40 p-4">
                <div className="flex items-start justify-between">
                  <div><div className="font-medium">{cat.nom}</div>{cat.code && <div className="text-xs text-muted-foreground mt-0.5">{cat.code}</div>}{cat.description && <div className="text-xs text-muted-foreground mt-1 line-clamp-2">{cat.description}</div>}</div>
                  {peutEcrire() && <button onClick={() => setDialogCat({ open: true, item: cat })} className="h-7 w-7 flex items-center justify-center rounded-lg hover:bg-surface-strong"><Pencil className="h-3.5 w-3.5 text-muted-foreground" /></button>}
                </div>
                <div className={`mt-2 inline-block rounded-full px-2 py-0.5 text-xs ${cat.est_active ? "bg-success/10 text-success" : "bg-muted text-muted-foreground"}`}>{cat.est_active ? "Active" : "Inactive"}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {dialogMed.open && (
        <MedicamentDialog
          initial={dialogMed.item} categories={categories}
          onSave={async (data) => { if (dialogMed.item?.id) await modifierMed.mutateAsync({ id: dialogMed.item.id, data }); else await creerMed.mutateAsync(data); }}
          onClose={() => setDialogMed({ open: false })}
        />
      )}
      {dialogCat.open && (
        <CategorieDialog
          initial={dialogCat.item}
          onSave={async (data) => { if (dialogCat.item?.id) { await api.categories.modifier(dialogCat.item.id, data); qc.invalidateQueries({ queryKey: ["categories"] }); } else await creerCat.mutateAsync(data); }}
          onClose={() => setDialogCat({ open: false })}
        />
      )}
    </div>
  );
}
