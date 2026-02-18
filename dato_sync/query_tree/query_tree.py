import datetime
from abc import ABC, abstractmethod
from typing import TypeVar, Generic

from dato_sync.errors import IllegalSyncOptionsError
from dato_sync.query_tree.constants import DATO_ID_FIELD_NAME
from dato_sync.sync_options import SyncOptions, DatoFieldPath
from dato_sync.util import (
    _order_tag,
    _flattened_order_tag,
    to_camel_case,
    from_dato_path,
    all_dato_objects_name,
)

# ⚠️ it's important that the id field always comes first, so the parser will create new objects before filling other fields
def _meta_mappings(base_name) -> list[DatoFieldPath]:
    return [
        DATO_ID_FIELD_NAME |from_dato_path("id", localized=True),
        "created" |from_dato_path("_createdAt"),

        # When a block in the parent changes its modified date also changes. The inverse is not true. Additionally, the child may refer to the
        # parent's fields so using the parents modification date (by setting absolute=True) ensures the delta sync works correctly.
        "modified" |from_dato_path(f"{base_name}._updatedAt", absolute=True),
    ]


UserInfo = TypeVar("UserInfo")
ReturnType = TypeVar("ReturnType")


class QueryTreeVisitor(Generic[UserInfo, ReturnType], ABC):
    @abstractmethod
    def visit_root(self, root: "QueryTree", user_info: UserInfo) -> ReturnType:
        pass

    @abstractmethod
    def visit_intermediate_node(self, intermediate_node: "QueryTreeNode", user_info: UserInfo) -> ReturnType:
        pass

    @abstractmethod
    def visit_leaf(self, leaf: "QueryTreeNode", user_info: UserInfo) -> ReturnType:
        pass

    @abstractmethod
    def visit_position_in_parent(self, leaf: "PositionInParent", user_info: UserInfo) -> ReturnType:
        pass

    @abstractmethod
    def visit_flattened_position(self, leaf: "FlattenedPosition", user_info: UserInfo) -> ReturnType:
        pass


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

    def visit(self, visitor: QueryTreeVisitor[UserInfo, ReturnType], user_info: UserInfo) -> ReturnType:
        if self.children:
            return visitor.visit_intermediate_node(self, user_info)
        else:
            return visitor.visit_leaf(self, user_info)


class QueryTree(QueryTreeNode):
    def __init__(
            self,
            job: SyncOptions,
            min_date: datetime.datetime | None,
    ):
        super().__init__(job.dato_model_path)
        self.min_date = min_date
        base_name = self.api_name

        self.api_name = all_dato_objects_name(base_name)
        self.query_name = f"{job.__name__}Fetch"
        _, _, self.relative_path = job.dato_model_path.partition(".")
        # ⚠️ it's important that the id field always comes first, so the parser will create new objects before filling other fields
        for mapping in _meta_mappings(base_name):
            self.insert_mapping(mapping, job)

        ids_path_components = [self.api_name, self.relative_path, "id"]
        self.ids_tree = QueryTreeNode(
            path=".".join([component for component in ids_path_components if component]),
            job=job,
            django_field_name=DATO_ID_FIELD_NAME,
            is_localized=False,
        )

    def insert(self, sub_path, job: SyncOptions, django_field_name: str, is_localized: bool):
        _, _, dato_field_name = sub_path.rpartition(".")
        if dato_field_name == _order_tag or dato_field_name == _flattened_order_tag:
            self.ids_tree.insert(sub_path, job, django_field_name, is_localized)
        else:
            super().insert(sub_path, job, django_field_name, is_localized)

    def insert_mapping(self, mapping: DatoFieldPath, job: SyncOptions):
        if mapping.is_absolute:
            root, _, subpath = mapping.path.partition(".")
            root_name = f"all{root[0].upper() + root[1:]}s"
            if self.api_name != root_name:
                raise IllegalSyncOptionsError(job.django_model.__name__, job.__name__, "All mappings must access the same dato model!")

        elif not self.relative_path:
            subpath = mapping.path

        else:
            subpath = f"{self.relative_path}.{mapping.path}"

        self.insert(
            sub_path=subpath,
            job=job,
            django_field_name=mapping.django_field_name,
            is_localized=mapping.is_localized,
        )

    def visit(self, visitor: QueryTreeVisitor[UserInfo, ReturnType], user_info: UserInfo) -> ReturnType:
        return visitor.visit_root(self, user_info)


class PositionInParent(QueryTreeNode):
    def __init__(self, django_field_name: str):
        self.django_field_name = django_field_name
        self.api_name = None

    def visit(self, visitor: QueryTreeVisitor[UserInfo, ReturnType], user_info: UserInfo) -> ReturnType:
        return visitor.visit_position_in_parent(self, user_info)


class FlattenedPosition(QueryTreeNode):
    def __init__(self, django_field_name: str):
        self.django_field_name = django_field_name
        self.api_name = None

    def visit(self, visitor: QueryTreeVisitor[UserInfo, ReturnType], user_info: UserInfo) -> ReturnType:
        return visitor.visit_flattened_position(self, user_info)