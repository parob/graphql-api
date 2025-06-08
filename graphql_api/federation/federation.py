from __future__ import annotations
from typing import Dict, List, Union, get_origin, get_args, Optional

from graphql import (GraphQLArgument, GraphQLField, GraphQLList, # Removed test-specific imports
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


@type
class _Service: # Reverted to _Service
    def __init__(self, sdl_strip_federation_definitions: bool = True):
        self.sdl_strip_federation_definitions = sdl_strip_federation_definitions

    @field
    def sdl(self, context: GraphQLContext) -> str:
        # Access self.sdl_strip_federation_definitions
        # The directive_filter and type_filter need to be defined here,
        # or be methods/staticmethods of _Service that can access it.

        def directive_filter(n):
            return not is_specified_directive(n) and (
                not self.sdl_strip_federation_definitions # Use self.
                or n not in federation_directives
            )

        def type_filter(n):
            return (
                not is_specified_scalar_type(n)
                and not is_introspection_type(n)
                and (
                    not self.sdl_strip_federation_definitions # Use self.
                    or (n not in federation_types and n.name != "_Service") # Reverted
                )
            )

        schema_str = print_filtered_schema( # Renamed from schema to schema_str to avoid conflict
            context.schema, directive_filter, type_filter
        )

        schema_str = schema_str.replace(
            "  _entities(representations: [_Any!]!): [_Entity]!\n", ""
        )
        schema_str = schema_str.replace("  _service: _Service!\n", "")
        return schema_str


def add_federation_types(
    api: GraphQLAPI, sdl_strip_federation_definitions: bool = True
):
    # _Service class is now at module level

    # This resolver function will be attached to the root type.
    # It needs to close over sdl_strip_federation_definitions.
    @field
    def _service_resolver(self) -> _Service: # Reverted
        # Pass the flag from the outer function's scope
        return _Service(sdl_strip_federation_definitions=sdl_strip_federation_definitions) # Instantiate _Service

    if api.root_type is not None:
        # Attach the resolver to the root_type. The actual field name on the GraphQL type will be '_service'.
        # The name of the Python method is `_service_resolver`.
        setattr(api.root_type, '_service', _service_resolver) # Reverted

    api.types |= set(federation_types)
    # Add _Service type itself to the API's recognized types if not automatically picked up
    # This might be necessary if _Service is not referenced elsewhere in a way that api.mapper would find it.
    # However, since it's the return type of a field on the root_type, it should be picked up.
    # Let's add it explicitly for safety for now, can be removed if redundant. / Removed to see if it changes behavior
    # api.types.add(_Service)
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

            # Targeted fix for ProblematicOptional has been removed.
            # The fix should be in the mapper's reverse_registry population.

            if entity_python_type is None:
                # This means the __typename didn't map to a known Python class.
                # This case should ideally be handled by schema validation or earlier checks.
                # Depending on federation spec, might need to return null for this entity or raise.
                # For now, let's skip this representation or signal an error.
                # This path is less likely to be the source of "Optional._resolve_reference" directly
                # unless type_registry.get() itself returns None for an entity_type that should exist.
                _entities.append(None) # Or handle error
                continue

            actual_entity_type_for_resolver = entity_python_type

            if entity_python_type is Union: # Check for plain Union (typing.Union)
                 raise NotImplementedError(
                    f"Cannot resolve reference for __typename '{entity_name}'. "
                    f"The Python type resolved to `typing.Union` itself, which is not a concrete entity."
                )
            if entity_python_type is list: # Check for plain list (typing.List)
                 raise NotImplementedError(
                    f"Cannot resolve reference for __typename '{entity_name}'. "
                    f"The Python type resolved to `typing.List` itself, which is not a concrete entity."
                )

            # Check if entity_python_type is Optional[X] (i.e., Union[X, NoneType])
            origin = get_origin(entity_python_type)

            if entity_python_type is origin and entity_python_type is Union: # e.g. entity_python_type is typing.Union without params
                # This should have been caught by `entity_python_type is Union` but origin check makes it more robust
                 raise NotImplementedError(
                    f"Cannot resolve reference for __typename '{entity_name}'. "
                    f"The Python type resolved to `typing.Union` (origin) itself."
                )

            if origin is Union: # Covers Union[X, NoneType] which is Optional[X]
                args = get_args(entity_python_type)
                if type(None) in args: # Confirms it's an Optional type
                    # Filter out NoneType to get the actual type X
                    actual_args = [arg for arg in args if arg is not type(None)]
                    if len(actual_args) == 1:
                        actual_entity_type_for_resolver = actual_args[0]
                    elif not actual_args: # This means it was Optional[NoneType]
                         raise NotImplementedError(
                            f"Cannot resolve reference for '{entity_name}'. "
                            f"Type was Optional[NoneType]."
                        )
                    else: # This means it was Union[A, B, ..., NoneType]
                        raise NotImplementedError(
                            f"Cannot resolve reference for '{entity_name}'. "
                            f"Type was Union of multiple types including None: {entity_python_type}."
                        )
            # It's okay if origin is None and entity_python_type is a concrete class (e.g. User).
            # It's also okay if origin is a generic like list/List, dict/Dict IF _resolve_reference was on them (it's not).
            # The key is actual_entity_type_for_resolver must be a class with _resolve_reference.

            # Now use actual_entity_type_for_resolver to find _resolve_reference
            resolve_reference_method = getattr(actual_entity_type_for_resolver, "_resolve_reference", None)

            if not callable(resolve_reference_method):
                # More detailed error
                err_msg = (
                    f"Federation method `{actual_entity_type_for_resolver.__name__}._resolve_reference` "
                    f"is not implemented or not callable for __typename '{entity_name}' "
                    f"(representation: '{representation}'). "
                )
                if entity_python_type is not actual_entity_type_for_resolver:
                    err_msg += (f"Original Python type was '{entity_python_type}' which resolved to "
                                f"'{actual_entity_type_for_resolver.__name__}'. ")
                else:
                    err_msg += f"Python type is '{entity_python_type.__name__}'. "

                if entity_python_type is Optional: # Specifically check if it was typing.Optional origin
                     err_msg += "The type resolved to `typing.Optional` itself, not `Optional[ConcreteType]`. Check type registry."

                raise NotImplementedError(err_msg)

            # noinspection PyProtectedMember
            resolved_entity = resolve_reference_method(representation)
            _entities.append(resolved_entity)

        return _entities

    def is_entity(_type: GraphQLType):
        for schema_directive in get_applied_directives(_type):
            if schema_directive.directive == key:
                return True
        return False

    python_entities = [
        type_registry.get(t) for t in schema.type_map.values() if is_entity(t)
    ]
    # Filter out any None values that might have come from type_registry.get()
    # if a GraphQL type considered an entity doesn't have a corresponding Python class registered.
    valid_python_entities = [entity for entity in python_entities if entity is not None]
    valid_python_entities.append(UnionFlagType) # Ensures it's treated as a Union by the mapper

    if api.query_mapper is None:
        # This should ideally not happen if the first check passed,
        # but defensively:
        return schema
    union_entity_type: GraphQLType = api.query_mapper.map_to_union(
        Union[tuple(valid_python_entities)]
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
            type_=GraphQLNonNull(GraphQLList(union_entity_type)),
            args={
                "representations": GraphQLArgument(
                    type_=GraphQLNonNull(GraphQLList(GraphQLNonNull(_Any)))
                )
            },
            resolve=resolve_entities,
        )
    else:
        # This case implies a severely misconfigured or unexpected schema state.
        # Depending on application logic, either raise an error or handle gracefully.
        # For now, let's assume this indicates a problem that should halt further processing.
        raise TypeError("schema.query_type is None or does not have a fields attribute.")

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
