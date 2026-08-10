"""
gestion/parametrage/services_cloud.py
Service de configuration de la connexion Cloud PharmApp (côté local).

Responsabilités :
  - Stocker et récupérer les paramètres cloud (OfficineParametrage)
  - Fournir la configuration au processeur Outbox
  - Gérer la rotation de clé API
"""

import logging
from dataclasses import dataclass
from typing import Optional

from django.db import transaction
from django.utils import timezone

logger = logging.getLogger("pharmapp.cloud")


@dataclass(frozen=True)
class ConfigCloud:
    """Configuration cloud nécessaire au processeur Outbox."""
    officine_id: str
    code_officine: str
    cloud_api_url: str
    cle_api: str          # déchiffrée — à utiliser immédiatement, ne pas stocker


class ServiceParametrageCloud:
    """
    Service singleton pour la gestion des paramètres de connexion cloud.
    """

    @classmethod
    def est_configure(cls) -> bool:
        """Retourne True si la connexion cloud est opérationnelle."""
        from gestion.parametrage.models_cloud import OfficineParametrage
        return OfficineParametrage.obtenir().est_configure

    @classmethod
    def obtenir_config(cls) -> ConfigCloud:
        """
        Retourne la configuration cloud active.

        Raises:
            ValueError : si la connexion cloud n'est pas configurée.
        """
        from gestion.parametrage.models_cloud import OfficineParametrage
        config = OfficineParametrage.obtenir()

        if not config.est_configure:
            raise ValueError(
                "Connexion cloud non configurée. "
                "Exécutez : python manage.py configurer_cloud --officine-id <UUID> "
                "--code <PHA-XXX> --url <https://...> --cle <phk_...>"
            )

        return ConfigCloud(
            officine_id=str(config.officine_id),
            code_officine=config.code_officine,
            cloud_api_url=config.cloud_api_url.rstrip("/"),
            cle_api=config.cle_api_dechiffree,
        )

    @classmethod
    @transaction.atomic
    def configurer(
        cls,
        officine_id: str,
        code_officine: str,
        cloud_api_url: str,
        cle_api: str,
    ) -> None:
        """
        Configure ou met à jour la connexion cloud.

        Args:
            officine_id   : UUID attribué par le cloud au provisionnement.
            code_officine : code court (ex: "PHA-001").
            cloud_api_url : URL de base de l'API cloud.
            cle_api       : clé API complète reçue au provisionnement (phk_...).

        Raises:
            ValueError : si les paramètres sont invalides.
        """
        import uuid as uuid_module
        from gestion.parametrage.models_cloud import OfficineParametrage

        # Validation
        try:
            uuid_module.UUID(officine_id)
        except ValueError as exc:
            raise ValueError(f"officine_id invalide : {exc}") from exc

        if not cle_api.startswith("phk_"):
            raise ValueError("La clé API doit commencer par 'phk_'.")

        if not cloud_api_url.startswith(("http://", "https://")):
            raise ValueError("cloud_api_url doit être une URL valide.")

        config = OfficineParametrage.obtenir()
        config.officine_id = uuid_module.UUID(officine_id)
        config.code_officine = code_officine.strip().upper()
        config.cloud_api_url = cloud_api_url.strip()
        config.stocker_cle_api(cle_api)
        config.configure_le = timezone.now()

        # Version logicielle (injectée depuis settings si disponible)
        from django.conf import settings
        config.version_logiciel = getattr(settings, "PHARMAPP_VERSION", "")

        config.save()

        logger.info(
            "Connexion cloud configurée",
            extra={
                "officine_id": officine_id,
                "code": code_officine,
                "url": cloud_api_url,
                "prefixe_cle": cle_api[:8],
            },
        )

    @classmethod
    @transaction.atomic
    def mettre_a_jour_cle(cls, nouvelle_cle: str) -> None:
        """
        Rotation de clé API — remplace l'ancienne clé sans toucher aux autres paramètres.

        Args:
            nouvelle_cle : nouvelle clé API reçue après rotation (phk_...).
        """
        from gestion.parametrage.models_cloud import OfficineParametrage

        config = OfficineParametrage.obtenir()
        if not config.est_configure:
            raise ValueError("Impossible de faire une rotation : connexion cloud non configurée.")

        config.stocker_cle_api(nouvelle_cle)
        config.save(update_fields=["cle_api_chiffree", "prefixe_cle", "modifie_le"])

        logger.warning(
            "Clé API cloud remplacée (rotation)",
            extra={"prefixe_cle": nouvelle_cle[:8]},
        )
