/**
 * Types partagés — miroir fidèle des DTO exposés par l'API Django.
 */

export type UUID = string;

export type ModePaiement =
  | "especes"
  | "mobile_money"
  | "assurance"
  | "credit"
  | "cheque";

export type StatutVente = "en_cours" | "validee" | "annulee" | "avoir";

export type TypeImprimante = "thermique" | "a4";

export type RoleUtilisateur =
  | "stagiaire"
  | "caissier"
  | "assistant"
  | "gestionnaire_stock"
  | "pharmacien_adjoint"
  | "titulaire"
  | "administrateur";

export type StatutBonCommande =
  | "brouillon"
  | "envoye"
  | "partiel"
  | "recu"
  | "cloture"
  | "annule";

// ── Pagination ────────────────────────────────────────────────────────────────

export interface Page<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

// ── Catalogue ────────────────────────────────────────────────────────────────

export interface CategorieProduit {
  id: UUID;
  nom: string;
  description?: string;
  code?: string;
  est_active: boolean;
  cree_le?: string;
}

export interface Medicament {
  id: UUID;
  code?: string;
  code_cis?: string;
  code_barre?: string;
  nom: string;
  dci?: string | null;
  forme?: string | null;
  denomination_commune_internationale?: string | null;
  forme_pharmaceutique?: string | null;
  dosage?: string | null;
  conditionnement?: string | null;
  fabricant?: string | null;
  prix_vente: string;
  prix_public?: string;
  prix_min_autorise?: string;
  prix_max_autorise?: string;
  taux_remise_max?: string;
  prix_reglemente?: boolean;
  prix_reference?: string | null;
  hors_nomenclature?: boolean;
  categorie?: UUID | null;
  categorie_nom?: string | null;
  necessite_ordonnance?: boolean;
  necessite_tracabilite_lot?: boolean;
  /** Étape 13 */
  est_produit_controle?: boolean;
  seuil_alerte_stock?: number;
  seuil_rupture_stock?: number;
  stock_total?: number;
  stock_total_disponible?: number;
  est_en_alerte_stock?: boolean;
  est_actif?: boolean;
  cree_le?: string;
  modifie_le?: string;
}

export interface Lot {
  id: UUID;
  medicament: UUID;
  numero_lot: string;
  date_peremption: string;
  quantite_disponible: number;
  prix_achat_unitaire?: string;
}

export interface LotDetail extends Lot {
  medicament_nom: string;
  quantite_initiale?: number;
  emplacement_stockage?: string;
  est_actif: boolean;
  est_perime: boolean;
  cree_le: string;
}

// ── Ventes ────────────────────────────────────────────────────────────────────

export interface LigneVente {
  id?: UUID;
  medicament: UUID;
  medicament_nom?: string;
  lot?: UUID | null;
  quantite: number;
  prix_unitaire: string;
  taux_remise?: string;
  prix_unitaire_apres_remise?: string;
  montant_total: string;
}

export interface Vente {
  id: UUID;
  numero: string;
  statut: StatutVente;
  mode_paiement: ModePaiement;
  montant_total: string;
  montant_encaisse: string;
  montant_rendu: string;
  montant_assurance?: string;
  sous_total?: string;
  montant_remise?: string;
  vendeur: UUID;
  vendeur_nom?: string;
  client?: UUID | null;
  client_nom?: string | null;
  ordonnance?: UUID | null;
  /** Étape 14 — référence à la vente d'origine pour les avoirs */
  vente_origine?: UUID | null;
  /** Étape 11 */
  reference_mobile_money?: string;
  annule_le?: string | null;
  motif_annulation?: string;
  notes?: string;
  cree_le: string;
  lignes?: LigneVente[];
}

export interface ClotureCaisse {
  id: UUID;
  date_cloture: string;
  statut: "en_cours" | "cloturee" | "validee";
  caissier: UUID;
  caissier_nom?: string;
  chiffre_affaires: string;
  recettes_especes: string;
  recettes_mobile_money: string;
  recettes_assurance: string;
  recettes_credit: string;
  recettes_cheque: string;
  nombre_ventes: number;
  nombre_annulations: number;
  ecart_caisse: string;
  notes?: string;
  cree_le?: string;
}

