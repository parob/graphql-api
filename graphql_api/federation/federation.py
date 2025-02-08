from typing import Dict, List, Union

from graphql import (
    GraphQLSchema,
    GraphQLField,
    GraphQLArgument,
    GraphQLList,
    GraphQLNonNull,
    GraphQLType,
    is_specified_scalar_type,
    is_introspection_type,
)

from graphql_api import GraphQLAPI
from graphql_api.mapper import UnionFlagType
from graphql_api.decorators import type, field
from graphql_api.context import GraphQLContext

from graphql_api.directives import (
    print_filtered_schema,
    is_specified_directive,
)

from graphql_api.federation.directives import (
    federation_directives,
    key,
    link,
)
from graphql_api.federation.types import federation_types, _Any
from graphql_api.schema import get_applied_directives, get_directives


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

    api.root_type._service = _service
    api.types |= set(federation_types)
    api.directives += federation_directives


def add_entity_type(api: GraphQLAPI, schema: GraphQLSchema):
    type_registry = api.query_mapper.reverse_registry

    def resolve_entities(root, info, representations: List[Dict]):
        _entities = []
        for representation in representations:
            entity_name = representation.get("__typename")
            entity_type = schema.type_map.get(entity_name)
            entity_python_type = type_registry.get(entity_type)

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
    python_entities.append(UnionFlagType)

    union_entity_type: GraphQLType = api.query_mapper.map_to_union(
        Union[tuple(python_entities)]
    )
    union_entity_type.name = "_Entity"

    # noinspection PyTypeChecker
    schema.type_map["_Entity"] = union_entity_type

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
    for _type in [*schema.type_map.values()] + [schema]:
        for name, directive in get_directives(_type).items():
            if directive in federation_directives:
                directives[name] = directive

    link(
        **{
            "url": "https://specs.apollo.dev/federation/v2.7",
            "import": [("@" + d.name) for d in directives.values() if d.name != "link"],
        }
    )(schema)
