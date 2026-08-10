"""
tests/securite/test_auth_jwt.py
ÉTAPE 03 — Tests JWT : cycle de vie des tokens, rotation, blacklist, brute-force.

Couvre :
  - Token expiré → 401
  - Refresh token blacklisté après rotation → 401
  - Token malformé → 401
  - Token d'un utilisateur désactivé → 401
  - 5 échecs de connexion consécutifs → compte verrouillé (DT-015)
  - Déconnexion blackliste le refresh token

Marqueur : pytest.mark.securite
"""

from datetime import timedelta
from unittest.mock import patch

import pytest
from django.utils import timezone
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

pytestmark = pytest.mark.securite


# ─── Fixtures locales ─────────────────────────────────────────────────────────

@pytest.fixture
def tokens_caissier(caissier):
    """Génère une paire access/refresh pour le caissier de test."""
    refresh = RefreshToken.for_user(caissier)
    return {
        "access": str(refresh.access_token),
        "refresh": str(refresh),
    }


@pytest.fixture
def tokens_titulaire(titulaire):
    """Génère une paire access/refresh pour le titulaire de test."""
    refresh = RefreshToken.for_user(titulaire)
    return {
        "access": str(refresh.access_token),
        "refresh": str(refresh),
    }


# ─── 1. Tokens valides ────────────────────────────────────────────────────────

class TestTokensValides:
    """Un token valide doit permettre l'accès aux endpoints protégés."""

    def test_access_token_valide_autorise_acces(self, api_client, tokens_caissier):
        """Un access token valide donne accès à /api/v1/ventes/."""
        api_client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {tokens_caissier['access']}"
        )
        reponse = api_client.get("/api/v1/ventes/")
        assert reponse.status_code == status.HTTP_200_OK

    def test_refresh_token_genere_nouveau_access(self, api_client, tokens_caissier):
        """Un refresh token valide génère un nouvel access token."""
        reponse = api_client.post(
            "/api/v1/auth/token/refresh/",
            data={"refresh": tokens_caissier["refresh"]},
            format="json",
        )
        assert reponse.status_code == status.HTTP_200_OK
        assert "access" in reponse.data
        # La rotation doit fournir un nouveau refresh token
        assert "refresh" in reponse.data
        assert reponse.data["refresh"] != tokens_caissier["refresh"]


# ─── 2. Tokens expirés ────────────────────────────────────────────────────────

class TestTokensExpires:
    """Un token expiré doit être rejeté avec 401."""

    def test_access_token_expire_retourne_401(self, api_client, caissier):
        """Un access token dont la durée est dépassée retourne 401."""
        with patch(
            "rest_framework_simplejwt.tokens.AccessToken.lifetime",
            new_callable=lambda: property(lambda self: timedelta(seconds=-1)),
        ):
            refresh = RefreshToken.for_user(caissier)
            # On force une expiration passée
            refresh.access_token.set_exp(lifetime=timedelta(seconds=-10))
            token_expire = str(refresh.access_token)

        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token_expire}")
        reponse = api_client.get("/api/v1/ventes/")
        assert reponse.status_code == status.HTTP_401_UNAUTHORIZED

    def test_refresh_token_expire_retourne_401(self, api_client, caissier):
        """Un refresh token expiré ne peut pas générer de nouveau token."""
        refresh = RefreshToken.for_user(caissier)
        refresh.set_exp(lifetime=timedelta(seconds=-10))
        token_expire = str(refresh)

        reponse = api_client.post(
            "/api/v1/auth/token/refresh/",
            data={"refresh": token_expire},
            format="json",
        )
        assert reponse.status_code == status.HTTP_401_UNAUTHORIZED


# ─── 3. Tokens malformés ─────────────────────────────────────────────────────

class TestTokensMalformes:
    """Un token malformé ou falsifié doit être rejeté avec 401."""

    @pytest.mark.parametrize("token_invalide", [
        "pas-un-jwt",
        "Bearer",
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.invalide.invalide",
        "",
        "null",
    ])
    def test_token_malforme_retourne_401(self, api_client, token_invalide):
        """Tout token syntaxiquement invalide doit retourner 401."""
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token_invalide}")
        reponse = api_client.get("/api/v1/ventes/")
        assert reponse.status_code == status.HTTP_401_UNAUTHORIZED

    def test_token_signature_falsifiee_retourne_401(self, api_client, tokens_caissier):
        """Un token dont la signature a été altérée doit retourner 401."""
        token = tokens_caissier["access"]
        # Altère le premier caractère de la signature : le dernier caractère
        # base64url peut coder des bits de bourrage et décoder aux mêmes octets.
        entete, charge, signature = token.split(".")
        signature = ("A" if signature[0] != "A" else "B") + signature[1:]
        token_falsifie = f"{entete}.{charge}.{signature}"
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token_falsifie}")
        reponse = api_client.get("/api/v1/ventes/")
        assert reponse.status_code == status.HTTP_401_UNAUTHORIZED


