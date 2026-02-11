from django.apps import AppConfig


class DatoSyncConfig(AppConfig):
    name = 'dato_sync'
    verbose_name = "Dato Sync"

    def ready(self):
        from dato_sync.models import handle_dato_sync_registrations

        handle_dato_sync_registrations()
