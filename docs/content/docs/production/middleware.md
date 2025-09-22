---
title: "Middleware"
weight: 1
description: >
  Using middleware for cross-cutting concerns like authentication, logging, and performance monitoring
---

# Middleware

Middleware allows you to wrap your GraphQL resolvers with custom logic that executes before and after field resolution. This is essential for implementing cross-cutting concerns like authentication, logging, performance monitoring, and data validation.

## Understanding Middleware

Middleware functions are executed in a chain for each resolved field. Each middleware can:
- Inspect and modify arguments before calling the next middleware
- Process and modify the result after calling the next middleware
- Handle errors from downstream middleware/resolvers
- Add context information for downstream resolvers
- Skip calling the next middleware entirely (for early returns)

## Creating Middleware

A middleware is a function that takes the next resolver in the chain and the standard GraphQL resolver arguments (`root`, `info`, and any field arguments).

### Basic Middleware Structure

```python
from typing import Any

def example_middleware(next_, root, info, **args) -> Any:
    """
    Basic middleware template.

    Args:
        next_: Function to call the next middleware or resolver
        root: The parent object being resolved
        info: GraphQL resolver info object
        **args: Field arguments
    """
    # Pre-processing logic here
    print(f"Before resolving {info.field_name}")

    # Call the next middleware or resolver
    result = next_(root, info, **args)

    # Post-processing logic here
    print(f"After resolving {info.field_name}")

    return result
```

## Common Middleware Patterns

### Logging Middleware

Track resolver execution for debugging and monitoring:

```python
def log_middleware(next_, root, info, **args) -> Any:
    """Log resolver execution details."""
    print(f"Executing resolver: {info.field_name}")
    print(f"Arguments: {args}")

    result = next_(root, info, **args)

    print(f"Result: {result}")
    return result
```

### Timing Middleware

Measure resolver performance:

```python
def timing_middleware(next_, root, info, **args) -> Any:
    """Measure and log resolver execution time."""
    import time

    start_time = time.time()
    result = next_(root, info, **args)
    end_time = time.time()

    execution_time = end_time - start_time
    print(f"Resolver {info.field_name} took {execution_time:.4f}s")

    return result
```

### Authentication Middleware

Protect resolvers that require authentication:

```python
def auth_middleware(next_, root, info, **args) -> Any:
    """Ensure user is authenticated for protected fields."""
    from graphql import GraphQLError

    # Check if user is authenticated
    current_user = getattr(info.context, 'current_user', None)
    if not current_user:
        raise GraphQLError("Authentication required")

    return next_(root, info, **args)
```

### Field-Specific Authentication

Protect only certain fields:

```python
PROTECTED_FIELDS = {'admin_data', 'user_secrets', 'payment_info'}

def selective_auth_middleware(next_, root, info, **args) -> Any:
    """Only authenticate for protected fields."""
    from graphql import GraphQLError

    if info.field_name in PROTECTED_FIELDS:
        current_user = getattr(info.context, 'current_user', None)
        if not current_user:
            raise GraphQLError(f"Authentication required for {info.field_name}")

    return next_(root, info, **args)
```

### Rate Limiting Middleware

Implement request rate limiting:

```python
from collections import defaultdict
import time

# Simple in-memory rate limiter (use Redis in production)
request_counts = defaultdict(list)

def rate_limit_middleware(next_, root, info, **args) -> Any:
    """Basic rate limiting middleware."""
    from graphql import GraphQLError

    # Get user identifier (IP, user ID, etc.)
    user_id = getattr(info.context, 'user_id', 'anonymous')
    current_time = time.time()

    # Clean old requests (older than 1 minute)
    request_counts[user_id] = [
        req_time for req_time in request_counts[user_id]
        if current_time - req_time < 60
    ]

    # Check rate limit (max 100 requests per minute)
    if len(request_counts[user_id]) >= 100:
        raise GraphQLError("Rate limit exceeded")

    # Record this request
    request_counts[user_id].append(current_time)

    return next_(root, info, **args)
```

## Applying Middleware

### Global Middleware

Apply middleware to all resolvers:

```python
from graphql_api.api import GraphQLAPI

# Middleware executes in the order specified
api = GraphQLAPI(middleware=[
    auth_middleware,      # First: Check authentication
    timing_middleware,    # Second: Start timing
    log_middleware       # Third: Log execution
])

@api.type(is_root_type=True)
class Root:
    @api.field
    def protected_data(self) -> str:
        return "Secret information"

    @api.field
    def public_data(self) -> str:
        return "Public information"
```

### Context Modification Middleware

Add data to context for downstream resolvers:

```python
def context_middleware(next_, root, info, **args):
    """Add request context information."""
    # Add request ID for tracing
    info.context.request_id = f"req_{int(time.time())}"

    # Add database session
    info.context.db_session = create_db_session()

    # Add user from authentication header
    auth_header = getattr(info.context, 'auth_header', None)
    if auth_header:
        info.context.current_user = get_user_from_token(auth_header)

    try:
        result = next_(root, info, **args)
        return result
    finally:
        # Cleanup resources
        if hasattr(info.context, 'db_session'):
            info.context.db_session.close()
```

### Error Handling Middleware

Catch and transform errors:

