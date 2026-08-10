"""
gestion/comptabilite/serialiseurs.py
Sérialiseurs DRF pour la comptabilité.
"""

from rest_framework import serializers

import logging as _logging
_logger_compta = _logging.getLogger("pharmapp.comptabilite")

try:
    from gestion.comptabilite.models import EcritureComptable

    class EcritureComptableSerialiseur(serializers.ModelSerializer):
        class Meta:
            model = EcritureComptable
            fields = "__all__"
            read_only_fields = ["id", "cree_le"]
except Exception as _exc:
    _logger_compta.warning(
        "EcritureComptable indisponible (migration non appliquée ?) : %s", _exc
    )

    class EcritureComptableSerialiseur(serializers.Serializer):
        pass
