from __future__ import annotations
from typing import Dict, List, Union

from graphql import (GraphQLArgument, GraphQLField, GraphQLList,
                     GraphQLNonNull, GraphQLSchema, GraphQLType,
                     is_introspection_type, is_specified_scalar_type)

from graphql_api import GraphQLAPI
from graphql_api.context import GraphQLContext
from graphql_api.decorators import field, type
from graphql_api.directives import (is_specified_directive,
                                    print_filtered_schema)
from graphql_api.federation.directives import federation_directives, key, link
from graphql_api.federation.types import _Any, federation_types
from graphql_api.mapper import UnionFlagType
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

    if api.root_type is not None: # Should always be true due to call site
        setattr(api.root_type, '_service', _service)
    # api.root_type._service = _service # Original line
    api.types |= set(federation_types)
    api.directives += federation_directives


def add_entity_type(api: GraphQLAPI, schema: GraphQLSchema):
    if api.query_mapper is None:
        # Or raise an error, or handle appropriately
        return schema
    type_registry = api.query_mapper.reverse_registry

    def resolve_entities(root, info, representations: List[Dict]):
        _entities = []
        for representation in representations:
            entity_name = representation.get("__typename")
            entity_type = schema.type_map.get(entity_name)
            entity_python_type = type_registry.get(entity_type)

            if entity_python_type is not None:
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
            else:
                # Handle case where entity_python_type is None, if necessary
                # For example, log a warning or raise an error
                pass # Or raise error if entity_python_type is critical

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

    if api.query_mapper is None:
        # This should ideally not happen if the first check passed,
        # but defensively:
        return schema
    union_entity_type: GraphQLType = api.query_mapper.map_to_union(
        Union[tuple(python_entities)]
    )
    if union_entity_type is None: # If map_to_union can return None
        # Handle this case: maybe raise error or return schema
        # Consider raising a specific error if this state is unexpected
        return schema # Or handle error appropriately

    # Before assigning name, ensure it's a type that can have a name attribute (e.g., not a wrapper)
    # However, map_to_union is expected to return a named type (GraphQLUnionType).
    # For robustness, one might check isinstance, but for now, direct assignment.
    union_entity_type.name = "_Entity"

    # noinspection PyTypeChecker
    schema.type_map["_Entity"] = union_entity_type

    # Guard access to schema.query_type and its fields attribute
    if schema.query_type and hasattr(schema.query_type, 'fields'):
        schema.query_type.fields["_entities"] = GraphQLField(
    else:
        # This case implies a severely misconfigured or unexpected schema state.
        # Depending on application logic, either raise an error or handle gracefully.
        # For now, let's assume this indicates a problem that should halt further processing.
        raise TypeError("schema.query_type is None or does not have a fields attribute.")
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
