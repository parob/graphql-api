from typing import List, Optional
from enum import Enum

from graphql import GraphQLList, GraphQLNonNull, GraphQLObjectType
from graphql.type.definition import GraphQLInterfaceType

from graphql_api.mapper import GraphQLMetaKey, GraphQLMutableField, GraphQLTypeMapError
from graphql_api.utils import has_mutable, iterate_fields, to_snake_case


class FilterResponse(Enum):
    """
    Response from a GraphQL filter indicating how to handle a field and transitive types.

    ALLOW - Keep the field, don't preserve transitive object types (should_filter=False, preserve_transitive=False)
    ALLOW_TRANSITIVE - Keep the field and preserve transitive object types (should_filter=False, preserve_transitive=True)
    REMOVE - Remove the field but preserve types referenced by unfiltered fields (should_filter=True, preserve_transitive=True)
    REMOVE_STRICT - Remove the field and don't preserve unreferenced types (should_filter=True, preserve_transitive=False)
    """

    ALLOW = "allow"
    ALLOW_TRANSITIVE = "allow_transitive"
    REMOVE = "remove"
    REMOVE_STRICT = "remove_strict"

    @property
    def should_filter(self) -> bool:
        """True if the field should be removed from the schema"""
        return self in (FilterResponse.REMOVE, FilterResponse.REMOVE_STRICT)

    @property
    def preserve_transitive(self) -> bool:
        """True if types referenced by unfiltered fields should be preserved"""
        return self in (FilterResponse.ALLOW_TRANSITIVE, FilterResponse.REMOVE)


class GraphQLFilter:
    def filter_field(self, name, meta: dict) -> FilterResponse:
        """
        Return FilterResponse indicating how to handle the field
        """
        raise NotImplementedError()


class TagFilter(GraphQLFilter):
    def __init__(
        self, tags: Optional[List[str]] = None, preserve_transitive: bool = True
    ):
        self.tags = tags or []
        self.preserve_transitive = preserve_transitive

    def filter_field(self, name: str, meta: dict) -> FilterResponse:
        should_filter = False
        if "tags" in meta:
            for tag in meta["tags"]:
                if tag in self.tags:
                    should_filter = True
                    break

        if not should_filter:
            # Field is allowed - use transitive preservation by default
            return FilterResponse.ALLOW_TRANSITIVE
        elif self.preserve_transitive:
            # Field is filtered but preserve transitive dependencies
            return FilterResponse.REMOVE
        else:
            # Field is filtered with strict behavior
            return FilterResponse.REMOVE_STRICT


