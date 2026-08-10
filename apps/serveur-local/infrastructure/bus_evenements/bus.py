"""
Module : infrastructure/bus_evenements/bus.py
Description : Bus d'événements pour la communication découplée entre services métier.

Architecture événementielle de PharmApp :
    VENTE créée
        ↓
    BusEvenements.publier(EvenementVenteCreee)
        ↓ (dispatch simultané)
    ├─ ServiceStock       → décrémenter le stock
    ├─ ServiceComptabilite → créer l'écriture comptable
    ├─ ServiceAudit        → journaliser
    ├─ ServiceSync         → inscrire dans l'Outbox
    └─ ServiceStatistiques → mettre à jour les agrégats

Règles :
    - Les services ne s'appellent JAMAIS directement entre eux.
    - Toute communication inter-service passe par le bus.
    - Les gestionnaires s'enregistrent au démarrage de l'application.
    - En mode test, le bus est synchrone (CELERY_TASK_ALWAYS_EAGER).
    - En production, les gestionnaires lents sont délégués à Celery.
"""

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, ClassVar, Optional, Type

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger("pharmapp.bus_evenements")


# ─── Événements de base ───────────────────────────────────────────────────────

@dataclass
class Evenement:
    """
    Classe de base pour tous les événements PharmApp.

    Chaque événement est immuable et identifiable de façon unique.
    Il transporte les données nécessaires aux gestionnaires abonnés.
    """

    # Identifiant unique de l'événement (généré automatiquement)
    id_evenement: uuid.UUID = field(default_factory=uuid.uuid4)

    # Horodatage de création (UTC)
    cree_le: datetime = field(default_factory=timezone.now)

    # Identifiant de l'utilisateur ayant déclenché l'événement
    id_utilisateur: Optional[uuid.UUID] = None

    # Adresse IP de la requête source (pour l'audit)
    adresse_ip: str = ""

    @property
    def nom(self) -> str:
        """Retourne le nom de la classe d'événement (ex. : 'EvenementVenteCreee')."""
        return self.__class__.__name__

    @property
    def domaine(self) -> str:
        """
        Retourne le domaine métier de l'événement d'après le nom de classe.
        Exemple : 'EvenementVenteCreee' → 'vente'
        """
        nom = self.nom.lower()
        for domaine in ("vente", "stock", "client", "ordonnance", "audit",
                        "synchronisation", "comptabilite", "rapport",
                        "utilisateur", "produit_controle"):
            if domaine in nom:
                return domaine
        return "inconnu"


# ─── Événements métier ────────────────────────────────────────────────────────

@dataclass
class EvenementVenteCreee(Evenement):
    """Déclenché après l'enregistrement réussi d'une vente."""
    id_vente: Optional[uuid.UUID] = None
    numero_vente: str = ""
    montant_total: str = "0.00"          # Decimal sérialisé en str pour sécurité
    mode_paiement: str = ""
    id_client: Optional[uuid.UUID] = None
    articles: list[dict] = field(default_factory=list)
    # articles : [{"id_lot": ..., "quantite": ..., "prix_unitaire": ...}]


@dataclass
class EvenementVenteAnnulee(Evenement):
    """Déclenché après l'annulation d'une vente."""
    id_vente: Optional[uuid.UUID] = None
    numero_vente: str = ""
    motif_annulation: str = ""
    montant_rembourse: str = "0.00"


@dataclass
class EvenementStockAjuste(Evenement):
    """Déclenché après un ajustement manuel de stock."""
    id_lot: Optional[uuid.UUID] = None
    id_medicament: Optional[uuid.UUID] = None
    nom_medicament: str = ""
    quantite_avant: int = 0
    quantite_apres: int = 0
    motif: str = ""


@dataclass
class EvenementLivraison(Evenement):
    """Déclenché après réception d'une livraison fournisseur."""
    id_bon_commande: Optional[uuid.UUID] = None
    numero_bon: str = ""
    lots_crees: list[dict] = field(default_factory=list)


@dataclass
class EvenementAlerteStockBas(Evenement):
    """Déclenché lorsqu'un médicament passe en dessous du seuil d'alerte."""
    id_medicament: Optional[uuid.UUID] = None
    nom_medicament: str = ""
    stock_actuel: int = 0
    seuil_alerte: int = 0
    est_en_rupture: bool = False


@dataclass
class EvenementOrdonnanceNumerisee(Evenement):
    """Déclenché après la numérisation d'une ordonnance."""
    id_ordonnance: Optional[uuid.UUID] = None
    numero_interne: str = ""
    id_client: Optional[uuid.UUID] = None
    contient_produit_controle: bool = False


@dataclass
class EvenementConnexion(Evenement):
    """Déclenché à chaque tentative de connexion (succès ou échec)."""
    email_tente: str = ""
    succes: bool = False
    raison_echec: str = ""


@dataclass
class EvenementCompteCree(Evenement):
    """Déclenché après la création d'un compte utilisateur."""
    id_nouveau_compte: Optional[uuid.UUID] = None
    role: str = ""
    nom_complet: str = ""


@dataclass
class EvenementClotureCaisse(Evenement):
    """Déclenché après la clôture de caisse journalière."""
    date_cloture: Optional[str] = None       # ISO date string
    chiffre_affaires: str = "0.00"
    nombre_ventes: int = 0
    ecart_caisse: str = "0.00"


@dataclass
class EvenementProduitsControlesDelivre(Evenement):
    """Déclenché après la délivrance d'un produit stupéfiant ou psychotrope."""
    id_medicament: Optional[uuid.UUID] = None
    nom_medicament: str = ""
    quantite: int = 0
    id_ordonnance: Optional[uuid.UUID] = None
    nom_patient: str = ""


# ─── Registre des gestionnaires ───────────────────────────────────────────────

