---
title: "Error Handling"
weight: 2
description: >
  Comprehensive error handling strategies for robust GraphQL APIs
---

# Error Handling

Proper error handling is crucial for building robust GraphQL APIs. `graphql-api` provides several mechanisms for handling and controlling error behavior, from basic exception catching to sophisticated structured error responses.

## Understanding GraphQL Errors

GraphQL has a unique approach to error handling compared to REST APIs:
- **Partial Success**: Some fields can succeed while others fail
- **Structured Errors**: Errors include location information and can have custom extensions
- **Type-based Behavior**: Non-null fields vs nullable fields behave differently when errors occur

## Basic Error Handling

By default, `graphql-api` catches exceptions in resolvers and converts them to GraphQL errors:

```python
from typing import Optional

@api.type(is_root_type=True)
class Root:
    @api.field
    def divide(self, a: float, b: float) -> float:
        """Non-null field - errors cause entire query to fail."""
        if b == 0:
            raise ValueError("Cannot divide by zero")
        return a / b

    @api.field
    def safe_divide(self, a: float, b: float) -> Optional[float]:
        """Nullable field - errors return null for this field only."""
        if b == 0:
            raise ValueError("Cannot divide by zero")
        return a / b

# Test the behavior
result = api.execute('query { divide(a: 10, b: 0) }')
# result.errors contains the ValueError, result.data is None

result = api.execute('query { safeDivide(a: 10, b: 0) }')
# result.errors contains the ValueError, result.data is {"safeDivide": None}
```

**Key behavior:**
- Errors in **non-null fields** cause the entire query to fail (`data: null`)
- Errors in **nullable fields** return `null` for that field but preserve other data

## Partial Error Responses

GraphQL allows partial success - some fields can succeed while others fail:

```python
@api.type(is_root_type=True)
class Root:
    @api.field
    def user_data(self, error: bool = False) -> Optional[str]:
        if error:
            raise Exception("User data failed")
        return "User data loaded"

    @api.field
    def settings_data(self, error: bool = False) -> str:
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

# Result will have:
# - errors: [exception from settingsData]
# - data: {"userData": "User data loaded", "settingsData": null}
```

This allows clients to receive partial data even when some operations fail.

## Error Protection Control

You can control error protection at the API level or individual field level:

```python
from graphql_api.context import GraphQLMetaKey

# Disable error protection globally - exceptions will propagate
api = GraphQLAPI(error_protection=False)

# Or disable for specific fields
@api.type(is_root_type=True)
class Root:
    @api.field({GraphQLMetaKey.error_protection: False})
    def dangerous_operation(self) -> str:
        raise Exception("This will propagate!")

    @api.field  # This field still has error protection
    def safe_operation(self) -> str:
        raise Exception("This becomes a GraphQL error")
```

**When `error_protection=False`:**
- Exceptions are **not caught** and will propagate to your application
- Useful for debugging or when you want to handle errors at a higher level
- Allows integration with external error handling systems

## Custom Exception Classes

Create structured exceptions for better error handling:

```python
from graphql import GraphQLError

class UserNotFoundError(GraphQLError):
    """A specific error for when a user is not found."""
    def __init__(self, user_id: int):
        super().__init__(
            f"User with ID {user_id} not found.",
            extensions={"code": "USER_NOT_FOUND", "user_id": user_id}
        )

class ValidationError(GraphQLError):
    """Error for input validation failures."""
    def __init__(self, field: str, message: str):
        super().__init__(
            f"Validation error on field '{field}': {message}",
            extensions={"code": "VALIDATION_ERROR", "field": field}
        )

class PermissionError(GraphQLError):
    """Error for permission violations."""
    def __init__(self, operation: str):
        super().__init__(
            f"Permission denied for operation: {operation}",
            extensions={"code": "PERMISSION_DENIED", "operation": operation}
        )

@api.type(is_root_type=True)
class Root:
    @api.field
    def get_user(self, user_id: int) -> User:
        if user_id < 1:
            raise ValidationError("user_id", "Must be positive")

        user = find_user_in_db(user_id)
        if not user:
            raise UserNotFoundError(user_id)
        return user
```

This provides structured error responses:

```json
{
  "errors": [
    {
      "message": "User with ID 123 not found.",
      "locations": [...],
      "path": ["getUser"],
      "extensions": {
        "code": "USER_NOT_FOUND",
        "user_id": 123
      }
    }
  ]
}
```

## Error Categories and Best Practices

### 1. Validation Errors

Handle input validation consistently:

```python
from pydantic import BaseModel, Field, validator

class CreateUserInput(BaseModel):
    name: str = Field(min_length=2, max_length=50)
    email: str
    age: int = Field(ge=13, le=120)

    @validator('email')
    def validate_email(cls, v):
        if '@' not in v:
            raise ValueError('Invalid email format')
        return v

@api.type(is_root_type=True)
class Root:
    @api.field(mutable=True)
    def create_user(self, input: CreateUserInput) -> User:
        try:
            # Pydantic validation happens automatically
            user = User.create(input)
            return user
        except ValueError as e:
            raise ValidationError("input", str(e))
```

### 2. Authorization Errors

Handle permission and authentication errors:

```python
class AuthenticationError(GraphQLError):
    def __init__(self):
        super().__init__(
            "Authentication required",
            extensions={"code": "UNAUTHENTICATED"}
        )

class AuthorizationError(GraphQLError):
    def __init__(self, resource: str):
        super().__init__(
            f"Access denied to resource: {resource}",
            extensions={"code": "FORBIDDEN", "resource": resource}
        )

@api.type(is_root_type=True)
class Root:
    @api.field
    def admin_data(self, context: GraphQLContext) -> str:
        user = getattr(context, 'current_user', None)
        if not user:
            raise AuthenticationError()

        if not user.is_admin:
            raise AuthorizationError("admin_data")

        return "Secret admin data"
```

