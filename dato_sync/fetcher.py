from typing import Type

from django.conf import settings
from django.db.models import Max

from dato_sync.datocms_api import fetch_datocms_content
from dato_sync.query_tree import QueryTree, QueryGenerator, ResponseParser
from dato_sync.sync_options import SyncOptions, DatoFieldPath
from search.config import DatoModel


class Fetcher:
    def __init__(self):
        self.jobs: list[SyncOptions] = []

    def register(self, model: Type[DatoModel], options: SyncOptions):
        options.django_model = model
        self.jobs.append(options)

    def fetch(self, force_full_sync: bool):
        default_locale = settings.LANGUAGE_CODE

        seen_ids = dict()

        for job in self.jobs:
            sanitized_mappings = [
                mapping if isinstance(mapping, DatoFieldPath) else DatoFieldPath(mapping)
                for mapping in job.field_mappings]

            if force_full_sync:
                min_date = None
            else:
                min_date = job.django_model.objects.aggregate(max_date=Max("modified"))["max_date"]

            query_tree = QueryTree(
                job=job,
                min_date=min_date,
            )

            for mapping in sanitized_mappings:
                query_tree.insert_mapping(mapping, job)

            base_query = QueryGenerator(for_localization=False).generate_query(query_tree)

            response = fetch_datocms_content(default_locale, base_query)
            if any(mapping.is_localized for mapping in sanitized_mappings):
                localization_query = QueryGenerator(for_localization=True).generate_query(query_tree)
                localization_responses = {language: fetch_datocms_content(language, localization_query)
                 for language, _ in settings.LANGUAGES
                 if language != default_locale}
            else:
                localization_responses = dict()

            new_ids = ResponseParser(job).parse_response(response, localization_responses, query_tree)
            ids_set: set[str] = seen_ids.get(job.django_model, set())
            ids_set = ids_set.union(new_ids)
            seen_ids[job.django_model] = ids_set

        for model, ids_set in seen_ids.items():
            (model.objects
             .exclude(dato_identifier__in=ids_set)
             .update(deleted=True))

fetcher = Fetcher()