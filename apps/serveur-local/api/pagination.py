"""
api/pagination.py — Paginateurs DRF pour PharmApp.
"""

from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


def _enveloppe(paginateur, data):
    """Enveloppe de pagination commune.

    Les clés françaises (`compte`, `resultats`, ...) sont le contrat historique
    du poste client. Les clés DRF standard (`count`, `results`, `next`,
    `previous`) sont exposées EN PLUS : elles sont attendues par les intégrations
    tierces et les outils génériques. Les deux jeux pointent sur les mêmes
    valeurs — aucune divergence possible.
    """
    suivant = paginateur.get_next_link()
    precedent = paginateur.get_previous_link()
    compte = paginateur.page.paginator.count
    return Response({
        "compte": compte,
        "page_suivante": suivant,
        "page_precedente": precedent,
        "resultats": data,
        "count": compte,
        "next": suivant,
        "previous": precedent,
        "results": data,
    })


class PaginateurStandard(PageNumberPagination):
    """25 résultats par page — catalogue, clients, utilisateurs."""
    page_size = 25
    page_size_query_param = "taille_page"
    max_page_size = 200

    def get_paginated_response(self, data):
        return _enveloppe(self, data)


class PaginateurVentes(PageNumberPagination):
    """50 résultats par page — historique des ventes."""
    page_size = 50
    page_size_query_param = "taille_page"
    max_page_size = 500

    def get_paginated_response(self, data):
        return _enveloppe(self, data)


class PaginateurAudit(PageNumberPagination):
    """100 résultats par page — journal d'audit (lecture seule, volumieux)."""
    page_size = 100
    page_size_query_param = "taille_page"
    max_page_size = 1000

    def get_paginated_response(self, data):
        return _enveloppe(self, data)
