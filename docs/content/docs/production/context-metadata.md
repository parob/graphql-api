---
title: "Context and Metadata"
weight: 2
description: >
  Managing request context and field metadata for sophisticated GraphQL APIs
---

# Context and Metadata

`graphql-api` provides powerful mechanisms for accessing request-specific information and attaching metadata to schema elements. This enables sophisticated features like authentication, authorization, request tracking, and custom field behaviors.

## Understanding GraphQL Context

GraphQL context is a shared object that flows through all resolvers during query execution. It's the primary way to pass request-specific data like:
- User authentication information
- Database connections
- Request metadata (IP, headers, etc.)
- Application-specific data

## Using GraphQLContext

For structured access to context information, use the `GraphQLContext` type annotation:

```python
from graphql_api.context import GraphQLContext

@api.type(is_root_type=True)
class Root:
    @api.field
    def get_my_profile(self, context: GraphQLContext) -> str:
        # Access custom context data stored as attributes
        current_user = getattr(context, 'current_user', None)
        if not current_user:
            raise PermissionError("You must be logged in")
        return f"Profile for {current_user}"

    @api.field
    def debug_context(self, context: GraphQLContext) -> str:
        # Access field name from request info
        return f"Field: {context.request.info.field_name}"

    @api.field
    def request_info(self, context: GraphQLContext) -> str:
        # Access various request information
        field_name = context.request.info.field_name
        path = str(context.request.info.path)
        return f"Executing {field_name} at path {path}"
```

## Populating Context

Context data is typically injected via middleware rather than passed directly to `execute()`:

```python
def context_middleware(next_, root, info, **args):
    """Add request context information."""
    # Add request ID for tracing
    info.context.request_id = f"req_{int(time.time())}"

    # Add database session
    info.context.db_session = create_db_session()

    # Add user from authentication header
    auth_token = getattr(info.context, 'auth_token', None)
    if auth_token:
        info.context.current_user = get_user_from_token(auth_token)

    # Add request metadata
    info.context.request_timestamp = time.time()
    info.context.client_ip = get_client_ip()

    try:
        # Call next middleware/resolver
        result = next_(root, info, **args)
        return result
    finally:
        # Cleanup resources
        if hasattr(info.context, 'db_session'):
            info.context.db_session.close()

api = GraphQLAPI(middleware=[context_middleware])
```

## Context Structure

The `GraphQLContext` object provides access to:

- **`context.schema`** - The GraphQL schema instance
- **`context.meta`** - Field metadata dictionary
- **`context.executor`** - The current executor instance
- **`context.request`** - Request context containing:
  - `context.request.info.field_name` - Current field name
  - `context.request.info.path` - GraphQL path (e.g., "user.posts.0.title")
  - `context.request.info.schema` - Schema reference
  - `context.request.args` - Field arguments
- **`context.field`** - Field context with metadata and query info
- **Custom attributes** - Added via middleware using `info.context.attribute_name = value`

## Context in Different Scenarios

### Authentication Context

```python
def auth_middleware(next_, root, info, **args):
    """Inject authentication context."""
    # Extract token from headers or context
    auth_header = getattr(info.context, 'authorization', None)

    if auth_header and auth_header.startswith('Bearer '):
        token = auth_header[7:]  # Remove 'Bearer ' prefix
        try:
            user = validate_token(token)
            info.context.current_user = user
            info.context.user_id = user.id
            info.context.user_roles = user.roles
        except InvalidTokenError:
            info.context.current_user = None
    else:
        info.context.current_user = None

    return next_(root, info, **args)

@api.type(is_root_type=True)
class Root:
    @api.field
    def me(self, context: GraphQLContext) -> Optional[User]:
        return getattr(context, 'current_user', None)

    @api.field
    def admin_data(self, context: GraphQLContext) -> str:
        user = getattr(context, 'current_user', None)
        if not user or 'admin' not in getattr(context, 'user_roles', []):
            raise PermissionError("Admin access required")
        return "Secret admin data"
```

### Database Context

```python
def database_middleware(next_, root, info, **args):
    """Provide database access through context."""
    # Create database session
    db_session = create_database_session()
    info.context.db = db_session

    # Add common database utilities
    info.context.get_user = lambda id: db_session.query(User).get(id)
    info.context.get_post = lambda id: db_session.query(Post).get(id)

    try:
        result = next_(root, info, **args)
        db_session.commit()  # Commit successful operations
        return result
    except Exception:
        db_session.rollback()  # Rollback on errors
        raise
    finally:
        db_session.close()

@api.type(is_root_type=True)
class Root:
    @api.field
    def user(self, user_id: str, context: GraphQLContext) -> Optional[User]:
        # Use database from context
        return context.get_user(user_id)

    @api.field(mutable=True)
    def create_post(self, title: str, content: str, context: GraphQLContext) -> Post:
        user = getattr(context, 'current_user', None)
        if not user:
            raise PermissionError("Authentication required")

        # Use database session from context
        post = Post(title=title, content=content, author_id=user.id)
        context.db.add(post)
        context.db.flush()  # Get the ID
        return post
```

### Request Tracking Context

```python
import uuid
from datetime import datetime

def request_tracking_middleware(next_, root, info, **args):
    """Add request tracking information."""
    if not hasattr(info.context, 'request_id'):
        info.context.request_id = str(uuid.uuid4())
        info.context.request_start_time = datetime.now()
        info.context.fields_resolved = []

    # Track field resolution
    info.context.fields_resolved.append({
        'field': info.field_name,
        'path': str(info.path),
        'timestamp': datetime.now()
    })

    return next_(root, info, **args)

@api.type(is_root_type=True)
class Root:
    @api.field
    def debug_request(self, context: GraphQLContext) -> dict:
        return {
            'request_id': getattr(context, 'request_id', 'unknown'),
            'start_time': getattr(context, 'request_start_time', None),
            'fields_resolved': getattr(context, 'fields_resolved', [])
        }
```

