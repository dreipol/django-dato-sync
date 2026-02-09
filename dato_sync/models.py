from django.db import models


class DatoModel(models.Model):
    dato_identifier = models.TextField(
        primary_key=True,
        blank=False,
        null=False,
        max_length=255
    )

    created = models.DateTimeField(
        verbose_name="created",
        db_index=True,
    )
    modified = models.DateTimeField(
        verbose_name="modified",
        db_index=True,
    )

    deleted = models.BooleanField(default=False)

    class Meta:
        abstract = True


def handle_dato_sync_registrations():
    """
        Auto-discover INSTALLED_APPS translation.py modules and fail silently when
        not present. This forces an import on them to register.
        Also import explicit modules.
        """
    import copy
    from importlib import import_module

    from django.apps import apps
    from django.utils.module_loading import module_has_submodule

    from dato_sync.fetcher import fetcher

    mods = [(app_config.name, app_config.module) for app_config in apps.get_app_configs()]

    for app, mod in mods:
        # Attempt to import the app's dato_sync module.
        module = "%s.dato_sync" % app
        before_import_jobs = copy.copy(fetcher.jobs)
        try:
            import_module(module)
        except ImportError:
            # Reset the model registry to the state before the last import as
            # this import will have to reoccur on the next request and this
            # could raise NotRegistered and AlreadyRegistered exceptions
            fetcher.jobs = before_import_jobs

            # Decide whether to bubble up this error. If the app just
            # doesn't have a dato_sync module, we can ignore the error
            # attempting to import it, otherwise we want it to bubble up.
            if module_has_submodule(mod, "dato_sync"):
                raise