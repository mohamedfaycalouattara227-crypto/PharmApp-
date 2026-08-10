/**
 * Paramétrage de la pharmacie (§3.1 du cahier des charges).
 *
 * Quatre sections :
 *   1. Identité officine  — nom, adresse, téléphone, email, agrément
 *   2. Alertes & seuils  — seuil stock bas, jours avant péremption
 *   3. Impression         — type d'imprimante, format de numérotation
 *   4. Sécurité           — timeout inactivité, tentatives connexion max
 *
 * Accès en lecture : tout utilisateur authentifié.
 * Modification (PATCH) : réservée au titulaire (EstTitulaire backend).
 */

import { createFileRoute } from "@tanstack/react-router";
import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Building2, Bell, Printer, Shield, Save, Loader2, CheckCircle2,
} from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Separator } from "@/components/ui/separator";
import { api } from "@/lib/api-client";
import { cn } from "@/lib/utils";
import type { Parametrage, TypeImprimante } from "@/lib/types";

export const Route = createFileRoute("/_app/parametres")({
  component: PageParametres,
  head: () => ({
    meta: [
      { title: "Paramétrage — PharmApp" },
      { name: "description", content: "Configuration de la pharmacie : identité, alertes, impression, sécurité." },
    ],
  }),
});

type Section = "identite" | "alertes" | "impression" | "securite";

const SECTIONS: { id: Section; label: string; icon: React.ReactNode }[] = [
  { id: "identite",   label: "Identité officine",   icon: <Building2 className="h-4 w-4" /> },
  { id: "alertes",    label: "Alertes & seuils",     icon: <Bell className="h-4 w-4" /> },
  { id: "impression", label: "Impression",           icon: <Printer className="h-4 w-4" /> },
  { id: "securite",   label: "Sécurité",             icon: <Shield className="h-4 w-4" /> },
];

function PageParametres() {
  const qc = useQueryClient();
  const [section, setSection] = useState<Section>("identite");
  const [form, setForm]       = useState<Partial<Parametrage>>({});
  const [modifie, setModifie] = useState(false);

  // ── Chargement ────────────────────────────────────────────────────────────
  const { data: parametrage, isLoading } = useQuery<Parametrage>({
    queryKey: ["parametrage"],
    queryFn: () => api.parametrage.get(),
  });

  // Initialiser le formulaire dès que les données arrivent
  useEffect(() => {
    if (parametrage) {
      setForm(parametrage);
      setModifie(false);
    }
  }, [parametrage]);

  // ── Helpers ───────────────────────────────────────────────────────────────
  const set = <K extends keyof Parametrage>(key: K, value: Parametrage[K]) => {
    setForm((prev) => ({ ...prev, [key]: value }));
    setModifie(true);
  };

  // ── Sauvegarde ────────────────────────────────────────────────────────────
  const sauvegarder = useMutation({
    mutationFn: () => api.parametrage.modifier(form),
    onSuccess: (data) => {
      toast.success("Paramétrage sauvegardé.");
      setForm(data);
      setModifie(false);
      void qc.invalidateQueries({ queryKey: ["parametrage"] });
    },
    onError: (e) => toast.error("Sauvegarde échouée", { description: String(e) }),
  });

  if (isLoading) {
    return (
      <div className="flex h-screen items-center justify-center gap-2 text-muted-foreground">
        <Loader2 className="h-5 w-5 animate-spin" />
        Chargement du paramétrage…
      </div>
    );
  }

  return (
    <div className="flex h-screen flex-col overflow-hidden">
      {/* ── En-tête ────────────────────────────────────────────────────── */}
      <header className="flex items-center justify-between border-b border-border/70 bg-surface/60 px-6 py-4 backdrop-blur shrink-0">
        <div>
          <h1 className="font-display text-3xl leading-none">Paramétrage</h1>
          <p className="text-xs text-muted-foreground mt-1">
            Configuration générale de la pharmacie — réservé au titulaire.
          </p>
        </div>
        <Button
          onClick={() => sauvegarder.mutate()}
          disabled={!modifie || sauvegarder.isPending}
          className="bg-primary text-primary-foreground"
        >
          {sauvegarder.isPending
            ? <Loader2 className="h-4 w-4 animate-spin" />
            : <Save className="h-4 w-4" />}
          {modifie ? "Enregistrer les modifications" : "Enregistré"}
        </Button>
      </header>

      <div className="flex flex-1 min-h-0 overflow-hidden">
        {/* ── Sidebar de navigation ───────────────────────────────────── */}
        <nav className="w-56 border-r border-border/70 bg-surface/40 p-4 space-y-1 shrink-0">
          {SECTIONS.map((s) => (
            <button
              key={s.id}
              onClick={() => setSection(s.id)}
              className={cn(
                "w-full flex items-center gap-2.5 rounded-md px-3 py-2 text-sm font-medium text-left transition-colors",
                section === s.id
                  ? "bg-primary/10 text-primary"
                  : "text-muted-foreground hover:bg-surface-strong hover:text-foreground",
              )}
            >
              {s.icon}
              {s.label}
            </button>
          ))}

          {modifie && (
            <div className="mt-4 pt-4 border-t border-border/60 text-xs text-warning flex items-center gap-1.5">
              <div className="h-1.5 w-1.5 rounded-full bg-warning" />
              Modifications non sauvegardées
            </div>
          )}
        </nav>

        {/* ── Contenu de la section active ────────────────────────────── */}
        <div className="flex-1 overflow-y-auto p-8">
          {section === "identite"   && <SectionIdentite   form={form} set={set} />}
          {section === "alertes"    && <SectionAlertes    form={form} set={set} />}
          {section === "impression" && <SectionImpression form={form} set={set} />}
          {section === "securite"   && <SectionSecurite   form={form} set={set} />}
        </div>
      </div>
    </div>
  );
}

