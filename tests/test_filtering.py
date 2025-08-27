from graphql_api.api import GraphQLAPI
from graphql_api.mapper import GraphQLMetaKey
from graphql_api.directives import print_schema


class TestSchemaFiltering:
    def test_query_remove_invalid(self):
        api = GraphQLAPI()

        class Person:
            def __init__(self):
                self.name = ""

            @api.field(mutable=True)
            def update_name(self, name: str) -> "Person":
                self.name = name
                return self

        # noinspection PyUnusedLocal
        @api.type(is_root_type=True)
        class Root:
            @api.field
            def person(self) -> Person:
                return Person()

        executor = api.executor()

        test_query = """
            query PersonName {
                person {
                    updateName(name:"phil") {
                        name
                    }
                }
            }
        """

        result = executor.execute(test_query)
        assert result.errors
        assert "Cannot query field" in result.errors[0].message

    def test_mutation_return_query(self):
        """
        Mutation fields by default should return queries
        :return:
        """
        api = GraphQLAPI()

        class Person:
            def __init__(self):
                self._name = ""

            @api.field
            def name(self) -> str:
                return self._name

            @api.field(mutable=True)
            def update_name(self, name: str) -> "Person":
                self._name = name
                return self

        # noinspection PyUnusedLocal
        @api.type(is_root_type=True)
        class Root:
            @api.field
            def person(self) -> Person:
                return Person()

        executor = api.executor()

        test_query = """
            mutation PersonName {
                person {
                    updateName(name:"phil") {
                        name
                    }
                }
            }
        """

        result = executor.execute(test_query)
        assert not result.errors

        expected = {"person": {"updateName": {"name": "phil"}}}

        assert result.data == expected

    def test_keep_interface(self):
        api = GraphQLAPI()

        @api.type(interface=True)
        class Person:
            @api.field
            def name(self) -> str:
                pass

        class Employee(Person):
            def __init__(self):
                self._name = "Bob"

            @api.field
            def name(self) -> str:
                return self._name

            @api.field
            def department(self) -> str:
                return "Human Resources"

            @api.field(mutable=True)
            def set_name(self, name: str) -> str:
                self._name = name
                return name

        bob_employee = Employee()

        # noinspection PyUnusedLocal
        @api.type(is_root_type=True)
        class Root:
            @api.field
            def person(self) -> Person:
                return bob_employee

        executor = api.executor()

        test_query = """
            query PersonName {
                person {
                    name
                    ... on Employee {
                        department
                    }
                }
            }
        """

        test_mutation = """
            mutation SetPersonName {
                person {
                    ... on EmployeeMutable {
                        setName(name: "Tom")
                    }
                }
            }
        """

        result = executor.execute(test_query)

        expected = {"person": {"name": "Bob", "department": "Human Resources"}}

        expected_2 = {"person": {"name": "Tom", "department": "Human Resources"}}

        assert result.data == expected

        result = executor.execute(test_mutation)

        assert not result.errors

        result = executor.execute(test_query)

        assert result.data == expected_2

    def test_mutation_return_mutable_flag(self):
        api = GraphQLAPI()

        @api.type
        class Person:
            def __init__(self):
                self._name = ""

            @api.field
            def name(self) -> str:
                return self._name

            @api.field(mutable=True)
            def update_name(self, name: str) -> "Person":
                self._name = name
                return self

            @api.field({GraphQLMetaKey.resolve_to_mutable: True}, mutable=True)
            def update_name_mutable(self, name: str) -> "Person":
                self._name = name
                return self

        # noinspection PyUnusedLocal
        @api.type(is_root_type=True)
        class Root:
            @api.field
            def person(self) -> Person:
                return Person()

        executor = api.executor()

        test_query = """
                    mutation PersonName {
                        person {
                            updateName(name:"phil") {
                                name
                            }
                        }
                    }
                """

        result = executor.execute(test_query)
        assert not result.errors

        expected = {"person": {"updateName": {"name": "phil"}}}

        assert result.data == expected

        test_mutable_query = """
                    mutation PersonName {
                        person {
                            updateNameMutable(name:"tom") {
                                updateName(name:"phil") {
                                    name
                                }
                            }
                        }
                    }
                """

        result = executor.execute(test_mutable_query)
        assert not result.errors

        expected = {"person": {"updateNameMutable": {"updateName": {"name": "phil"}}}}

        assert result.data == expected

        test_invalid_query = """
                    mutation PersonName {
                        person {
                            updateName(name:"tom") {
                                updateName(name:"phil") {
                                    name
                                }
                            }
                        }
                    }
                """

        result = executor.execute(test_invalid_query)
        assert result.errors
        assert "Cannot query field 'updateName'" in result.errors[0].message

        test_invalid_mutable_query = """
                    mutation PersonName {
                        person {
                            updateNameMutable(name:"tom") {
                                name
                            }
                        }
                    }
                """

        result = executor.execute(test_invalid_mutable_query)
        assert result.errors
        assert "Cannot query field 'name'" in result.errors[0].message

    def test_filter_all_fields_removes_empty_type(self):
        """
        Test that when filtering removes all fields from a type,
        in strict mode the empty type is completely removed from the schema
        """
        from graphql_api.reduce import TagFilter
        from graphql_api.decorators import field

        class SecretData:
            @field({"tags": ["admin"]})
            def secret_value(self) -> str:
                return "secret"

            @field({"tags": ["admin"]})
            def another_secret(self) -> int:
                return 42

        class Root:
            @field
            def public_data(self) -> str:
                return "public"

            @field
            def secret_data(self) -> SecretData:
                return SecretData()

        # Create API with filter that removes admin fields using strict mode (preserve_transitive=False)
        filtered_api = GraphQLAPI(
            root_type=Root,
            filters=[TagFilter(tags=["admin"], preserve_transitive=False)],
        )
        executor = filtered_api.executor()

        # This query should work without errors
        test_query = """
            query GetPublicData {
                publicData
            }
        """

        result = executor.execute(test_query)
        assert not result.errors
        assert result.data == {"publicData": "public"}

        # SecretData should be completely removed in strict mode
        # The field referencing it should also be removed
        test_query_with_empty_type = """
            query GetSecretData {
                secretData {
                    secretValue
                }
            }
        """

        result = executor.execute(test_query_with_empty_type)
        assert result.errors
        assert "Cannot query field 'secretData'" in str(result.errors[0])

        # Verify schema structure - SecretData should be completely absent
        schema, _ = filtered_api.build_schema()
        type_map = schema.type_map
        assert "SecretData" not in type_map

        # Root should not have the secretData field
        assert schema.query_type is not None
        root_fields = schema.query_type.fields
        assert "publicData" in root_fields
        assert "secretData" not in root_fields

    def test_preserve_transitive_empty_types(self):
        """
        Test that preserve_transitive=True preserves object types that have some accessible fields
        when they are referenced by unfiltered types, even if some of their fields are filtered.
        Types with NO accessible fields cannot be preserved due to GraphQL constraints.
        """
        from graphql_api.reduce import TagFilter
        from graphql_api.decorators import field

        # Type that has some fields filtered but retains one accessible field
        class PartiallyFiltered:
            @field({"tags": ["admin"]})
            def admin_only_field(self) -> str:
                return "admin-only"

            @field  # This field remains accessible
            def public_field(self) -> str:
                return "public data"

        class HasValidFields:
            @field
            def public_field(self) -> str:
                return "public"

            @field
            def partial_ref(self) -> PartiallyFiltered:
                return PartiallyFiltered()

        class Root:
            @field
            def has_valid_fields(self) -> HasValidFields:
                return HasValidFields()

        # Test with preserve_transitive=True (default)
        preserve_api = GraphQLAPI(
            root_type=Root,
            filters=[TagFilter(tags=["admin"], preserve_transitive=True)],
        )

        # Build schema and verify PartiallyFiltered is preserved
        schema, _ = preserve_api.build_schema()
        type_map = schema.type_map

        assert "HasValidFields" in type_map
        assert (
            "PartiallyFiltered" in type_map
        )  # Should be preserved because it has accessible fields!

        # Verify the reference field is preserved
        from graphql import GraphQLObjectType

        has_valid_fields_type = type_map["HasValidFields"]
        assert isinstance(has_valid_fields_type, GraphQLObjectType)
        assert "publicField" in has_valid_fields_type.fields
        assert (
            "partialRef" in has_valid_fields_type.fields
        )  # Reference should be preserved

        # Verify PartiallyFiltered has one accessible field (admin field filtered out)
        partial_type = type_map["PartiallyFiltered"]
        assert isinstance(partial_type, GraphQLObjectType)
        assert len(partial_type.fields) == 1  # One accessible field
        assert "adminOnlyField" not in partial_type.fields  # Filtered field removed
        assert "publicField" in partial_type.fields  # Public field preserved

        # Compare with preserve_transitive=False - in this case, both modes should preserve the type
        # because it has accessible fields
        strict_api = GraphQLAPI(
            root_type=Root,
            filters=[TagFilter(tags=["admin"], preserve_transitive=False)],
        )

        strict_schema, _ = strict_api.build_schema()
        strict_type_map = strict_schema.type_map

        assert "HasValidFields" in strict_type_map
        assert (
            "PartiallyFiltered" in strict_type_map
        )  # Should also be preserved in strict mode

        # Verify the behavior is the same since the type has accessible fields
        strict_partial_type = strict_type_map["PartiallyFiltered"]
        assert isinstance(strict_partial_type, GraphQLObjectType)
        assert len(strict_partial_type.fields) == 1
        assert "publicField" in strict_partial_type.fields

    def test_preserve_transitive_vs_strict_difference(self):
        """
        Test the difference between preserve_transitive=True and preserve_transitive=False.
        preserve_transitive=True should preserve more types that are referenced
        but might not be directly needed.
        """
        from graphql_api.reduce import TagFilter
        from graphql_api.decorators import field

        # A type that would only be preserved with preserve_transitive=True
        class IndirectlyReferenced:
            @field
            def some_data(self) -> str:
                return "data"

        class DirectlyReferenced:
            @field
            def public_info(self) -> str:
                return "public"

            # This creates a transitive reference
            @field
            def indirect_ref(self) -> IndirectlyReferenced:
                return IndirectlyReferenced()

        class Root:
            @field
            def direct_ref(self) -> DirectlyReferenced:
                return DirectlyReferenced()

        # Test preserve_transitive=True (default)
        preserve_api = GraphQLAPI(root_type=Root)
        preserve_schema, _ = preserve_api.build_schema()
        preserve_type_map = preserve_schema.type_map

        # Both types should be preserved
        assert "DirectlyReferenced" in preserve_type_map
        assert "IndirectlyReferenced" in preserve_type_map

        # Test preserve_transitive=False
        strict_api = GraphQLAPI(
            root_type=Root,
            filters=[
                TagFilter(tags=[], preserve_transitive=False)
            ],  # Empty filter with strict behavior
        )
        strict_schema, _ = strict_api.build_schema()
        strict_type_map = strict_schema.type_map

        # Both types should also be preserved in this case since no filtering is applied
        # and both types have accessible fields
        assert "DirectlyReferenced" in strict_type_map
        assert "IndirectlyReferenced" in strict_type_map

    def test_default_filtering_behavior_is_preserve_transitive(self):
        """
        Test that the default filtering behavior preserves transitive dependencies.
        This test verifies that TagFilter defaults to preserve_transitive=True.
        """
        from graphql_api.reduce import TagFilter
        from graphql_api.decorators import field

        class ReferencedType:
            @field
            def some_field(self) -> str:
                return "data"

        class Root:
            @field
            def reference(self) -> ReferencedType:
                return ReferencedType()

        # Test default behavior (TagFilter should default to preserve_transitive=True)
        api_default = GraphQLAPI(root_type=Root, filters=[TagFilter(tags=[])])
        schema_default, _ = api_default.build_schema()

        # Test explicit preserve_transitive=True
        api_preserve = GraphQLAPI(
            root_type=Root, filters=[TagFilter(tags=[], preserve_transitive=True)]
        )
        schema_preserve, _ = api_preserve.build_schema()

        # Both should have the same types
        default_types = {
            name
            for name, type_obj in schema_default.type_map.items()
            if hasattr(type_obj, "fields") and not name.startswith("_")
        }
        preserve_types = {
            name
            for name, type_obj in schema_preserve.type_map.items()
            if hasattr(type_obj, "fields") and not name.startswith("_")
        }

        assert default_types == preserve_types
        assert "ReferencedType" in default_types
        assert "Root" in default_types

    def test_filter_response_enum_properties(self):
        """
        Test that the FilterResponse enum has correct properties
        """
        from graphql_api.reduce import FilterResponse

        # Test ALLOW - keep field, don't preserve transitive
        assert not FilterResponse.KEEP.should_filter
        assert not FilterResponse.KEEP.preserve_transitive

        # Test ALLOW_TRANSITIVE - keep field, preserve transitive
        assert not FilterResponse.KEEP_TRANSITIVE.should_filter
        assert FilterResponse.KEEP_TRANSITIVE.preserve_transitive

        # Test REMOVE - remove field, preserve transitive
        assert FilterResponse.REMOVE.should_filter
        assert FilterResponse.REMOVE.preserve_transitive

        # Test REMOVE_STRICT - remove field, don't preserve transitive
        assert FilterResponse.REMOVE_STRICT.should_filter
        assert not FilterResponse.REMOVE_STRICT.preserve_transitive

    def test_all_filter_response_behaviors(self):
        """
        Test all 4 FilterResponse enum values in a comprehensive scenario
        """
        from graphql_api.reduce import FilterResponse, TagFilter
        from graphql_api.decorators import field

        class AllBehaviorsFilter(TagFilter):
            def __init__(self):
                super().__init__(tags=[], preserve_transitive=True)

            def filter_field(self, name: str, meta: dict) -> FilterResponse:
                tags = meta.get("tags", [])

                if "allow" in tags:
                    return FilterResponse.KEEP  # Keep field, don't preserve transitive
                elif "allow_transitive" in tags:
                    return (
                        FilterResponse.KEEP_TRANSITIVE
                    )  # Keep field, preserve transitive
                elif "remove" in tags:
                    return FilterResponse.REMOVE  # Remove field, preserve transitive
                elif "remove_strict" in tags:
                    return (
                        FilterResponse.REMOVE_STRICT
                    )  # Remove field, don't preserve transitive
                else:
                    return FilterResponse.KEEP_TRANSITIVE  # Default behavior

        class ReferencedType:
            @field({"tags": ["allow"]})
            def allow_field(self) -> str:
                return "allow"

            @field({"tags": ["allow_transitive"]})
            def allow_transitive_field(self) -> str:
                return "allow_transitive"

            @field({"tags": ["remove"]})
            def remove_field(self) -> str:
                return "remove"

            @field({"tags": ["remove_strict"]})
            def remove_strict_field(self) -> str:
                return "remove_strict"

        class Root:
            @field({"tags": ["allow"]})
            def allow_ref(self) -> ReferencedType:
                return ReferencedType()

            @field({"tags": ["allow_transitive"]})
            def allow_transitive_ref(self) -> ReferencedType:
                return ReferencedType()

            @field({"tags": ["remove"]})
            def remove_ref(self) -> ReferencedType:
                return ReferencedType()

            @field({"tags": ["remove_strict"]})
            def remove_strict_ref(self) -> ReferencedType:
                return ReferencedType()

        # Test with the comprehensive filter
        api = GraphQLAPI(root_type=Root, filters=[AllBehaviorsFilter()])
        schema, _ = api.build_schema()
        executor = api.executor()

        # Verify schema structure
        assert schema.query_type is not None
        root_fields = schema.query_type.fields

        # ALLOW and ALLOW_TRANSITIVE should keep the fields
        assert "allowRef" in root_fields
        assert "allowTransitiveRef" in root_fields

        # REMOVE and REMOVE_STRICT should remove the fields
        assert "removeRef" not in root_fields
        assert "removeStrictRef" not in root_fields

        # ReferencedType should still exist (preserved by ALLOW_TRANSITIVE and REMOVE behaviors)
        assert "ReferencedType" in schema.type_map

        from graphql import GraphQLObjectType

        referenced_type = schema.type_map["ReferencedType"]
        assert isinstance(referenced_type, GraphQLObjectType)

        # Only ALLOW and ALLOW_TRANSITIVE fields should remain in ReferencedType
        assert "allowField" in referenced_type.fields
        assert "allowTransitiveField" in referenced_type.fields
        assert "removeField" not in referenced_type.fields
        assert "removeStrictField" not in referenced_type.fields

        # Test queries work for allowed fields
        result = executor.execute(
            """
            query TestAllowed {
                allowRef {
                    allowField
                    allowTransitiveField
                }
                allowTransitiveRef {
                    allowField
                    allowTransitiveField
                }
            }
        """
        )

        assert not result.errors
        expected = {
            "allowRef": {
                "allowField": "allow",
                "allowTransitiveField": "allow_transitive",
            },
            "allowTransitiveRef": {
                "allowField": "allow",
                "allowTransitiveField": "allow_transitive",
            },
        }
        assert result.data == expected

    def test_custom_filter_without_preserve_transitive_attribute(self):
        """
        Test that custom filters without preserve_transitive attributes work correctly.
        This addresses the issue where the system was trying to access preserve_transitive
        on filter objects instead of determining behavior from FilterResponse values.
        """
        from graphql_api.reduce import GraphQLFilter, FilterResponse
        from graphql_api.decorators import field

        class CustomFilter(GraphQLFilter):
            """Custom filter without preserve_transitive attribute"""

            def filter_field(self, name: str, meta: dict) -> FilterResponse:
                tags = meta.get("tags", [])

                if "private" in tags:
                    return FilterResponse.REMOVE_STRICT  # Remove without preservation
                elif "admin" in tags:
                    return FilterResponse.REMOVE  # Remove with preservation
                else:
                    return FilterResponse.KEEP_TRANSITIVE  # Keep with preservation

        class DataType:
            @field
            def public_field(self) -> str:
                return "public"

            @field({"tags": ["private"]})
            def private_field(self) -> str:
                return "private"

            @field({"tags": ["admin"]})
            def admin_field(self) -> str:
                return "admin"

        class Root:
            @field
            def data(self) -> DataType:
                return DataType()

        # This should work without errors (no preserve_transitive attribute access)
        api = GraphQLAPI(root_type=Root, filters=[CustomFilter()])
        schema, _ = api.build_schema()
        executor = api.executor()

        # Verify schema structure
        assert "DataType" in schema.type_map
        from graphql import GraphQLObjectType

        data_type = schema.type_map["DataType"]
        assert isinstance(data_type, GraphQLObjectType)

        # Should have public field but not private/admin fields
        assert "publicField" in data_type.fields
        assert "privateField" not in data_type.fields
        assert "adminField" not in data_type.fields

        # Test query execution
        result = executor.execute(
            """
            query TestQuery {
                data {
                    publicField
                }
            }
        """
        )

        assert not result.errors
        assert result.data == {"data": {"publicField": "public"}}

    def test_non_root_mutable_types_contain_both_field_types(self):
        """
        Test that non-root mutable types (like UserMutable) contain both mutable fields
        and query fields for GraphQL compatibility. This validates the core mutation behavior.
        """
        from graphql_api.decorators import field

        class User:
            def __init__(self):
                self._name = "John"
                self._email = "john@example.com"
                self._age = 25

            @field
            def name(self) -> str:
                """Regular query field - should NOT be in mutable type"""
                return self._name

            @field
            def email(self) -> str:
                """Regular query field - should NOT be in mutable type"""
                return self._email

            @field
            def age(self) -> int:
                """Regular query field - should NOT be in mutable type"""
                return self._age

            @field(mutable=True)
            def update_name(self, new_name: str) -> "User":
                """Mutable field - should be in mutable type"""
                self._name = new_name
                return self

            @field(mutable=True)
            def update_email(self, new_email: str) -> "User":
                """Mutable field - should be in mutable type"""
                self._email = new_email
                return self

        class Root:
            @field
            def user(self) -> User:
                return User()

        # Build the API
        api = GraphQLAPI(root_type=Root)
        schema, _ = api.build_schema()

        # Check that User (query type) has all fields
        from graphql import GraphQLObjectType
        user_type = schema.type_map["User"]
        assert isinstance(user_type, GraphQLObjectType)
        user_fields = set(user_type.fields.keys())
        expected_user_fields = {"name", "email", "age"}

        print(f"User (query) fields: {user_fields}")
        assert expected_user_fields.issubset(user_fields), f"User should have query fields {expected_user_fields}"

        # Check that UserMutable has both mutable and query fields for compatibility
        user_mutable_type = schema.type_map["UserMutable"]
        assert isinstance(user_mutable_type, GraphQLObjectType)
        user_mutable_fields = set(user_mutable_type.fields.keys())
        expected_mutable_fields = {"updateName", "updateEmail"}
        expected_query_fields = {"name", "email", "age"}

        print(f"UserMutable fields: {user_mutable_fields}")

        # CRITICAL TEST: Mutable type should have mutable fields
        assert expected_mutable_fields.issubset(user_mutable_fields), f"UserMutable should have mutable fields {expected_mutable_fields}"

        # CRITICAL TEST: Non-root mutable type should also have query fields for compatibility
        assert expected_query_fields.issubset(user_mutable_fields), f"UserMutable should have query fields {expected_query_fields} for GraphQL compatibility"

        # Test that mutations work correctly
        executor = api.executor()
        result = executor.execute("""
            mutation UpdateUser {
                user {
                    updateName(newName: "Jane") {
                        name
                        email
                    }
                }
            }
        """)

        assert not result.errors
        assert result.data == {
            "user": {
                "updateName": {
                    "name": "Jane",
                    "email": "john@example.com"
                }
            }
        }

    def test_root_mutation_type_only_has_mutable_fields(self):
        """
        Test that the root mutation type only contains mutable fields, not query fields.
        This validates that the mutation root filtering is working correctly.
        """
        from graphql_api.decorators import field

        class User:
            def __init__(self):
                self._name = "John"
                self._email = "john@example.com"

            @field
            def name(self) -> str:
                return self._name

            @field
            def email(self) -> str:
                return self._email

            @field(mutable=True)
            def update_name(self, new_name: str) -> "User":
                self._name = new_name
                return self

        class Root:
            def __init__(self):
                self._counter = 0

            @field
            def user(self) -> User:
                """Query field - should NOT be in root mutation type"""
                return User()

            @field
            def counter(self) -> int:
                """Query field - should NOT be in root mutation type"""
                return self._counter

            @field(mutable=True)
            def create_user(self, name: str) -> User:
                """Mutable field - should be in root mutation type"""
                user = User()
                user._name = name
                return user

            @field(mutable=True)
            def increment_counter(self) -> int:
                """Mutable field - should be in root mutation type"""
                self._counter += 1
                return self._counter

        # Build the API
        api = GraphQLAPI(root_type=Root)
        schema, _ = api.build_schema()

        # Check that Root (query type) has all fields
        from graphql import GraphQLObjectType
        root_type = schema.type_map["Root"]
        assert isinstance(root_type, GraphQLObjectType)
        root_fields = set(root_type.fields.keys())
        expected_query_fields = {"user", "counter"}

        print(f"Root (query) fields: {root_fields}")
        assert expected_query_fields.issubset(root_fields), f"Root should have query fields {expected_query_fields}"

        # Check that RootMutable (mutation root) has mutable fields and fields providing mutable access
        root_mutation_type = schema.mutation_type
        assert root_mutation_type is not None
        assert isinstance(root_mutation_type, GraphQLObjectType)
        root_mutation_fields = set(root_mutation_type.fields.keys())
        expected_fields = {"createUser", "incrementCounter", "user"}  # mutable fields + fields providing mutable access
        unexpected_fields = {"counter"}  # pure query fields that don't provide mutable access

        print(f"RootMutable (mutation root) fields: {root_mutation_fields}")

        # CRITICAL TEST: Root mutation type should have mutable fields and mutable access fields
        assert expected_fields.issubset(root_mutation_fields), f"RootMutable should have fields {expected_fields}"

        # CRITICAL TEST: Root mutation type should NOT have pure query fields
        overlapping_fields = root_mutation_fields.intersection(unexpected_fields)
        assert not overlapping_fields, f"RootMutable should NOT contain pure query fields: {overlapping_fields}"

        # Test that mutations work correctly
        executor = api.executor()
        result = executor.execute("""
            mutation CreateAndRead {
                createUser(name: "Alice") {
                    name
                    email
                }
                incrementCounter
            }
        """)

        assert not result.errors
        assert result.data == {
            "createUser": {
                "name": "Alice",
                "email": "john@example.com"
            },
            "incrementCounter": 1
        }

    def test_allow_transitive_preserves_object_types(self):
        """
        Test that ALLOW_TRANSITIVE correctly preserves transitive object types
        that would otherwise be filtered out.
        """
        from graphql_api.decorators import field
        from graphql_api.reduce import FilterResponse

        class AdminUser:
            """This type would normally be filtered out due to admin tags"""
            def __init__(self):
                self._name = "Admin User"
                self._secret = "classified"

            @field({"tags": ["admin"]})
            def name(self) -> str:
                return self._name

            @field({"tags": ["admin"]})
            def secret(self) -> str:
                return self._secret

        class PublicData:
            """This type has no admin tags and should always be present"""
            def __init__(self):
                self._info = "public info"

            @field
            def info(self) -> str:
                return self._info

        class Root:
            @field({"tags": ["admin"]})  # This field should use ALLOW_TRANSITIVE
            def admin_user(self) -> AdminUser:
                """Field that returns AdminUser - should preserve AdminUser type with ALLOW_TRANSITIVE"""
                return AdminUser()

            @field
            def public_data(self) -> PublicData:
                return PublicData()

        # Create a custom filter that uses ALLOW_TRANSITIVE for admin_user field
        from graphql_api.reduce import GraphQLFilter

        class TestFilter(GraphQLFilter):
            def filter_field(self, name: str, meta: dict) -> FilterResponse:
                tags = meta.get("tags", [])
                if "admin" in tags:
                    if name == "admin_user":
                        # Use ALLOW_TRANSITIVE to preserve the AdminUser type
                        return FilterResponse.KEEP_TRANSITIVE
                    else:
                        # Other admin fields should be removed
                        return FilterResponse.REMOVE_STRICT
                return FilterResponse.KEEP

        # Build the API with the custom filter
        api = GraphQLAPI(root_type=Root, filters=[TestFilter()])
        schema, _ = api.build_schema()

        type_map = schema.type_map

        print(f"Types in schema: {sorted([k for k in type_map.keys() if not k.startswith('__')])}")

        # The key test: AdminUser should be preserved because admin_user field uses ALLOW_TRANSITIVE
        assert "AdminUser" in type_map, "AdminUser type should be preserved due to ALLOW_TRANSITIVE on admin_user field"

        # PublicData should also be present (normal case)
        assert "PublicData" in type_map, "PublicData should be present"

        # Root should be present
        assert "Root" in type_map, "Root should be present"

        # Check that the admin_user field is present on Root
        from graphql import GraphQLObjectType
        root_type = type_map["Root"]
        assert isinstance(root_type, GraphQLObjectType)
        assert "adminUser" in root_type.fields, "adminUser field should be present on Root"

        # Check that AdminUser type has its fields (they should be filtered out but type preserved)
        admin_user_type = type_map["AdminUser"]
        assert isinstance(admin_user_type, GraphQLObjectType)

        # The AdminUser fields should be filtered out (REMOVE_STRICT), but the type should exist
        admin_user_fields = set(admin_user_type.fields.keys())
        print(f"AdminUser fields: {admin_user_fields}")

        # Test that we can query the preserved type structure
        executor = api.executor()

        # This should work - we can access the admin_user field and get back data
        result = executor.execute("""
            query TestQuery {
                adminUser {
                    __typename
                }
                publicData {
                    info
                }
            }
        """)

        print(f"Query result: {result.data}")
        print(f"Query errors: {result.errors}")

        assert not result.errors, f"Query should succeed, but got errors: {result.errors}"
        assert result.data == {
            "adminUser": {"__typename": "AdminUser"},
            "publicData": {"info": "public info"}
        }

    def test_allow_transitive_with_remove_vs_remove_strict(self):
        """
        Test that ALLOW_TRANSITIVE works correctly with both REMOVE and REMOVE_STRICT
        for filtering out other fields on the preserved type.
        """
        from graphql_api.decorators import field
        from graphql_api.reduce import FilterResponse, GraphQLFilter

        class AdminUser:
            """This type would normally be filtered out due to admin tags"""
            def __init__(self):
                self._name = "Admin User"
                self._secret = "classified"
                self._level = 5

            @field({"tags": ["admin"]})
            def name(self) -> str:
                return self._name

            @field({"tags": ["admin"]})
            def secret(self) -> str:
                return self._secret

            @field({"tags": ["admin"]})
            def level(self) -> int:
                return self._level

        class PublicData:
            def __init__(self):
                self._info = "public info"

            @field
            def info(self) -> str:
                return self._info

        class Root:
            @field({"tags": ["admin"]})
            def admin_user(self) -> AdminUser:
                """Field that returns AdminUser - should preserve AdminUser type with ALLOW_TRANSITIVE"""
                return AdminUser()

            @field
            def public_data(self) -> PublicData:
                return PublicData()

        # Test 1: ALLOW_TRANSITIVE with REMOVE_STRICT (existing behavior)
        class TestFilterStrict(GraphQLFilter):
            def filter_field(self, name: str, meta: dict) -> FilterResponse:
                tags = meta.get("tags", [])
                if "admin" in tags:
                    if name == "admin_user":
                        return FilterResponse.KEEP_TRANSITIVE
                    else:
                        return FilterResponse.REMOVE_STRICT
                return FilterResponse.KEEP

        api_strict = GraphQLAPI(root_type=Root, filters=[TestFilterStrict()])
        schema_strict, _ = api_strict.build_schema()

        # Test 2: ALLOW_TRANSITIVE with REMOVE (new test case)
        class TestFilterRemove(GraphQLFilter):
            def filter_field(self, name: str, meta: dict) -> FilterResponse:
                tags = meta.get("tags", [])
                if "admin" in tags:
                    if name == "admin_user":
                        return FilterResponse.KEEP_TRANSITIVE
                    else:
                        return FilterResponse.REMOVE  # Use REMOVE instead of REMOVE_STRICT
                return FilterResponse.KEEP

        api_remove = GraphQLAPI(root_type=Root, filters=[TestFilterRemove()])
        schema_remove, _ = api_remove.build_schema()

        # Both schemas should preserve AdminUser type
        for schema, test_name in [(schema_strict, "REMOVE_STRICT"), (schema_remove, "REMOVE")]:
            type_map = schema.type_map

            print(f"{test_name} - Types in schema: {sorted([k for k in type_map.keys() if not k.startswith('__')])}")

            # AdminUser should be preserved in both cases
            assert "AdminUser" in type_map, f"AdminUser type should be preserved with ALLOW_TRANSITIVE + {test_name}"

            # Check that AdminUser has at least one field preserved
            from graphql import GraphQLObjectType
            admin_user_type = type_map["AdminUser"]
            assert isinstance(admin_user_type, GraphQLObjectType)
            admin_user_fields = set(admin_user_type.fields.keys())

            print(f"{test_name} - AdminUser fields: {admin_user_fields}")
            assert len(admin_user_fields) > 0, f"AdminUser should have at least one field preserved with {test_name}"

        # Both should work for queries
        for api, test_name in [(api_strict, "REMOVE_STRICT"), (api_remove, "REMOVE")]:
            executor = api.executor()
            result = executor.execute("""
                query TestQuery {
                    adminUser {
                        __typename
                    }
                    publicData {
                        info
                    }
                }
            """)

            print(f"{test_name} - Query result: {result.data}")
            print(f"{test_name} - Query errors: {result.errors}")

            assert not result.errors, f"Query should succeed with ALLOW_TRANSITIVE + {test_name}, but got errors: {result.errors}"
            assert result.data == {
                "adminUser": {"__typename": "AdminUser"},
                "publicData": {"info": "public info"}
            }, f"Query data should be correct with {test_name}"

    def test_remove_strict_always_removed_regardless_of_transitive(self):
        """
        Test that fields marked with REMOVE_STRICT are always removed,
        even when the type is preserved due to ALLOW_TRANSITIVE logic.
        """
        from graphql_api.decorators import field
        from graphql_api.reduce import FilterResponse, GraphQLFilter

        class SecretData:
            """This type will be preserved due to ALLOW_TRANSITIVE, but some fields should still be removed"""
            def __init__(self):
                self._public_info = "public"
                self._secret_info = "secret"
                self._classified_info = "classified"

            @field
            def public_info(self) -> str:
                """This field should be preserved (no tags)"""
                return self._public_info

            @field({"tags": ["secret"]})
            def secret_info(self) -> str:
                """This field should be removed with REMOVE_STRICT"""
                return self._secret_info

            @field({"tags": ["classified"]})
            def classified_info(self) -> str:
                """This field should be removed with REMOVE_STRICT"""
                return self._classified_info

        class Root:
            @field({"tags": ["admin"]})
            def secret_data(self) -> SecretData:
                """This field uses ALLOW_TRANSITIVE to preserve SecretData type"""
                return SecretData()

            @field
            def public_field(self) -> str:
                return "public"

        # Create a filter that uses ALLOW_TRANSITIVE for secret_data field
        # but REMOVE_STRICT for secret_info and classified_info fields
        class TestFilter(GraphQLFilter):
            def filter_field(self, name: str, meta: dict) -> FilterResponse:
                tags = meta.get("tags", [])

                if name == "secret_data" and "admin" in tags:
                    # Use ALLOW_TRANSITIVE to preserve SecretData type
                    return FilterResponse.KEEP_TRANSITIVE
                elif "secret" in tags or "classified" in tags:
                    # These fields should ALWAYS be removed, even if type is preserved
                    return FilterResponse.REMOVE_STRICT
                elif "admin" in tags:
                    # Other admin fields are removed normally
                    return FilterResponse.REMOVE
                else:
                    # Allow all other fields
                    return FilterResponse.KEEP

        # Build the API with the test filter
        api = GraphQLAPI(root_type=Root, filters=[TestFilter()])
        schema, _ = api.build_schema()

        type_map = schema.type_map

        print(f"Types in schema: {sorted([k for k in type_map.keys() if not k.startswith('__')])}")

        # SecretData should be preserved due to ALLOW_TRANSITIVE
        assert "SecretData" in type_map, "SecretData type should be preserved due to ALLOW_TRANSITIVE"

        # Check SecretData fields
        from graphql import GraphQLObjectType
        secret_data_type = type_map["SecretData"]
        assert isinstance(secret_data_type, GraphQLObjectType)
        secret_data_fields = set(secret_data_type.fields.keys())

        print(f"SecretData fields: {secret_data_fields}")

        # CRITICAL TEST: REMOVE_STRICT fields should be removed despite ALLOW_TRANSITIVE
        assert "secretInfo" not in secret_data_fields, "secretInfo should be removed (REMOVE_STRICT) even though type is preserved"
        assert "classifiedInfo" not in secret_data_fields, "classifiedInfo should be removed (REMOVE_STRICT) even though type is preserved"

        # public_info should be preserved (it has no filtering tags)
        assert "publicInfo" in secret_data_fields, "publicInfo should be preserved (no filtering applied)"

        # Test that queries work correctly
        executor = api.executor()

        # This should work - we can access secret_data but only get allowed fields
        result = executor.execute("""
            query TestQuery {
                secretData {
                    publicInfo
                }
                publicField
            }
        """)

        print(f"Query result: {result.data}")
        print(f"Query errors: {result.errors}")

        assert not result.errors, f"Query should succeed, but got errors: {result.errors}"
        assert result.data == {
            "secretData": {"publicInfo": "public"},
            "publicField": "public"
        }

        # This should fail - trying to access REMOVE_STRICT fields
        result_with_forbidden = executor.execute("""
            query TestForbiddenQuery {
                secretData {
                    secretInfo
                }
            }
        """)

        print(f"Forbidden query errors: {result_with_forbidden.errors}")

        # Should get an error trying to access the REMOVE_STRICT field
        assert result_with_forbidden.errors, "Should get error when trying to access REMOVE_STRICT field"
        assert "Cannot query field 'secretInfo'" in str(result_with_forbidden.errors[0])

    def test_unused_mutable_types_filtered_out(self):
        """
        Test that mutable object types that are not used from the root mutation type are filtered out.
        Only mutable types that are actually reachable from the root should remain in the schema.

        This test verifies that:
        1. Unused mutable types (UnusedMutableType, AnotherUnusedMutableType) are not included in the schema
        2. Used mutable types (UsedMutableType) are correctly included
        3. The filtering works correctly even with the fixed field.type assignment
        4. Query fields are preserved on mutable types (unless marked with resolve_to_mutable: True)
        """
        from graphql_api.decorators import field

        class UsedMutableType:
            """This type will be referenced from the root mutation"""

            def __init__(self):
                self._value = "used"

            @field
            def value(self) -> str:
                return self._value

            @field(mutable=True)
            def update_value(self, new_value: str) -> "UsedMutableType":
                self._value = new_value
                return self

        class UnusedMutableType:
            """This type will NOT be referenced from the root mutation"""

            def __init__(self):
                self._data = "unused"

            @field
            def data(self) -> str:
                return self._data

            @field(mutable=True)
            def update_data(self, new_data: str) -> "UnusedMutableType":
                self._data = new_data
                return self

        class AnotherUnusedMutableType:
            """Another unused mutable type to make the test more comprehensive"""

            def __init__(self):
                self._info = "also unused"

            @field
            def info(self) -> str:
                return self._info

            @field(mutable=True)
            def update_info(self, new_info: str) -> "AnotherUnusedMutableType":
                self._info = new_info
                return self

        class Root:
            @field
            def used_object(self) -> UsedMutableType:
                return UsedMutableType()

            @field(mutable=True)
            def create_used_object(self, value: str) -> UsedMutableType:
                obj = UsedMutableType()
                obj._value = value
                return obj

            # Note: We deliberately don't reference UnusedMutableType or AnotherUnusedMutableType

        # Build the API
        api = GraphQLAPI(root_type=Root)
        schema, _ = api.build_schema()

        # Check that only used types are in the schema
        type_map = schema.type_map

        # UsedMutableType should be present (both in query and mutation forms)
        assert "UsedMutableType" in type_map
        assert "UsedMutableTypeMutable" in type_map

        # UnusedMutableType should NOT be present in either form
        assert "UnusedMutableType" not in type_map
        assert "UnusedMutableTypeMutable" not in type_map

        # AnotherUnusedMutableType should NOT be present in either form
        assert "AnotherUnusedMutableType" not in type_map
        assert "AnotherUnusedMutableTypeMutable" not in type_map

        # Verify the mutation schema only contains used types
        mutation_type = schema.mutation_type
        assert mutation_type is not None

        # Should have create_used_object mutation field
        assert "createUsedObject" in mutation_type.fields

        # Should be able to access the used object's mutable methods
        assert "usedObject" in mutation_type.fields

        # Test that mutation operations work correctly
        executor = api.executor()

        # Test creating and updating the used object
        result = executor.execute(
            """
            mutation TestMutation {
                createUsedObject(value: "test") {
                    updateValue(newValue: "updated") {
                        value
                    }
                }
            }
        """
        )

        assert not result.errors
        assert result.data == {
            "createUsedObject": {"updateValue": {"value": "updated"}}
        }

        # Test that we can't access unused types (they shouldn't exist in the schema)
        # This mutation should fail at schema build time, not execution time
        try:
            _ = executor.execute(
                """
                mutation BadMutation {
                    unusedObject {
                        updateData(newData: "test") {
                            data
                        }
                    }
                }
            """
            )
            # If we get here, the unused type wasn't properly filtered out
            assert False, "Unused mutable type should not be accessible in mutations"
        except Exception:
            # Expected - the field shouldn't exist
            pass

    def test_filter_mutable_fields(self):
        """
        Test filtering of mutable fields in both query and mutation contexts
        """
        from graphql_api.reduce import TagFilter
        from graphql_api.decorators import field

        class User:
            def __init__(self):
                self._name = "John"
                self._email = "john@example.com"
                self._admin_notes = "secret notes"

            @field
            def name(self) -> str:
                return self._name

            @field
            def email(self) -> str:
                return self._email

            @field({"tags": ["admin"]})
            def admin_notes(self) -> str:
                return self._admin_notes

            @field(mutable=True)
            def update_name(self, name: str) -> "User":
                self._name = name
                return self

            @field({"tags": ["admin"]}, mutable=True)
            def update_admin_notes(self, notes: str) -> "User":
                self._admin_notes = notes
                return self

            @field({"tags": ["admin"]}, mutable=True)
            def delete_user(self) -> bool:
                return True

        class Root:
            @field
            def user(self) -> User:
                return User()

        # Test with admin filter
        filtered_api = GraphQLAPI(root_type=Root, filters=[TagFilter(tags=["admin"])])
        executor = filtered_api.executor()

        # Query should work for non-admin fields
        query_test = """
            query GetUser {
                user {
                    name
                    email
                }
            }
        """
        result = executor.execute(query_test)
        assert not result.errors
        assert result.data == {"user": {"name": "John", "email": "john@example.com"}}

        # Query should fail for admin fields
        admin_query_test = """
            query GetAdminNotes {
                user {
                    adminNotes
                }
            }
        """
        result = executor.execute(admin_query_test)
        assert result.errors
        assert "Cannot query field 'adminNotes'" in str(result.errors[0])

        # Mutation should work for non-admin mutable fields
        mutation_test = """
            mutation UpdateName {
                user {
                    updateName(name: "Jane") {
                        name
                    }
                }
            }
        """
        result = executor.execute(mutation_test)
        assert not result.errors
        assert result.data == {"user": {"updateName": {"name": "Jane"}}}

        # Mutation should fail for admin mutable fields
        admin_mutation_test = """
            mutation UpdateAdminNotes {
                user {
                    updateAdminNotes(notes: "new notes") {
                        name
                    }
                }
            }
        """
        result = executor.execute(admin_mutation_test)
        assert result.errors
        assert "Cannot query field 'updateAdminNotes'" in str(result.errors[0])

    def test_filter_interface_fields(self):
        """
        Test filtering of fields on interfaces and their implementations
        """
        from graphql_api.reduce import TagFilter
        from graphql_api.decorators import field

        class Animal:
            @field
            def name(self) -> str:
                ...

            @field({"tags": ["vet"]})
            def medical_history(self) -> str:
                ...

        class Dog(Animal):
            def __init__(self):
                self._name = "Buddy"

            @field
            def name(self) -> str:
                return self._name

            @field({"tags": ["vet"]})
            def medical_history(self) -> str:
                return "Vaccinated"

            @field
            def breed(self) -> str:
                return "Golden Retriever"

            @field({"tags": ["vet"]})
            def vet_notes(self) -> str:
                return "Healthy dog"

        class Root:
            @field
            def dog(self) -> Dog:
                return Dog()

            @field({"tags": ["vet"]})
            def vet_data(self) -> str:
                return "Only for vets"

        # Test with vet filter
        filtered_api = GraphQLAPI(root_type=Root, filters=[TagFilter(tags=["vet"])])
        executor = filtered_api.executor()

        # Should work for non-vet fields
        test_query = """
            query GetAnimals {
                dog {
                    name
                    breed
                }
            }
        """
        result = executor.execute(test_query)
        assert not result.errors
        expected = {"dog": {"name": "Buddy", "breed": "Golden Retriever"}}
        assert result.data == expected

        # Should fail for vet fields
        vet_query = """
            query GetVetInfo {
                dog {
                    medicalHistory
                }
            }
        """
        result = executor.execute(vet_query)
        assert result.errors
        assert "Cannot query field 'medicalHistory'" in str(result.errors[0])

        # Should fail for vet root fields
        vet_root_query = """
            query GetVetData {
                vetData
            }
        """
        result = executor.execute(vet_root_query)
        assert result.errors
        assert "Cannot query field 'vetData'" in str(result.errors[0])

    def test_filter_nested_types(self):
        """
        Test filtering with deeply nested type structures
        """
        from graphql_api.reduce import TagFilter
        from graphql_api.decorators import field

        class Address:
            @field
            def street(self) -> str:
                return "123 Main St"

            @field({"tags": ["private"]})
            def apartment_number(self) -> str:
                return "Apt 4B"

        class ContactInfo:
            @field
            def email(self) -> str:
                return "user@example.com"

            @field({"tags": ["private"]})
            def phone(self) -> str:
                return "555-0123"

            @field
            def address(self) -> Address:
                return Address()

        class Profile:
            @field
            def bio(self) -> str:
                return "Software developer"

            @field({"tags": ["private"]})
            def salary(self) -> int:
                return 75000

            @field
            def contact(self) -> ContactInfo:
                return ContactInfo()

        class User:
            @field
            def username(self) -> str:
                return "johndoe"

            @field
            def profile(self) -> Profile:
                return Profile()

        class Root:
            @field
            def user(self) -> User:
                return User()

        # Test with private filter
        filtered_api = GraphQLAPI(root_type=Root, filters=[TagFilter(tags=["private"])])
        executor = filtered_api.executor()

        # Should work for non-private nested fields
        test_query = """
            query GetUserData {
                user {
                    username
                    profile {
                        bio
                        contact {
                            email
                            address {
                                street
                            }
                        }
                    }
                }
            }
        """
        result = executor.execute(test_query)
        assert not result.errors
        expected = {
            "user": {
                "username": "johndoe",
                "profile": {
                    "bio": "Software developer",
                    "contact": {
                        "email": "user@example.com",
                        "address": {"street": "123 Main St"},
                    },
                },
            }
        }
        assert result.data == expected

        # Should fail for private fields at any level
        private_query = """
            query GetPrivateData {
                user {
                    profile {
                        salary
                    }
                }
            }
        """
        result = executor.execute(private_query)
        assert result.errors
        assert "Cannot query field 'salary'" in str(result.errors[0])

    def test_filter_list_and_optional_fields(self):
        """
        Test filtering with list and optional field types
        """
        from graphql_api.reduce import TagFilter
        from graphql_api.decorators import field
        from typing import List, Optional

        class Tag:
            def __init__(self, name: str):
                self._name = name

            @field
            def name(self) -> str:
                return self._name

            @field({"tags": ["internal"]})
            def internal_id(self) -> int:
                return 123

        class Post:
            @field
            def title(self) -> str:
                return "My Post"

            @field
            def tags(self) -> List[Tag]:
                return [Tag("python"), Tag("graphql")]

            @field({"tags": ["internal"]})
            def internal_tags(self) -> Optional[List[Tag]]:
                return [Tag("draft")]

            @field
            def optional_summary(self) -> Optional[str]:
                return None

            @field({"tags": ["admin"]})
            def admin_notes(self) -> Optional[str]:
                return "Admin only note"

        class Root:
            @field
            def post(self) -> Post:
                return Post()

            @field({"tags": ["internal"]})
            def internal_posts(self) -> List[Post]:
                return [Post()]

        # Test with internal and admin filters
        filtered_api = GraphQLAPI(
            root_type=Root, filters=[TagFilter(tags=["internal", "admin"])]
        )
        executor = filtered_api.executor()

        # Should work for non-filtered list/optional fields
        test_query = """
            query GetPost {
                post {
                    title
                    tags {
                        name
                    }
                    optionalSummary
                }
            }
        """
        result = executor.execute(test_query)
        assert not result.errors
        expected = {
            "post": {
                "title": "My Post",
                "tags": [{"name": "python"}, {"name": "graphql"}],
                "optionalSummary": None,
            }
        }
        assert result.data == expected

        # Should fail for filtered fields
        internal_query = """
            query GetInternalData {
                post {
                    internalTags {
                        name
                    }
                }
            }
        """
        result = executor.execute(internal_query)
        assert result.errors
        assert "Cannot query field 'internalTags'" in str(result.errors[0])

    def test_filter_union_types(self):
        """
        Test filtering with union types
        """
        from graphql_api.reduce import TagFilter
        from graphql_api.decorators import field
        from typing import Union

        class PublicContent:
            @field
            def title(self) -> str:
                return "Public Content"

            @field
            def content(self) -> str:
                return "This is public"

        class PrivateContent:
            @field({"tags": ["admin"]})
            def title(self) -> str:
                return "Private Content"

            @field({"tags": ["admin"]})
            def secret_data(self) -> str:
                return "Secret information"

        class MixedContent:
            @field
            def public_field(self) -> str:
                return "Public"

            @field({"tags": ["admin"]})
            def private_field(self) -> str:
                return "Private"

        class Root:
            @field
            def content(self) -> Union[PublicContent, PrivateContent, MixedContent]:
                return PublicContent()

            @field
            def mixed_content(self) -> Union[PublicContent, MixedContent]:
                return MixedContent()

        # Test with admin filter
        filtered_api = GraphQLAPI(root_type=Root, filters=[TagFilter(tags=["admin"])])
        executor = filtered_api.executor()

        # Should work for public union types
        test_query = """
            query GetContent {
                content {
                    ... on PublicContent {
                        title
                        content
                    }
                }
                mixedContent {
                    ... on PublicContent {
                        title
                        content
                    }
                    ... on MixedContent {
                        publicField
                    }
                }
            }
        """
        result = executor.execute(test_query)
        assert not result.errors
        expected = {
            "content": {"title": "Public Content", "content": "This is public"},
            "mixedContent": {"publicField": "Public"},
        }
        assert result.data == expected

        # PrivateContent should be removed from union since all its fields are filtered
        # This should still work but PrivateContent won't be available
        private_query = """
            query GetPrivateContent {
                content {
                    ... on PrivateContent {
                        title
                    }
                }
            }
        """
        result = executor.execute(private_query)
        # This should execute without errors but return no data for PrivateContent
        assert not result.errors
        assert result.data == {"content": {}}

    def test_filter_multiple_criteria(self):
        """
        Test filtering with multiple filter criteria
        """
        from graphql_api.reduce import TagFilter, FilterResponse
        from graphql_api.decorators import field

        class CustomFilter(TagFilter):
            def filter_field(self, name: str, meta: dict) -> FilterResponse:
                # Filter out fields with 'admin' tag OR fields starting with 'internal_'
                parent_response = super().filter_field(name, meta)
                if parent_response.should_filter:
                    return parent_response

                # Filter fields starting with 'internal_'
                if name.startswith("internal_"):
                    return (
                        FilterResponse.REMOVE
                        if self.preserve_transitive
                        else FilterResponse.REMOVE_STRICT
                    )
                else:
                    return FilterResponse.KEEP_TRANSITIVE

        class Data:
            @field
            def public_data(self) -> str:
                return "public"

            @field({"tags": ["admin"]})
            def admin_data(self) -> str:
                return "admin only"

            @field
            def internal_data(self) -> str:
                return "internal"

            @field({"tags": ["user"]})
            def internal_user_data(self) -> str:
                return "internal user data"

        class Root:
            @field
            def data(self) -> Data:
                return Data()

        # Test with custom filter
        filtered_api = GraphQLAPI(
            root_type=Root, filters=[CustomFilter(tags=["admin"])]
        )
        executor = filtered_api.executor()

        # Should be able to query public data
        test_query = """
            query GetData {
                data {
                    publicData
                }
            }
        """

        result = executor.execute(test_query)
        assert not result.errors
        assert result.data == {"data": {"publicData": "public"}}

        # Should NOT be able to query admin data (filtered by tag)
        admin_query = """
            query GetAdminData {
                data {
                    adminData
                }
            }
        """

        result = executor.execute(admin_query)
        assert result.errors
        assert "Cannot query field 'adminData'" in str(result.errors[0])

        # Should NOT be able to query internal data (filtered by name)
        internal_query = """
            query GetInternalData {
                data {
                    internalData
                }
            }
        """

        result = executor.execute(internal_query)
        assert result.errors
        assert "Cannot query field 'internalData'" in str(result.errors[0])

        # Should NOT be able to query internal user data (filtered by name, even though tag is not in filter)
        internal_user_query = """
            query GetInternalUserData {
                data {
                    internalUserData
                }
            }
        """

        result = executor.execute(internal_user_query)
        assert result.errors
        assert "Cannot query field 'internalUserData'" in str(result.errors[0])

    def test_filter_empty_mutation_type(self):
        """
        Test that filtering can remove all mutable fields leaving empty mutation type
        """
        from graphql_api.reduce import TagFilter
        from graphql_api.decorators import field

        class User:
            def __init__(self):
                self._name = "John"

            @field
            def name(self) -> str:
                return self._name

            @field({"tags": ["admin"]}, mutable=True)
            def update_name(self, name: str) -> "User":
                self._name = name
                return self

            @field({"tags": ["admin"]}, mutable=True)
            def delete_user(self) -> bool:
                return True

        class Root:
            @field
            def user(self) -> User:
                return User()

            @field({"tags": ["admin"]}, mutable=True)
            def create_user(self, name: str) -> User:
                return User()

        # Filter out all admin fields
        filtered_api = GraphQLAPI(root_type=Root, filters=[TagFilter(tags=["admin"])])
        executor = filtered_api.executor()

        # Query should still work
        test_query = """
            query GetUser {
                user {
                    name
                }
            }
        """
        result = executor.execute(test_query)
        assert not result.errors
        assert result.data == {"user": {"name": "John"}}

        # Mutation should fail since all mutable fields are filtered
        mutation_query = """
            mutation UpdateUser {
                user {
                    updateName(name: "Jane") {
                        name
                    }
                }
            }
        """
        result = executor.execute(mutation_query)
        assert result.errors
        # Should fail because updateName field is filtered out

    def test_custom_public_filter(self):
        """
        Test that we can use a custom filter to keep public fields and remove non-public ones
        """
        from graphql_api.reduce import GraphQLFilter

        class PublicFilter(GraphQLFilter):

            def filter_field(self, name: str, meta: dict) -> bool:
                # Return True to remove the field, False to keep it
                # We want to keep public fields and remove non-public ones

                is_public = meta.get("public")
                should_filter = not is_public
                if should_filter:
                    print(f"Filtering field {name} with meta {meta}: {should_filter}")
                else:
                    print(f"Keeping field {name} with meta {meta}: {should_filter}")

                return should_filter

        api = GraphQLAPI(filters=[PublicFilter()])

        @api.type(is_root_type=True)
        class Root:

            @api.field({"public": True})
            def public_field(self) -> str:
                return "public"

            @api.field
            def non_public_field(self) -> str:
                return "non-public"

        schema, _ = api.build_schema()
        printed_schema = print_schema(schema)
        assert "publicField" in printed_schema
        assert "nonPublicField" not in printed_schema

    def test_recursive_object_type_preservation(self):
        """
        Test that object types on fields of unfiltered objects (recursive)
        are still left on the schema, even if the referenced types would
        otherwise be filtered out, as long as the referenced types have at least one accessible field.
        Types with NO accessible fields cannot be preserved due to GraphQL constraints.
        """
        from graphql_api.reduce import TagFilter
        from graphql_api.decorators import field

        # Deepest nested type - has one accessible field after filtering
        class DeepConfig:
            @field({"tags": ["admin"]})
            def secret_key(self) -> str:
                return "secret"

            @field  # This field will remain accessible
            def public_setting(self) -> str:
                return "public setting"

        # Middle type - references DeepConfig, has unfiltered fields
        class MiddleConfig:
            @field
            def public_setting(self) -> str:
                return "public"

            @field
            def deep_config(self) -> DeepConfig:
                return DeepConfig()

        # Root type - references MiddleConfig and has unfiltered fields
        class AppConfig:
            @field
            def app_name(self) -> str:
                return "MyApp"

            @field
            def middle_config(self) -> MiddleConfig:
                return MiddleConfig()

        class Root:
            @field
            def config(self) -> AppConfig:
                return AppConfig()

        # Create filtered API that removes admin fields using preserve_transitive=True (default)
        filtered_api = GraphQLAPI(
            root_type=Root,
            filters=[TagFilter(tags=["admin"], preserve_transitive=True)],
        )

        # Build the schema to check its structure
        schema, _ = filtered_api.build_schema()
        type_map = schema.type_map

        # All object types should be preserved because they're reachable
        # from unfiltered fields and DeepConfig has at least one accessible field
        assert "AppConfig" in type_map
        assert "MiddleConfig" in type_map
        assert "DeepConfig" in type_map  # This should be preserved!

        # Verify that the fields referencing these types are preserved
        assert schema.query_type is not None
        root_fields = schema.query_type.fields
        assert "config" in root_fields

        from graphql import GraphQLObjectType

        app_config_type = type_map["AppConfig"]
        assert isinstance(app_config_type, GraphQLObjectType)
        assert "appName" in app_config_type.fields
        assert "middleConfig" in app_config_type.fields

        middle_config_type = type_map["MiddleConfig"]
        assert isinstance(middle_config_type, GraphQLObjectType)
        assert "publicSetting" in middle_config_type.fields
        assert "deepConfig" in middle_config_type.fields  # This should be preserved!

        # DeepConfig should exist with accessible fields (admin field filtered out)
        deep_config_type = type_map["DeepConfig"]
        assert isinstance(deep_config_type, GraphQLObjectType)
        # The admin field should be removed from DeepConfig
        assert "secretKey" not in deep_config_type.fields
        # But the public field should remain
        assert "publicSetting" in deep_config_type.fields
        assert len(deep_config_type.fields) == 1

        # Test that queries work for the preserved structure
        executor = filtered_api.executor()
        result = executor.execute(
            """
            query GetConfig {
                config {
                    appName
                    middleConfig {
                        publicSetting
                        deepConfig {
                            publicSetting
                        }
                    }
                }
            }
        """
        )

        assert not result.errors
        expected = {
            "config": {
                "appName": "MyApp",
                "middleConfig": {
                    "publicSetting": "public",
                    "deepConfig": {"publicSetting": "public setting"},
                },
            }
        }
        assert result.data == expected

    def test_filter_response_type_safety(self):
        """Test that the filtering system handles unexpected filter response types gracefully"""
        from graphql_api.reduce import GraphQLFilter, FilterResponse

        class BrokenFilter(GraphQLFilter):
            """A filter that returns unexpected types to test error handling"""

            def __init__(self, return_type="bool"):
                self.return_type = return_type

            def filter_field(self, name: str, meta: dict):
                if self.return_type == "bool":
                    return True  # Should be FilterResponse
                elif self.return_type == "none":
                    return None  # Should be FilterResponse
                elif self.return_type == "string":
                    return "invalid"  # Should be FilterResponse
                elif self.return_type == "int":
                    return 42  # Should be FilterResponse
                else:
                    return FilterResponse.KEEP  # Valid response

        api = GraphQLAPI()

        @api.type
        class TestType:
            @api.field
            def field1(self) -> str:
                return "test"

            @api.field
            def field2(self) -> str:
                return "test2"

        @api.type(is_root_type=True)
        class Root:
            @api.field
            def test(self) -> TestType:
                return TestType()

        # Test with boolean filter response
        broken_filter_bool = BrokenFilter(return_type="bool")
        filtered_api_bool = GraphQLAPI(root_type=Root, filters=[broken_filter_bool])
        executor = filtered_api_bool.executor()
        # Should not raise AttributeError

        # Test with None filter response
        broken_filter_none = BrokenFilter(return_type="none")
        filtered_api_none = GraphQLAPI(root_type=Root, filters=[broken_filter_none])
        executor = filtered_api_none.executor()
        # Should not raise AttributeError

        # Test with string filter response
        broken_filter_string = BrokenFilter(return_type="string")
        filtered_api_string = GraphQLAPI(root_type=Root, filters=[broken_filter_string])
        executor = filtered_api_string.executor()
        # Should not raise AttributeError

        # Test with int filter response
        broken_filter_int = BrokenFilter(return_type="int")
        filtered_api_int = GraphQLAPI(root_type=Root, filters=[broken_filter_int])
        executor = filtered_api_int.executor()
        # Should not raise AttributeError

        # Test with valid filter response
        valid_filter = BrokenFilter(return_type="valid")
        filtered_api_valid = GraphQLAPI(root_type=Root, filters=[valid_filter])
        executor = filtered_api_valid.executor()
        # Should work normally

        # All tests should pass without AttributeError
        assert executor is not None

    def test_remove_unreferenced_types_after_filtering(self):
        """Test that types referenced only by filtered fields are removed from the schema."""
        from graphql_api.reduce import TagFilter
        from graphql_api.decorators import field
        from enum import Enum

        api = GraphQLAPI()

        class UsedEnum(str, Enum):
            """This enum should appear in schema."""
            VALUE_A = "A"
            VALUE_B = "B"

        class FilteredEnum(str, Enum):
            """This enum should NOT appear in filtered schema."""
            FILTERED_X = "X"
            FILTERED_Y = "Y"

        class UsedModel:
            def __init__(self):
                self.name = "test"
                self.status = UsedEnum.VALUE_A

            @field
            def name(self) -> str:
                return self.name

            @field
            def status(self) -> UsedEnum:
                return self.status

        class FilteredModel:
            def __init__(self):
                self.internal_field = "internal"
                self.filtered_enum = FilteredEnum.FILTERED_X

            @field
            def internal_field(self) -> str:
                return self.internal_field

            @field
            def filtered_enum(self) -> FilteredEnum:
                return self.filtered_enum

        @api.type(is_root_type=True)
        class Root:
            @field
            def get_used_item(self) -> UsedModel:
                """This uses UsedModel and UsedEnum."""
                return UsedModel()

            @field({"tags": ["admin"]})  # Tag for filtering
            def get_filtered_item(self) -> FilteredModel:
                """This field should be filtered out."""
                return FilteredModel()

            @field
            def get_simple_string(self) -> str:
                """This doesn't use any custom types."""
                return "simple"

        # Test without filtering - all types should be present
        unfiltered_api = GraphQLAPI(root_type=Root)
        unfiltered_schema, _ = unfiltered_api.build_schema()

        from graphql import print_schema
        unfiltered_sdl = print_schema(unfiltered_schema)

        assert "UsedEnum" in unfiltered_sdl
        assert "UsedModel" in unfiltered_sdl
        assert "FilteredEnum" in unfiltered_sdl
        assert "FilteredModel" in unfiltered_sdl
        assert "getFilteredItem" in unfiltered_sdl

        # Test with filtering - filtered types should be removed
        filtered_api = GraphQLAPI(root_type=Root, filters=[TagFilter(tags=["admin"])])
        filtered_schema, _ = filtered_api.build_schema()

        filtered_sdl = print_schema(filtered_schema)

        # Should keep used types
        assert "UsedEnum" in filtered_sdl
        assert "UsedModel" in filtered_sdl

        # Should remove filtered types and field
        assert "FilteredEnum" not in filtered_sdl  # This is the key test
        assert "FilteredModel" not in filtered_sdl  # This is the key test
        assert "getFilteredItem" not in filtered_sdl

        # Should keep other fields
        assert "getUsedItem" in filtered_sdl
        assert "getSimpleString" in filtered_sdl

    def test_remove_unreferenced_types_configurable(self):
        """Test that unreferenced type removal can be disabled via configuration."""
        from graphql_api.reduce import TagFilter
        from graphql_api.decorators import field
        from enum import Enum

        api = GraphQLAPI()

        class UsedEnum(str, Enum):
            VALUE_A = "A"

        class FilteredEnum(str, Enum):
            FILTERED_X = "X"

        class UsedModel:
            @field
            def name(self) -> str:
                return "test"

            @field
            def status(self) -> UsedEnum:
                return UsedEnum.VALUE_A

        class FilteredModel:
            @field
            def internal_field(self) -> str:
                return "internal"

            @field
            def filtered_enum(self) -> FilteredEnum:
                return FilteredEnum.FILTERED_X

        @api.type(is_root_type=True)
        class Root:
            @field
            def get_used_item(self) -> UsedModel:
                return UsedModel()

            @field({"tags": ["admin"]})
            def get_filtered_item(self) -> FilteredModel:
                return FilteredModel()

        # Test with cleanup DISABLED
        api_disabled = GraphQLAPI(
            root_type=Root,
            filters=[TagFilter(tags=["admin"], cleanup_types=False)]  # Disable cleanup
        )
        disabled_schema, _ = api_disabled.build_schema()

        from graphql import print_schema
        disabled_sdl = print_schema(disabled_schema)

        # Field should still be filtered out
        assert "getFilteredItem" not in disabled_sdl

        # But types should be preserved even though unreferenced
        assert "FilteredModel" in disabled_sdl  # Should be preserved
        assert "FilteredEnumEnum" in disabled_sdl  # Should be preserved (note: framework adds "Enum" suffix)

        # Used types should remain
        assert "UsedModel" in disabled_sdl
        assert "UsedEnumEnum" in disabled_sdl

        # Test with cleanup ENABLED (default behavior)
        api_enabled = GraphQLAPI(
            root_type=Root,
            filters=[TagFilter(tags=["admin"], cleanup_types=True)]  # Enable cleanup (this is the default)
        )
        enabled_schema, _ = api_enabled.build_schema()

        enabled_sdl = print_schema(enabled_schema)

        # Field should be filtered out
        assert "getFilteredItem" not in enabled_sdl

        # Unreferenced types should be removed
        assert "FilteredModel" not in enabled_sdl  # Should be removed
        assert "FilteredEnumEnum" not in enabled_sdl  # Should be removed

        # Used types should remain
        assert "UsedModel" in enabled_sdl
        assert "UsedEnumEnum" in enabled_sdl
