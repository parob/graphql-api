from typing import List, Optional, Union
from enum import Enum

from graphql import GraphQLList, GraphQLNonNull, GraphQLObjectType
from graphql.type.definition import GraphQLInterfaceType

from graphql_api.mapper import GraphQLTypeMapError
from graphql_api.utils import iterate_fields, to_snake_case
from graphql_api.type_utils import TypeWrapper, FieldCleaner
from graphql_api.mutation_schema import MutationSchemaBuilder


class FilterResponse(Enum):
    """
    Response from a GraphQL filter indicating how to handle a field and transitive types.

    KEEP - Keep the field, don't preserve transitive object types
    KEEP_TRANSITIVE - Keep the field and preserve transitive object types
    REMOVE - Remove the field but preserve types referenced by unfiltered fields
    REMOVE_STRICT - Always remove the field even if it is referenced by an unfiltered field that preserves transitive types.

    """

    KEEP = "keep"
    KEEP_TRANSITIVE = "allow_transitive"
    REMOVE = "remove"
    REMOVE_STRICT = "remove_strict"

    @property
    def should_filter(self) -> bool:
        """True if the field should be removed from the schema"""
        return self in (FilterResponse.REMOVE, FilterResponse.REMOVE_STRICT)

    @property
    def preserve_transitive(self) -> bool:
        """True if types referenced by unfiltered fields should be preserved"""
        return self in (FilterResponse.KEEP_TRANSITIVE, FilterResponse.REMOVE)


class GraphQLFilter:

    def __init__(self, cleanup_types: bool = True):
        """
        Initialize a GraphQL filter.

        Args:
            cleanup_types: Whether to remove unreferenced types after filtering.
                Only applies when filters are active. Defaults to True.
        """
        self.cleanup_types = cleanup_types

    def filter_field(self, name: str, meta: dict) -> Union[bool, FilterResponse]:
        """
        Return either FilterReponse or a bool value indicating how to handle the field.

        There are two options for what is returned;

        Basic usage:
            True: This field should be removed.
            False: This field should be kept.

        Advanced usage:
            FilterResponse.KEEP_TRANSITIVE: This field should be kept and any transitive types should be kept.
            FilterResponse.KEEP: This field should be kept but any transitive types set to REMOVE or REMOVE_STRICT will be removed.
            FilterResponse.REMOVE: This field should generally be removed, but will be kept if it is referenced by an unfiltered field that is set to KEEP_TRANSITIVE.
            FilterResponse.REMOVE_STRICT: This field should always be removed, even if it is referenced by an unfiltered field that is set to KEEP_TRANSITIVE.
        """
        raise NotImplementedError()


class TagFilter(GraphQLFilter):

    def __init__(
        self, tags: Optional[List[str]] = None, preserve_transitive: bool = True, cleanup_types: bool = True
    ):
        super().__init__(cleanup_types=cleanup_types)
        self.tags = tags or []
        self.preserve_transitive = (
            preserve_transitive  # Used internally for FilterResponse logic
        )

    def filter_field(self, name: str, meta: dict) -> FilterResponse:
        should_filter = False
        if "tags" in meta:
            for tag in meta["tags"]:
                if tag in self.tags:
                    should_filter = True
                    break

        if not should_filter:
            # Field is allowed - use ALLOW_TRANSITIVE only if preserve_transitive is enabled
            if self.preserve_transitive:
                return FilterResponse.KEEP_TRANSITIVE
            else:
                return FilterResponse.KEEP
        elif self.preserve_transitive:
            # Field is filtered but preserve transitive dependencies
            return FilterResponse.REMOVE
        else:
            # Field is filtered with strict behavior
            return FilterResponse.REMOVE_STRICT