## Field Metadata with GraphQLMetaKey

Attach metadata to individual fields using `GraphQLMetaKey`:

```python
from graphql_api.context import GraphQLMetaKey

@api.type(is_root_type=True)
class Root:
    @api.field({
        GraphQLMetaKey.error_protection: False,
        "cache_duration": 3600,
        "requires_auth": True,
        "custom_meta": "field_metadata"
    })
    def advanced_field(self) -> str:
        return "This field has custom metadata"

    @api.field({
        "rate_limit": 100,  # Custom metadata
        "expensive": True
    })
    def expensive_operation(self) -> str:
        return "Expensive computation result"
```

**Available GraphQLMetaKey options:**
- `GraphQLMetaKey.error_protection`: Control error handling for individual fields
- `GraphQLMetaKey.extensions`: Add custom extensions to the GraphQL field definition
- Custom metadata: Add your own metadata for middleware or other processing

## Accessing Metadata in Middleware

Use field metadata to control middleware behavior:

```python
def caching_middleware(next_, root, info, **args):
    """Cache responses based on field metadata."""
    # Access field metadata
    cache_duration = getattr(info.field_definition, 'cache_duration', None)

    if not cache_duration:
        return next_(root, info, **args)

    # Create cache key
    cache_key = f"{info.field_name}:{hash(str(args))}"

    # Check cache
    cached_result = get_from_cache(cache_key)
    if cached_result is not None:
        return cached_result

    # Compute and cache result
    result = next_(root, info, **args)
    set_in_cache(cache_key, result, duration=cache_duration)
    return result

def permission_middleware(next_, root, info, **args):
    """Check permissions based on field metadata."""
    requires_auth = getattr(info.field_definition, 'requires_auth', False)

    if requires_auth:
        user = getattr(info.context, 'current_user', None)
        if not user:
            raise GraphQLError("Authentication required")

    return next_(root, info, **args)

api = GraphQLAPI(middleware=[caching_middleware, permission_middleware])
```

## Context Best Practices

### 1. Use Attributes, Not Dictionary Access

```python
# ✅ Good: Use attributes
info.context.current_user = user
user = getattr(info.context, 'current_user', None)

# ❌ Avoid: Dictionary-style access (not supported)
info.context['current_user'] = user  # This won't work
user = info.context.get('current_user')  # This won't work
```

### 2. Handle Missing Context Gracefully

```python
def safe_context_access(context: GraphQLContext) -> str:
    # Use getattr with defaults for safety
    user = getattr(context, 'current_user', None)
    request_id = getattr(context, 'request_id', 'unknown')

    if user:
        return f"User {user.name} in request {request_id}"
    else:
        return f"Anonymous user in request {request_id}"
```

### 3. Clean Up Resources

```python
def resource_middleware(next_, root, info, **args):
    """Properly manage resources in context."""
    resources_to_cleanup = []

    try:
        # Add database connection
        db = create_db_connection()
        info.context.db = db
        resources_to_cleanup.append(db)

        # Add cache connection
        cache = create_cache_connection()
        info.context.cache = cache
        resources_to_cleanup.append(cache)

        return next_(root, info, **args)
    finally:
        # Clean up all resources
        for resource in resources_to_cleanup:
            try:
                resource.close()
            except Exception as e:
                logging.warning(f"Error closing resource: {e}")
```

### 4. Context Validation

```python
def validate_context_middleware(next_, root, info, **args):
    """Validate required context before proceeding."""
    required_context = ['db', 'cache', 'current_user']
    missing_context = []

    for key in required_context:
        if not hasattr(info.context, key):
            missing_context.append(key)

    if missing_context:
        raise GraphQLError(f"Missing required context: {missing_context}")

    return next_(root, info, **args)
```

## Advanced Context Patterns

### Context Inheritance

```python
class BaseContext:
    """Base context with common functionality."""
    def __init__(self):
        self.request_id = str(uuid.uuid4())
        self.timestamp = time.time()

    def get_user(self) -> Optional[User]:
        return getattr(self, 'current_user', None)

    def require_user(self) -> User:
        user = self.get_user()
        if not user:
            raise AuthenticationError()
        return user

def enhanced_context_middleware(next_, root, info, **args):
    """Create enhanced context with methods."""
    if not hasattr(info.context, '_enhanced'):
        # Enhance context with BaseContext methods
        base = BaseContext()
        for attr_name in dir(base):
            if not attr_name.startswith('_'):
                setattr(info.context, attr_name, getattr(base, attr_name))
        info.context._enhanced = True

    return next_(root, info, **args)
```

### Context Scoping

```python
def scoped_context_middleware(next_, root, info, **args):
    """Create field-scoped context data."""
    # Create field-specific context
    field_context = {
        'field_name': info.field_name,
        'field_path': str(info.path),
        'field_args': args,
        'execution_start': time.time()
    }

    # Store in context with field-specific key
    context_key = f"field_context_{info.field_name}"
    setattr(info.context, context_key, field_context)

    try:
        result = next_(root, info, **args)
        field_context['execution_time'] = time.time() - field_context['execution_start']
        field_context['success'] = True
        return result
    except Exception as e:
        field_context['execution_time'] = time.time() - field_context['execution_start']
        field_context['success'] = False
        field_context['error'] = str(e)
        raise
```

Context and metadata provide the foundation for building sophisticated, secure GraphQL APIs with clean separation of concerns and powerful cross-cutting functionality.