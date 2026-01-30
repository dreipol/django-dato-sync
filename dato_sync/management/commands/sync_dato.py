from django.core.management import BaseCommand


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("--force-full-sync", nargs="?", const=True, default=False, help="Force full sync")

    def handle(self, *args, **options):
        from dato_sync.fetcher import fetcher

        force_full_sync = options["force_full_sync"]
        fetcher.fetch(force_full_sync)