// ── Section 1 — Identité officine ─────────────────────────────────────────────

function SectionIdentite({
  form, set,
}: {
  form: Partial<Parametrage>;
  set: <K extends keyof Parametrage>(key: K, val: Parametrage[K]) => void;
}) {
  return (
    <div className="max-w-xl space-y-6">
      <div>
        <h2 className="font-display text-2xl mb-1">Identité officine</h2>
        <p className="text-sm text-muted-foreground">
          Ces informations apparaissent sur les reçus et documents officiels.
        </p>
      </div>
      <Separator />

      <Champ label="Nom de la pharmacie" required>
        <Input
          value={form.nom_pharmacie ?? ""}
          onChange={(e) => set("nom_pharmacie", e.target.value)}
          placeholder="Pharmacie du Centre"
        />
      </Champ>

      <Champ label="Adresse complète">
        <Textarea
          value={form.adresse ?? ""}
          onChange={(e) => set("adresse", e.target.value)}
          placeholder="Rue, quartier, secteur…"
          className="min-h-[80px]"
        />
      </Champ>

      <div className="grid grid-cols-2 gap-4">
        <Champ label="Ville">
          <Input
            value={form.ville ?? ""}
            onChange={(e) => set("ville", e.target.value)}
            placeholder="Bobo-Dioulasso"
          />
        </Champ>
        <Champ label="Téléphone">
          <Input
            value={form.telephone ?? ""}
            onChange={(e) => set("telephone", e.target.value)}
            placeholder="+226 00 00 00 00"
          />
        </Champ>
      </div>

      <Champ label="Adresse e-mail">
        <Input
          type="email"
          value={form.email ?? ""}
          onChange={(e) => set("email", e.target.value)}
          placeholder="pharmacie@exemple.bf"
        />
      </Champ>

      <Champ label="Numéro d'agrément ANRP">
        <Input
          value={form.numero_agrement ?? ""}
          onChange={(e) => set("numero_agrement", e.target.value)}
          placeholder="PHR-XXXX-YYYY"
          className="font-mono"
        />
      </Champ>

      <Champ label="Devise">
        <Input
          value={form.devise ?? "FCFA"}
          onChange={(e) => set("devise", e.target.value)}
          placeholder="FCFA"
          className="max-w-[160px]"
        />
      </Champ>
    </div>
  );
}

// ── Section 2 — Alertes & seuils ──────────────────────────────────────────────

function SectionAlertes({
  form, set,
}: {
  form: Partial<Parametrage>;
  set: <K extends keyof Parametrage>(key: K, val: Parametrage[K]) => void;
}) {
  return (
    <div className="max-w-xl space-y-6">
      <div>
        <h2 className="font-display text-2xl mb-1">Alertes & seuils</h2>
        <p className="text-sm text-muted-foreground">
          Seuils déclenchant les alertes automatiques du tableau de bord.
        </p>
      </div>
      <Separator />

      <Champ
        label="Seuil stock bas (unités)"
        aide="Une alerte est créée quand le stock total d'un médicament passe sous ce nombre."
      >
        <Input
          type="number" min={0}
          className="numeric max-w-[200px]"
          value={form.seuil_alerte_stock_jours ?? 20}
          onChange={(e) => set("seuil_alerte_stock_jours", parseInt(e.target.value, 10))}
        />
      </Champ>

      <Champ
        label="Alerte péremption (jours)"
        aide="Un lot est signalé comme « proche de la péremption » quand il expire dans ce délai."
      >
        <Input
          type="number" min={1}
          className="numeric max-w-[200px]"
          value={form.seuil_peremption_jours ?? 60}
          onChange={(e) => set("seuil_peremption_jours", parseInt(e.target.value, 10))}
        />
      </Champ>

      <div className="rounded-lg border border-info/30 bg-info/5 p-4 text-sm text-info">
        <strong>À noter :</strong> les alertes de rupture (stock = 0) sont toujours actives,
        indépendamment de ce seuil.
      </div>
    </div>
  );
}

