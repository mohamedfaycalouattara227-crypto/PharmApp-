"""
api/throttling.py — Limiteurs de débit (rate limiting) par scope.
"""

from rest_framework.throttling import UserRateThrottle, AnonRateThrottle

# NOTE : aucune classe ne fixe `rate` en dur. Le débit est lu depuis
# REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"][scope] (settings.py), source unique
# de vérité et seul moyen de piloter les quotas par environnement.


class ThrottleConnexion(AnonRateThrottle):
    """5 tentatives de connexion par minute par IP — protection brute-force."""
    scope = "connexion"


class ThrottleVente(UserRateThrottle):
    """60 ventes par minute par utilisateur — prévention des erreurs de masse."""
    scope = "vente"


class ThrottleAjustementStock(UserRateThrottle):
    """30 ajustements de stock par minute."""
    scope = "ajustement_stock"


class ThrottleRapport(UserRateThrottle):
    """10 générations de rapport par minute — les rapports sont coûteux."""
    scope = "rapport"


class ThrottleStandard(UserRateThrottle):
    """200 requêtes par minute par utilisateur."""
    scope = "user"