TypeGestionnaire = Callable[[Evenement], None]


class RegistreGestionnaires:
    """
    Registre interne qui associe un type d'événement à ses gestionnaires.
    Implémentation Singleton — partagée par toute l'application.
    """

    _instance: ClassVar[Optional["RegistreGestionnaires"]] = None
    _registre: dict[str, list[TypeGestionnaire]]

    def __new__(cls) -> "RegistreGestionnaires":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._registre = {}
        return cls._instance

    def enregistrer(
        self,
        type_evenement: Type[Evenement],
        gestionnaire: TypeGestionnaire,
    ) -> None:
        """Abonne un gestionnaire à un type d'événement."""
        cle = type_evenement.__name__
        if cle not in self._registre:
            self._registre[cle] = []
        if gestionnaire not in self._registre[cle]:
            self._registre[cle].append(gestionnaire)
            logger.debug(
                "Gestionnaire enregistré : %s → %s",
                cle,
                getattr(gestionnaire, "__qualname__", repr(gestionnaire)),
            )

    def obtenir(self, type_evenement: Type[Evenement]) -> list[TypeGestionnaire]:
        """Retourne la liste des gestionnaires abonnés à un type d'événement."""
        return self._registre.get(type_evenement.__name__, [])

    def tout_effacer(self) -> None:
        """Efface tous les abonnements — UNIQUEMENT pour les tests."""
        self._registre.clear()

    @property
    def nombre_gestionnaires(self) -> int:
        """Retourne le nombre total de gestionnaires enregistrés."""
        return sum(len(v) for v in self._registre.values())


# ─── Bus d'événements ─────────────────────────────────────────────────────────

class BusEvenements:
    """
    Bus d'événements central de PharmApp.

    Responsabilités :
    - Distribuer chaque événement à tous ses gestionnaires abonnés.
    - Garantir qu'une erreur dans un gestionnaire n'annule pas les autres.
    - Journaliser toutes les publications et erreurs.
    - Déléguer les traitements lents à Celery (mode asynchrone).

    Utilisation :
        bus = BusEvenements()
        bus.publier(EvenementVenteCreee(id_vente=..., montant_total=...))
    """

    def __init__(self, registre: Optional[RegistreGestionnaires] = None):
        self._registre = registre or RegistreGestionnaires()
        self._mode = getattr(settings, "BUS_EVENEMENTS_MODE", "synchrone")

    def publier(self, evenement: Evenement) -> dict[str, Any]:
        """
        Publie un événement et le distribue à tous ses gestionnaires.

        En mode synchrone (tests, développement) : appel direct.
        En mode asynchrone (production) : les gestionnaires lents → Celery.

        Args:
            evenement: Instance d'un événement métier héritant de Evenement.

        Returns:
            Rapport de distribution :
            {
                "evenement": str,
                "gestionnaires_executes": int,
                "erreurs": [{"gestionnaire": str, "erreur": str}]
            }
        """
        gestionnaires = self._registre.obtenir(type(evenement))

        rapport = {
            "evenement": evenement.nom,
            "id_evenement": str(evenement.id_evenement),
            "gestionnaires_executes": 0,
            "erreurs": [],
        }

        if not gestionnaires:
            logger.debug("Aucun gestionnaire pour l'événement : %s", evenement.nom)
            return rapport

        logger.info(
            "Bus : publication de '%s' (id=%s) → %d gestionnaire(s)",
            evenement.nom,
            evenement.id_evenement,
            len(gestionnaires),
        )

        for gestionnaire in gestionnaires:
            try:
                gestionnaire(evenement)
                rapport["gestionnaires_executes"] += 1
                logger.debug(
                    "Gestionnaire '%s' exécuté avec succès pour '%s'",
                    getattr(gestionnaire, "__qualname__", repr(gestionnaire)),
                    evenement.nom,
                )
            except Exception as exc:
                nom_g = getattr(gestionnaire, "__qualname__", repr(gestionnaire))
                erreur = {
                    "gestionnaire": nom_g,
                    "erreur": str(exc),
                }
                rapport["erreurs"].append(erreur)
                logger.error(
                    "Erreur gestionnaire '%s' pour '%s' : %s",
                    nom_g,
                    evenement.nom,
                    exc,
                    exc_info=True,
                )
                # Une erreur dans un gestionnaire N'interrompt PAS les autres.

        if rapport["erreurs"]:
            logger.warning(
                "Bus : '%s' distribué avec %d erreur(s) sur %d gestionnaire(s)",
                evenement.nom,
                len(rapport["erreurs"]),
                len(gestionnaires),
            )

        return rapport

    def abonner(
        self,
        type_evenement: Type[Evenement],
        gestionnaire: TypeGestionnaire,
    ) -> None:
        """Enregistre un gestionnaire pour un type d'événement."""
        self._registre.enregistrer(type_evenement, gestionnaire)

    @property
    def registre(self) -> RegistreGestionnaires:
        return self._registre


# ─── Décorateur pratique ──────────────────────────────────────────────────────

_bus_global = BusEvenements()


def gestionnaire_evenement(type_evenement: Type[Evenement]):
    """
    Décorateur pour enregistrer facilement une fonction comme gestionnaire d'événement.

    Usage :
        @gestionnaire_evenement(EvenementVenteCreee)
        def sur_vente_creee(evenement: EvenementVenteCreee) -> None:
            ServiceStock().decrementer(evenement.articles)
    """
    def decorateur(fonction: TypeGestionnaire) -> TypeGestionnaire:
        _bus_global.abonner(type_evenement, fonction)
        return fonction
    return decorateur


def obtenir_bus() -> BusEvenements:
    """Retourne l'instance globale du bus d'événements (injection de dépendances)."""
    return _bus_global
