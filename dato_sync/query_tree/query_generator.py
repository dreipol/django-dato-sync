from dato_sync.query_tree.constants import IDS_ALIAS
from dato_sync.query_tree.query_tree import (
    QueryTreeVisitor,
    QueryTree,
    FlattenedPosition,
    PositionInParent,
    QueryTreeNode,
)
from dato_sync.util import to_camel_case


class QueryGenerator(QueryTreeVisitor[None, str | None]):
    def __init__(self, for_localization: bool):
        self.for_localization = for_localization

    def generate_query(self, query: QueryTree) -> str:
        return query.visit(self, None)

    def visit_root(self, root: QueryTree, user_info: None) -> str | None:
        filter_expression = f""", filter: {{_updatedAt: {{gt: "{root.min_date}"}} }}""" if root.min_date else ""

        subqueries = [child.visit(self, None) for child in root.children]
        child_query = "\n".join([subquery for subquery in subqueries if subquery])

        return f"""
           query {root.query_name}($locale: SiteLocale!) {{
               {root.all_name}(locale: $locale{filter_expression}) {{
                   {child_query}
               }}
               {"" if self.for_localization else f"""
               {IDS_ALIAS}: {root.ids_tree.visit(self, None)}   
               """}
           }}
       """

    def visit_intermediate_node(self, intermediate_node: QueryTreeNode, user_info: None) -> str | None:
        if self.for_localization and not intermediate_node.is_localized:
            return None

        subqueries = [child.visit(self, None) for child in intermediate_node.children]
        child_query = "\n".join([subquery for subquery in subqueries if subquery])
        return f"""{to_camel_case(intermediate_node.api_name)} {{
            {child_query}
        }}"""

    def visit_leaf(self, leaf: QueryTreeNode, user_info: None) -> str | None:
        if self.for_localization and not leaf.is_localized:
            return None

        return leaf.api_name

    def visit_position_in_parent(self, leaf: PositionInParent, user_info: None) -> str | None:
        return None

    def visit_flattened_position(self, leaf: FlattenedPosition, user_info: None) -> str | None:
        return None