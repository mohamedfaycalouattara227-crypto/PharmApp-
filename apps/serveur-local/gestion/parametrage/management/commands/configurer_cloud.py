"""
Commande Django : python manage.py configurer_cloud

Configure la connexion de ce serveur local vers le Cloud PharmApp.
À exécuter une seule fois lors de l'onboarding, ou après rotation de clé.

Usage :
    python manage.py configurer_cloud \\
        --officine-id 550e8400-e29b-41d4-a716-446655440000 \\
        --code PHA-001 \\
        --url https://cloud.pharmapp.bf \\
        --cle phk_xK9mP...

    python manage.py configurer_cloud --rotation --cle phk_nouvelle_cle...
    python manage.py configurer_cloud --statut
"""

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Configure ou met à jour la connexion vers le Cloud PharmApp."

    def add_arguments(self, parser):
        parser.add_argument(
            "--officine-id",
            type=str,
            help="UUID de l'officine attribué par le cloud au provisionnement.",
        )
        parser.add_argument(
            "--code",
            type=str,
            help='Code court de la pharmacie (ex: "PHA-001").',
        )
        parser.add_argument(
            "--url",
            type=str,
            default="https://cloud.pharmapp.bf",
            help="URL de base de l'API cloud.",
        )
        parser.add_argument(
            "--cle",
            type=str,
            help="Clé API complète (phk_...) reçue lors du provisionnement.",
        )
        parser.add_argument(
            "--rotation",
            action="store_true",
            help="Mode rotation de clé — met à jour uniquement la clé API.",
        )
        parser.add_argument(
            "--statut",
            action="store_true",
            help="Affiche le statut de la connexion cloud sans modifier la configuration.",
        )

    def handle(self, *args, **options):
        from gestion.parametrage.models_cloud import OfficineParametrage
        from gestion.parametrage.services_cloud import ServiceParametrageCloud

        # ── Affichage du statut ────────────────────────────────────────────
        if options["statut"]:
            config = OfficineParametrage.obtenir()
            if config.est_configure:
                self.stdout.write(self.style.SUCCESS("✓ Connexion cloud configurée"))
                self.stdout.write(f"  Officine ID : {config.officine_id}")
                self.stdout.write(f"  Code        : {config.code_officine}")
                self.stdout.write(f"  URL cloud   : {config.cloud_api_url}")
                self.stdout.write(f"  Préfixe clé : {config.prefixe_cle}")
                self.stdout.write(f"  Configuré le: {config.configure_le}")
            else:
                self.stdout.write(self.style.WARNING("⚠ Connexion cloud non configurée."))
                self.stdout.write(
                    "  Exécutez : python manage.py configurer_cloud "
                    "--officine-id <UUID> --code <PHA-XXX> --cle <phk_...>"
                )
            return

        # ── Rotation de clé ────────────────────────────────────────────────
        if options["rotation"]:
            cle = options.get("cle")
            if not cle:
                raise CommandError("--cle est requis pour une rotation.")
            try:
                ServiceParametrageCloud.mettre_a_jour_cle(cle)
                self.stdout.write(
                    self.style.SUCCESS(f"✓ Clé API mise à jour (préfixe: {cle[:8]})")
                )
            except ValueError as exc:
                raise CommandError(str(exc)) from exc
            return

        # ── Configuration initiale ─────────────────────────────────────────
        officine_id = options.get("officine_id")
        code = options.get("code")
        url = options.get("url")
        cle = options.get("cle")

        manquants = [n for n, v in [
            ("--officine-id", officine_id),
            ("--code", code),
            ("--url", url),
            ("--cle", cle),
        ] if not v]

        if manquants:
            raise CommandError(
                f"Paramètres manquants : {', '.join(manquants)}. "
                "Utilisez --statut pour voir la configuration actuelle."
            )

        try:
            ServiceParametrageCloud.configurer(
                officine_id=officine_id,
                code_officine=code,
                cloud_api_url=url,
                cle_api=cle,
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f"✓ Connexion cloud configurée — {code} → {url}"
                )
            )
            self.stdout.write(
                "  Testez avec : python manage.py configurer_cloud --statut"
            )
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
