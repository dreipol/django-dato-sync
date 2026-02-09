import datetime

from dato_sync.errors import IllegalSyncOptionsError
from dato_sync.sync_options import SyncOptions, DatoFieldPath
from dato_sync.util import (
    _order_tag,
    _flattened_order_tag,
    to_camel_case,
    from_dato_path,
)
from search.api.views import query

_DATO_ID_FIELD_NAME = "dato_identifier"
_META_MAPPINGS = [
    _DATO_ID_FIELD_NAME |from_dato_path("id", localized=True),
    "created" |from_dato_path("_createdAt"),

    # When a block in the parent changes its modified date also changes. The inverse is not true. Additionally, the child may refer to the
    # parent's fields so using the parents modification date (by setting absolute=True) ensures the delta sync works correctly.
    "modified" |from_dato_path("_updatedAt", absolute=True),
]

_IDS_ALIAS = "allIds"


class QueryTreeNode:
    def __init__(
            self,
            path: str,
            job: SyncOptions | None = None,
            django_field_name: str | None = None,
            is_localized: bool | None = None
    ):
        root, _, rest = path.partition(".")
        self.api_name = to_camel_case(root)
        self.children = []
        self.is_localized = False
        if rest:
            self.insert(rest, job, django_field_name, is_localized)

    def insert(self, sub_path, job: SyncOptions | None, django_field_name: str | None, is_localized: bool | None):
        self.is_localized = self.is_localized or is_localized

        child_name, _, rest = sub_path.partition(".")
        child_api_name = to_camel_case(child_name)
        child = next((child for child in self.children if child.api_name == child_api_name), None)
        if rest:
            if child:
                child.insert(rest, job, django_field_name, is_localized)
            else:
                self.children.append(QueryTreeNode(sub_path, job, django_field_name, is_localized))

        elif child:
            raise IllegalSyncOptionsError(job.django_model.__name__, job.__name__, "Cannot map the same field twice")
        elif child_name == _order_tag:
            self.children.append(PositionInParent(django_field_name))
        elif child_name == _flattened_order_tag:
            self.children.append(FlattenedPosition(django_field_name))
        else:
            leaf = QueryTreeNode(child_name)
            leaf._make_leaf(django_field_name, is_localized)
            self.children.append(leaf)

    def _make_leaf(self, django_field_name: str, is_localized: bool):
        self.django_field_name = django_field_name
        self.is_localized = is_localized

    def construct_query(self, localized: bool) -> str | None:
        if localized and not self.is_localized:
            return None
        elif self.children:
            subqueries = [child.construct_query(localized) for child in self.children]
            child_query = "\n".join([subquery for subquery in subqueries if subquery])
            return f"""{to_camel_case(self.api_name)} {{
            {child_query}
            }}"""
        else:
            return self.api_name



class QueryTree(QueryTreeNode):
    def __init__(
            self,
            job: SyncOptions,
            min_date: datetime.datetime | None,
    ):
        super().__init__(job.dato_model_path)
        self.all_name = f"all{self.api_name[0].upper() + self.api_name[1:]}s"
        self.filter_expression = f""", filter: {{_updatedAt: {{gt: "{min_date}"}} }}""" if min_date else ""
        self.query_name = f"{job.__name__}Fetch"
        _, _, self.relative_path = job.dato_model_path.partition(".")
        for mapping in _META_MAPPINGS:
            self.insert_mapping(mapping, job)

        ids_path_components = [self.all_name, self.relative_path, "id"]
        self.ids_tree = QueryTreeNode(
            path=".".join([component for component in ids_path_components if component]),
            job=job,
            django_field_name=_DATO_ID_FIELD_NAME,
            is_localized=False,
        )

    def insert(self, sub_path, job: SyncOptions, django_field_name: str, is_localized: bool):
        super().insert(sub_path, job, django_field_name, is_localized)

    def insert_mapping(self, mapping: DatoFieldPath, job: SyncOptions):
        path = (
            mapping.path
            if mapping.is_absolute or not self.relative_path
            else f"{self.relative_path}.{mapping.path}"
        )
        self.insert(
            sub_path=path,
            job=job,
            django_field_name=mapping.django_field_name,
            is_localized=mapping.is_localized,
        )

    def construct_query(self, localized: bool) -> str | None:
        subqueries = [child.construct_query(localized) for child in self.children]
        child_query = "\n".join([subquery for subquery in subqueries if subquery])

        return f"""
           query {self.query_name}($locale: SiteLocale!) {{
               {self.all_name}(locale: $locale{self.filter_expression}) {{
                   {child_query}
               }}
               {"" if localized else f"""
               {_IDS_ALIAS}: {self.ids_tree.construct_query(localized=False)}   
               """}
           }}
       """


class PositionInParent(QueryTreeNode):
    def __init__(self, django_field_name: str):
        self.django_field_name = django_field_name

    def construct_query(self, localized: bool) -> str | None:
        return None


class FlattenedPosition(QueryTreeNode):
    def __init__(self, django_field_name: str):
        self.django_field_name = django_field_name

    def construct_query(self, localized: bool) -> str | None:
        return None