class GraphQLSchemaReducer:
    @staticmethod
    def reduce_query(mapper, root, filters=None):
        query: GraphQLObjectType = mapper.map(root)

        # Determine preservation behavior from filters
        preserve_transitive = any(f.preserve_transitive for f in (filters or []))

        # Remove any types that have no fields
        # (and remove any fields that returned that type)
        invalid_types, invalid_fields = GraphQLSchemaReducer.invalid(
            root_type=query,
            filters=filters,
            meta=mapper.meta,
            preserve_transitive=preserve_transitive,
        )

        # Remove fields that reference invalid types
        additional_invalid_fields = set()
        for type_ in list(mapper.registry.values()):
            if hasattr(type_, "fields"):
                for field_name, field in list(type_.fields.items()):
                    field_type = field.type
                    # Unwrap NonNull and List wrappers
                    while isinstance(field_type, (GraphQLNonNull, GraphQLList)):
                        field_type = field_type.of_type

                    if field_type in invalid_types:
                        additional_invalid_fields.add((type_, field_name))

        # Combine all invalid fields
        all_invalid_fields = (invalid_fields or set()).union(additional_invalid_fields)

        for type_, key in all_invalid_fields:
            if hasattr(type_, "fields") and key in type_.fields:
                del type_.fields[key]

        for key, value in dict(mapper.registry).items():
            if value in invalid_types:
                del mapper.registry[key]

        return query

    @staticmethod
    def reduce_mutation(mapper, root, filters=None):
        mutation: GraphQLObjectType = mapper.map(root)

        # Determine preservation behavior from filters
        preserve_transitive = any(f.preserve_transitive for f in (filters or []))

        # Apply filtering to mutation schema first
        if filters:
            invalid_types, invalid_fields = GraphQLSchemaReducer.invalid(
                root_type=mutation,
                filters=filters,
                meta=mapper.meta,
                preserve_transitive=preserve_transitive,
            )

            # Remove fields that reference invalid types
            additional_invalid_fields = set()
            for type_ in list(mapper.registry.values()):
                if hasattr(type_, "fields"):
                    for field_name, field in list(type_.fields.items()):
                        field_type = field.type
                        # Unwrap NonNull and List wrappers
                        while isinstance(field_type, (GraphQLNonNull, GraphQLList)):
                            field_type = field_type.of_type

                        if field_type in invalid_types:
                            additional_invalid_fields.add((type_, field_name))

            # Combine all invalid fields
            all_invalid_fields = (invalid_fields or set()).union(
                additional_invalid_fields
            )

            for type_, key in all_invalid_fields:
                if hasattr(type_, "fields") and key in type_.fields:
                    del type_.fields[key]

            for key, value in dict(mapper.registry).items():
                if value in invalid_types:
                    del mapper.registry[key]

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
        for type_ in filtered_mutation_types:
            while isinstance(type_, (GraphQLNonNull, GraphQLList)):
                type_ = type_.of_type
            if isinstance(type_, GraphQLObjectType):
                interface_fields = []
                for interface in type_.interfaces:
                    interface_fields += [key for key, field in interface.fields.items()]
                for key, field in type_.fields.items():
                    if (
                        key not in interface_fields
                        and not isinstance(field, GraphQLMutableField)
                        and not has_mutable(field.type)
                    ):
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
        invalid_fields=None,
        preserve_transitive=True,
    ):
        if not checked_types:
            checked_types = set()

        if not invalid_types:
            invalid_types = set()

        if not invalid_fields:
            invalid_fields = set()

        if not preserve_transitive:
            # Strict behavior: remove types that have no accessible fields
            return GraphQLSchemaReducer._invalid_strict(
                root_type, filters, meta, checked_types, invalid_types, invalid_fields
            )
        else:
            # Preserve transitive: preserve types referenced by unfiltered types
            return GraphQLSchemaReducer._invalid_preserve_transitive(
                root_type, filters, meta, checked_types, invalid_types, invalid_fields
            )

    @staticmethod
    def _invalid_strict(
        root_type,
        filters=None,
        meta=None,
        checked_types=None,
        invalid_types=None,
        invalid_fields=None,
    ):
        """Original strict filtering behavior"""
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
                field_meta = meta.get((root_type.name, field_name), {}) if meta else {}

                if filters:
                    for field_filter in filters:
                        filter_response = field_filter.filter_field(
                            field_name, field_meta
                        )
                        if filter_response.should_filter:
                            invalid_fields.add((root_type, key))

                if isinstance(type_, (GraphQLInterfaceType, GraphQLObjectType)):
                    try:
                        assert type_.fields
                        sub_invalid = GraphQLSchemaReducer._invalid_strict(
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

        # After processing all fields, check if this type has no remaining valid fields
        # (excluding interface fields which are inherited)
        remaining_fields = []
        for key, field in fields.items():
            if key not in interface_fields and (root_type, key) not in invalid_fields:
                remaining_fields.append(key)

        # If no fields remain after filtering, mark this type as invalid
        if not remaining_fields and root_type not in invalid_types:
            invalid_types.add(root_type)

        return invalid_types, invalid_fields

    @staticmethod
    def _invalid_preserve_transitive(
        root_type,
        filters=None,
        meta=None,
        checked_types=None,
        invalid_types=None,
        invalid_fields=None,
    ):
        """Preserve transitive dependencies filtering behavior"""
        if not checked_types:
            checked_types = set()

        if not invalid_types:
            invalid_types = set()

        if not invalid_fields:
            invalid_fields = set()

        # First pass: identify all invalid fields and collect type information
        types_with_valid_fields = set()
        all_object_types = set()
        type_field_refs = {}  # Maps (parent_type, child_type) -> [(field_name, field)]

        def collect_type_info(current_type, current_checked=None):
            if current_checked is None:
                current_checked = set()

            if current_type in current_checked:
                return

            current_checked.add(current_type)

            try:
                fields = current_type.fields
            except (AssertionError, GraphQLTypeMapError):
                invalid_types.add(current_type)
                return

            interfaces = []
            if hasattr(current_type, "interfaces"):
                interfaces = current_type.interfaces

            interface_fields = []
            for interface in interfaces:
                try:
                    interface_fields += [key for key, field in interface.fields.items()]
                except (AssertionError, GraphQLTypeMapError):
                    invalid_types.add(interface)

            # Track all object types we encounter
            if isinstance(current_type, (GraphQLInterfaceType, GraphQLObjectType)):
                all_object_types.add(current_type)

            has_valid_fields = False
            for key, field in fields.items():
                if key not in interface_fields:
                    type_ = field.type

                    while isinstance(type_, (GraphQLNonNull, GraphQLList)):
                        type_ = type_.of_type

                    field_name = to_snake_case(key)
                    field_meta = (
                        meta.get((current_type.name, field_name), {}) if meta else {}
                    )

                    field_is_filtered = False
                    if filters:
                        for field_filter in filters:
                            filter_response = field_filter.filter_field(
                                field_name, field_meta
                            )
                            if filter_response.should_filter:
                                invalid_fields.add((current_type, key))
                                field_is_filtered = True
                                break

                    if not field_is_filtered:
                        has_valid_fields = True

                    # Track field references between types (only for unfiltered fields)
                    if (
                        isinstance(type_, (GraphQLInterfaceType, GraphQLObjectType))
                        and not field_is_filtered
                    ):
                        if (current_type, type_) not in type_field_refs:
                            type_field_refs[(current_type, type_)] = []
                        type_field_refs[(current_type, type_)].append((key, field))

                    if isinstance(type_, (GraphQLInterfaceType, GraphQLObjectType)):
                        collect_type_info(type_, current_checked)

            if has_valid_fields:
                types_with_valid_fields.add(current_type)

        # Start the recursive collection
        collect_type_info(root_type)

        # Second pass: find types that should be preserved
        # A type should be preserved if:
        # 1. It has valid fields, OR
        # 2. It's reachable from a type with valid fields AND it will have at least one field after filtering
        preservable_types = set(types_with_valid_fields)

        def mark_preservable_types(current_type, visited=None):
            if visited is None:
                visited = set()

            if current_type in visited:
                return

            visited.add(current_type)
            preservable_types.add(current_type)

            # Traverse to all child types referenced by unfiltered fields
            for parent, child in type_field_refs:
                if parent == current_type and child not in visited:
                    # Only preserve the child if it will have at least one accessible field
                    # (GraphQL requires object types to have at least one field)
                    child_will_have_fields = False
                    try:
                        child_fields = child.fields
                        for field_key, field_val in child_fields.items():
                            if (child, field_key) not in invalid_fields:
                                child_will_have_fields = True
                                break
                    except (AssertionError, GraphQLTypeMapError):
                        pass

                    if child_will_have_fields:
                        mark_preservable_types(child, visited.copy())

        # Start from types with valid fields and mark all reachable types as preservable
        for type_with_valid_fields in list(types_with_valid_fields):
            mark_preservable_types(type_with_valid_fields)

        # Third pass: mark types as invalid only if they're not preservable
        for obj_type in all_object_types:
            if obj_type not in preservable_types and obj_type not in invalid_types:
                invalid_types.add(obj_type)

        return invalid_types, invalid_fields
