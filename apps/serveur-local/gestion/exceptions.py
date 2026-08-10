"""
gestion/exceptions.py
Exceptions métier centralisées pour PharmApp.
Toutes les erreurs fonctionnelles héritent de ExceptionPharmApp
pour faciliter le traitement uniforme dans les vues DRF.
"""


# ─── Base ─────────────────────────────────────────────────────────────────────

class ExceptionPharmApp(Exception):
    """Classe de base pour toutes les exceptions métier PharmApp."""
    code_erreur: str = "erreur_generale"
    statut_http: int = 400

    def __init__(self, message: str = "", **contexte):
        self.message = message or self.__class__.__doc__ or "Erreur PharmApp"
        self.contexte = contexte
        super().__init__(self.message)

    def to_dict(self) -> dict:
        """Sérialise l'exception pour les réponses API."""
        return {
            "erreur": self.code_erreur,
            "message": self.message,
            **self.contexte,
        }


# ─── Permissions & Authentification ──────────────────────────────────────────

class PermissionRefusee(ExceptionPharmApp):
    """Accès refusé — permissions insuffisantes pour cette opération."""
    code_erreur = "permission_refusee"
    statut_http = 403


class CompteBloqueException(ExceptionPharmApp):
    """Compte utilisateur temporairement bloqué suite à des tentatives échouées."""
    code_erreur = "compte_bloque"
    statut_http = 403


class CompteDesactiveException(ExceptionPharmApp):
    """Compte utilisateur désactivé par un administrateur."""
    code_erreur = "compte_desactive"
    statut_http = 403


class MotDePasseIncorrect(ExceptionPharmApp):
    """Mot de passe incorrect."""
    code_erreur = "mot_de_passe_incorrect"
    statut_http = 401


class TokenExpire(ExceptionPharmApp):
    """Jeton d'authentification expiré."""
    code_erreur = "token_expire"
    statut_http = 401


class EmailDejaUtilise(ExceptionPharmApp):
    """Un compte existe déjà avec cet email."""
    code_erreur = "email_deja_utilise"
    statut_http = 400


# ─── Ventes ───────────────────────────────────────────────────────────────────

class PanierVide(ExceptionPharmApp):
    """Impossible de traiter une vente avec un panier vide."""
    code_erreur = "panier_vide"
    statut_http = 400


class MontantEncaisseInsuffisant(ExceptionPharmApp):
    """Le montant encaissé est inférieur au montant total de la vente."""
    code_erreur = "montant_encaisse_insuffisant"
    statut_http = 400


class VenteDejaAnnulee(ExceptionPharmApp):
    """Cette vente a déjà été annulée et ne peut pas l'être à nouveau."""
    code_erreur = "vente_deja_annulee"
    statut_http = 409


class VenteIntrouvable(ExceptionPharmApp):
    """La vente demandée n'existe pas ou n'est pas accessible."""
    code_erreur = "vente_introuvable"
    statut_http = 404


class ModePaiementInvalide(ExceptionPharmApp):
    """Mode de paiement non reconnu ou non supporté."""
    code_erreur = "mode_paiement_invalide"
    statut_http = 400


class PrixHorsPlage(ExceptionPharmApp):
    """Le prix demandé est en dehors de la plage autorisée (min/max) pour ce médicament."""
    code_erreur = "prix_hors_plage"
    statut_http = 400


class RemiseNonAutorisee(ExceptionPharmApp):
    """Remise supérieure au plafond autorisé pour ce rôle."""
    code_erreur = "remise_non_autorisee"
    statut_http = 403


class OrdonnanceRequise(ExceptionPharmApp):
    """Ce médicament nécessite une ordonnance valide pour être vendu."""
    code_erreur = "ordonnance_requise"
    statut_http = 400


class DelaiAnnulationDepasse(ExceptionPharmApp):
    """Le délai maximum pour annuler cette vente est dépassé."""
    code_erreur = "delai_annulation_depasse"
    statut_http = 409


