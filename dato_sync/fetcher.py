from datetime import datetime
from typing import Type

from django.conf import settings
from django.db.models import Max, Q

from dato_sync.datocms_api import fetch_datocms_content
from dato_sync.errors import IllegalSyncOptionsError
from dato_sync.models import DatoModel
from dato_sync.query_tree import QueryTree, QueryGenerator, ResponseParser
from dato_sync.sync_options import SyncOptions, DatoFieldPath


class Fetcher:
    def __init__(self):
        self.jobs: list[SyncOptions] = []

    def register(self, model: Type[DatoModel], options: SyncOptions):
        options.django_model = model
        _run_sanity_checks(options)
        self.jobs.append(options)

    def fetch(self, force_full_sync: bool):
        default_locale = settings.LANGUAGE_CODE

        seen_ids = dict()
        min_date_map = dict() if force_full_sync else _create_min_date_map(self.jobs)

        for job in self.jobs:
            sanitized_mappings = [
                mapping if isinstance(mapping, DatoFieldPath) else DatoFieldPath(mapping)
                for mapping in job.field_mappings]

            min_date = min_date_map.get(job.django_model)

            query_tree = QueryTree(
                job=job,
                min_date=min_date,
            )

            for mapping in sanitized_mappings:
                query_tree.insert_mapping(mapping, job)

            base_query = QueryGenerator(for_localization=False).generate_query(query_tree)

            has_localized_fields = any(mapping.is_localized for mapping in sanitized_mappings)
            localization_query = QueryGenerator(for_localization=True).generate_query(query_tree) if has_localized_fields else None

            last_page_full = True
            current_page = 0
            while last_page_full:
                response = fetch_datocms_content(default_locale, base_query, page=current_page)
                if has_localized_fields and localization_query is not None:
                    localization_responses = {
                        language: fetch_datocms_content(language, localization_query, page=current_page)
                        for language, _ in settings.LANGUAGES
                        if language != default_locale
                    }
                else:
                    localization_responses = dict()

                new_ids, last_page_full = ResponseParser(job).parse_response(response, localization_responses, query_tree)
                ids_set: set[str] = seen_ids.get(job.django_model, set())
                ids_set = ids_set.union(new_ids)
                seen_ids[job.django_model] = ids_set

                current_page += 1

        for model, ids_set in seen_ids.items():
            (model.objects
             .update(deleted=~Q(dato_identifier__in=ids_set)))

fetcher = Fetcher()

def _run_sanity_checks(options: SyncOptions):
    reserved_names = [field.name for field in DatoModel._meta.fields]

    for mapping in options.field_mappings:
        field_name: str = mapping.django_field_name if isinstance(mapping, DatoFieldPath) else mapping
        if field_name in reserved_names:
            raise IllegalSyncOptionsError(options.django_model.__name__, options.__name__, f"{field_name} is reserved and should not be mapped manually. It will be populated automatically.")


def _create_min_date_map(jobs: list[SyncOptions]) -> dict[DatoModel, datetime | None]:
    models: set[DatoModel] = {job.django_model for job in jobs}
    return {model: model.objects.aggregate(max_date=Max("modified"))["max_date"] for model in models}