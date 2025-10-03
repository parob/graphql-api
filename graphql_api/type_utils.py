"""
Utility classes and functions for GraphQL type manipulation.

This module provides clean abstractions for common type operations like unwrapping
GraphQLNonNull/GraphQLList wrappers, collecting type information, and managing
type registries.
"""

from typing import Set, List, Tuple, Optional, Type as TypingType
from graphql import (
    GraphQLObjectType,
    GraphQLNonNull,
    GraphQLList,
    GraphQLType,
)


class TypeWrapper:
    """
    Handles wrapping and unwrapping of GraphQL type modifiers (NonNull, List).

    This provides a cleaner interface for dealing with nested type wrappers
    rather than having unwrapping logic scattered throughout the codebase.
    """

    @staticmethod
    def unwrap(field_type: GraphQLType) -> GraphQLType:
        """
        Unwrap GraphQLNonNull and GraphQLList wrappers to get the core type.

        Args:
            field_type: A potentially wrapped GraphQL type

        Returns:
            The unwrapped core type

        Example:
            GraphQLNonNull(GraphQLList(GraphQLString)) -> GraphQLString
        """
        while isinstance(field_type, (GraphQLNonNull, GraphQLList)):
            field_type = field_type.of_type
        return field_type

    @staticmethod
    def unwrap_with_wrappers(field_type: GraphQLType) -> Tuple[GraphQLType, List[type]]:
        """
        Unwrap a type and return both the core type and the wrapper classes.

        Args:
            field_type: A potentially wrapped GraphQL type

        Returns:
            Tuple of (unwrapped_type, list_of_wrapper_classes)

        Example:
            GraphQLNonNull(GraphQLList(GraphQLString))
            -> (GraphQLString, [GraphQLNonNull, GraphQLList])
        """
        wrappers = []
        while isinstance(field_type, (GraphQLNonNull, GraphQLList)):
            wrappers.append(field_type.__class__)
            field_type = field_type.of_type
        return field_type, wrappers

    @staticmethod
    def rewrap(core_type: GraphQLType, wrappers: List[type]) -> GraphQLType:
        """
        Apply wrapper classes to a core type.

        Args:
            core_type: The base GraphQL type
            wrappers: List of wrapper classes to apply

        Returns:
            The wrapped type

        Example:
            rewrap(GraphQLString, [GraphQLNonNull, GraphQLList])
            -> GraphQLNonNull(GraphQLList(GraphQLString))
        """
        result = core_type
        for wrapper in wrappers:
            result = wrapper(result)
        return result


class TypeCollector:
    """
    Utilities for collecting and categorizing types from a GraphQL schema.

    This consolidates type collection logic that was previously scattered
    throughout the reducer and mapper.
    """

    @staticmethod
    def collect_interface_fields(type_: GraphQLObjectType) -> List[str]:
        """
        Collect all field names from a type's interfaces.

        Args:
            type_: A GraphQL object type

        Returns:
            List of field names defined in interfaces
        """
        return [
            key
            for interface in type_.interfaces
            for key in interface.fields.keys()
        ]

    @staticmethod
    def iterate_all_fields(root_type: GraphQLObjectType):
        """
        Iterate through all fields in a schema starting from root.

        Yields:
            Tuples of (type, field_name, field_object)
        """
        visited = set()
        queue = [root_type]

        while queue:
            current = queue.pop(0)
            if current in visited or not isinstance(current, GraphQLObjectType):
                continue

            visited.add(current)

            for field_name, field in current.fields.items():
                yield current, field_name, field

                # Add field type to queue for traversal
                field_type = TypeWrapper.unwrap(field.type)
                if isinstance(field_type, GraphQLObjectType) and field_type not in visited:
                    queue.append(field_type)


class TypeRegistry:
    """
    Helper for managing and querying a type registry.

    Provides cleaner interfaces for common registry operations.
    """

    @staticmethod
    def get_base_type_name(type_name: str, suffix: str) -> str:
        """
        Get the base type name by removing a suffix.

        Args:
            type_name: The full type name (e.g., "UserMutable")
            suffix: The suffix to remove (e.g., "Mutable")

        Returns:
            The base type name (e.g., "User")
        """
        return type_name.replace(suffix, "", 1) if suffix else type_name

    @staticmethod
    def has_suffix(type_obj: GraphQLType, suffix: str) -> bool:
        """
        Check if a type has a specific suffix in its name.

        Args:
            type_obj: A GraphQL type
            suffix: The suffix to check for

        Returns:
            True if the type name contains the suffix
        """
        return suffix in str(type_obj)

    @staticmethod
    def filter_by_suffix(
        registry: dict, suffix: str, type_filter: Optional[TypingType] = None
    ) -> List[Tuple[str, GraphQLType]]:
        """
        Filter registry entries by suffix and optionally by type.

        Args:
            registry: The type registry dictionary
            suffix: The suffix to filter by
            type_filter: Optional type class to filter by (e.g., GraphQLObjectType)

        Returns:
            List of (key, type) tuples matching the criteria
        """
        results = []
        for key, type_obj in registry.items():
            if suffix not in str(type_obj):
                continue
            if type_filter and not isinstance(type_obj, type_filter):
                continue
            results.append((key, type_obj))
        return results


class FieldCleaner:
    """
    Utilities for cleaning/removing fields from types based on criteria.

    Consolidates field removal logic that was duplicated in multiple places.
    """

    @staticmethod
    def remove_fields(type_: GraphQLObjectType, field_names: Set[str]) -> int:
        """
        Remove specified fields from a type.

        Args:
            type_: The GraphQL object type to clean
            field_names: Set of field names to remove

        Returns:
            Number of fields removed
        """
        count = 0
        for field_name in field_names:
            if hasattr(type_, "fields") and field_name in type_.fields:
                del type_.fields[field_name]
                count += 1
        return count

    @staticmethod
    def remove_field_list(types_and_fields: Set[Tuple[GraphQLObjectType, str]]) -> int:
        """
        Remove fields specified as (type, field_name) tuples.

        Args:
            types_and_fields: Set of (type, field_name) tuples

        Returns:
            Number of fields removed
        """
        count = 0
        for type_, field_name in types_and_fields:
            if hasattr(type_, "fields") and field_name in type_.fields:
                del type_.fields[field_name]
                count += 1
        return count
