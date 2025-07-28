from graphql_api.api import GraphQLAPI
from graphql_api.mapper import GraphQLMetaKey


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
        the empty type is also removed from the schema
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

        # Create API with filter that removes admin fields
        filtered_api = GraphQLAPI(root_type=Root, filters=[TagFilter(tags=["admin"])])
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

        # This query should fail gracefully because SecretData type should be removed
        # when all its fields are filtered out
        test_query_with_empty_type = """
            query GetSecretData {
                secretData {
                    secretValue
                }
            }
        """

        result = executor.execute(test_query_with_empty_type)
        # Should fail with "Cannot query field 'secretData'" error since the field
        # referencing the empty type was removed
        assert result.errors
        assert "Cannot query field 'secretData'" in str(result.errors[0])

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
                pass

            @field({"tags": ["vet"]})
            def medical_history(self) -> str:
                pass

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
        expected = {
            "dog": {"name": "Buddy", "breed": "Golden Retriever"}
        }
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
                        "address": {
                            "street": "123 Main St"
                        }
                    }
                }
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
        filtered_api = GraphQLAPI(root_type=Root, filters=[TagFilter(tags=["internal", "admin"])])
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
                "optionalSummary": None
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
            "mixedContent": {"publicField": "Public"}
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
        from graphql_api.reduce import TagFilter
        from graphql_api.decorators import field

        class CustomFilter(TagFilter):
            def filter_field(self, name: str, meta: dict) -> bool:
                # Filter out fields with 'admin' tag OR fields starting with 'internal_'
                if super().filter_field(name, meta):
                    return True
                return name.startswith('internal_')

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
        filtered_api = GraphQLAPI(root_type=Root, filters=[CustomFilter(tags=["admin"])])
        executor = filtered_api.executor()

        # Should work for allowed fields
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

        # Should fail for admin tagged fields
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

        # Should fail for internal_ prefixed fields
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

        # Should fail for internal_ prefixed fields even with different tags
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
