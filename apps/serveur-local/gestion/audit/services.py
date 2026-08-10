"""
Module : gestion/audit/services.py
Description : Service d'audit automatique pour PharmApp.
"""

import logging
import uuid
from datetime import timedelta
from typing import Optional

from django.utils import timezone

# Import module-level pour que patch("gestion.audit.services.JournalAudit") fonctionne
from gestion.audit.models import JournalAudit

logger = logging.getLogger("pharmapp.audit")

# Seuil de tentatives échouées pour passer en sévérité "critique"
SEUIL_ECHECS_CRITIQUE = 5


class ServiceAudit:
    """Service d'audit centralisé de PharmApp."""

    def enregistrer(
        self,
        type_action: str,
        description: str,
        severite: str = "info",
        utilisateur=None,
        adresse_ip: str = "",
        donnees_supplementaires: dict | None = None,
        id_objet: str = "",
        modele_source: str = "",
    ) -> object:
        """Point d'entrée générique du journal d'audit.

        Les méthodes ``journaliser_*`` couvrent les événements métier connus ;
        ``enregistrer`` expose la même garantie d'intégrité (empreinte SHA-256
        chaînée) pour tout autre événement.
        """
        return JournalAudit.objects.journaliser(
            type_action=type_action,
            description=description,
            severite=severite,
            utilisateur=utilisateur,
            adresse_ip=adresse_ip,
            donnees_supplementaires=donnees_supplementaires,
            id_objet=id_objet,
            modele_source=modele_source,
        )

    def journaliser_vente(
        self,
        vente,
        utilisateur,
        adresse_ip: str = "",
    ) -> object:
        """Journalise la création d'une vente."""
        return JournalAudit.objects.journaliser(
            type_action="vente_creee",
            description=(
                f"Vente {vente.numero} enregistrée — "
                f"Montant : {vente.montant_total} FCFA — "
                f"Mode : {vente.get_mode_paiement_display()}"
                + (f" — Client : {vente.client.nom_complet}" if vente.client else "")
            ),
            utilisateur=utilisateur,
            severite="info",
            adresse_ip=adresse_ip,
            donnees_supplementaires={
                "numero": vente.numero,
                "montant_total": str(vente.montant_total),
                "mode_paiement": vente.mode_paiement,
                "nombre_lignes": vente.lignes.count(),
            },
        )

    def journaliser_annulation_vente(
        self,
        vente,
        motif: str,
        utilisateur,
        adresse_ip: str = "",
    ) -> object:
        """Journalise l'annulation d'une vente."""
        return JournalAudit.objects.journaliser(
            type_action="vente_annulee",
            description=(
                f"Vente {vente.numero} ANNULÉE — "
                f"Motif : {motif} — "
                f"Montant annulé : {vente.montant_total} FCFA"
            ),
            utilisateur=utilisateur,
            severite="avertissement",
            adresse_ip=adresse_ip,
        )

    def journaliser_ajustement_stock(
        self,
        lot,
        quantite_avant: int,
        quantite_apres: int,
        motif: str,
        utilisateur,
        adresse_ip: str = "",
    ) -> object:
        """Journalise un ajustement manuel de stock."""
        ecart = quantite_apres - quantite_avant
        ecart_pct = abs(ecart / quantite_avant * 100) if quantite_avant else 100
        severite = "alerte" if ecart_pct > 10 else "avertissement"
        return JournalAudit.objects.journaliser(
            type_action="ajustement_stock",
            description=(
                f"Ajustement : {lot.medicament.nom} — "
                f"{quantite_avant} → {quantite_apres} "
                f"({'+'if ecart >= 0 else ''}{ecart}) — "
                f"Motif : {motif}"
            ),
            utilisateur=utilisateur,
            severite=severite,
            adresse_ip=adresse_ip,
        )

    def journaliser_connexion(
        self,
        email: str,
        succes: bool,
        utilisateur=None,
        adresse_ip: str = "",
        raison_echec: str = "",
    ) -> object:
        """
        Journalise une tentative de connexion (réussie ou échouée).

        La sévérité escalade automatiquement :
          - Connexion réussie → info
          - Échec unique → alerte
          - 5+ échecs → critique (attaque probable)
        """
        if succes:
            severite = "info"
            type_action = "connexion_reussie"
        else:
            echecs = self._compter_echecs_recents(email)
            severite = "critique" if echecs >= SEUIL_ECHECS_CRITIQUE else "alerte"
            type_action = "connexion_echouee"

        return JournalAudit.objects.journaliser(
            type_action=type_action,
            description=(
                f"Connexion {'réussie' if succes else 'ÉCHOUÉE'} — {email}"
                + (f" — {raison_echec}" if not succes and raison_echec else "")
            ),
            utilisateur=utilisateur,
            adresse_ip=adresse_ip,
            severite=severite,
            # CORRECTIF (audit 2026-07-21) : email stocké dans un champ
            # structuré, exploité par _compter_echecs_recents() ci-dessous
            # via une correspondance exacte — plutôt que par sous-chaîne
            # (icontains) dans la description, qui pouvait produire des faux
            # positifs entre deux emails dont l'un contient l'autre
            # (ex. "jo@pharma.bf" et "rejo@pharma.bf").
            donnees_supplementaires={"email": email.strip().lower()},
        )

    def _compter_echecs_recents(
        self,
        email: str,
        fenetre_minutes: int = 30,
    ) -> int:
        """
        Compte les tentatives de connexion échouées récentes pour un email.

        Args:
            email: Adresse email tentée.
            fenetre_minutes: Fenêtre de temps (défaut 30 minutes).

        Returns:
            Nombre de tentatives échouées dans la fenêtre.
        """
        depuis = timezone.now() - timedelta(minutes=fenetre_minutes)
        # CORRECTIF (audit 2026-07-21) : correspondance exacte sur le champ
        # structuré donnees_supplementaires__email (JSONField), au lieu d'un
        # description__icontains sujet aux faux positifs entre emails proches.
        return JournalAudit.objects.filter(
            type_action="connexion_echouee",
            donnees_supplementaires__email=email.strip().lower(),
            cree_le__gte=depuis,
        ).count()

    def journaliser_acces_ordonnance(
        self,
        ordonnance,
        utilisateur,
        adresse_ip: str = "",
    ) -> object:
        """
        Journalise l'accès à une ordonnance (données médicales sensibles).

        Sévérité : toujours "alerte" (données personnelles de santé).
        """
        return JournalAudit.objects.journaliser(
            type_action="acces_sensible",
            description=(
                f"Accès ordonnance {ordonnance.numero_interne} — "
                f"Patient : {ordonnance.client.nom_complet}"
            ),
            utilisateur=utilisateur,
            severite="alerte",
            adresse_ip=adresse_ip,
        )

    def journaliser_produit_controle(
        self,
        registre,
        type_mouvement: str,
        utilisateur,
        adresse_ip: str = "",
    ) -> object:
        """
        Journalise un mouvement sur un produit contrôlé (stupéfiants, psychotropes).

        Sévérité : toujours "critique" (obligation légale de traçabilité).
        """
        return JournalAudit.objects.journaliser(
            type_action="produit_controle_mouvement",
            description=(
                f"Mouvement {type_mouvement} — Produit contrôlé : "
                f"{registre.medicament.nom} — "
                f"Quantité : {registre.quantite_mouvement} {registre.unite} — "
                f"Lot : {registre.numero_lot_fabricant}"
            ),
            utilisateur=utilisateur,
            severite="critique",
            adresse_ip=adresse_ip,
        )

    def verifier_integrite_journal(self) -> dict:
        """
        Vérifie l'intégrité SHA-256 de toutes les entrées du journal.

        Returns:
            {"total": int, "valides": int, "corrompues": list[str], "integrite_ok": bool}
        """
        entrees = JournalAudit.objects.all()
        total = entrees.count()
        corrompues = []

        for entree in entrees:
            if not entree.verifier_integrite():
                corrompues.append(str(entree.id))

        return {
            "total": total,
            "valides": total - len(corrompues),
            "corrompues": corrompues,
            "integrite_ok": len(corrompues) == 0,
        }

    def rapport_activite(
        self,
        date_debut=None,
        date_fin=None,
        utilisateur_id: Optional[uuid.UUID] = None,
    ) -> dict:
        """
        Génère un rapport d'activité du journal d'audit.

        Returns:
            {
                "total_connexions": int,
                "connexions_echouees": int,
                "total_ventes": int,
                "ajustements_stock": int,
                "acces_sensibles": int,
                "produits_controles": int,
                "par_severite": {severite: count},
            }
        """
        from django.db.models import Count

        qs = JournalAudit.objects.all()
        if date_debut:
            qs = qs.filter(cree_le__gte=date_debut)
        if date_fin:
            qs = qs.filter(cree_le__lte=date_fin)
        if utilisateur_id:
            qs = qs.filter(utilisateur_id=utilisateur_id)

        def _compter(type_action: str) -> int:
            return qs.filter(type_action=type_action).count()

        par_severite = dict(
            qs.values("severite").annotate(total=Count("id"))
            .values_list("severite", "total")
        )

        return {
            "total_connexions": _compter("connexion_reussie") + _compter("connexion_echouee"),
            "connexions_echouees": _compter("connexion_echouee"),
            "total_ventes": _compter("vente_creee"),
            "ajustements_stock": _compter("ajustement_stock"),
            "acces_sensibles": _compter("acces_sensible"),
            "produits_controles": _compter("produit_controle_mouvement"),
            "par_severite": par_severite,
        }


