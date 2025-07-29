from typing import Dict, List, Union, cast

from graphql import (
    GraphQLArgument,
    GraphQLField,
    GraphQLList,
    GraphQLNonNull,
    GraphQLSchema,
    GraphQLType,
    GraphQLUnionType,
    is_introspection_type,
    is_specified_scalar_type,
)

from graphql_api import GraphQLAPI
from graphql_api.context import GraphQLContext
from graphql_api.decorators import field, type
from graphql_api.directives import (
    is_specified_directive,
    print_filtered_schema,
    SchemaDirective,
)
from graphql_api.federation.directives import federation_directives, key, link
from graphql_api.federation.types import _Any, federation_types
from graphql_api.mapper import UnionFlagType
from graphql_api.schema import get_applied_directives


def add_federation_types(
    api: GraphQLAPI, sdl_strip_federation_definitions: bool = True
):
    @type
    class _Service:
        @field
        def sdl(self, context: GraphQLContext) -> str:
            def directive_filter(n):
                return not is_specified_directive(n) and (
                    not sdl_strip_federation_definitions
                    or n not in federation_directives
                )

            def type_filter(n):
                return (
                    not is_specified_scalar_type(n)
                    and not is_introspection_type(n)
                    and (
                        not sdl_strip_federation_definitions
                        or (n not in federation_types and n.name != "_Service")
                    )
                )

            if not context.schema:
                return ""

            schema = print_filtered_schema(
                context.schema, directive_filter, type_filter
            )

            # remove the federation types from the SDL
            schema = schema.replace(
                "  _entities(representations: [_Any!]!): [_Entity]!\n", ""
            )
            schema = schema.replace("  _service: _Service!\n", "")

            return schema

    @field
    def _service(self) -> _Service:
        return _Service()

    if api.root_type:
        api.root_type._service = _service
    api.types |= set(federation_types)
    api.directives += federation_directives


def add_entity_type(api: GraphQLAPI, schema: GraphQLSchema):
    if not api.query_mapper:
        return schema

    type_registry = api.query_mapper.reverse_registry

    def resolve_entities(root, info, representations: List[Dict]):
        _entities = []
        for representation in representations:
            entity_name = representation.get("__typename")
            if not entity_name:
                continue
            entity_type = schema.type_map.get(entity_name)
            if not entity_type:
                continue

            entity_python_type = type_registry.get(entity_type)
            if not entity_python_type:
                continue

            if callable(getattr(entity_python_type, "_resolve_reference", None)):
                # noinspection PyProtectedMember
                _entities.append(entity_python_type._resolve_reference(representation))
            else:
                raise NotImplementedError(
                    f"Federation method '{entity_python_type.__name__}"
                    f"._resolve_reference(representation: _Any!): _Entity' is not "
                    f"implemented. Implement the '_resolve_reference' on class "
                    f"'{entity_python_type.__name__}' to enable Entity support."
                )

        return _entities

    def is_entity(_type: GraphQLType):
        for schema_directive in get_applied_directives(_type):
            if schema_directive.directive == key:
                return True
        return False

    python_entities = [
        type_registry.get(t) for t in schema.type_map.values() if is_entity(t)
    ]
    python_entities = [p for p in python_entities if p]

    if not python_entities:
        return schema

    python_entities.append(UnionFlagType)

    union_type = Union[*python_entities]  # type: ignore

    union_entity_type: GraphQLUnionType = cast(
        GraphQLUnionType, api.query_mapper.map_to_union(union_type)  # type: ignore
    )
    union_entity_type.name = "_Entity"

    # noinspection PyTypeChecker
    schema.type_map["_Entity"] = union_entity_type

    if schema.query_type:
        schema.query_type.fields["_entities"] = GraphQLField(
            type_=GraphQLNonNull(GraphQLList(union_entity_type)),
            args={
                "representations": GraphQLArgument(
                    type_=GraphQLNonNull(GraphQLList(GraphQLNonNull(_Any)))
                )
            },
            resolve=resolve_entities,
        )

    return schema


def link_directives(schema: GraphQLSchema):
    directives = {}
    for item in list(schema.type_map.values()) + [schema]:
        for applied_directive in get_applied_directives(item):
            if applied_directive.directive in federation_directives:
                directives[applied_directive.directive.name] = applied_directive

    if directives:
        cast(SchemaDirective, link)(  # type: ignore
            **{
                "url": "https://specs.apollo.dev/federation/v2.7",
                "import": [
                    ("@" + d.directive.name)
                    for d in directives.values()
                    if d.directive.name != "link"
                ],
            }
        )(schema)
