from django.db import models


class DatoModel(models.Model):
    dato_id = models.TextField(primary_key=True, blank=False, null=False)

    class Meta:
        abstract = True