# ─── Gestionnaires d'événements automatiques ─────────────────────────────────
#
# ATTENTION (audit 2026-07-21) : à la date de ce correctif, aucun appel réel
# à bus.publier(EvenementVenteCreee | EvenementVenteAnnulee | EvenementStockAjuste
# | EvenementConnexion) n'existe dans le code de production — ces quatre
# gestionnaires sont enregistrés au démarrage (gestion/audit/apps.py) mais ne
# sont donc actuellement JAMAIS déclenchés en dehors des tests unitaires, qui
# les appellent directement avec un objet événement synthétique.
#
# La source de vérité actuelle pour le journal d'audit est l'appel DIRECT à
# ServiceAudit(), effectué dans la même transaction que l'action métier :
#   - vente créée / annulée      → gestion/ventes/services.py (§13)
#   - ajustement de stock manuel → gestion/stocks/services.py
#   - connexion réussie/échouée  → gestion/authentification/vues.py
#
# Si le bus d'événements est un jour réellement câblé pour ces flux, RETIRER
# l'appel direct correspondant ci-dessus (ou inversement), sous peine de
# journaliser chaque événement deux fois. Ne jamais activer les deux
# mécanismes simultanément pour un même flux métier.

def _sur_vente_creee(evenement) -> None:
    """Journalise automatiquement chaque vente créée."""
    JournalAudit.objects.journaliser(
        type_action="vente_creee",
        description=(
            f"Vente {evenement.numero_vente} enregistrée — "
            f"Montant : {evenement.montant_total} FCFA — "
            f"Mode : {evenement.mode_paiement}"
        ),
        severite="info",
    )


