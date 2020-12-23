from typing import List

from graphql import GraphQLNonNull, GraphQLList, GraphQLObjectType
from graphql.type.definition import GraphQLInterfaceType

from graphql_api.mapper import \
    GraphQLMutableField, \
    GraphQLTypeMapError, \
    GraphQLMetaKey
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
            root_type=query,
            filters=filters,
            meta=mapper.meta
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
            field_definition_type = meta.get('type', 'query')

            wraps = []
            while isinstance(field_type, (GraphQLNonNull, GraphQLList)):
                wraps.append(field_type.__class__)
                field_type = field_type.of_type

            if meta.get(GraphQLMetaKey.resolve_to_mutable):
                # Flagged as mutable
                continue

            if field_definition_type == "query":
                if mapper.suffix in str(field_type) or \
                        field_type in filtered_mutation_types:
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
        for type_ in filtered_mutation_types:
            while isinstance(type_, (GraphQLNonNull, GraphQLList)):
                type_ = type_.of_type
            if isinstance(type_, GraphQLObjectType):
                interface_fields = []
                for interface in type_.interfaces:
                    interface_fields += [
                        key
                        for key, field in interface.fields.items()
                    ]
                for key, field in type_.fields.items():
                    if key not in interface_fields and \
                            not isinstance(field, GraphQLMutableField) and \
                            not has_mutable(field.type):
                        fields_to_remove.add((type_, key))

        for type_, key in fields_to_remove:
            del type_.fields[key]

        return mutation

    @staticmethod
    def invalid(
        root_type,
        filters=None,
        meta=None,
        checked_types=None,
        invalid_types=None,
        invalid_fields=None
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

        if hasattr(root_type, 'interfaces'):
            interfaces = root_type.interfaces

        interface_fields = []
        for interface in interfaces:
            try:
                interface_fields += [
                    key
                    for key, field in interface.fields.items()
                ]
            except (AssertionError, GraphQLTypeMapError):
                invalid_types.add(interface)

        for key, field in fields.items():
            if key not in interface_fields:
                type_ = field.type

                while isinstance(type_, (GraphQLNonNull, GraphQLList)):
                    type_ = type_.of_type

                field_name = to_snake_case(key)

                field_meta = meta.get((root_type.name, field_name), {})

                if filters:
                    for field_filter in filters:
                        if field_filter.filter_field(field_name, field_meta):
                            invalid_fields.add((root_type, key))

                if isinstance(
                    type_,
                    (GraphQLInterfaceType, GraphQLObjectType)
                ):
                    try:
                        assert type_.fields
                        sub_invalid = GraphQLSchemaReducer.invalid(
                            root_type=type_,
                            filters=filters,
                            meta=meta,
                            checked_types=checked_types,
                            invalid_types=invalid_types,
                            invalid_fields=invalid_fields
                        )

                        invalid_types.update(sub_invalid[0])
                        invalid_fields.update(sub_invalid[1])

                    except (AssertionError, GraphQLTypeMapError):
                        invalid_types.add(type_)
                        invalid_fields.add((root_type, key))

        return invalid_types, invalid_fields