export interface RecuDTO {
  id: UUID;
  numero: string;
  pharmacie: {
    nom: string;
    adresse?: string;
    telephone?: string;
    numero_agrement?: string;
  };
  vendeur_nom: string;
  client_nom?: string;
  date: string;
  mode_paiement: ModePaiement;
  lignes: Array<{
    nom: string;
    quantite: number;
    prix_unitaire: number;
    taux_remise: number;
    montant_total: number;
  }>;
  montant_total: number;
  montant_encaisse: number;
  montant_rendu: number;
  nb_impressions: number;
  reimprime: boolean;
  /** Étape 14 */
  est_avoir?: boolean;
  vente_origine_numero?: string | null;
}

// ── Clients ───────────────────────────────────────────────────────────────────

export interface Client {
  id: UUID;
  nom: string;
  prenom: string;
  nom_complet: string;
  telephone?: string | null;
  email?: string;
  date_naissance?: string | null;
  adresse?: string;
  type_client: "particulier" | "assurance" | "institution";
  assureur?: string;
  numero_assurance?: string | null;
  taux_prise_en_charge: string;
  credit_autorise: boolean;
  plafond_credit: string;
  encours_credit: string;
  /** Visible uniquement pharmacien_adjoint+ (§7.2 CDC, masqué côté serveur) */
  allergies?: string;
  est_actif: boolean;
  est_anonymise: boolean;
  notes?: string;
  cree_le: string;
  modifie_le?: string;
}

// ── Registre produits contrôlés (Étape 13) ───────────────────────────────────

export interface RegistreProduitControle {
  id: UUID;
  medicament: UUID;
  medicament_nom?: string;
  lot: UUID;
  numero_lot_fabricant: string;
  type_mouvement:
    | "entree"
    | "sortie_vente"
    | "retour"
    | "mise_au_rebut"
    | "controle_autorite";
  type_mouvement_display?: string;
  quantite_mouvement: number;
  unite: string;
  stock_avant: number;
  stock_apres: number;
  ordonnance?: UUID | null;
  ordonnance_numero?: string | null;
  prescripteur_nom?: string;
  prescripteur_num_ordre?: string;
  /** Nom patient décryptré (retourné si l'utilisateur a les droits) */
  patient_nom?: string;
  effectue_par: UUID;
  effectue_par_nom?: string;
  supervise_par?: UUID | null;
  motif?: string;
  cree_le: string;
}

// ── Synchronisation (Étape 15) ────────────────────────────────────────────────

export interface EtatSync {
  est_connecte?: boolean;
  nb_en_attente: number;
  nb_en_echec: number;
  derniere_synchro_reussie: string | null;
  /** @alias derniere_synchro_reussie */
  derniere_sync_reussie?: string | null;
  /** Étape 15 — ping Supabase */
  supabase_accessible: boolean;
  conflits_non_resolus: number;
  /** Additional fields used by tableau-bord sync panel */
  statut_connexion?: string;
  nombre_evenements_en_attente?: number;
  nombre_evenements_en_echec?: number;
}

// ── Alertes stock ─────────────────────────────────────────────────────────────

export interface AlerteStock {
  id: UUID;
  medicament: UUID;
  medicament_nom?: string;
  lot?: UUID | null;
  lot_numero?: string | null;
  type_alerte: string;
  niveau?: "alerte" | "rupture";
  seuil?: number;
  seuil_depasse?: number;
  stock_actuel?: number;
  stock_au_moment_alerte?: number;
  date_peremption?: string | null;
  est_resolue: boolean;
  cree_le: string;
}

// ── Utilisateurs ─────────────────────────────────────────────────────────────

export interface Utilisateur {
  id: UUID;
  email: string;
  prenom: string;
  nom: string;
  nom_complet: string;
  role: string;
  role_display?: string;
  telephone?: string;
  numero_ordre?: string;
  est_actif: boolean;
  est_verrouille?: boolean;
  tentatives_connexion_echouees?: number;
  derniere_connexion_reussie?: string | null;
  cree_le?: string;
}

// ── Ordonnances ────────────────────────────────────────────────────────────────

export interface Ordonnance {
  id: UUID;
  numero_interne: string;
  client?: UUID | null;
  client_nom?: string | null;
  prescripteur_nom?: string;
  prescripteur_etablissement?: string;
  date_prescription?: string;
  fichier?: string | null;
  statut?: string;
  notes?: string;
  cree_le?: string;
}

// ── Rapports ──────────────────────────────────────────────────────────────────