# ─── 4. Blacklist après rotation ─────────────────────────────────────────────

class TestBlacklistRotation:
    """Après rotation, l'ancien refresh token doit être blacklisté."""

    def test_ancien_refresh_token_blackliste_apres_rotation(
        self, api_client, tokens_caissier
    ):
        """Réutiliser un ancien refresh token après rotation → 401."""
        ancien_refresh = tokens_caissier["refresh"]

        # 1. Rotation : obtenir un nouveau refresh token
        reponse = api_client.post(
            "/api/v1/auth/token/refresh/",
            data={"refresh": ancien_refresh},
            format="json",
        )
        assert reponse.status_code == status.HTTP_200_OK

        # 2. Tenter de réutiliser l'ancien refresh token → doit échouer
        reponse_replay = api_client.post(
            "/api/v1/auth/token/refresh/",
            data={"refresh": ancien_refresh},
            format="json",
        )
        assert reponse_replay.status_code == status.HTTP_401_UNAUTHORIZED, (
            "L'ancien refresh token a pu être réutilisé après rotation — "
            "ROTATE_REFRESH_TOKENS ou BLACKLIST_AFTER_ROTATION non configuré."
        )


# ─── 5. Utilisateur désactivé ────────────────────────────────────────────────

class TestUtilisateurDesactive:
    """Un token émis pour un utilisateur désactivé doit être rejeté."""

    def test_token_utilisateur_desactive_retourne_401(
        self, api_client, caissier, tokens_caissier
    ):
        """Après désactivation du compte, le token existant ne doit plus fonctionner."""
        # Désactive le compte
        caissier.est_actif = False
        caissier.save()

        api_client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {tokens_caissier['access']}"
        )
        reponse = api_client.get("/api/v1/ventes/")
        assert reponse.status_code == status.HTTP_401_UNAUTHORIZED


# ─── 6. Brute-force et verrouillage de compte ────────────────────────────────

class TestBruteForceVerrouillage:
    """5 échecs de connexion consécutifs verrouillent le compte (DT-015)."""

    def test_cinq_echecs_verrouillent_compte(self, api_client, caissier):
        """Après 5 tentatives échouées, le compte est verrouillé."""
        url = "/api/v1/auth/connexion/"
        for _ in range(5):
            api_client.post(
                url,
                data={"email": caissier.email, "password": "mauvais_mot_de_passe"},
                format="json",
            )

        caissier.refresh_from_db()
        assert caissier.est_verrouille, (
            "Le compte n'est pas verrouillé après 5 tentatives échouées."
        )

    def test_compte_verrouille_retourne_401_meme_bon_mdp(
        self, api_client, caissier
    ):
        """Un compte verrouillé retourne 401 même avec le bon mot de passe."""
        caissier.est_verrouille = True
        caissier.verrouille_jusqu_au = timezone.now() + timedelta(minutes=30)
        caissier.save()

        reponse = api_client.post(
            "/api/v1/auth/connexion/",
            data={"email": caissier.email, "password": "motDePasse@Securise1!"},
            format="json",
        )
        assert reponse.status_code == status.HTTP_401_UNAUTHORIZED

    def test_compteur_echecs_reinitialisé_apres_succes(
        self, api_client, caissier
    ):
        """Une connexion réussie remet le compteur d'échecs à zéro."""
        caissier.tentatives_connexion_echouees = 3
        caissier.save()

        api_client.post(
            "/api/v1/auth/connexion/",
            data={"email": caissier.email, "password": "motDePasse@Securise1!"},
            format="json",
        )

        caissier.refresh_from_db()
        assert caissier.tentatives_connexion_echouees == 0


# ─── 7. Déconnexion blackliste le refresh token ──────────────────────────────

class TestDeconnexion:
    """La déconnexion doit invalider le refresh token."""

    def test_deconnexion_blackliste_refresh_token(
        self, api_client, tokens_caissier
    ):
        """Après déconnexion, le refresh token ne peut plus être utilisé."""
        api_client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {tokens_caissier['access']}"
        )
        # Déconnexion
        reponse_logout = api_client.post(
            "/api/v1/auth/deconnexion/",
            data={"refresh": tokens_caissier["refresh"]},
            format="json",
        )
        assert reponse_logout.status_code in (
            status.HTTP_200_OK,
            status.HTTP_204_NO_CONTENT,
        )

        # Tenter de rafraîchir le token après déconnexion → 401
        reponse_refresh = api_client.post(
            "/api/v1/auth/token/refresh/",
            data={"refresh": tokens_caissier["refresh"]},
            format="json",
        )
        assert reponse_refresh.status_code == status.HTTP_401_UNAUTHORIZED, (
            "Le refresh token est encore valide après déconnexion."
        )