def _sur_vente_annulee(evenement) -> None:
    """Journalise automatiquement chaque annulation de vente."""
    JournalAudit.objects.journaliser(
        type_action="vente_annulee",
        description=(
            f"Vente {evenement.numero_vente} ANNULÉE — "
            f"Motif : {evenement.motif_annulation}"
        ),
        severite="avertissement",
    )


def _sur_stock_ajuste(evenement) -> None:
    """Journalise automatiquement chaque ajustement de stock."""
    ecart = evenement.quantite_apres - evenement.quantite_avant
    JournalAudit.objects.journaliser(
        type_action="stock_ajuste",
        description=(
            f"Ajustement : {evenement.nom_medicament} — "
            f"{evenement.quantite_avant} → {evenement.quantite_apres} "
            f"({'+'if ecart >= 0 else ''}{ecart}) — "
            f"Motif : {evenement.motif}"
        ),
        severite="alerte" if abs(ecart) > 10 else "avertissement",
    )


def _sur_connexion(evenement) -> None:
    """Journalise automatiquement toutes les tentatives de connexion."""
    JournalAudit.objects.journaliser(
        type_action="connexion_reussie" if evenement.succes else "connexion_echouee",
        description=(
            f"Connexion {'réussie' if evenement.succes else 'ÉCHOUÉE'} — "
            f"{evenement.email_tente}"
            + (f" — {evenement.raison_echec}" if not evenement.succes else "")
        ),
        adresse_ip=getattr(evenement, "adresse_ip", ""),
        severite="info" if evenement.succes else "alerte",
    )


def enregistrer_gestionnaires_audit(bus) -> None:
    """Enregistre tous les gestionnaires d'audit sur le bus d'événements."""
    from infrastructure.bus_evenements.bus import (
        EvenementVenteCreee,
        EvenementVenteAnnulee,
        EvenementStockAjuste,
        EvenementConnexion,
    )

    bus.abonner(EvenementVenteCreee, _sur_vente_creee)
    bus.abonner(EvenementVenteAnnulee, _sur_vente_annulee)
    bus.abonner(EvenementStockAjuste, _sur_stock_ajuste)
    bus.abonner(EvenementConnexion, _sur_connexion)

    logger.info("Audit : %d gestionnaire(s) enregistré(s) sur le bus.", 4)
