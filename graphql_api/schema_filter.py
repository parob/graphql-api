"""
Schema Filtering Logic

This module handles the complex logic of applying filters to GraphQL schemas,
determining which types and fields should be kept or removed based on filter
criteria and transitive preservation rules.

Separated from reduce.py to keep the reducer focused on orchestration.
"""

from typing import Set, Tuple, Optional, List
from graphql import GraphQLObjectType

from graphql_api.reduce import FilterResponse, GraphQLFilter
from graphql_api.mapper import GraphQLTypeMapError
from graphql_api.utils import to_snake_case


class SchemaFilterEngine:
    """
    Engine for applying filters to GraphQL schemas.

    This class encapsulates the complex logic of:
    - Evaluating filter responses
    - Handling transitive type preservation
    - Determining which types/fields are valid/invalid
    """

    def __init__(self, root_type: GraphQLObjectType, filters: Optional[List[GraphQLFilter]], meta: dict):
        """
        Initialize the filter engine.

        Args:
            root_type: The root GraphQL type to filter
            filters: List of filters to apply
            meta: Metadata dictionary for field information
        """
        self.root_type = root_type
        self.filters = filters or []
        self.meta = meta
        self.checked_types: Set[GraphQLObjectType] = set()
        self.invalid_types: Set[GraphQLObjectType] = set()
        self.invalid_fields: Set[Tuple[GraphQLObjectType, str]] = set()
        self.allow_transitive_types: Set[GraphQLObjectType] = set()

    def apply_filters(self) -> Tuple[Set, Set]:
        """
        Apply all filters and determine invalid types/fields.

        Returns:
            Tuple of (invalid_types, invalid_fields)
        """
        if not self.filters:
            return set(), set()

        # Collect filter responses and transitive types
        self._collect_filter_responses(self.root_type)

        # Determine what should be filtered
        self._determine_invalid_items(self.root_type)

        return self.invalid_types, self.invalid_fields

    def _should_filter_field(self, type_name: str, field_name: str) -> Tuple[bool, bool]:
        """
        Determine if a field should be filtered and if it preserves transitive types.

        Args:
            type_name: Name of the type containing the field
            field_name: Name of the field

        Returns:
            Tuple of (should_filter, preserve_transitive)
        """
        if not self.filters:
            return False, False

        # Get metadata for this field
        field_meta = self.meta.get((type_name, to_snake_case(field_name)), {})

        # Evaluate all filters
        for filter_obj in self.filters:
            response = filter_obj.filter_field(field_name, field_meta)

            # Handle different response types
            if isinstance(response, FilterResponse):
                if response.should_filter:
                    return True, response.preserve_transitive
                elif response == FilterResponse.KEEP_TRANSITIVE:
                    return False, True
                elif response == FilterResponse.KEEP:
                    return False, False
            elif isinstance(response, bool):
                # Legacy boolean response - assume preserve_transitive=True
                if response:
                    return True, True
                else:
                    return False, True

        # Default: don't filter, preserve transitive
        return False, True

    def _collect_filter_responses(self, current_type, current_checked=None):
        """
        Traverse schema and collect types that should be preserved transitively.

        Args:
            current_type: Type to examine
            current_checked: Set of already checked types
        """
        if current_checked is None:
            current_checked = set()

        if current_type in current_checked:
            return

        current_checked.add(current_type)

        try:
            fields = current_type.fields
        except (AssertionError, GraphQLTypeMapError):
            return

        # Get interface fields
        interface_fields = []
        if hasattr(current_type, "interfaces"):
            for interface in current_type.interfaces:
                interface_fields.extend(interface.fields.keys())

        # Check each field
        for field_name, field in fields.items():
            if field_name in interface_fields:
                continue

            should_filter, preserve_transitive = self._should_filter_field(
                current_type.name, field_name
            )

            # If field is kept with KEEP_TRANSITIVE, mark field type for preservation
            if not should_filter and preserve_transitive:
                field_type = self._get_core_field_type(field.type)
                if isinstance(field_type, GraphQLObjectType):
                    self.allow_transitive_types.add(field_type)

            # Recursively check field type
            field_type = self._get_core_field_type(field.type)
            if isinstance(field_type, GraphQLObjectType):
                self._collect_filter_responses(field_type, current_checked)

    def _determine_invalid_items(self, current_type, current_checked=None):
        """
        Determine which types and fields are invalid based on filters.

        Args:
            current_type: Type to examine
            current_checked: Set of already checked types
        """
        if current_checked is None:
            current_checked = set()

        if current_type in current_checked:
            return

        current_checked.add(current_type)

        try:
            fields = current_type.fields
        except (AssertionError, GraphQLTypeMapError):
            self.invalid_types.add(current_type)
            return

        # Get interface fields
        interface_fields = []
        if hasattr(current_type, "interfaces"):
            for interface in current_type.interfaces:
                interface_fields.extend(interface.fields.keys())

        # Check each field
        valid_field_count = 0
        for field_name, field in list(fields.items()):
            if field_name in interface_fields:
                valid_field_count += 1
                continue

            should_filter, preserve_transitive = self._should_filter_field(
                current_type.name, field_name
            )

            if should_filter:
                # Field is filtered - mark as invalid
                self.invalid_fields.add((current_type, field_name))
            else:
                valid_field_count += 1

            # Recursively check field type
            field_type = self._get_core_field_type(field.type)
            if isinstance(field_type, GraphQLObjectType):
                self._determine_invalid_items(field_type, current_checked)

        # If type has no valid fields and isn't preserved transitively, mark as invalid
        if valid_field_count == 0 and current_type not in self.allow_transitive_types:
            self.invalid_types.add(current_type)

    @staticmethod
    def _get_core_field_type(field_type):
        """Get the core type by unwrapping NonNull and List wrappers."""
        from graphql import GraphQLNonNull, GraphQLList

        while isinstance(field_type, (GraphQLNonNull, GraphQLList)):
            field_type = field_type.of_type
        return field_type
