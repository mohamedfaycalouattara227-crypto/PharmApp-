"""
gestion/rapports/serialiseurs.py
Sérialiseurs DRF pour les rapports.
"""

from rest_framework import serializers

import logging as _logging
_logger_rapports = _logging.getLogger("pharmapp.rapports")

try:
    from gestion.rapports.models import RapportGenere

    class RapportGenereSerialiseur(serializers.ModelSerializer):
        class Meta:
            model = RapportGenere
            fields = "__all__"
            read_only_fields = ["id", "cree_le"]
except Exception as _exc:
    _logger_rapports.warning(
        "RapportGenere indisponible (migration non appliquée ?) : %s", _exc
    )

    class RapportGenereSerialiseur(serializers.Serializer):
        pass
