from typing import Type

from django.conf import settings

from dato_sync.datocms_api import fetch_datocms_content
from dato_sync.sync_options import SyncOptions
from dato_sync.util import to_camel_case
from search.config import DatoModel
from services.models import Scoring


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
            api_name = to_camel_case(job.dato_model_path) # TODO: split
            all_name = f"all{api_name.capitalize()}s"

            sanitized_mappings = [
                mapping if isinstance(mapping, tuple) else (mapping, False, mapping)
                for mapping in job.field_mappings]

            all_fields: list[str] = []
            localized_fields: list[str] = []
            for mapping in sanitized_mappings:
                if mapping[2] == _order_tag:
                    continue

                all_fields.append(mapping[2])
                if mapping[1]:
                    localized_fields.append(mapping[2])

            base_query = self._generate_query(job, all_fields)
            localization_query = self._generate_query(job, localized_fields)

            response = fetch_datocms_content(default_locale, base_query)
            localization_responses = {language: fetch_datocms_content(language, localization_query)
             for language, _ in settings.LANGUAGES
             if language != default_locale}

            for record_index, dato_record in enumerate(response.get(all_name, [])):
                django_object, _ = job.django_model.objects.get_or_create(dato_identifier=dato_record["id"])
                for django_field, isLocalized, dato_field in sanitized_mappings:
                    setattr(django_object, django_field, record_index if dato_field == _order_tag else dato_record[dato_field])

                    if isLocalized:
                        setattr(django_object, f"{django_field}_{default_locale}", dato_record[dato_field])
                        for language in (language for language, _ in settings.LANGUAGES if language != default_locale):
                            localized_record = localization_responses[language].get(all_name, [])[record_index]
                            setattr(django_object, f"{django_field}_{language}", localized_record[dato_field])

                django_object.save()


    def _generate_query(self, job: SyncOptions, fields: list[str]):
        api_name = to_camel_case(job.dato_model_path)  # TODO: split
        all_name = f"all{api_name.capitalize()}s"

        return f"""
           query {job.__name__}Fetch($locale: SiteLocale!) {{
               {all_name}(locale: $locale) {{
                   id
                   {"\n".join(fields)}                        
               }}
           }}
       """

fetcher = Fetcher()