# ─── Stock ────────────────────────────────────────────────────────────────────

class StockInsuffisant(ExceptionPharmApp):
    """Stock disponible insuffisant pour satisfaire cette demande."""
    code_erreur = "stock_insuffisant"
    statut_http = 409

    def __init__(self, message: str = "", **contexte):
        if not message and "medicament" in contexte:
            medicament = contexte.get("medicament", "")
            disponible = contexte.get("disponible", 0)
            demande = contexte.get("demande", 0)
            message = f"Stock insuffisant pour {medicament} : {disponible} disponible(s), {demande} demandé(s)."
        super().__init__(message, **contexte)


class LotIntrouvable(ExceptionPharmApp):
    """Le lot de stock demandé n'existe pas ou a été archivé."""
    code_erreur = "lot_introuvable"
    statut_http = 404


class LotInactif(ExceptionPharmApp):
    """Ce lot de stock est inactif (périmé, retiré ou archivé)."""
    code_erreur = "lot_inactif"
    statut_http = 409


class LotPerime(ExceptionPharmApp):
    """Ce lot est périmé et ne peut pas être vendu."""
    code_erreur = "lot_perime"
    statut_http = 409


class EcartInventaireSignificatif(ExceptionPharmApp):
    """L'écart entre le stock système et le comptage physique dépasse le seuil autorisé."""
    code_erreur = "ecart_inventaire_significatif"
    statut_http = 403


class InventaireEnCours(ExceptionPharmApp):
    """Un inventaire est déjà en cours — une seule session à la fois."""
    code_erreur = "inventaire_en_cours"
    statut_http = 409


class InventaireIntrouvable(ExceptionPharmApp):
    """L'inventaire demandé n'existe pas."""
    code_erreur = "inventaire_introuvable"
    statut_http = 404


class BonCommandeInvalide(ExceptionPharmApp):
    """Le bon de commande est invalide ou ne correspond pas à la livraison."""
    code_erreur = "bon_commande_invalide"
    statut_http = 400


# ─── Clients ──────────────────────────────────────────────────────────────────

class ClientIntrouvable(ExceptionPharmApp):
    """Le client demandé n'existe pas ou a été supprimé."""
    code_erreur = "client_introuvable"
    statut_http = 404


class ClientDejaExistant(ExceptionPharmApp):
    """Un client avec ce numéro de téléphone ou cet email existe déjà."""
    code_erreur = "client_deja_existant"
    statut_http = 409


class ClientAnonymise(ExceptionPharmApp):
    """Ce client a exercé son droit à l'oubli — ses données sont anonymisées."""
    code_erreur = "client_anonymise"
    statut_http = 410


class CreditNonAutorise(ExceptionPharmApp):
    """Ce client n'est pas autorisé à utiliser le crédit."""
    code_erreur = "credit_non_autorise"
    statut_http = 403


class PlafondCreditDepasse(ExceptionPharmApp):
    """Le montant dépasse le plafond de crédit autorisé pour ce client."""
    code_erreur = "plafond_credit_depasse"
    statut_http = 402


class TelephoneDejaUtilise(ExceptionPharmApp):
    """Ce numéro de téléphone est déjà enregistré pour un autre client."""
    code_erreur = "telephone_deja_utilise"
    statut_http = 409


# ─── Médicaments & Catalogue ──────────────────────────────────────────────────

class MedicamentIntrouvable(ExceptionPharmApp):
    """Le médicament demandé n'existe pas dans le catalogue."""
    code_erreur = "medicament_introuvable"
    statut_http = 404


class MedicamentInactif(ExceptionPharmApp):
    """Ce médicament est inactif et ne peut plus être vendu."""
    code_erreur = "medicament_inactif"
    statut_http = 409


class CategorieIntrouvable(ExceptionPharmApp):
    """La catégorie demandée n'existe pas."""
    code_erreur = "categorie_introuvable"
    statut_http = 404


