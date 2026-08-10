"""
api/urls.py — Routage principal de l'API REST PharmApp.

ÉTAPES 4–10 : ajout des endpoints :
  POST /api/medicaments/import-csv/              — étape 4
  POST /api/auth/utilisateurs/{id}/suspendre/    — étape 9
  POST /api/auth/utilisateurs/{id}/deverrouiller/ — étape 9
  POST /api/ventes/{id}/avoir/                   — étape 7
  GET  /api/rapports/ventes/                     — étape 8
  GET  /api/rapports/top-produits/               — étape 8
  GET  /api/rapports/marges/                     — étape 8
  GET  /api/rapports/ecarts-inventaire/          — étape 8
  GET  /api/rapports/export-ventes/              — étape 8
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView
from api.permissions import EstTitulaire, EstPharmacienAdjoint, EstGestionnaireStock, EstCaissier

# Vues d'authentification
from gestion.authentification.vues import (
    VueConnexion,
    VueDeconnexion,
    VueProfil,
    VueUtilisateur,
)

# Vues catalogue
from gestion.catalogue.vues import (
    VueMedicament,
    VueCategorieProduit,
    VueLot,
)

# Vues clients
from gestion.clients.vues import VueClient

# Vues ventes
from gestion.ventes.vues import VueVente, VueClotureCaisse

# Vues stocks
from gestion.stocks.vues import VueStock, VueAlerteStock

# Vues ordonnances
from gestion.ordonnances.vues import VueOrdonnance

# Vues audit
from gestion.audit.vues import VueJournalAudit

# Vues synchronisation
from gestion.synchronisation.vues import VueSynchronisation, VueConflitSync

# Vues comptabilité
from gestion.comptabilite.vues import VueComptabilite

# Vues rapports
from gestion.rapports.vues import VueRapport

# Vues matériel (tiroir-caisse, imprimante ESC/POS, scanner code-barres)
from gestion.materiel.vues import (
    ouvrir_tiroir,
    imprimer_recu,
    test_imprimante,
    lire_code_barres,
)

# Vues produits contrôlés
from gestion.produits_controles.vues import VueProduitControle

# Vues fournisseurs & achats
from gestion.fournisseurs.vues import VueFournisseur, VueBonCommande, VueReception

# Vues paramétrage (Étape 3)
from gestion.parametrage.vues import VueParametrage

router = DefaultRouter()
router.register(r"medicaments",     VueMedicament,       basename="medicament")
router.register(r"categories",      VueCategorieProduit, basename="categorie")
router.register(r"lots",            VueLot,              basename="lot")
router.register(r"clients",         VueClient,           basename="client")
router.register(r"ventes",          VueVente,            basename="vente")
router.register(r"clotures",        VueClotureCaisse,    basename="cloture")
router.register(r"alertes-stock",   VueAlerteStock,      basename="alerte-stock")
router.register(r"ordonnances",     VueOrdonnance,       basename="ordonnance")
router.register(r"journal-audit",   VueJournalAudit,     basename="journal-audit")
# Alias contractuel historique : /api/audit/.
router.register(r"audit",           VueJournalAudit,     basename="audit")
router.register(r"synchronisation/conflits", VueConflitSync, basename="conflit-sync")
router.register(r"produits-controles", VueProduitControle, basename="produit-controle")
router.register(r"rapports",        VueRapport,          basename="rapport")
router.register(r"ecritures",       VueComptabilite,     basename="ecriture")
router.register(r"auth/utilisateurs", VueUtilisateur,    basename="utilisateur")
router.register(r"utilisateurs",       VueUtilisateur,    basename="utilisateur-legacy")
router.register(r"fournisseurs",    VueFournisseur,      basename="fournisseur")
router.register(r"bons-commande",   VueBonCommande,      basename="bon-commande")
router.register(r"receptions",      VueReception,        basename="reception")
# Alias domaine : les réceptions sont aussi exposées sous /fournisseurs/receptions/
router.register(r"fournisseurs/receptions", VueReception,   basename="fournisseur-reception")

# ── Alias de routage canoniques (contrat documenté) ───────────────────────────
# Les mêmes ViewSets sont exposés sous leur espace de noms métier, en plus des
# routes historiques ci-dessus, afin que le contrat "/api/v1/<domaine>/<res>/"
# soit respecté sans casser le poste client existant.
router.register(r"catalogue/medicaments", VueMedicament,       basename="catalogue-medicament")
router.register(r"catalogue/categories",  VueCategorieProduit, basename="catalogue-categorie")
router.register(r"catalogue/lots",        VueLot,              basename="catalogue-lot")
router.register(r"stocks/alertes",        VueAlerteStock,      basename="alerte-stock-domaine")
router.register(r"stocks",                VueStock,            basename="stock")
router.register(r"audit/journal",         VueJournalAudit,     basename="audit-journal")
router.register(r"comptabilite",          VueComptabilite,     basename="comptabilite")

_api_patterns = [
    # Authentification
    path("auth/connexion/",             VueConnexion.as_view(),        name="connexion"),
    path("auth/deconnexion/",           VueDeconnexion.as_view(),      name="deconnexion"),
    path("auth/profil/",                VueProfil.as_view(),           name="profil"),
    path("auth/token/rafraichir/",      TokenRefreshView.as_view(),    name="token-rafraichir"),
    path("auth/token/refresh/",         TokenRefreshView.as_view(),    name="token-refresh"),

    # Stock — actions spéciales (Étapes 1 & 2)
    path("stocks/ajuster/",             VueStock.as_view({"post": "ajuster"}),              name="stock-ajuster"),
    # Alias domaine : /stocks/ajustements/ (nom au pluriel employé par le poste
    # client et les scénarios de recette) pointe sur la même action.
    path("stocks/ajustements/",         VueStock.as_view({"post": "ajuster"}),              name="stock-ajustements"),
    path("stocks/besoins-reappro/",     VueStock.as_view({"get": "besoins_reappro"}),       name="stock-besoins-reappro"),
    path("stocks/inventaires/",         VueStock.as_view({"get": "list", "post": "demarrer_inventaire"}), name="inventaire-list"),
    path("stocks/mouvements/",          VueStock.as_view({"get": "mouvements"}),            name="stock-mouvements"),

    # Rapports : AUCUNE route manuelle ici. VueRapport est enregistré dans le
    # router DRF, qui génère lui-même /rapports/<action>/ EN CONSERVANT les
    # `permission_classes` déclarées sur chaque @action (elles transitent par
    # les initkwargs du router). Un `as_view({"get": "..."})` écrit à la main
    # les perd et applique la permission de la classe — c'est ainsi que
    # /rapports/tableau-bord/ exigeait un pharmacien adjoint et que
    # /rapports/marges/ s'ouvrait à des rôles non titulaires.

    # Matériel local (poste client) — les permissions sont portées par les vues.
    path("materiel/tiroir/",            ouvrir_tiroir,                                      name="materiel-tiroir"),
    path("materiel/imprimer-recu/",     imprimer_recu,                                      name="materiel-imprimer-recu"),
    path("materiel/test-imprimante/",   test_imprimante,                                    name="materiel-test-imprimante"),
    path("materiel/scanner/",           lire_code_barres,                                   name="materiel-scanner"),

    # Paramétrage — singleton (Étape 3)
    path("parametrage/",                VueParametrage.as_view(),                           name="parametrage"),

    # Synchronisation — actions spéciales
    path("synchronisation/etat/",       VueSynchronisation.as_view({"get": "etat"}),        name="sync-etat"),
    path("synchronisation/statut/",     VueSynchronisation.as_view({"get": "etat"}),        name="sync-statut"),
    path("synchronisation/rejouer-echecs/", VueSynchronisation.as_view({"post": "rejouer"}, permission_classes=[EstTitulaire]), name="sync-rejouer"),
    path("synchronisation/rejouer/", VueSynchronisation.as_view({"post": "rejouer"}, permission_classes=[EstTitulaire]), name="sync-rejouer-legacy"),

    # Router DRF
    path("", include(router.urls)),
]

# DT-003 (corrigé) : `pharmapp/urls.py` inclut déjà ce module sous le préfixe
# "api/" (`path("api/", include("api.urls"))`). Re-préfixer ici produisait des
# routes effectives en double : "/api/api/...". Les URL exposées ici sont donc
# relatives à la racine de ce module (déjà "api/"), sans second préfixe.
urlpatterns = _api_patterns
