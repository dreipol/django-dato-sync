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


class ParserContext:
    def __init__(
            self,
            response: dict,
            localization_responses: dict[str, dict],
            context: dict[str, Any] | None = None,
            active_object: DatoModel | None = None,
            position_in_parent: int = 0,
    ) -> None:
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

        if per_object_localized_sub_responses:
            return [ParserContext(
                response=response,
                localization_responses=localized_response,
                context=self.context.copy(),
                active_object=self.active_object,
                position_in_parent=position
            )
             for position, (response, localized_response) in enumerate(zip(sub_response, per_object_localized_sub_responses))]
        else:
            return [ParserContext(
                response=response,
                localization_responses={},
                context=self.context.copy(),
                active_object=self.active_object,
                position_in_parent=position,
            )
                for position, response in enumerate(sub_response)]


class ResponseParser(QueryTreeVisitor[list[ParserContext], list[str]]):
    def __init__(self, job: SyncOptions):
        self.job = job
        self.objects: dict[str, DatoModel] = dict()

    def parse_response(self, response: dict, localization_responses: dict[str, dict], query_tree: QueryTree) -> list[str]:
        self.objects = dict()
        context = ParserContext(response, localization_responses)
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
        return [field
                for child in intermediate_node.children
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

                for key, value in context.context.items():
                    setattr(obj, key, value)
                context.active_object = obj

            self._set_value_or_context(context, leaf.django_field_name, value)
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
