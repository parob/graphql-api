"""
Mutation Schema Builder

This module handles the complex logic of building and cleaning mutation schemas.
It separates the concerns of mutation type management from the general schema
reduction logic.
"""

from typing import Set
from graphql import GraphQLObjectType

from graphql_api.mapper import GraphQLMetaKey, GraphQLMutableField
from graphql_api.utils import has_mutable, iterate_fields, to_snake_case
from graphql_api.type_utils import (
    TypeWrapper,
    TypeCollector,
    TypeRegistry,
    FieldCleaner,
)


class MutationSchemaBuilder:
    """
    Responsible for building and cleaning mutation schemas.

    This class encapsulates all the logic around:
    - Collecting types that should be mutable
    - Removing unused mutable types
    - Converting between mutable and immutable field types
    - Cleaning query fields from mutation types
    """

    def __init__(self, mapper, root_mutation_type):
        """
        Initialize the mutation schema builder.

        Args:
            mapper: GraphQLTypeMapper instance
            root_mutation_type: The root mutation type to work with
        """
        self.mapper = mapper
        self.root = root_mutation_type
        self.types_with_resolve_to_mutable = set()

    def build(self):
        """
        Main entry point to build and clean the mutation schema.

        This orchestrates all the mutation schema transformations in the
        correct order:
        1. Collect types flagged as mutable
        2. Remove unused mutable types
        3. Replace immutable fields where appropriate
        4. Remove query fields from mutable types
        5. Clean root mutation type
        6. Remove federation types
        """
        # Step 1: Collect types with resolve_to_mutable flag
        self.types_with_resolve_to_mutable = self._collect_mutable_types()

        # Step 2: Remove unused mutable types
        self._remove_unused_mutable_types()

        # Step 3: Replace mutable with immutable where appropriate
        self._replace_mutable_with_immutable_fields()

        # Step 4: Remove query fields from mutable types
        self._remove_query_fields_from_mutable_types()

        # Step 5: Clean root mutation type
        self._clean_root_mutation()

        # Step 6: Clean federation types
        self._cleanup_federation_types()

    def _collect_mutable_types(self) -> Set[GraphQLObjectType]:
        """
        Collect types returned by fields with resolve_to_mutable: True.

        Returns:
            Set of base types that have the resolve_to_mutable flag
        """
        mutable_types = set()

        for type_, key, field in iterate_fields(self.root):
            meta = self.mapper.meta.get((type_.name, to_snake_case(key)), {})
            if meta.get(GraphQLMetaKey.resolve_to_mutable):
                field_type = TypeWrapper.unwrap(field.type)

                if isinstance(field_type, GraphQLObjectType):
                    # Get the base type (query version)
                    base_type_name = TypeRegistry.get_base_type_name(
                        str(field_type), self.mapper.suffix
                    )
                    base_type = self.mapper.registry.get(base_type_name)
                    if base_type:
                        mutable_types.add(base_type)

        return mutable_types

    def _remove_unused_mutable_types(self):
        """
        Remove mutable types that aren't actually needed.

        A mutable type is kept only if:
        - Its base type has resolve_to_mutable flag, OR
        - The type itself has mutable fields, OR
        - It's the root mutation type
        """
        mutable_types = TypeRegistry.filter_by_suffix(
            self.mapper.registry, self.mapper.suffix, GraphQLObjectType
        )

        types_to_remove = []
        for key, type_obj in mutable_types:
            base_type_name = TypeRegistry.get_base_type_name(
                str(type_obj), self.mapper.suffix
            )
            base_type = self.mapper.registry.get(base_type_name)

            # Determine if we should keep this mutable type
            has_resolve_to_mutable = base_type in self.types_with_resolve_to_mutable
            has_mutable_fields = has_mutable(type_obj, interfaces_default_mutable=False)
            is_root_mutation = type_obj == self.root

            if not (has_resolve_to_mutable or has_mutable_fields or is_root_mutation):
                types_to_remove.append(key)

        # Remove from registry
        for key in types_to_remove:
            if key in self.mapper.registry:
                del self.mapper.registry[key]

    def _replace_mutable_with_immutable_fields(self):
        """
        Replace field types with immutable versions where mutable isn't needed.

        Fields are converted to immutable unless:
        - They're flagged with resolve_to_mutable
        - They're already mutable types
        - They return mutable types
        """
        # Collect all types that are truly mutable
        filtered_mutation_types = {self.root}
        for type_ in self.mapper.types():
            if has_mutable(type_, interfaces_default_mutable=False):
                filtered_mutation_types.add(type_)

        # Check each field and convert to immutable if appropriate
        for type_, key, field in iterate_fields(self.root):
            meta = self.mapper.meta.get((type_.name, to_snake_case(key)), {})
            field_definition_type = meta.get("graphql_type", "field")

            # Unwrap to get core type and wrappers
            core_type, wrappers = TypeWrapper.unwrap_with_wrappers(field.type)

            # Skip if flagged as mutable
            if meta.get(GraphQLMetaKey.resolve_to_mutable):
                continue

            # Skip if it's a field type and already mutable
            if field_definition_type == "field":
                if TypeRegistry.has_suffix(core_type, self.mapper.suffix):
                    continue
                if core_type in filtered_mutation_types:
                    continue

            # Convert to immutable
            query_type_name = TypeRegistry.get_base_type_name(
                str(core_type), self.mapper.suffix
            )
            query_type = self.mapper.registry.get(query_type_name)

            if query_type:
                field.type = TypeWrapper.rewrap(query_type, wrappers)

    def _remove_query_fields_from_mutable_types(self):
        """
        Remove query-only fields from mutable return types.

        For types returned by resolve_to_mutable fields, we remove
        query fields if the type itself has mutable fields.
        """
        # Find types returned by resolve_to_mutable fields
        mutable_return_types = set()
        for type_, key, field in iterate_fields(self.root):
            meta = self.mapper.meta.get((type_.name, to_snake_case(key)), {})
            if meta.get(GraphQLMetaKey.resolve_to_mutable):
                field_type = TypeWrapper.unwrap(field.type)
                mutable_return_types.add(field_type)

        # Collect fields to remove
        fields_to_remove = set()
        for type_ in mutable_return_types:
            if not isinstance(type_, GraphQLObjectType):
                continue

            # Only remove query fields if type has its own mutable fields
            if not has_mutable(type_, interfaces_default_mutable=False):
                continue

            interface_fields = TypeCollector.collect_interface_fields(type_)

            for key, field in type_.fields.items():
                # Keep interface fields, mutable fields, and fields returning mutable types
                if key in interface_fields:
                    continue
                if isinstance(field, GraphQLMutableField):
                    continue
                if has_mutable(field.type):
                    continue

                # This is a query field - remove it
                fields_to_remove.add((type_, key))

        FieldCleaner.remove_field_list(fields_to_remove)

    def _clean_root_mutation(self):
        """
        Clean the root mutation type to only contain mutable operations.

        Root mutation should only have:
        - Explicitly mutable fields
        - Fields that provide access to mutable functionality
        """
        if not isinstance(self.root, GraphQLObjectType):
            return

        interface_fields = TypeCollector.collect_interface_fields(self.root)
        fields_to_remove = set()

        for key, field in self.root.fields.items():
            # Keep interface fields
            if key in interface_fields:
                continue
            # Keep mutable fields
            if isinstance(field, GraphQLMutableField):
                continue
            # Keep fields that return mutable types
            if has_mutable(field.type):
                continue

            # This is a query-only field - remove it
            fields_to_remove.add(key)

        FieldCleaner.remove_fields(self.root, fields_to_remove)

    def _cleanup_federation_types(self):
        """
        Remove federation types from mutation schema.

        Federation types (_Service, _Entity, etc.) should only exist
        in the query schema, not in mutations.
        """
        if not (hasattr(self.mapper, "schema") and self.mapper.schema
                and getattr(self.mapper.schema, "federation", False)):
            return

        # Define federation type names
        federation_type_names = {
            "_Service", "_ServiceMutable",
            "_Entity", "_EntityMutable",
            "_Any", "_AnyMutable",
        }

        # Find and remove federation types from registry
        types_to_remove = [
            key for key, value in self.mapper.registry.items()
            if hasattr(value, "name") and value.name in federation_type_names
        ]

        for key in types_to_remove:
            if key in self.mapper.registry:
                del self.mapper.registry[key]

        # Also remove federation fields from root mutation
        if hasattr(self.root, "fields"):
            federation_fields = {"_service", "_entities"}
            FieldCleaner.remove_fields(self.root, federation_fields)
