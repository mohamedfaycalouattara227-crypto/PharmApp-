"""
gestion/audit/models.py
Journal d'audit immuable avec intégrité SHA-256.
AUCUNE entrée ne peut être modifiée ou supprimée via l'API.
"""

import hashlib
import json
import uuid
from django.conf import settings
from django.db import models
from django.utils import timezone


class TypeAction(models.TextChoices):
    CONNEXION_REUSSIE         = "connexion_reussie",         "Connexion réussie"
    CONNEXION_ECHOUEE         = "connexion_echouee",         "Connexion échouée"
    DECONNEXION               = "deconnexion",               "Déconnexion"
    VENTE_CREEE               = "vente_creee",               "Vente créée"
    VENTE_ANNULEE             = "vente_annulee",             "Vente annulée"
    AJUSTEMENT_STOCK          = "ajustement_stock",          "Ajustement de stock"
    RECEPTION_STOCK           = "reception_stock",           "Réception fournisseur"
    ALERTE_STOCK              = "alerte_stock",              "Alerte stock générée"
    INVENTAIRE_DEMARRE        = "inventaire_demarre",        "Inventaire démarré"
    INVENTAIRE_VALIDE         = "inventaire_valide",         "Inventaire validé"
    ORDONNANCE_NUMERISEE      = "ordonnance_numerisee",      "Ordonnance numérisée"
    ACCES_SENSIBLE            = "acces_sensible",            "Accès données sensibles"
    PRODUIT_CONTROLE_MOUVEMENT= "produit_controle_mouvement","Mouvement produit contrôlé"
    CLOTURE_CAISSE            = "cloture_caisse",            "Clôture de caisse"
    MODIFICATION_UTILISATEUR  = "modification_utilisateur",  "Modification compte utilisateur"
    CREATION_COMPTE           = "creation_compte",           "Création de compte"
    SUPPRESSION_COMPTE        = "suppression_compte",        "Désactivation de compte"
    EXPORT_DONNEES            = "export_donnees",            "Export de données"
    INTEGRITE_VERIFIEE        = "integrite_verifiee",        "Vérification intégrité journal"


class Severite(models.TextChoices):
    INFO        = "info",        "Information"
    AVERTISSEMENT = "avertissement", "Avertissement"
    ALERTE      = "alerte",      "Alerte"
    CRITIQUE    = "critique",    "Critique"


class JournalAuditManager(models.Manager):
    def journaliser(
        self,
        type_action: str,
        description: str,
        severite: str = Severite.INFO,
        utilisateur=None,
        adresse_ip: str = "",
        donnees_supplementaires: dict = None,
        id_objet: str = "",
        modele_source: str = "",
    ) -> "JournalAudit":
        """Crée une entrée d'audit et calcule son empreinte SHA-256.

        CORRECTIF (audit 2026-07-21) : ``cree_le`` est calculé UNE SEULE FOIS
        ici et utilisé à la fois pour le contenu haché et pour la valeur
        persistée (JournalAudit.cree_le n'est plus auto_now_add). C'est cette
        même valeur que verifier_integrite() relira depuis la base — ce qui
        garantit que le hash reste vérifiable après écriture.
        """
        maintenant = timezone.now()
        entree = self.model(
            type_action=type_action,
            description=description,
            severite=severite,
            utilisateur=utilisateur,
            adresse_ip=adresse_ip,
            donnees_supplementaires=donnees_supplementaires or {},
            id_objet=id_objet,
            modele_source=modele_source,
            cree_le=maintenant,
        )
        # Calculer l'empreinte avant sauvegarde — avec la même valeur de
        # cree_le que celle qui sera effectivement persistée ci-dessous.
        contenu = json.dumps({
            "type_action": type_action,
            "description": description,
            "severite": severite,
            "utilisateur_id": str(utilisateur.id) if utilisateur else "",
            "adresse_ip": adresse_ip,
            "cree_le": maintenant.isoformat(),
            "id_objet": id_objet,
            "modele_source": modele_source,
            "donnees": donnees_supplementaires or {},
        }, sort_keys=True, ensure_ascii=False)
        entree.empreinte_sha256 = hashlib.sha256(contenu.encode()).hexdigest()
        entree.save()
        return entree


