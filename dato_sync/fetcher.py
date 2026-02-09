import datetime
from typing import Type

from django.conf import settings
from django.db.models import Max

from dato_sync.datocms_api import fetch_datocms_content
from dato_sync.query_tree import QueryTree
from dato_sync.sync_options import SyncOptions, DatoFieldPath
from search.config import DatoModel


class Fetcher:
    def __init__(self):
        self.jobs: list[SyncOptions] = []

    def register(self, model: Type[DatoModel], options: SyncOptions):
        options.django_model = model
        self.jobs.append(options)

    def fetch(self, force_full_sync: bool):
        from dato_sync.util import _order_tag

        default_locale = settings.LANGUAGE_CODE

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

            base_query = query_tree.construct_query(localized=False)
            localization_query = query_tree.construct_query(localized=True)

            response = fetch_datocms_content(default_locale, base_query)
            localization_responses = {language: fetch_datocms_content(language, localization_query)
             for language, _ in settings.LANGUAGES
             if language != default_locale}

            # for record_index, dato_record in enumerate(response.get(all_name, [])):
            #     django_object, _ = job.django_model.objects.get_or_create(dato_identifier=dato_record["id"])
            #     django_object.deleted = False
            #     for django_field, isLocalized, dato_field in sanitized_mappings:
            #         setattr(django_object, django_field, record_index if dato_field == _order_tag else dato_record[dato_field])
            #
            #         if isLocalized:
            #             setattr(django_object, f"{django_field}_{default_locale}", dato_record[dato_field])
            #             for language in (language for language, _ in settings.LANGUAGES if language != default_locale):
            #                 localized_record = localization_responses[language].get(all_name, [])[record_index]
            #                 setattr(django_object, f"{django_field}_{language}", localized_record[dato_field])
            #
            #     django_object.save()
            #
            # all_ids = response.get(_IDS_ALIAS)
            # if all_ids:
            #     (job.django_model.objects
            #      .exclude(dato_identifier__in=[entry["id"] for entry in all_ids])
            #      .update(deleted=True))


    @staticmethod
    def _generate_query(
            job: SyncOptions,
            fields: list[str],
            all_name: str,
            min_date: datetime.datetime,
            fetch_all_ids: bool = False
    ):

        return f"""
           query {job.__name__}Fetch($locale: SiteLocale!) {{
               {all_name}(locale: $locale{filter_expression}) {{
                   id
                   {"\n".join(fields)}                        
               }}
               {"" if not fetch_all_ids else f"""
               {_IDS_ALIAS}: {all_name} {{
                id
               }}               
               """}
           }}
       """

fetcher = Fetcher()