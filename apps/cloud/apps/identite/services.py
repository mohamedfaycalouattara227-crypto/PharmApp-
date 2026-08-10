"""
apps/identite/services.py
Services métier pour la gestion des Officines et des clés API.

Règles de sécurité appliquées :
- Génération : secrets.token_urlsafe (256 bits d'entropie CSPRNG)
- Stockage   : SHA-256 du token — jamais le token brut
- Vérification : secrets.compare_digest (protection timing side-channel)
- Préfixe    : 8 premiers caractères pour identification sans exposition
"""

import hashlib
import logging
import secrets
from dataclasses import dataclass
from typing import Optional

from django.db import transaction
from django.utils import timezone

from apps.identite.models import Officine, StatutAbonnement

logger = logging.getLogger("pharmapp_cloud.identite")


# ─── DTO résultat provisionnement ─────────────────────────────────────────────

@dataclass(frozen=True)
class ResultatProvisionnement:
    """
    Résultat de la création d'une officine.
    cle_api n'est disponible QU'ICI — elle ne peut pas être récupérée ensuite.
    """
    officine_id: str
    code: str
    nom: str
    cle_api: str          # clé complète — à transmettre immédiatement à la pharmacie
    cle_api_prefixe: str  # préfixe non-secret pour identification


# ─── Fonctions de clé API ──────────────────────────────────────────────────────

def generer_cle_api() -> tuple[str, str, str]:
    """
    Génère une clé API sécurisée avec 256 bits d'entropie.

    Retourne : (cle_complete, prefixe, hash_sha256)
    La cle_complete ne doit JAMAIS être persistée.
    Le prefixe est stocké pour identification sans exposition.
    Le hash_sha256 est stocké en base.
    """
    token = secrets.token_urlsafe(32)       # 256 bits d'entropie
    cle_complete = f"phk_{token}"           # format : "phk_<base64url>"
    prefixe = cle_complete[:8]              # "phk_A1B2"
    hash_sha256 = _hacher_cle(cle_complete)
    return cle_complete, prefixe, hash_sha256


def verifier_cle_api(cle_candidate: str, hash_stocke: str) -> bool:
    """
    Vérifie une clé API candidate contre son hash stocké.

    Utilise secrets.compare_digest pour une comparaison en temps constant
    résistante au timing side-channel.

    Args:
        cle_candidate : clé brute reçue dans le header X-Api-Key
        hash_stocke   : hash SHA-256 stocké en base pour cette officine

    Returns:
        True si la clé est valide, False sinon.
    """
    if not cle_candidate or not hash_stocke:
        return False
    hash_candidate = _hacher_cle(cle_candidate)
    return secrets.compare_digest(hash_candidate, hash_stocke)


def _hacher_cle(cle: str) -> str:
    """Hash SHA-256 hexadécimal d'une clé API."""
    return hashlib.sha256(cle.encode("utf-8")).hexdigest()


# ─── Service Officine ──────────────────────────────────────────────────────────

class ServiceOfficine:
    """
    Logique métier de gestion des officines.
    Toutes les méthodes sont des classméthodes (pas d'état).
    """

    @classmethod
    @transaction.atomic
    def provisionner(
        cls,
        nom: str,
        code: str,
        ville: str = "",
        pays: str = "Burkina Faso",
        notes: str = "",
    ) -> ResultatProvisionnement:
        """
        Crée une nouvelle officine et génère sa clé API.

        La clé API complète est retournée UNE SEULE FOIS dans le résultat.
        Elle n'est jamais stockée en clair — uniquement son hash SHA-256.

        Raises:
            ValueError : si le code est déjà pris.
        """
        code = code.strip().upper()

        if Officine.objects.filter(code=code).exists():
            raise ValueError(f"Le code '{code}' est déjà attribué à une officine.")

        cle_api, prefixe, hash_sha256 = generer_cle_api()

        officine = Officine.objects.create(
            nom=nom.strip(),
            code=code,
            ville=ville.strip(),
            pays=pays.strip(),
            cle_api_hash=hash_sha256,
            cle_api_prefixe=prefixe,
            statut_abonnement=StatutAbonnement.ESSAI,
            notes=notes.strip(),
        )

        logger.info(
            "Officine provisionnée",
            extra={
                "officine_id": str(officine.id),
                "code": officine.code,
                "prefixe_cle": prefixe,
            },
        )

        return ResultatProvisionnement(
            officine_id=str(officine.id),
            code=officine.code,
            nom=officine.nom,
            cle_api=cle_api,
            cle_api_prefixe=prefixe,
        )

    @classmethod
    @transaction.atomic
    def regenerer_cle_api(cls, officine_id: str) -> ResultatProvisionnement:
        """
        Régénère la clé API d'une officine existante (rotation de clé).

        L'ancienne clé est immédiatement invalidée.
        La nouvelle clé est retournée UNE SEULE FOIS.

        Raises:
            Officine.DoesNotExist : si l'officine n'existe pas.
        """
        officine = Officine.objects.select_for_update().get(id=officine_id)

        cle_api, prefixe, hash_sha256 = generer_cle_api()

        officine.cle_api_hash = hash_sha256
        officine.cle_api_prefixe = prefixe
        officine.save(update_fields=["cle_api_hash", "cle_api_prefixe", "mis_a_jour_le"])

        logger.warning(
            "Clé API régénérée",
            extra={
                "officine_id": str(officine.id),
                "code": officine.code,
                "nouveau_prefixe": prefixe,
            },
        )

        return ResultatProvisionnement(
            officine_id=str(officine.id),
            code=officine.code,
            nom=officine.nom,
            cle_api=cle_api,
            cle_api_prefixe=prefixe,
        )

    @classmethod
    def suspendre(cls, officine_id: str, raison: str = "") -> None:
        """Suspend l'accès d'une officine (clé API rejetée)."""
        updated = Officine.objects.filter(id=officine_id).update(
            statut_abonnement=StatutAbonnement.SUSPENDU,
            est_active=False,
        )
        if not updated:
            raise Officine.DoesNotExist(f"Officine {officine_id} introuvable.")

        logger.warning(
            "Officine suspendue",
            extra={"officine_id": officine_id, "raison": raison},
        )

    @classmethod
    def reactiver(cls, officine_id: str) -> None:
        """Réactive une officine suspendue."""
        updated = Officine.objects.filter(id=officine_id).update(
            statut_abonnement=StatutAbonnement.ACTIF,
            est_active=True,
        )
        if not updated:
            raise Officine.DoesNotExist(f"Officine {officine_id} introuvable.")

        logger.info("Officine réactivée", extra={"officine_id": officine_id})

    @classmethod
    def mettre_a_jour_connexion(
        cls,
        officine: Officine,
        version_logiciel: Optional[str] = None,
    ) -> None:
        """
        Met à jour la dernière connexion et la version logicielle déclarée.
        Appelé à chaque requête authentifiée réussie.
        """
        champs = {"derniere_connexion": timezone.now()}
        if version_logiciel:
            champs["version_logiciel"] = version_logiciel[:20]

        Officine.objects.filter(pk=officine.pk).update(**champs)
