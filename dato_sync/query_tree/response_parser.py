from typing import Any

from django.conf import settings
from django.contrib.postgres.fields import ArrayField

from dato_sync.models import DatoModel
from dato_sync.query_tree.constants import DATO_ID_FIELD_NAME, IDS_ALIAS
from dato_sync.query_tree.query_tree import (
    QueryTreeVisitor,
    FlattenedPosition,
    PositionInParent,
    QueryTreeNode,
    QueryTree,
)
from dato_sync.sync_options import SyncOptions
from dato_sync.util import to_camel_case, all_dato_objects_name


class ParserContext:
    def __init__(
        self,
        response: dict,
        localization_responses: dict[str, dict],
        model_path: str,
        path: str = "",
        context: dict[str, Any] | None = None,
        active_object: DatoModel | None = None,
        position_in_parent: int = 0,
    ) -> None:
        self.path = path
        self.model_path = model_path
        self.context = context or dict()
        self.active_object= active_object
        self.response: dict | Any = response
        self.localization_responses: dict[str, dict | Any] = localization_responses
        self.position_in_parent = position_in_parent

    def visit(self, api_name: str) -> list["ParserContext"]:
        sub_response = self.response.get(api_name)
        if not isinstance(sub_response, list):
            sub_response = [sub_response]

        localized_sub_responses = {key: value.get(api_name) for key, value in self.localization_responses.items() if value}
        localized_sub_responses = {key: value if isinstance(value, list) else [value]
                                   for key, value in localized_sub_responses.items()
                                   if value}
        per_object_localized_sub_responses = [dict(zip(localized_sub_responses, object_info))
                                              for object_info in zip(*localized_sub_responses.values())]

        subpath = api_name if not self.path else f"{self.path}.{api_name}"

        if per_object_localized_sub_responses:
            return [
                ParserContext(
                    response=response,
                    localization_responses=localized_response,
                    context=self.context.copy()
                    if self._needs_context_split(subpath)
                    else self.context,
                    model_path=self.model_path,
                    path=subpath,
                    active_object=self.active_object,
                    position_in_parent=position,
                )
                for position, (response, localized_response) in enumerate(
                    zip(sub_response, per_object_localized_sub_responses)
                )
            ]
        else:
            return [
                ParserContext(
                    response=response,
                    localization_responses={},
                    context=self.context.copy()
                    if self._needs_context_split(subpath)
                    else self.context,
                    model_path=self.model_path,
                    path=subpath,
                    active_object=self.active_object,
                    position_in_parent=position,
                )
                for position, response in enumerate(sub_response)
            ]

    def _needs_context_split(self, subpath: str) -> bool:
        # Consider the following GraphQL response:
        #        ┌─────►b──────►c
        # a──────┤
        #        │             ┌──►e1────►id1
        #        │             │
        #        ├─────►d1─────┤
        #        │             └──►f1
        #        │
        #        └─────►d2───┬────►f2
        #                    │
        #                    ├─────►e2───►id2
        #                    │
        #                    └─────►e3───►id3
        #
        # This should result in the following 3 objects (model_path="a.d.e"):
        # id1, f1, c
        # id2, f2, c
        # id3, f2, c
        #
        # To achieve this we copy the context while going along the model_path (so changes from other branches don't affect us) and we
        # allow aliasing along other paths (while making sure to visit those paths first below so the context contains all necessary
        # information by the time we create an object).
        return self.model_path.startswith(subpath)


