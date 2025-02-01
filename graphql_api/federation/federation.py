from typing import Dict, List, Union

from graphql import (
    GraphQLSchema,
    GraphQLField,
    GraphQLArgument,
    GraphQLList,
    GraphQLNonNull,
    GraphQLType,
)

from graphql_api import GraphQLAPI
from graphql_api.mapper import UnionFlagType
from graphql_api.decorators import type, field
from graphql_api.context import GraphQLContext

from graphql_api.directives import is_defined_type, print_filtered_schema, is_specified_directive

from graphql_api.federation.directives import federation_directives, key
from graphql_api.federation.types import federation_types, _Any


@type
class _Service:
    @field
    def sdl(self, context: GraphQLContext) -> str:
        def directive_filter(n):
            return not is_specified_directive(n) and n not in federation_directives

        def type_filter(n):
            return (
                is_defined_type(n)
                and n not in federation_types
                and not n.name == "_Service"
            )

        printed_directives = []

        schema = print_filtered_schema(
            context.schema, directive_filter, type_filter, printed_directives
        )

        schema = schema.replace("  _service: _Service!\n", "")
        imported_directives = str(
            ["@" + directive.directive.name for directive in printed_directives]
        ).replace("'", '"')

        extends_schema = (
            f"\n\nextend schema @link(url: "
            f'"https://specs.apollo.dev/federation/v2.3", '
            f"import: {imported_directives})"
        )

        return schema + extends_schema


@field
def _service(self) -> _Service:
    return _Service()


def apply_federation_api(api: GraphQLAPI):
    api.root_type._service = _service
    api.types |= set(federation_types)
    api.directives += federation_directives


def apply_federation_schema(api: GraphQLAPI, schema: GraphQLSchema):
    type_registry = api.query_mapper.reverse_registry

    def resolve_entities(root, info, representations: List[Dict]):
        _entities = []
        for representation in representations:
            entity_name = representation.get(("__typename"))
            entity_type = schema.type_map.get(entity_name)
            entity_python_type = type_registry.get(entity_type)

            if callable(getattr(entity_python_type, "_resolve_reference", None)):
                # noinspection PyProtectedMember
                _entities.append(entity_python_type._resolve_reference(representation))
            else:
                _entities.append(None)

        return _entities

    def is_entity(_type: GraphQLType):
        schema_directives = getattr(_type, "_schema_directives", [])
        for schema_directive in schema_directives:
            if schema_directive.directive == key:
                return True
        return False

    entities = [type_registry.get(t) for t in schema.type_map.values() if is_entity(t)]
    entities.append(UnionFlagType)

    union_type: GraphQLType = api.query_mapper.map_to_union(Union[tuple(entities)])
    union_type.name = "_Entity"

    # noinspection PyTypeChecker
    schema.type_map["_Entity"] = union_type

    schema.query_type.fields["_entities"] = GraphQLField(
        type_=GraphQLNonNull(GraphQLList(union_type)),
        args={
            "representations": GraphQLArgument(
                type_=GraphQLNonNull(GraphQLList(GraphQLNonNull(_Any)))
            )
        },
        resolve=resolve_entities,
    )
    return schema
