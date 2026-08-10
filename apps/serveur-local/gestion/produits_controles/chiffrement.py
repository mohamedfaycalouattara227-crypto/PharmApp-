"""
gestion/produits_controles/chiffrement.py

Chiffrement AES-256-GCM des données patient sensibles inscrites au
registre réglementaire des stupéfiants et psychotropes.

Cohérence de traitement des données de santé :
    - Les images d'ordonnances (module ``ordonnances``) sont chiffrées
      AES-256-GCM (voir ``gestion.ordonnances.services``).
    - Le nom patient inscrit au registre stupéfiants est **la même
      catégorie de donnée** (identité rattachée à une prescription).
      Il est donc chiffré avec le même algorithme, la même clé maîtresse
      (``settings.ORDONNANCE_ENCRYPTION_KEY``), et un AAD dédié
      (``pc-patient``) évitant toute substitution transverse avec un
      blob d'image d'ordonnance.

Format du champ ``patient_nom_chiffre`` en base :

    base64_urlsafe( nonce_12o || ciphertext_avec_tag_16o )

Une valeur vide (chaîne vide) est autorisée : le registre n'exige pas
systématiquement l'identité (par ex. délivrance à une structure
hospitalière). Dans ce cas, le champ chiffré reste vide et
``patient_nom`` retourne "".
"""
from __future__ import annotations

import base64
import logging

from gestion.ordonnances.services import (
    ServiceChiffrementOrdonnance,
    OrdonnanceChiffrementInvalide,
)

logger = logging.getLogger("pharmapp.securite")

# AAD dédié au registre produits contrôlés — empêche qu'un blob issu
# d'une ordonnance soit interprété comme un nom patient (et inversement).
AAD_PATIENT_REGISTRE = b"pc-patient-v1"


def chiffrer_nom_patient(clair: str) -> str:
    """Chiffre un nom patient et retourne un blob base64 urlsafe.

    Retourne "" si ``clair`` est vide.
    """
    if not clair:
        return ""
    service = ServiceChiffrementOrdonnance()
    nonce, ct = service.chiffrer(clair.encode("utf-8"), associe=AAD_PATIENT_REGISTRE)
    return base64.urlsafe_b64encode(nonce + ct).decode("ascii")


def dechiffrer_nom_patient(blob_b64: str) -> str:
    """Déchiffre un blob produit par ``chiffrer_nom_patient``.

    Retourne "" si le blob est vide. Lève
    ``OrdonnanceChiffrementInvalide`` si le blob est corrompu.
    """
    if not blob_b64:
        return ""
    try:
        raw = base64.urlsafe_b64decode(blob_b64.encode("ascii"))
    except Exception as exc:
        logger.error("registre_pc_blob_base64_invalide")
        raise OrdonnanceChiffrementInvalide() from exc
    if len(raw) < 12 + 16:
        logger.error("registre_pc_blob_tronque")
        raise OrdonnanceChiffrementInvalide()
    nonce, ct = raw[:12], raw[12:]
    service = ServiceChiffrementOrdonnance()
    return service.dechiffrer(nonce, ct, associe=AAD_PATIENT_REGISTRE).decode("utf-8")