class ResponseParser(QueryTreeVisitor[list[ParserContext], list[str]]):
    def __init__(self, job: SyncOptions):
        self.job = job
        self.objects: dict[str, DatoModel] = dict()
        root, _, subpath = to_camel_case(self.job.dato_model_path).partition(".")
        self.model_path = f"{all_dato_objects_name(root)}.{subpath}"

    def parse_response(
        self,
        response: dict,
        localization_responses: dict[str, dict],
        query_tree: QueryTree,
    ) -> list[str]:
        self.objects = dict()

        context = ParserContext(
            response=response,
            localization_responses=localization_responses,
            model_path=self.model_path,
        )
        fields = query_tree.visit(self, [context])
        self.job.django_model.objects.bulk_create(
            self.objects.values(),
            update_conflicts=True,
            unique_fields=[DATO_ID_FIELD_NAME],
            update_fields=fields,
        )

        ids_visitor = ResponseParser(self.job)
        special_fields_context = self._visit_contexts([context], IDS_ALIAS)
        special_fields = [field
         for child in query_tree.ids_tree.children
         for field in child.visit(ids_visitor, special_fields_context)]
        if special_fields:
            self.job.django_model.objects.bulk_update(
                ids_visitor.objects.values(),
                fields=special_fields,
            )

        return [obj.dato_identifier for obj in ids_visitor.objects.values()]



    def visit_root(self, root: QueryTree, user_info: list[ParserContext]) -> list[str]:
        return self.visit_intermediate_node(root, user_info)

    def visit_intermediate_node(self, intermediate_node: QueryTreeNode, user_info: list[ParserContext]) -> list[str]:
        next_context = self._visit_contexts(user_info, intermediate_node.api_name)
        if not next_context:
            return []

        # Ensure we collect the entire context before creating objects as described above.
        collect_context_first = (
            lambda c: 1
            if self.model_path.startswith(f"{next_context[0].path}.{c.api_name}")
            else 0
        )

        return [field
                for child in sorted(intermediate_node.children, key=collect_context_first)
                for field in child.visit(self, next_context)]

    def visit_leaf(self, leaf: QueryTreeNode, user_info: list[ParserContext]) -> list[str]:
        default_locale = settings.LANGUAGE_CODE

        for context in user_info:
            value = context.response.get(leaf.api_name)
            if leaf.api_name == "id":
                obj = self.objects.get(value)
                if obj is None:
                    obj = self.job.django_model()
                    self.objects[value] = obj

                for key, context_value in context.context.items():
                    try:
                        setattr(obj, key, context_value)
                    except AttributeError as e:
                        if context.context.get(f"{key}_{default_locale}"):
                            pass # Allow localization without a base field
                        else:
                            raise e

                context.active_object = obj

            try:
                self._set_value_or_context(context, leaf.django_field_name, value)
            except AttributeError as e:
                if leaf.is_localized:
                    pass # Allow localization without a base field
                else:
                    raise e

            if leaf.is_localized and leaf.api_name != "id":
                self._set_value_or_context(context, f"{leaf.django_field_name}_{default_locale}", value)

                for language in (language for language, _ in settings.LANGUAGES if language != default_locale):
                    localized_value = context.localization_responses[language].get(leaf.api_name)
                    self._set_value_or_context(context, f"{leaf.django_field_name}_{language}", localized_value)

        return [] if leaf.api_name == "id" else [leaf.django_field_name]


    def visit_position_in_parent(self, leaf: PositionInParent, user_info: list[ParserContext]) -> list[str]:
        for context in user_info:
            setattr(context.active_object, leaf.django_field_name, context.position_in_parent)

        return [leaf.django_field_name]

    def visit_flattened_position(self, leaf: FlattenedPosition, user_info: list[ParserContext]) -> list[str]:
        for position, context in enumerate(user_info):
            setattr(context.active_object, leaf.django_field_name, position)

        return [leaf.django_field_name]

    @staticmethod
    def _visit_contexts(contexts: list[ParserContext], api_name: str) -> list[ParserContext]:
        return [sub_context
         for context in contexts
         for sub_context in context.visit(api_name)]

    @staticmethod
    def _set_value_or_context(context: ParserContext, key: str, value: Any):
        if context.active_object:
            if isinstance(context.active_object._meta.get_field(key), ArrayField):
                if context.position_in_parent == 0:
                    setattr(context.active_object, key, [])
                getattr(context.active_object, key).append(value)
            else:
                setattr(context.active_object, key, value)
        else:
            context.context[key] = value
