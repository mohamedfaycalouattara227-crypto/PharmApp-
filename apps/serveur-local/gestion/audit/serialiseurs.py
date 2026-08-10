"""
gestion/audit/serialiseurs.py
Sérialiseurs DRF pour le journal d'audit.
"""

from rest_framework import serializers
from gestion.audit.models import JournalAudit


class JournalAuditSerialiseur(serializers.ModelSerializer):
    class Meta:
        model = JournalAudit
        fields = [
            "id", "type_action", "description", "severite",
            "utilisateur", "adresse_ip", "empreinte_sha256",
            "donnees_supplementaires", "cree_le",
        ]
        read_only_fields = fields
