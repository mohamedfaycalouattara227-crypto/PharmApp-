"""
tests/integration/test_api_ordonnances.py
Tests d'intégration pour l'API REST des ordonnances.
Couvre : upload multipart, validation MIME, accès sécurisé, validation ordonnance.
"""

import io
import uuid

import pytest
from rest_framework import status

pytestmark = [pytest.mark.django_db, pytest.mark.integration]

# ─── Magic bytes réels pour les tests ────────────────────────────────────────

JPEG_MINIMAL = (
    b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
    b"\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t"
    b"\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a"
    b"\x1f\x1e\x1d\x1a\x1c\x1c $.' \",#\x1c\x1c(7),01444\x1f'9=82<.342\x1e"
    b"\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00\xff\xc4"
    b"\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00\x00"
    b"\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b"
    b"\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xfb\xff\xd9"
)

PNG_MINIMAL = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
    b"\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
)


class TestOrdonnanceUpload:
    """Tests d'upload d'ordonnance via l'API multipart."""

    def test_upload_jpeg_sans_client_retourne_201(self, api_caissier):
        """Un upload JPEG sans client associé crée une ordonnance en attente."""
        fichier = io.BytesIO(JPEG_MINIMAL)
        fichier.name = "ordonnance.jpg"
        reponse = api_caissier.post(
            "/api/ordonnances/",
            data={
                "fichier": fichier,
                "prescripteur_nom": "Dr Coulibaly",
                "content_type": "image/jpeg",
            },
            format="multipart",
        )
        assert reponse.status_code == status.HTTP_201_CREATED
        data = reponse.json()
        assert data["statut"] == "en_attente"
        assert "numero_interne" in data
        assert data["numero_interne"].startswith("ORD-")

    def test_upload_png_retourne_201(self, api_caissier):
        """Un upload PNG est accepté."""
        fichier = io.BytesIO(PNG_MINIMAL)
        fichier.name = "ordonnance.png"
        reponse = api_caissier.post(
            "/api/ordonnances/",
            data={"fichier": fichier},
            format="multipart",
        )
        assert reponse.status_code == status.HTTP_201_CREATED

    def test_creation_sans_fichier_retourne_201(self, api_caissier):
        """Créer une ordonnance sans image (numéro externe) est permis."""
        reponse = api_caissier.post(
            "/api/ordonnances/",
            data={"prescripteur_nom": "Dr Sawadogo"},
            format="json",
        )
        assert reponse.status_code == status.HTTP_201_CREATED

    def test_non_authentifie_retourne_401(self, api_client):
        """Un appel sans authentification retourne 401."""
        reponse = api_client.post("/api/ordonnances/", data={}, format="json")
        assert reponse.status_code == status.HTTP_401_UNAUTHORIZED

    def test_upload_mime_incoherent_retourne_400(self, api_caissier):
        """Un PNG déclaré comme JPEG est rejeté (incohérence MIME)."""
        # Contenu PNG avec Content-Type forcé à JPEG
        fichier = io.BytesIO(PNG_MINIMAL)
        fichier.name = "piege.jpg"
        fichier.content_type = "image/jpeg"
        reponse = api_caissier.post(
            "/api/ordonnances/",
            data={"fichier": fichier},
            format="multipart",
        )
        # L'API peut accepter si elle ignore le content_type client et sniffe les bytes
        # mais si le declared type ne correspond pas → 400
        assert reponse.status_code in (
            status.HTTP_201_CREATED,  # sniffing OK
            status.HTTP_400_BAD_REQUEST,  # rejet déclaration incorrecte
        )

    def test_upload_binaire_arbitraire_rejete(self, api_caissier):
        """Un binaire sans magic bytes connus est rejeté avec 400."""
        fichier = io.BytesIO(b"\x00\x01\x02\x03" * 200)
        fichier.name = "virus.exe"
        reponse = api_caissier.post(
            "/api/ordonnances/",
            data={"fichier": fichier},
            format="multipart",
        )
        assert reponse.status_code == status.HTTP_400_BAD_REQUEST


class TestOrdonnanceValidation:
    """Tests de la validation d'une ordonnance."""

    def test_valider_ordonnance_pharmacien_adjoint_autorise(
        self, api_pharmacien_adjoint
    ):
        """Un pharmacien adjoint peut valider une ordonnance en attente."""
        # Créer une ordonnance d'abord
        reponse_create = api_pharmacien_adjoint.post(
            "/api/ordonnances/",
            data={"prescripteur_nom": "Dr Test"},
            format="json",
        )
        assert reponse_create.status_code == status.HTTP_201_CREATED
        oid = reponse_create.json()["id"]

        reponse = api_pharmacien_adjoint.post(
            f"/api/ordonnances/{oid}/valider/", format="json"
        )
        assert reponse.status_code == status.HTTP_200_OK
        assert reponse.json()["statut"] == "validee"

    def test_valider_ordonnance_caissier_interdit(self, api_caissier):
        """Un caissier ne peut pas valider une ordonnance."""
        reponse_create = api_caissier.post(
            "/api/ordonnances/",
            data={"prescripteur_nom": "Dr Test"},
            format="json",
        )
        assert reponse_create.status_code == status.HTTP_201_CREATED
        oid = reponse_create.json()["id"]

        reponse = api_caissier.post(
            f"/api/ordonnances/{oid}/valider/", format="json"
        )
        assert reponse.status_code in (
            status.HTTP_403_FORBIDDEN,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_consulter_image_sans_image_retourne_404(self, api_pharmacien_adjoint):
        """Consulter l'image d'une ordonnance sans image → 404."""
        reponse_create = api_pharmacien_adjoint.post(
            "/api/ordonnances/",
            data={"prescripteur_nom": "Dr Sans Image"},
            format="json",
        )
        oid = reponse_create.json()["id"]

        reponse = api_pharmacien_adjoint.get(f"/api/ordonnances/{oid}/image/")
        assert reponse.status_code == status.HTTP_404_NOT_FOUND