class GraphQLSchemaReducer:
    """
    Responsible for reducing/filtering GraphQL schemas.

    This class handles the complex logic of filtering schemas, removing unused types,
    and managing the relationship between query and mutation schemas.
    """

    @staticmethod
    def _apply_filtering(root_type, mapper, filters):
        """
        Apply filters to a schema and remove invalid types and fields.

        Even without filters, this method removes types with no fields.

        Args:
            root_type: The root type (query or mutation)
            mapper: GraphQLTypeMapper instance
            filters: List of filters to apply (can be None/empty)

        Returns:
            Tuple of (invalid_types, all_invalid_fields) for reference
        """
        # Find invalid types and fields based on filters
        # Note: invalid() handles None/empty filters and still removes empty types
        invalid_types, invalid_fields = GraphQLSchemaReducer.invalid(
            root_type=root_type,
            filters=filters,
            meta=mapper.meta,
        )

        # Find fields that reference invalid types
        additional_invalid_fields = set()
        for type_ in list(mapper.registry.values()):
            if hasattr(type_, "fields"):
                for field_name, field in list(type_.fields.items()):
                    field_type = TypeWrapper.unwrap(field.type)
                    if field_type in invalid_types:
                        additional_invalid_fields.add((type_, field_name))

        # Combine all invalid fields
        all_invalid_fields = (invalid_fields or set()).union(additional_invalid_fields)

        # Remove invalid fields
        FieldCleaner.remove_field_list(all_invalid_fields)

        # Remove invalid types from registry
        for key, value in dict(mapper.registry).items():
            if value in invalid_types:
                del mapper.registry[key]

        return invalid_types, all_invalid_fields

    @staticmethod
    def reduce_query(mapper, root, filters=None):
        """
        Reduce and filter a query schema.

        Args:
            mapper: GraphQLTypeMapper instance
            root: Root query type
            filters: Optional list of filters to apply

        Returns:
            Filtered GraphQLObjectType for queries
        """
        query: GraphQLObjectType = mapper.map(root)

        # Always apply filtering (even without filters, this removes empty types)
        GraphQLSchemaReducer._apply_filtering(query, mapper, filters)

        return query

    @staticmethod
    def reduce_mutation(mapper, root, filters=None):
        """
        Reduce and filter a mutation schema.

        This method handles both filtering and the complex mutation-specific logic
        like removing unused mutable types, converting between mutable/immutable,
        and cleaning query fields from mutation types.

        Args:
            mapper: GraphQLTypeMapper instance
            root: Root mutation type
            filters: Optional list of filters to apply

        Returns:
            Filtered GraphQLObjectType for mutations
        """
        mutation: GraphQLObjectType = mapper.map(root)

        # Apply filtering if specified
        GraphQLSchemaReducer._apply_filtering(mutation, mapper, filters)

        # Trigger dynamic fields to be evaluated
        for _ in iterate_fields(mutation):
            pass

        # Build and clean mutation schema using dedicated builder
        builder = MutationSchemaBuilder(mapper, root)
        builder.build()

        return mutation

    @staticmethod
    def _remove_unreferenced_types(mapper, root_type):
        """
        Remove types from the registry that are no longer referenced by any field
        after filtering has been applied.

        This method should only be called when filtering is applied, so that explicitly
        registered types (via types=[...] parameter) remain in unfiltered schemas.
        """
        # Collect all types that are still referenced by fields
        referenced_types = set()

        def collect_interface_implementations(interface_type, visited=None):
            """Find all types that implement the given interface."""
            if visited is None:
                visited = set()

            # Look through all registered types to find implementations
            # Create a snapshot to avoid RuntimeError during iteration
            registry_snapshot = list(mapper.registry.values())
            for type_obj in registry_snapshot:
                if (isinstance(type_obj, GraphQLObjectType)
                        and hasattr(type_obj, 'interfaces')
                        and interface_type in type_obj.interfaces):
                    if type_obj not in visited:
                        collect_referenced_types(type_obj, visited)

        def collect_referenced_types(current_type, visited=None):
            if visited is None:
                visited = set()

            if current_type in visited:
                return

            visited.add(current_type)
            referenced_types.add(current_type)

            try:
                fields = current_type.fields
            except (AssertionError, GraphQLTypeMapError, AttributeError):
                return

            for field_name, field in fields.items():
                field_type = field.type
                # Unwrap NonNull and List wrappers
                while isinstance(field_type, (GraphQLNonNull, GraphQLList)):
                    field_type = field_type.of_type

                if isinstance(field_type, (GraphQLInterfaceType, GraphQLObjectType)):
                    collect_referenced_types(field_type, visited)

                    # If this is an interface, also preserve all its implementations
                    if isinstance(field_type, GraphQLInterfaceType):
                        collect_interface_implementations(field_type, visited)
                else:
                    # For enums and other scalar types, just add them to referenced
                    referenced_types.add(field_type)

        # Start from the root type and collect all reachable types
        collect_referenced_types(root_type)

        # Remove any types from the registry that are no longer referenced
        registry_snapshot = dict(mapper.registry)
        for key, type_obj in registry_snapshot.items():
            if type_obj not in referenced_types:
                # Don't remove built-in GraphQL types (they start with __)
                if not key.startswith('__') and not key.startswith('_'):
                    del mapper.registry[key]

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

        # Use the new unified approach that works with FilterResponse values
        return GraphQLSchemaReducer._invalid_with_filter_responses(
            root_type, filters, meta, checked_types, invalid_types, invalid_fields
        )

    @staticmethod
    def _invalid_with_filter_responses(
        root_type,
        filters=None,
        meta=None,
        checked_types=None,
        invalid_types=None,
        invalid_fields=None,
    ):
        """
        New unified approach that determines behavior from FilterResponse values
        """
        if not checked_types:
            checked_types = set()

        if not invalid_types:
            invalid_types = set()

        if not invalid_fields:
            invalid_fields = set()

        # First, traverse the schema and collect all FilterResponse values
        # Track types that should be preserved due to ALLOW_TRANSITIVE fields
        allow_transitive_types = set()
        preserve_transitive = False

        def collect_filter_responses(current_type, current_checked=None):
            nonlocal preserve_transitive

            if current_checked is None:
                current_checked = set()

            if current_type in current_checked:
                return

            current_checked.add(current_type)

            try:
                fields = current_type.fields
            except (AssertionError, GraphQLTypeMapError):
                return

            interfaces = []
            if hasattr(current_type, "interfaces"):
                interfaces = current_type.interfaces

            interface_fields = []
            for interface in interfaces:
                try:
                    interface_fields += [key for key,
                                         field in interface.fields.items()]
                except (AssertionError, GraphQLTypeMapError):
                    pass

            for key, field in fields.items():
                if key not in interface_fields:
                    type_ = field.type

                    while isinstance(type_, (GraphQLNonNull, GraphQLList)):
                        type_ = type_.of_type

                    field_name = to_snake_case(key)
                    field_meta = (
                        meta.get((current_type.name, field_name),
                                 {}) if meta else {}
                    )

                    # Check what each filter returns for this field
                    if filters:
                        for field_filter in filters:
                            filter_response = field_filter.filter_field(
                                field_name, field_meta
                            )

                            # Handle backwards compatibility with boolean returns
                            if isinstance(filter_response, bool):
                                # Boolean True means filter the field (old API)
                                # Convert to FilterResponse for consistent handling
                                if filter_response:
                                    # Field should be filtered - use REMOVE_STRICT as default
                                    filter_response = FilterResponse.REMOVE_STRICT
                                else:
                                    # Field should be kept - use KEEP as default
                                    filter_response = FilterResponse.KEEP

                            # If this field uses ALLOW_TRANSITIVE, preserve its referenced type
                            if isinstance(filter_response, FilterResponse) and filter_response == FilterResponse.KEEP_TRANSITIVE:
                                if isinstance(type_, (GraphQLInterfaceType, GraphQLObjectType)):
                                    allow_transitive_types.add(type_)
                            # If any filter response wants to preserve transitive,
                            # use preserve_transitive logic for the entire schema
                            if isinstance(filter_response, FilterResponse) and filter_response.preserve_transitive:
                                preserve_transitive = True

                    if isinstance(type_, (GraphQLInterfaceType, GraphQLObjectType)):
                        collect_filter_responses(type_, current_checked)

        # Collect all filter responses to determine overall behavior
        collect_filter_responses(root_type)

        # Use preserve_transitive method if needed, but with explicit ALLOW_TRANSITIVE preservation
        if preserve_transitive:
            invalid_types, invalid_fields = GraphQLSchemaReducer._invalid_preserve_transitive(
                root_type, filters, meta, checked_types, invalid_types, invalid_fields
            )
        else:
            invalid_types, invalid_fields = GraphQLSchemaReducer._invalid_strict(
                root_type, filters, meta, checked_types, invalid_types, invalid_fields
            )

        # Handle ALLOW_TRANSITIVE types: preserve them only if they have filtered fields to restore
        for allow_type in allow_transitive_types:
            if hasattr(allow_type, 'fields'):
                type_has_valid_field = False
                type_has_filtered_field = False

                # Check if the type has any valid (non-filtered) fields
                for field_key, field_val in allow_type.fields.items():
                    if (allow_type, field_key) not in invalid_fields:
                        type_has_valid_field = True
                    else:
                        type_has_filtered_field = True

                # Only apply ALLOW_TRANSITIVE if:
                # 1. The type has no valid fields AND
                # 2. The type has fields that were filtered out (not just absent)
                if not type_has_valid_field and type_has_filtered_field:
                    # Preserve the type and restore all filtered fields
                    invalid_types.discard(allow_type)

                    # Find all fields that were marked for removal and preserve them
                    for field_key, field_val in allow_type.fields.items():
                        if (allow_type, field_key) in invalid_fields:
                            # Remove this field from invalid_fields to preserve it
                            invalid_fields.discard((allow_type, field_key))
                elif type_has_valid_field:
                    # Type already has valid fields, just preserve it
                    invalid_types.discard(allow_type)

        return invalid_types, invalid_fields

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
                interface_fields += [key for key,
                                     field in interface.fields.items()]
            except (AssertionError, GraphQLTypeMapError):
                invalid_types.add(interface)

        for key, field in fields.items():
            if key not in interface_fields:
                type_ = field.type

                while isinstance(type_, (GraphQLNonNull, GraphQLList)):
                    type_ = type_.of_type

                field_name = to_snake_case(key)
                field_meta = meta.get(
                    (root_type.name, field_name), {}) if meta else {}

                if filters:
                    for field_filter in filters:
                        filter_response = field_filter.filter_field(
                            field_name, field_meta
                        )

                        # Handle backwards compatibility with boolean returns
                        if isinstance(filter_response, bool):
                            # Boolean True means filter the field (old API)
                            if filter_response:
                                invalid_fields.add((root_type, key))
                        elif isinstance(filter_response, FilterResponse) and filter_response.should_filter:
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
        # Maps (parent_type, child_type) -> [(field_name, field)]
        type_field_refs = {}

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
                    interface_fields += [key for key,
                                         field in interface.fields.items()]
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
                        meta.get((current_type.name, field_name),
                                 {}) if meta else {}
                    )

                    field_is_filtered = False
                    if filters:
                        for field_filter in filters:
                            filter_response = field_filter.filter_field(
                                field_name, field_meta
                            )

                            # Handle backwards compatibility with boolean returns
                            should_filter_field = False
                            if isinstance(filter_response, bool):
                                # Boolean True means filter the field (old API)
                                should_filter_field = filter_response
                            elif isinstance(filter_response, FilterResponse):
                                should_filter_field = filter_response.should_filter

                            if should_filter_field:
                                invalid_fields.add((current_type, key))
                                field_is_filtered = True
                                break

                    if not field_is_filtered:
                        has_valid_fields = True

                    # Track field references between types (only for unfiltered fields)
                    if (
                        isinstance(
                            type_, (GraphQLInterfaceType, GraphQLObjectType))
                        and not field_is_filtered
                    ):
                        if (current_type, type_) not in type_field_refs:
                            type_field_refs[(current_type, type_)] = []
                        type_field_refs[(current_type, type_)
                                        ].append((key, field))

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