class JournalAudit(models.Model):
    """
    Entrée du journal d'audit.
    IMMUABLE : ni update ni delete n'est autorisé après création.
    L'intégrité est garantie par un hash SHA-256 de l'ensemble des champs.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    type_action = models.CharField(max_length=40, choices=TypeAction.choices)
    description = models.TextField()
    severite = models.CharField(
        max_length=15, choices=Severite.choices, default=Severite.INFO
    )
    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="journal_audit",
    )
    adresse_ip = models.GenericIPAddressField(null=True, blank=True)
    id_objet = models.CharField(max_length=100, blank=True)
    modele_source = models.CharField(max_length=100, blank=True)
    donnees_supplementaires = models.JSONField(default=dict, blank=True)
    empreinte_sha256 = models.CharField(max_length=64, blank=True)
    # CORRECTIF (audit 2026-07-21) : auto_now_add=True retiré.
    # auto_now_add recalcule sa propre valeur de timezone.now() au moment du
    # save() interne, à un instant nécessairement postérieur et distinct de
    # celui utilisé pour construire empreinte_sha256 dans le manager — ce qui
    # rendait verifier_integrite() perpétuellement False, y compris pour une
    # entrée jamais modifiée. cree_le est désormais fixé explicitement par
    # JournalAuditManager.journaliser() AVANT le calcul du hash, avec la même
    # valeur utilisée pour les deux. Voir test_service_audit.py::
    # test_verifier_integrite_entree_reelle_valide.
    cree_le = models.DateTimeField()

    objects = JournalAuditManager()

    class Meta:
        db_table = "audit_journal"
        verbose_name = "Entrée d'audit"
        verbose_name_plural = "Journal d'audit"
        ordering = ["-cree_le"]
        indexes = [
            models.Index(fields=["type_action", "cree_le"]),
            models.Index(fields=["utilisateur", "cree_le"]),
            models.Index(
                fields=["type_action", "cree_le"], name="audit_type_cree_le_idx"
            ),
            models.Index(
                fields=["utilisateur", "cree_le"], name="audit_utilisateur_cree_le_idx"
            ),
            models.Index(fields=["severite", "cree_le"]),
            models.Index(fields=["cree_le"]),
        ]

    def __str__(self):
        return f"[{self.severite.upper()}] {self.get_type_action_display()} — {self.cree_le}"

    def verifier_integrite(self) -> bool:
        """Vérifie que l'empreinte SHA-256 correspond au contenu."""
        contenu = json.dumps({
            "type_action": self.type_action,
            "description": self.description,
            "severite": self.severite,
            "utilisateur_id": str(self.utilisateur_id) if self.utilisateur_id else "",
            "adresse_ip": str(self.adresse_ip) if self.adresse_ip else "",
            "cree_le": self.cree_le.isoformat() if self.cree_le else "",
            "id_objet": self.id_objet,
            "modele_source": self.modele_source,
            "donnees": self.donnees_supplementaires,
        }, sort_keys=True, ensure_ascii=False)
        empreinte_attendue = hashlib.sha256(contenu.encode()).hexdigest()
        return empreinte_attendue == self.empreinte_sha256

    def save(self, *args, **kwargs):
        # Journal append-only : une entrée déjà persistée n'est JAMAIS réécrite.
        # On ignore silencieusement l'UPDATE (aucune donnée falsifiée n'atteint
        # la base) et on trace la tentative, plutôt que de lever une exception :
        # une écriture d'audit ne doit jamais faire échouer la transaction
        # métier appelante. Le refus explicite (PermissionError) reste porté
        # par la couche dépôt, DepotJournalAudit.sauvegarder().
        if self.pk and JournalAudit.objects.filter(pk=self.pk).exists():
            import logging

            logging.getLogger("pharmapp.audit").warning(
                "Tentative de modification d'une entrée d'audit immuable "
                "(id=%s) — ignorée.",
                self.pk,
            )
            return
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise PermissionError(
            "Le journal d'audit est immuable — aucune suppression n'est permise."
        )