export interface RapportVentes {
  total_ventes: number;
  chiffre_affaires: string;
  panier_moyen: string;
  ventes_par_mode: Record<ModePaiement, string>;
  ventes_par_jour: Array<{ date: string; total: string; count: number }>;
  /** Alternative field names returned by some API versions */
  ca_total?: string;
  nb_ventes?: number;
  remises_total?: string;
  top_produits?: TopProduit[];
  repartition_paiement?: Record<string, string | number>;
}

export interface TopProduit {
  medicament_id?: UUID;
  medicament_nom?: string;
  /** Django ORM aggregation style field names */
  medicament__nom?: string;
  medicament__denomination_commune_internationale?: string;
  quantite_totale: number;
  chiffre_affaires?: string;
  /** Alternative CA fields returned by different API endpoints */
  ca?: string;
  ca_total?: string;
}

export interface MargeProduit {
  medicament_id?: UUID;
  medicament_nom: string;
  cout_moyen?: string;
  prix_vente?: string;
  marge?: string;
  taux_marge?: string;
  /** Additional fields used by the rapports route */
  quantite_totale?: number;
  ca_total?: string;
  pa_moyen?: string;
  marge_brute?: string;
  taux_marge_pct?: string;
}

export interface TableauBord {
  ventes_jour: number;
  ca_jour: string;
  alertes_stock: number;
  /** @alias alertes_stock */
  nb_alertes_stock?: number;
  nb_ruptures?: number;
  nb_peremptions_proches?: number;
  seuil_peremption_jours?: number;
  /** @alias ca_jour — some API responses use this key */
  ca_aujourd_hui?: string;
  /** @alias ventes_jour */
  nb_ventes_aujourd_hui?: number;
  clients_en_attente?: number;
  top_produits?: TopProduit[];
  derniere_synchro?: string | null;
  supabase_accessible?: boolean;
}

// ── Paramétrage ────────────────────────────────────────────────────────────────

export interface Parametrage {
  id: UUID;
  nom_pharmacie: string;
  adresse?: string;
  telephone?: string;
  email?: string;
  ville?: string;
  numero_agrement?: string;
  devise?: string;
  format_numerotation?: string;
  type_imprimante?: TypeImprimante;
  logo?: string | null;
  inactivite_timeout_minutes?: number;
  /** Seuil d'alerte de stock bas (en jours d'approvisionnement) */
  seuil_alerte_stock_jours?: number;
  /** Seuil de péremption proche (en jours) */
  seuil_peremption_jours?: number;
  /** Timeout d'inactivité en minutes */
  timeout_inactivite_minutes?: number;
  /** Nombre max de tentatives de connexion avant verrouillage */
  nb_tentatives_connexion_max?: number;
  cree_le?: string;
  modifie_le?: string;
}

// ── Fournisseurs / Bons de commande ──────────────────────────────────────────

export interface Fournisseur {
  id: UUID;
  nom: string;
  code?: string;
  contact_principal?: string;
  telephone?: string;
  email?: string;
  adresse?: string;
  ville?: string;
  pays?: string;
  numero_agrement?: string;
  delai_livraison_jours?: number;
  conditions_paiement?: string;
  est_actif: boolean;
  /** @alias est_actif — some API responses use this shorter key */
  actif?: boolean;
  notes?: string;
  cree_le?: string;
}

export interface LigneBonCommande {
  id?: UUID;
  medicament: UUID;
  medicament_nom?: string;
  quantite: number;
  quantite_commandee?: number;
  quantite_recue?: number;
  quantite_restante?: number;
  prix_unitaire?: string;
  prix_unitaire_ht?: string;
  montant_total?: string;
}

export interface BonCommande {
  id: UUID;
  numero: string;
  fournisseur: UUID;
  fournisseur_nom?: string;
  statut: StatutBonCommande;
  date_commande: string;
  date_livraison_prevue?: string;
  montant_total: string;
  total_ht?: string;
  total_tva?: string;
  total_ttc?: string;
  lignes?: LigneBonCommande[];
  notes?: string;
  cree_le?: string;
}

// ── Stocks ────────────────────────────────────────────────────────────────────

export interface MouvementStock {
  id: UUID;
  lot: UUID;
  lot_nom?: string;
  medicament_nom?: string;
  type_mouvement: string;
  type_mouvement_libelle?: string;
  quantite: number;
  quantite_avant: number;
  quantite_apres: number;
  motif?: string;
  reference_document?: string;
  effectue_par?: UUID;
  cree_le: string;
}
