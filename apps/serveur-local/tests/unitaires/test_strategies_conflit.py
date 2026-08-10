"""
Tests des stratégies de résolution de conflits (§2.5 du cahier des charges).
"""

from datetime import datetime, timezone as dt_tz

import pytest

from gestion.synchronisation.strategies import (
    DecisionConflit,
    StrategieCatalogue,
    StrategieClients,
    StrategieStockAdditif,
    StrategieUtilisateurs,
    StrategieVentesImmuable,
    obtenir_strategie,
)


# ─── Ventes ──────────────────────────────────────────────────────────────────


def test_vente_local_autoritaire():
    """§2.5 CdC : la caisse locale est source de vérité — CONSERVER_LOCAL par défaut."""
    strat = StrategieVentesImmuable()
    r = strat.resoudre(
        donnees_locales={"statut": "validee", "montant_total": "1000"},
        donnees_cloud={"statut": "validee", "montant_total": "1500"},
    )
    assert r.decision is DecisionConflit.CONSERVER_LOCAL
    assert r.payload_final["montant_total"] == "1000"


def test_vente_annulation_cloud_declenche_alerte():
    strat = StrategieVentesImmuable()
    r = strat.resoudre(
        donnees_locales={"statut": "validee"},
        donnees_cloud={"statut": "annulee"},
    )
    assert r.decision is DecisionConflit.APPLIQUER_CLOUD
    assert r.alerte_titulaire is True


# ─── Stock ──────────────────────────────────────────────────────────────────


def test_stock_fusion_additive():
    strat = StrategieStockAdditif()
    r = strat.resoudre(
        donnees_locales={"delta_depuis_sync": -5},   # 5 vendues localement
        donnees_cloud={"delta_depuis_sync": -3},     # 3 vendues sur autre poste
        contexte={"quantite_base_commune": 20},
    )
    assert r.decision is DecisionConflit.FUSIONNER
    assert r.payload_final["quantite_disponible"] == 12


def test_stock_sur_consommation_escalade():
    strat = StrategieStockAdditif()
    r = strat.resoudre(
        donnees_locales={"delta_depuis_sync": -8},
        donnees_cloud={"delta_depuis_sync": -5},
        contexte={"quantite_base_commune": 10},
    )
    assert r.decision is DecisionConflit.ESCALADER
    assert r.alerte_titulaire is True


# ─── Catalogue ──────────────────────────────────────────────────────────────


def test_catalogue_lww_local_plus_recent():
    strat = StrategieCatalogue()
    r = strat.resoudre(
        donnees_locales={"prix_vente": "500", "modifie_le": "2026-07-19T10:00:00Z"},
        donnees_cloud={"prix_vente": "450", "modifie_le": "2026-07-18T09:00:00Z"},
    )
    assert r.decision is DecisionConflit.CONSERVER_LOCAL
    assert r.payload_final["prix_vente"] == "500"


def test_catalogue_lww_cloud_gagne_par_defaut():
    strat = StrategieCatalogue()
    r = strat.resoudre(
        donnees_locales={"prix_vente": "500"},
        donnees_cloud={"prix_vente": "450", "modifie_le": "2026-07-19T10:00:00Z"},
    )
    assert r.decision is DecisionConflit.APPLIQUER_CLOUD


# ─── Clients ────────────────────────────────────────────────────────────────


def test_clients_fusion_champ_par_champ():
    strat = StrategieClients()
    r = strat.resoudre(
        donnees_locales={"nom": "Kaboré", "telephone": "70000000", "email": ""},
        donnees_cloud={"nom": "Kaboré", "telephone": "70111111", "email": "k@x.bf"},
    )
    assert r.decision is DecisionConflit.FUSIONNER
    assert r.payload_final["email"] == "k@x.bf"       # vide local → cloud
    assert r.payload_final["telephone"] == "70000000" # divergent → local
    assert "telephone" in r.champs_divergents
    assert r.alerte_titulaire is True                 # champ sensible


# ─── Utilisateurs ───────────────────────────────────────────────────────────


def test_utilisateurs_local_autoritaire():
    """§2.5 CdC : local prévaut pour les utilisateurs/rôles — CONSERVER_LOCAL."""
    strat = StrategieUtilisateurs()
    r = strat.resoudre(
        donnees_locales={"role": "caissier"},
        donnees_cloud={"role": "pharmacien_adjoint"},
    )
    assert r.decision is DecisionConflit.CONSERVER_LOCAL


def test_utilisateurs_retrogradation_escalade():
    strat = StrategieUtilisateurs()
    r = strat.resoudre(
        donnees_locales={"role": "titulaire"},
        donnees_cloud={"role": "caissier"},
    )
    assert r.decision is DecisionConflit.ESCALADER
    assert r.alerte_titulaire is True


# ─── Registre ───────────────────────────────────────────────────────────────


def test_registre_mappe_les_types_documentes():
    assert obtenir_strategie("ventes.vente").nom == "ventes_immuable"
    assert obtenir_strategie("catalogue.lot").nom == "stock_additif"
    assert obtenir_strategie("catalogue.medicament").nom == "catalogue_lww"
    assert obtenir_strategie("clients.client").nom == "clients_merge_champ"


def test_registre_leve_pour_type_inconnu():
    with pytest.raises(LookupError):
        obtenir_strategie("inconnu.entite")
