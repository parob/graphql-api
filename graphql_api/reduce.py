from typing import List

from graphql import GraphQLList, GraphQLNonNull, GraphQLObjectType
from graphql.type.definition import GraphQLInterfaceType

from graphql_api.mapper import (GraphQLMetaKey, GraphQLMutableField,
                                GraphQLTypeMapError)
from graphql_api.utils import has_mutable, iterate_fields, to_snake_case


class GraphQLFilter:
    def filter_field(self, name, meta: dict) -> bool:
        """
        Return True to filter (remove) a field from the schema
        """
        raise NotImplementedError()


class TagFilter(GraphQLFilter):
    def __init__(self, tags: List[str] = None):
        """
        Remove any fields that are tagged with a tag in tags
        """
        self.tags = tags

    def filter_field(self, name: str, meta: dict) -> bool:
        tags = meta.get("tags", [])

        for tag in tags:
            if tag in self.tags:
                return True

        return False


class GraphQLSchemaReducer:
    @staticmethod
    def reduce_query(mapper, root, filters=None):
        query: GraphQLObjectType = mapper.map(root)

        # Remove any types that have no fields
        # (and remove any fields that returned that type)
        invalid_types, invalid_fields = GraphQLSchemaReducer.invalid(
            root_type=query, filters=filters, meta=mapper.meta
        )

        for type_, key in invalid_fields:
            del type_.fields[key]

        for key, value in dict(mapper.registry).items():
            if value in invalid_types:
                del mapper.registry[key]

        return query

    @staticmethod
    def reduce_mutation(mapper, root):
        mutation: GraphQLObjectType = mapper.map(root)

        # Trigger dynamic fields to be called
        for _ in iterate_fields(mutation):
            pass

        # Find all mutable Registry types
        filtered_mutation_types = {root}
        for type_ in mapper.types():
            if has_mutable(type_, interfaces_default_mutable=False):
                filtered_mutation_types.add(type_)

        # Replace fields that have no mutable
        # subtypes with their non-mutable equivalents

        for type_, key, field in iterate_fields(mutation):
            field_type = field.type
            meta = mapper.meta.get((type_.name, to_snake_case(key)), {})
            field_definition_type = meta.get("graphql_type", "field")

            wraps = []
            while isinstance(field_type, (GraphQLNonNull, GraphQLList)):
                wraps.append(field_type.__class__)
                field_type = field_type.of_type

            if meta.get(GraphQLMetaKey.resolve_to_mutable):
                # Flagged as mutable
                continue

            if field_definition_type == "field":
                if (
                    mapper.suffix in str(field_type)
                    or field_type in filtered_mutation_types
                ):
                    # Calculated as it as mutable
                    continue

            # convert it to immutable
            query_type_name = str(field_type).replace(mapper.suffix, "", 1)
            query_type = mapper.registry.get(query_type_name)

            if query_type:
                for wrap in wraps:
                    query_type = wrap(query_type)
                field.type = query_type

        # Remove any query fields from mutable types
        fields_to_remove = set()
        # Only apply this aggressive field removal to the actual root mutation type's fields
        if isinstance(mutation, GraphQLObjectType): # mutation is the root mutation type, e.g. RootMutable
            root_mutation_type_obj = mutation # Clarity
            # Unwrap if it's NonNull or List (though root mutation type usually isn't)
            # This unwrap logic might be redundant if 'mutation' is always the direct GraphQLObjectType
            # type_to_inspect_for_fields = mutation
            # while isinstance(type_to_inspect_for_fields, (GraphQLNonNull, GraphQLList)):
            #    type_to_inspect_for_fields = type_to_inspect_for_fields.of_type

            # if isinstance(type_to_inspect_for_fields, GraphQLObjectType): # Ensure it's an object type after unwrapping
            #    root_mutation_type_obj = type_to_inspect_for_fields

            interface_fields = []
            for interface in root_mutation_type_obj.interfaces: # Use root_mutation_type_obj
                interface_fields += [key for key, field in interface.fields.items()]

            for key, field in root_mutation_type_obj.fields.items(): # Use root_mutation_type_obj
                if (
                    key not in interface_fields
                    and not isinstance(field, GraphQLMutableField)
                    and not has_mutable(field.type)
                ):
                    # Add only fields from the root mutation type itself for removal
                    fields_to_remove.add((root_mutation_type_obj, key))

        # The old loop iterated all types in filtered_mutation_types.
        # This was too broad and removed fields from payload types like PersonMutable.
        # By restricting the above collection of fields_to_remove to only the root 'mutation' type,
        # other types in filtered_mutation_types (like PersonMutable) will not have their readable fields removed.

        for type_, key in fields_to_remove:
            # Ensure field still exists before attempting deletion, good practice
            if hasattr(type_, 'fields') and key in type_.fields:
                 del type_.fields[key]

        return mutation

    @staticmethod
    def invalid(
        root_type,
        filters=None,
        meta=None,
        checked_types=None,
        invalid_types=None,
        invalid_fields=None,
    ):
        if not checked_types:
            checked_types = set()

        if not invalid_types:
            invalid_types = set()

        if not invalid_fields:
            invalid_fields = set()

        if root_type in checked_types:
            return invalid_types, invalid_fields

        checked_types.add(root_type)

        try:
            fields = root_type.fields
        except (AssertionError, GraphQLTypeMapError):
            invalid_types.add(root_type)
            return invalid_types, invalid_fields

        interfaces = []

        if hasattr(root_type, "interfaces"):
            interfaces = root_type.interfaces

        interface_fields = []
        for interface in interfaces:
            try:
                interface_fields += [key for key, field in interface.fields.items()]
            except (AssertionError, GraphQLTypeMapError):
                invalid_types.add(interface)

        for key, field in fields.items():
            if key not in interface_fields:
                type_ = field.type

                while isinstance(type_, (GraphQLNonNull, GraphQLList)):
                    type_ = type_.of_type

                field_name = to_snake_case(key)

                field_meta = {} # Default to empty dict
                if meta is not None: # Guard against meta being None
                    field_meta = meta.get((root_type.name, field_name), {})

                if filters:
                    for field_filter in filters:
                        if field_filter.filter_field(field_name, field_meta):
                            invalid_fields.add((root_type, key))

                if isinstance(type_, (GraphQLInterfaceType, GraphQLObjectType)):
                    try:
                        assert type_.fields
                        sub_invalid = GraphQLSchemaReducer.invalid(
                            root_type=type_,
                            filters=filters,
                            meta=meta,
                            checked_types=checked_types,
                            invalid_types=invalid_types,
                            invalid_fields=invalid_fields,
                        )

                        invalid_types.update(sub_invalid[0])
                        invalid_fields.update(sub_invalid[1])

                    except (AssertionError, GraphQLTypeMapError):
                        invalid_types.add(type_)
                        invalid_fields.add((root_type, key))

        return invalid_types, invalid_fields