class CategorieNonSupprimable(ExceptionPharmApp):
    """Impossible de supprimer une catégorie contenant des médicaments actifs."""
    code_erreur = "categorie_non_supprimable"
    statut_http = 409


# ─── Ordonnances ──────────────────────────────────────────────────────────────

class OrdonnanceIntrouvable(ExceptionPharmApp):
    """L'ordonnance demandée n'existe pas."""
    code_erreur = "ordonnance_introuvable"
    statut_http = 404


class OrdonnanceDejaUtilisee(ExceptionPharmApp):
    """Cette ordonnance a déjà été utilisée et ne peut pas être réutilisée."""
    code_erreur = "ordonnance_deja_utilisee"
    statut_http = 409


class OrdonnanceExpiree(ExceptionPharmApp):
    """Cette ordonnance est expirée (validité de 3 mois dépassée)."""
    code_erreur = "ordonnance_expiree"
    statut_http = 409


class ImageOrdonnanceInvalide(ExceptionPharmApp):
    """L'image d'ordonnance fournie est invalide (format, taille, ou corruption)."""
    code_erreur = "image_ordonnance_invalide"
    statut_http = 400


# ─── Produits Contrôlés ───────────────────────────────────────────────────────

class ProduitControleIntrouvable(ExceptionPharmApp):
    """Ce produit contrôlé (stupéfiant/psychotrope) n'existe pas dans le registre."""
    code_erreur = "produit_controle_introuvable"
    statut_http = 404


class RegistreProduitControleIncomplet(ExceptionPharmApp):
    """Toutes les informations réglementaires sont requises pour les produits contrôlés."""
    code_erreur = "registre_incomplet"
    statut_http = 400


class QuantiteControleInsuffisante(ExceptionPharmApp):
    """Quantité insuffisante dans le registre des produits contrôlés."""
    code_erreur = "quantite_controlee_insuffisante"
    statut_http = 409


# ─── Caisse & Comptabilité ────────────────────────────────────────────────────

class ClotureCaisseIntrouvable(ExceptionPharmApp):
    """La clôture de caisse demandée n'existe pas."""
    code_erreur = "cloture_introuvable"
    statut_http = 404


class CaisseDejaClôturee(ExceptionPharmApp):
    """La caisse a déjà été clôturée pour cette date."""
    code_erreur = "caisse_deja_cloturee"
    statut_http = 409


class EcartCaisseSignificatif(ExceptionPharmApp):
    """L'écart de caisse détecté dépasse le seuil d'alerte."""
    code_erreur = "ecart_caisse_significatif"
    statut_http = 400


# ─── Synchronisation ──────────────────────────────────────────────────────────

class ConflitSynchronisation(ExceptionPharmApp):
    """Un conflit de synchronisation a été détecté entre le serveur local et le cloud."""
    code_erreur = "conflit_synchronisation"
    statut_http = 409


class ResolutionConflitInvalide(ExceptionPharmApp):
    """La résolution de conflit choisie n'est pas valide ('locale' ou 'cloud' uniquement)."""
    code_erreur = "resolution_conflit_invalide"
    statut_http = 400


# ─── Audit ────────────────────────────────────────────────────────────────────

class JournalAuditCorrompu(ExceptionPharmApp):
    """L'intégrité du journal d'audit est compromise — entrée(s) corrompue(s) détectée(s)."""
    code_erreur = "journal_audit_corrompu"
    statut_http = 500


# ─── Utilitaires ──────────────────────────────────────────────────────────────

class DonneesInvalides(ExceptionPharmApp):
    """Les données fournies ne respectent pas les contraintes métier."""
    code_erreur = "donnees_invalides"
    statut_http = 400


class OperationNonSupportee(ExceptionPharmApp):
    """Cette opération n'est pas supportée dans ce contexte."""
    code_erreur = "operation_non_supportee"
    statut_http = 405


class LimiteAtteinte(ExceptionPharmApp):
    """Une limite système a été atteinte (quota, taille, nombre)."""
    code_erreur = "limite_atteinte"
    statut_http = 429
