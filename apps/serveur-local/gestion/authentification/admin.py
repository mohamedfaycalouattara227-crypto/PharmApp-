"""Admin Django pour les utilisateurs — visible uniquement pour l'administrateur."""

from django.contrib import admin

from gestion.authentification.models import UtilisateurPharmacien


@admin.register(UtilisateurPharmacien)
class UtilisateurPharmacienAdmin(admin.ModelAdmin):
    list_display = ("email", "nom", "prenom", "role", "est_actif", "est_verrouille", "derniere_connexion_reussie")
    list_filter = ("role", "est_actif", "est_verrouille")
    search_fields = ("email", "nom", "prenom", "numero_ordre")
    readonly_fields = (
        "id", "cree_le", "modifie_le", "derniere_connexion_reussie",
        "tentatives_connexion_echouees", "verrouille_jusqu_au",
    )
    ordering = ("nom", "prenom")

    actions = ["deverrouiller_comptes", "desactiver_comptes"]

    @admin.action(description="Déverrouiller les comptes sélectionnés")
    def deverrouiller_comptes(self, request, queryset):
        for u in queryset:
            u.reinitialiser_echecs_connexion()
        self.message_user(request, f"{queryset.count()} compte(s) déverrouillé(s).")

    @admin.action(description="Désactiver les comptes sélectionnés")
    def desactiver_comptes(self, request, queryset):
        queryset.update(est_actif=False)
