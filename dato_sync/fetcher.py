from typing import Type

from dato_sync.sync_options import SyncOptions
from search.config import DatoModel


class Fetcher:
    def __init__(self):
        self.jobs = []

    def register(self, model: Type[DatoModel], options: SyncOptions):
        options.django_model = model
        self.jobs.append(options)

    def fetch(self, force_full_sync: bool):
        pass

fetcher = Fetcher()