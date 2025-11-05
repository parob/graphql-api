"""
Test all code examples from the advanced.md documentation
"""
import pytest
from typing import Any, Optional
from graphql import GraphQLError, DirectiveLocation, GraphQLArgument, GraphQLString
from graphql_api.api import GraphQLAPI
from graphql_api.context import GraphQLContext
from graphql_api.mapper import GraphQLMetaKey
from graphql_api.directives import SchemaDirective, deprecated


class TestAdvancedExamples:

    def test_middleware_basic(self):
        """Test basic middleware functionality"""
        execution_log = []

        def log_middleware(next_, root, info, **args) -> Any:
            execution_log.append(f"before_{info.field_name}")
            result = next_(root, info, **args)
            execution_log.append(f"after_{info.field_name}")
            return result

        def timing_middleware(next_, root, info, **args) -> Any:
            import time
            start_time = time.time()
            result = next_(root, info, **args)
            end_time = time.time()
            execution_time = end_time - start_time
            execution_log.append(f"timing_{info.field_name}_{execution_time:.4f}")
            return result

        api = GraphQLAPI(middleware=[timing_middleware, log_middleware])

        @api.type(is_root_type=True)
        class Query:
            @api.field
            def test_field(self) -> str:
                return "test_result"

        result = api.execute("query { testField }")
        assert not result.errors
        assert result.data == {"testField": "test_result"}

        # Verify middleware executed
        assert "before_testField" in execution_log
        assert "after_testField" in execution_log
        assert any("timing_testField_" in log for log in execution_log)

    def test_error_protection_control(self):
        """Test error protection at API and field level"""
        # Test API-level error protection disabled
        api_no_protection = GraphQLAPI(error_protection=False)

        @api_no_protection.type(is_root_type=True)
        class QueryNoProtection:
            @api_no_protection.field
            def dangerous_operation(self) -> str:
                raise Exception("This will propagate!")

        with pytest.raises(Exception, match="This will propagate!"):
            api_no_protection.execute("query { dangerousOperation }")

        # Test field-level error protection disabled
        api = GraphQLAPI()

        @api.type(is_root_type=True)
        class Query:
            @api.field({GraphQLMetaKey.error_protection: False})
            def field_no_protection(self) -> str:
                raise Exception("Field-level exception!")

            @api.field
            def field_with_protection(self) -> str:
                raise Exception("This becomes a GraphQL error")

        with pytest.raises(Exception, match="Field-level exception!"):
            api.execute("query { fieldNoProtection }")

        # This should work and return a GraphQL error
        result = api.execute("query { fieldWithProtection }")
        assert result.errors
        assert "This becomes a GraphQL error" in str(result.errors[0])

    def test_custom_exceptions(self):
        """Test custom exception classes"""
        class ValidationError(GraphQLError):
            def __init__(self, field: str, message: str):
                super().__init__(
                    f"Validation failed for {field}: {message}",
                    extensions={"code": "VALIDATION_ERROR", "field": field}
                )

        api = GraphQLAPI()

        @api.type(is_root_type=True)
        class Query:
            @api.field
            def validate_input(self, input_data: str) -> str:
                if not input_data.strip():
                    raise ValidationError("input_data", "Cannot be empty")
                return f"Valid: {input_data}"

        result = api.execute('query { validateInput(inputData: "") }')
        assert result.errors
        error = result.errors[0]
        assert "Validation failed for input_data" in error.message
        assert error.extensions["code"] == "VALIDATION_ERROR"
        assert error.extensions["field"] == "input_data"

    def test_partial_error_responses(self):
        """Test partial error responses"""
        api = GraphQLAPI()

        @api.type(is_root_type=True)
        class Query:
            @api.field
            def user_data(self, error: bool = False) -> Optional[str]:
                if error:
                    raise Exception("User data failed")
                return "User data loaded"

            @api.field
            def settings_data(self, error: bool = False) -> Optional[str]:  # Make nullable
                if error:
                    raise Exception("Settings failed")
                return "Settings loaded"

        # Query both fields with mixed success
        result = api.execute('''
            query {
                userData(error: false)
                settingsData(error: true)
            }
        ''')

        assert result.errors  # Should have errors from settingsData
        assert result.data["userData"] == "User data loaded"
        assert result.data["settingsData"] is None

    def test_graphql_context(self):
        """Test GraphQLContext usage"""
        # Custom middleware to inject user context
        def auth_middleware(next_, root, info, **args):
            # Simulate authentication - in real app this would check headers/tokens
            info.context.current_user = getattr(info.context, 'current_user', None)
            return next_(root, info, **args)

        api = GraphQLAPI(middleware=[auth_middleware])

        @api.type(is_root_type=True)
        class Query:
            @api.field
            def get_my_profile(self, context: GraphQLContext) -> str:
                current_user = getattr(context, 'current_user', None)
                if not current_user:
                    raise PermissionError("You must be logged in")
                return f"Profile for {current_user}"

            @api.field
            def debug_context(self, context: GraphQLContext) -> str:
                return f"Field: {context.request.info.field_name}"

        # Test without user context
        result = api.execute("query { getMyProfile }")
        assert result.errors
        assert "You must be logged in" in str(result.errors[0])

        # Test debug context
        result = api.execute("query { debugContext }")
        assert not result.errors
        assert result.data["debugContext"] == "Field: debugContext"

    def test_custom_directives(self):
        """Test custom directive creation and usage"""
        # Define custom directive
        tag = SchemaDirective(
            name="tag",
            locations=[DirectiveLocation.FIELD_DEFINITION, DirectiveLocation.OBJECT],
            args={
                "name": GraphQLArgument(
                    GraphQLString,
                    description="Tag name"
                )
            },
            description="Tag directive for categorization",
            is_repeatable=True,
        )

        api = GraphQLAPI(directives=[tag])

        @tag(name="user_type")
        @api.type
        class User:
            @api.field
            def id(self) -> str:
                return "user123"

            @tag(name="sensitive")
            @api.field
            def email(self) -> str:
                return "user@example.com"

        @api.type(is_root_type=True)
        class Query:
            @api.field
            def user(self) -> User:
                return User()

        # Test the schema can be built with directives
        schema, _ = api.build()
        assert schema is not None

        # Test query execution works
        result = api.execute("query { user { id email } }")
        assert not result.errors
        assert result.data == {
            "user": {
                "id": "user123",
                "email": "user@example.com"
            }
        }

    def test_deprecated_directive(self):
        """Test built-in deprecated directive"""
        api = GraphQLAPI()

        @api.type(is_root_type=True)
        class Query:
            @deprecated(reason="Use getNewEndpoint instead")
            @api.field
            def get_old_endpoint(self) -> str:
                return "This endpoint is deprecated"

            @api.field
            def get_new_endpoint(self) -> str:
                return "Use this endpoint instead"

        # Test functionality still works
        result = api.execute("query { getOldEndpoint getNewEndpoint }")
        assert not result.errors
        assert result.data == {
            "getOldEndpoint": "This endpoint is deprecated",
            "getNewEndpoint": "Use this endpoint instead"
        }

    def test_schema_filtering(self):
        """Test schema filtering and validation"""
        api = GraphQLAPI()

        class Person:
            def __init__(self):
                self._name = "Alice"

            @api.field
            def name(self) -> str:
                return self._name

            @api.field(mutable=True)
            def update_name(self, name: str) -> str:
                self._name = name
                return self._name

        @api.type(is_root_type=True)
        class Root:
            @api.field
            def person(self) -> Person:
                return Person()

        # Test that mutation fields work in mutations
        result = api.execute('''
            mutation {
                person {
                    updateName(name: "Bob")
                }
            }
        ''')
        assert not result.errors
        assert result.data["person"]["updateName"] == "Bob"

        # Test that mutation fields don't work in queries
        result = api.execute('''
            query {
                person {
                    updateName(name: "Charlie")
                }
            }
        ''')
        assert result.errors
        assert "Cannot query field" in str(result.errors[0])

    def test_middleware_with_context(self):
        """Test middleware interaction with context"""
        def context_middleware(next_, root, info, **args):
            # Add request ID to context as an attribute
            info.context.request_id = "req_123"

            # Call next middleware/resolver
            result = next_(root, info, **args)

            return result

        api = GraphQLAPI(middleware=[context_middleware])

        @api.type(is_root_type=True)
        class Query:
            @api.field
            def get_request_info(self, context: GraphQLContext) -> str:
                request_id = getattr(context, "request_id", "no_id")
                return f"Request ID: {request_id}"

        result = api.execute("query { getRequestInfo }")
        assert not result.errors
        assert result.data["getRequestInfo"] == "Request ID: req_123"

    def test_error_handling_nullable_vs_nonnull(self):
        """Test error behavior with nullable vs non-null fields"""
        api = GraphQLAPI()

        @api.type(is_root_type=True)
        class Query:
            @api.field
            def nullable_field(self) -> Optional[str]:
                raise Exception("Error in nullable field")

            @api.field
            def nonnull_field(self) -> str:
                raise Exception("Error in non-null field")

            @api.field
            def working_field(self) -> str:
                return "This works"

        # Test nullable field error - should return null for that field
        result = api.execute("query { nullableField workingField }")
        assert result.errors
        assert result.data["nullableField"] is None
        assert result.data["workingField"] == "This works"

        # Test non-null field error - should fail entire query
        result = api.execute("query { nonnullField }")
        assert result.errors
        assert result.data is None