```python
def error_middleware(next_, root, info, **args):
    """Handle and transform errors."""
    from graphql import GraphQLError
    import logging

    try:
        return next_(root, info, **args)
    except ValueError as e:
        # Transform validation errors
        raise GraphQLError(f"Validation error: {str(e)}")
    except Exception as e:
        # Log unexpected errors
        logging.error(f"Unexpected error in {info.field_name}: {e}")
        raise GraphQLError("Internal server error")
```

## Middleware Execution Order

Middleware executes in a nested fashion, like onion layers:

```python
# With middleware=[middleware_a, middleware_b, middleware_c]
# Execution flow:
# middleware_a (before)
#   middleware_b (before)
#     middleware_c (before)
#       ACTUAL RESOLVER
#     middleware_c (after)
#   middleware_b (after)
# middleware_a (after)
```

Example demonstrating execution order:

```python
def middleware_a(next_, root, info, **args):
    print("A: Before")
    result = next_(root, info, **args)
    print("A: After")
    return result

def middleware_b(next_, root, info, **args):
    print("B: Before")
    result = next_(root, info, **args)
    print("B: After")
    return result

def middleware_c(next_, root, info, **args):
    print("C: Before")
    result = next_(root, info, **args)
    print("C: After")
    return result

api = GraphQLAPI(middleware=[middleware_a, middleware_b, middleware_c])

# Output when a field is resolved:
# A: Before
# B: Before
# C: Before
# C: After
# B: After
# A: After
```

## Advanced Middleware Patterns

### Conditional Middleware

Skip middleware execution based on conditions:

```python
def caching_middleware(next_, root, info, **args):
    """Cache results for expensive operations."""
    cache_key = f"{info.field_name}:{hash(str(args))}"

    # Check if this field should be cached
    if not getattr(info.field_definition, 'cacheable', False):
        return next_(root, info, **args)

    # Check cache
    cached_result = cache.get(cache_key)
    if cached_result is not None:
        return cached_result

    # Compute and cache result
    result = next_(root, info, **args)
    cache.set(cache_key, result, timeout=300)  # 5 minutes
    return result
```

### Field Metadata Access

Use field metadata in middleware:

```python
from graphql_api.context import GraphQLMetaKey

def permission_middleware(next_, root, info, **args):
    """Check permissions based on field metadata."""
    from graphql import GraphQLError

    # Get required permission from field metadata
    required_permission = info.field_definition.extensions.get('permission')
    if not required_permission:
        return next_(root, info, **args)

    # Check if user has permission
    user = getattr(info.context, 'current_user', None)
    if not user or not user.has_permission(required_permission):
        raise GraphQLError(f"Permission '{required_permission}' required")

    return next_(root, info, **args)

# Usage with field metadata
@api.type(is_root_type=True)
class Root:
    @api.field({GraphQLMetaKey.extensions: {'permission': 'admin'}})
    def admin_data(self) -> str:
        return "Admin only data"
```

### Async Middleware

Handle async resolvers:

```python
import asyncio

def async_timing_middleware(next_, root, info, **args):
    """Time both sync and async resolvers."""
    import time

    start_time = time.time()
    result = next_(root, info, **args)

    # Handle async results
    if asyncio.iscoroutine(result):
        async def async_wrapper():
            actual_result = await result
            end_time = time.time()
            print(f"Async resolver {info.field_name} took {end_time - start_time:.4f}s")
            return actual_result
        return async_wrapper()
    else:
        end_time = time.time()
        print(f"Sync resolver {info.field_name} took {end_time - start_time:.4f}s")
        return result
```

## Best Practices

**Keep middleware focused:**
```python
# ✅ Good: Single responsibility
def auth_middleware(next_, root, info, **args):
    # Only handle authentication
    pass

# ❌ Avoid: Multiple responsibilities
def everything_middleware(next_, root, info, **args):
    # Authentication, logging, caching, validation, etc.
    pass
```

**Order middleware carefully:**
```python
# ✅ Good: Logical order
api = GraphQLAPI(middleware=[
    auth_middleware,      # First: Authenticate
    permission_middleware, # Second: Check permissions
    rate_limit_middleware, # Third: Rate limiting
    timing_middleware,     # Fourth: Performance monitoring
    log_middleware        # Last: Logging
])
```

**Handle errors gracefully:**
```python
def robust_middleware(next_, root, info, **args):
    try:
        return next_(root, info, **args)
    except Exception as e:
        # Log error with context
        logger.error(f"Error in {info.field_name}: {e}", extra={
            'field': info.field_name,
            'args': args,
            'user': getattr(info.context, 'user_id', None)
        })
        raise  # Re-raise to maintain error handling
```

**Use context efficiently:**
```python
def efficient_context_middleware(next_, root, info, **args):
    # Only add context data when needed
    if not hasattr(info.context, 'db_session'):
        info.context.db_session = create_db_session()

    return next_(root, info, **args)
```

Middleware provides a powerful way to implement cross-cutting concerns in your GraphQL API while keeping your resolvers focused on business logic.

## Related Topics

Middleware integrates with other production features:

**Error management:** [Error Handling](error-handling/) covers robust error management strategies that work well with middleware.

**Advanced patterns:**
- [Context & Metadata](context-metadata/) - Pass data between middleware and resolvers
- [Custom Directives](directives/) - Add declarative behavior to your schema
- [Schema Filtering](schema-filtering/) - Control field access dynamically