// ── Section 3 — Impression ────────────────────────────────────────────────────

function SectionImpression({
  form, set,
}: {
  form: Partial<Parametrage>;
  set: <K extends keyof Parametrage>(key: K, val: Parametrage[K]) => void;
}) {
  return (
    <div className="max-w-xl space-y-6">
      <div>
        <h2 className="font-display text-2xl mb-1">Impression</h2>
        <p className="text-sm text-muted-foreground">
          Format des reçus et modèle de numérotation des documents.
        </p>
      </div>
      <Separator />

      <Champ label="Type d'imprimante">
        <div className="mt-2 flex gap-3">
          {(["thermique", "a4"] as TypeImprimante[]).map((t) => (
            <label
              key={t}
              className={cn(
                "flex flex-1 flex-col items-center gap-2 rounded-lg border-2 p-4 cursor-pointer transition-colors",
                form.type_imprimante === t
                  ? "border-primary bg-primary/5"
                  : "border-border hover:border-border/80",
              )}
            >
              <input
                type="radio"
                name="type_imprimante"
                value={t}
                checked={form.type_imprimante === t}
                onChange={() => set("type_imprimante", t)}
                className="sr-only"
              />
              <Printer className="h-6 w-6 text-muted-foreground" />
              <span className="text-sm font-medium">
                {t === "thermique" ? "Thermique 80 mm" : "Feuille A4"}
              </span>
              <span className="text-xs text-muted-foreground text-center">
                {t === "thermique"
                  ? "Imprimante de caisse standard"
                  : "Imprimante bureau ou laser"}
              </span>
            </label>
          ))}
        </div>
      </Champ>

      <Champ
        label="Format de numérotation"
        aide="Variables : {YYYY} = année, {MM} = mois, {DD} = jour, {NNNN} = séquence."
      >
        <Input
          className="font-mono"
          value={form.format_numerotation ?? "VTE-{YYYY}-{NNNN}"}
          onChange={(e) => set("format_numerotation", e.target.value)}
          placeholder="VTE-{YYYY}-{NNNN}"
        />
        <p className="text-xs text-muted-foreground mt-1">
          Aperçu : VTE-{new Date().getFullYear()}-0001
        </p>
      </Champ>
    </div>
  );
}

// ── Section 4 — Sécurité ─────────────────────────────────────────────────────

function SectionSecurite({
  form, set,
}: {
  form: Partial<Parametrage>;
  set: <K extends keyof Parametrage>(key: K, val: Parametrage[K]) => void;
}) {
  return (
    <div className="max-w-xl space-y-6">
      <div>
        <h2 className="font-display text-2xl mb-1">Sécurité</h2>
        <p className="text-sm text-muted-foreground">
          Paramètres de verrouillage et de session (§9.1 CDC).
        </p>
      </div>
      <Separator />

      <Champ
        label="Délai d'inactivité avant verrouillage (minutes)"
        aide="L'écran se verrouille automatiquement après cette durée sans interaction."
      >
        <Input
          type="number" min={1} max={480}
          className="numeric max-w-[200px]"
          value={form.timeout_inactivite_minutes ?? 30}
          onChange={(e) => set("timeout_inactivite_minutes", parseInt(e.target.value, 10))}
        />
      </Champ>

      <Champ
        label="Tentatives de connexion maximum"
        aide="Le compte est temporairement bloqué après ce nombre d'échecs consécutifs."
      >
        <Input
          type="number" min={1} max={20}
          className="numeric max-w-[200px]"
          value={form.nb_tentatives_connexion_max ?? 5}
          onChange={(e) => set("nb_tentatives_connexion_max", parseInt(e.target.value, 10))}
        />
      </Champ>

      <div className="rounded-lg border border-warning/30 bg-warning/5 p-4 text-sm">
        <p className="font-medium text-warning mb-1">Bonnes pratiques recommandées</p>
        <ul className="text-muted-foreground space-y-1 list-disc list-inside text-xs">
          <li>Délai d'inactivité : 15–30 min pour les caisses, 60 min pour les bureaux.</li>
          <li>Max tentatives : 5 est la valeur recommandée par les référentiels RGPD santé.</li>
          <li>Chaque opération sensible est traçable dans le journal d'audit.</li>
        </ul>
      </div>
    </div>
  );
}

// ── Composant champ de formulaire ─────────────────────────────────────────────

function Champ({
  label, aide, required, children,
}: {
  label: string;
  aide?: string;
  required?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-1.5">
      <Label className="font-medium">
        {label}
        {required && <span className="text-destructive ml-1">*</span>}
      </Label>
      {children}
      {aide && <p className="text-xs text-muted-foreground leading-relaxed">{aide}</p>}
    </div>
  );
}