### 3. Business Logic Errors

Handle domain-specific errors:

```python
class InsufficientFundsError(GraphQLError):
    def __init__(self, available: float, requested: float):
        super().__init__(
            f"Insufficient funds: {available} available, {requested} requested",
            extensions={
                "code": "INSUFFICIENT_FUNDS",
                "available": available,
                "requested": requested
            }
        )

class InvalidTransactionError(GraphQLError):
    def __init__(self, reason: str):
        super().__init__(
            f"Invalid transaction: {reason}",
            extensions={"code": "INVALID_TRANSACTION", "reason": reason}
        )

@api.type(is_root_type=True)
class Root:
    @api.field(mutable=True)
    def transfer_money(self, from_account: str, to_account: str, amount: float) -> bool:
        if amount <= 0:
            raise InvalidTransactionError("Amount must be positive")

        account = get_account(from_account)
        if account.balance < amount:
            raise InsufficientFundsError(account.balance, amount)

        # Perform transfer
        execute_transfer(from_account, to_account, amount)
        return True
```

## Error Handling in Middleware

Use middleware to standardize error handling across your API:

```python
import logging

def error_handling_middleware(next_, root, info, **args):
    """Standardize error handling and logging."""
    try:
        return next_(root, info, **args)
    except ValidationError:
        # Let validation errors pass through as-is
        raise
    except GraphQLError:
        # Let GraphQL errors pass through as-is
        raise
    except Exception as e:
        # Log unexpected errors
        logging.exception(
            f"Unexpected error in {info.field_name}",
            extra={
                'field': info.field_name,
                'args': args,
                'user': getattr(info.context, 'user_id', None)
            }
        )

        # Convert to user-friendly error
        raise GraphQLError(
            "An unexpected error occurred",
            extensions={
                "code": "INTERNAL_ERROR",
                "timestamp": time.time()
            }
        )

api = GraphQLAPI(middleware=[error_handling_middleware])
```

## Development vs Production Error Handling

Configure different error handling for different environments:

```python
import os

DEBUG = os.getenv('DEBUG', 'false').lower() == 'true'

if DEBUG:
    # Development: Full error details
    api = GraphQLAPI(
        error_protection=False,  # Get full stack traces
        middleware=[timing_middleware, debug_middleware]
    )
else:
    # Production: Sanitized errors
    api = GraphQLAPI(
        error_protection=True,   # Hide internal errors
        middleware=[auth_middleware, logging_middleware, error_handling_middleware]
    )
```

## Error Context and Debugging

Add context to errors for better debugging:

```python
def debug_error_middleware(next_, root, info, **args):
    """Add debugging context to errors."""
    try:
        return next_(root, info, **args)
    except GraphQLError as e:
        # Add debug info to existing GraphQL errors
        if DEBUG:
            e.extensions = e.extensions or {}
            e.extensions.update({
                "debug": {
                    "field": info.field_name,
                    "path": str(info.path),
                    "args": args,
                    "timestamp": time.time()
                }
            })
        raise
    except Exception as e:
        # Convert unexpected errors with debug context
        error_extensions = {"code": "INTERNAL_ERROR"}

        if DEBUG:
            error_extensions["debug"] = {
                "original_error": str(e),
                "error_type": type(e).__name__,
                "field": info.field_name,
                "args": args
            }

        raise GraphQLError(
            "An internal error occurred",
            extensions=error_extensions
        )
```

## Testing Error Scenarios

Test your error handling thoroughly:

```python
def test_error_handling():
    # Test validation errors
    result = api.execute('''
        mutation {
            createUser(input: {name: "", email: "invalid"}) {
                id
            }
        }
    ''')
    assert result.errors
    assert "VALIDATION_ERROR" in str(result.errors[0])

    # Test authorization errors
    result = api.execute('query { adminData }')  # No auth context
    assert result.errors
    assert "UNAUTHENTICATED" in str(result.errors[0])

    # Test partial success
    result = api.execute('''
        query {
            publicData
            adminData
        }
    ''')
    assert result.errors  # adminData failed
    assert result.data["publicData"]  # but publicData succeeded
    assert result.data["adminData"] is None
```

## Best Practices Summary

**Structure your error hierarchy:**
```python
class APIError(GraphQLError):
    """Base class for all API errors."""
    pass

class ValidationError(APIError):
    """Input validation failures."""
    pass

class AuthenticationError(APIError):
    """Authentication required."""
    pass

class AuthorizationError(APIError):
    """Permission denied."""
    pass

class BusinessLogicError(APIError):
    """Domain-specific errors."""
    pass
```

**Use consistent error codes:**
```python
# Define standard error codes
ERROR_CODES = {
    'VALIDATION_ERROR': 'VALIDATION_ERROR',
    'UNAUTHENTICATED': 'UNAUTHENTICATED',
    'FORBIDDEN': 'FORBIDDEN',
    'NOT_FOUND': 'NOT_FOUND',
    'INTERNAL_ERROR': 'INTERNAL_ERROR'
}
```

**Log errors appropriately:**
```python
# Log user errors at info level
logging.info(f"Validation error: {error}")

# Log system errors at error level
logging.error(f"Unexpected error: {error}", exc_info=True)
```

**Return helpful error messages:**
```python
# ✅ Good: Specific, actionable
raise ValidationError("email", "Email format is invalid")

# ❌ Avoid: Generic, unhelpful
raise Exception("Something went wrong")
```

Well-structured error handling improves both developer experience and production reliability by providing clear, actionable error information while protecting sensitive system details.