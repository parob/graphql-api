---
title: "Schema Filtering"
weight: 2
description: >
  Controlling field access and schema structure with automatic filtering capabilities
---

# Schema Filtering

`graphql-api` provides powerful schema filtering capabilities that automatically control field access and maintain proper GraphQL schema structure. This includes separating query and mutation fields, validating field combinations, and ensuring interface compliance.

## Understanding Schema Filtering

Schema filtering works automatically to:
- Separate query fields from mutation fields
- Prevent invalid field combinations
- Maintain interface contracts
- Ensure proper GraphQL schema structure
- Filter out inappropriate fields based on context

This happens transparently during schema generation and query execution, ensuring your API follows GraphQL best practices.

## Field-Level Access Control

### Query vs Mutation Field Separation

You can control which fields are available in queries vs mutations using the `mutable` parameter:

```python
@api.type(is_root_type=True)
class Root:
    @api.field
    def public_data(self) -> str:
        """Available in queries only."""
        return "Available in queries"

    @api.field(mutable=True)
    def update_data(self, value: str) -> str:
        """Available in mutations only."""
        return f"Updated: {value}"

    @api.field
    def read_user(self, id: str) -> str:
        """Query operation."""
        return f"User: {id}"

    @api.field(mutable=True)
    def create_user(self, name: str) -> str:
        """Mutation operation."""
        return f"Created user: {name}"
```

**Schema separation:**
- In **queries**: only non-mutable fields (`public_data`, `read_user`) are available
- In **mutations**: both regular and mutable fields may be available depending on context

**GraphQL schema generated:**
```graphql
type Query {
  publicData: String!
  readUser(id: String!): String!
}

type Mutation {
  updateData(value: String!): String!
  createUser(name: String!): String!
}
```

## Automatic Schema Validation

The library automatically filters invalid field combinations to maintain GraphQL correctness:

```python
class Person:
    @api.field
    def name(self) -> str:
        return "Alice"

    @api.field(mutable=True)
    def update_name(self, name: str) -> str:
        self.name = name
        return name

@api.type(is_root_type=True)
class Root:
    @api.field
    def person(self) -> Person:
        return Person()
```

**Automatic filtering behavior:**
```graphql
# ❌ This query will fail - can't use mutation fields in queries
query {
  person {
    updateName(name: "Bob")  # ERROR: mutation field in query
  }
}

# ✅ This query will succeed - only query fields
query {
  person {
    name  # OK: query field in query
  }
}

# ✅ This mutation will succeed - mutation fields allowed
mutation {
  person {
    updateName(name: "Bob")  # OK: mutation field in mutation
  }
}
```

## Interface and Implementation Filtering

The library maintains proper GraphQL schema structure even when implementations are filtered:

```python
@api.type(interface=True)
class Animal:
    @api.field
    def name(self) -> str:
        return "Generic Animal"

    @api.field
    def species(self) -> str:
        return "Unknown"

class Dog(Animal):
    @api.field
    def name(self) -> str:
        return "Dog"

    @api.field
    def breed(self) -> str:
        return "Golden Retriever"

    @api.field(mutable=True)
    def update_name(self, name: str) -> str:
        return f"Updated dog name to {name}"

class Cat(Animal):
    @api.field
    def name(self) -> str:
        return "Cat"

    @api.field
    def indoor(self) -> bool:
        return True

@api.type(is_root_type=True)
class Root:
    @api.field
    def animals(self) -> List[Animal]:
        return [Dog(), Cat()]
```

**Schema filtering ensures:**
- Interface contracts are maintained
- Only appropriate fields are available in each operation type
- Implementation-specific fields are properly filtered

## Context-Based Filtering

Fields can be filtered based on request context and user permissions:

```python
from graphql_api.context import GraphQLContext

@api.type(is_root_type=True)
class Root:
    @api.field
    def public_info(self) -> str:
        """Always available."""
        return "Public information"

    @api.field
    def user_info(self, context: GraphQLContext) -> Optional[str]:
        """Only available to authenticated users."""
        user = getattr(context, 'current_user', None)
        if not user:
            return None
        return f"Info for {user.name}"

    @api.field
    def admin_info(self, context: GraphQLContext) -> Optional[str]:
        """Only available to admin users."""
        user = getattr(context, 'current_user', None)
        if not user or not user.is_admin:
            return None
        return "Admin-only information"

    @api.field(mutable=True)
    def delete_data(self, context: GraphQLContext, id: str) -> bool:
        """Dangerous operation with strict access control."""
        user = getattr(context, 'current_user', None)
        if not user or not user.has_permission('delete'):
            raise PermissionError("Delete permission required")
        return True
```

## Advanced Filtering Patterns

### Role-Based Field Access

Implement role-based access control that filters fields based on user roles:

```python
def role_based_filter_middleware(next_, root, info, **args):
    """Filter fields based on user roles."""
    user = getattr(info.context, 'current_user', None)
    field_name = info.field_name

    # Define role requirements for fields
    role_requirements = {
        'admin_data': ['admin'],
        'moderator_tools': ['admin', 'moderator'],
        'user_secrets': ['user', 'admin', 'moderator'],
        'system_info': ['admin', 'system']
    }

    required_roles = role_requirements.get(field_name, [])
    if required_roles:
        if not user:
            raise GraphQLError("Authentication required")

        user_roles = getattr(user, 'roles', [])
        if not any(role in user_roles for role in required_roles):
            raise GraphQLError(f"Insufficient permissions for {field_name}")

    return next_(root, info, **args)

@api.type(is_root_type=True)
class Root:
    @api.field
    def public_data(self) -> str:
        return "Available to everyone"

    @api.field
    def admin_data(self) -> str:
        return "Admin only data"

    @api.field
    def moderator_tools(self) -> str:
        return "Moderator tools"

    @api.field
    def user_secrets(self) -> str:
        return "User-specific secrets"

api = GraphQLAPI(middleware=[role_based_filter_middleware])
```

### Dynamic Field Filtering

Filter fields dynamically based on request context:

```python
def dynamic_field_filter_middleware(next_, root, info, **args):
    """Dynamically filter fields based on various factors."""
    field_name = info.field_name
    context = info.context

    # Filter expensive operations during peak hours
    if field_name in ['expensive_calculation', 'heavy_query']:
        current_hour = datetime.now().hour
        if 9 <= current_hour <= 17:  # Business hours
            peak_hours = getattr(context, 'allow_peak_operations', False)
            if not peak_hours:
                raise GraphQLError("Operation not available during peak hours")

    # Filter based on API key tier
    api_key_tier = getattr(context, 'api_key_tier', 'free')
    premium_fields = ['advanced_analytics', 'bulk_operations', 'priority_support']

    if field_name in premium_fields and api_key_tier != 'premium':
        raise GraphQLError(f"Premium subscription required for {field_name}")

    # Filter based on feature flags
    feature_flags = getattr(context, 'feature_flags', {})
    beta_fields = ['beta_feature', 'experimental_api']

    if field_name in beta_fields:
        if not feature_flags.get(f'{field_name}_enabled', False):
            raise GraphQLError(f"Feature {field_name} is not enabled")

    return next_(root, info, **args)
```

### Schema-Level Filtering

Filter entire types or sets of fields based on configuration:

```python
class FilteredSchema:
    def __init__(self, enabled_features=None):
        self.enabled_features = enabled_features or set()

    def is_feature_enabled(self, feature: str) -> bool:
        return feature in self.enabled_features

schema_config = FilteredSchema(enabled_features={
    'user_management',
    'reporting',
    # 'admin_tools',  # Disabled
    # 'beta_features'  # Disabled
})

def schema_filter_middleware(next_, root, info, **args):
    """Filter based on enabled schema features."""
    field_name = info.field_name

    # Map fields to features
    feature_map = {
        'create_user': 'user_management',
        'delete_user': 'user_management',
        'generate_report': 'reporting',
        'admin_panel': 'admin_tools',
        'beta_endpoint': 'beta_features'
    }

    required_feature = feature_map.get(field_name)
    if required_feature and not schema_config.is_feature_enabled(required_feature):
        raise GraphQLError(f"Feature {required_feature} is not available")

    return next_(root, info, **args)

@api.type(is_root_type=True)
class Root:
    @api.field(mutable=True)
    def create_user(self, name: str) -> str:
        return f"Created user: {name}"

    @api.field
    def generate_report(self) -> str:
        return "Generated report"

    @api.field
    def admin_panel(self) -> str:
        return "Admin panel access"

    @api.field
    def beta_endpoint(self) -> str:
        return "Beta feature"
```

## Conditional Field Inclusion

Include or exclude fields based on runtime conditions:

```python
@api.type
class User:
    @api.field
    def id(self) -> str:
        return self._id

    @api.field
    def name(self) -> str:
        return self._name

    @api.field
    def email(self, context: GraphQLContext) -> Optional[str]:
        """Email only available to user themselves or admins."""
        current_user = getattr(context, 'current_user', None)
        if not current_user:
            return None

        # Users can see their own email, admins can see any email
        if current_user.id == self._id or current_user.is_admin:
            return self._email

        return None

    @api.field
    def phone(self, context: GraphQLContext) -> Optional[str]:
        """Phone number with privacy controls."""
        current_user = getattr(context, 'current_user', None)
        if not current_user:
            return None

        # Only show to user themselves
        if current_user.id == self._id:
            return self._phone

        return None

    @api.field
    def internal_notes(self, context: GraphQLContext) -> Optional[str]:
        """Internal notes only for staff."""
        current_user = getattr(context, 'current_user', None)
        if not current_user or not current_user.is_staff:
            return None

        return self._internal_notes
```

## Best Practices

**Use clear field separation:**
```python
# ✅ Good: Clear separation of concerns
@api.field
def get_user(self, id: str) -> User:
    return fetch_user(id)

@api.field(mutable=True)
def update_user(self, id: str, data: UpdateUserInput) -> User:
    return update_user_data(id, data)

# ❌ Avoid: Mixing query and mutation logic
@api.field
def user_operation(self, id: str, action: str, data: Optional[dict] = None):
    if action == "get":
        return fetch_user(id)
    elif action == "update":
        return update_user_data(id, data)
```

**Implement graceful degradation:**
```python
@api.field
def premium_feature(self, context: GraphQLContext) -> Optional[str]:
    """Gracefully handle unavailable features."""
    user = getattr(context, 'current_user', None)

    if not user:
        return None  # Not an error, just not available

    if not user.has_premium:
        return None  # Graceful degradation

    return "Premium content here"
```

**Use middleware for consistent filtering:**
```python
# Apply filtering logic consistently across all fields
api = GraphQLAPI(middleware=[
    authentication_middleware,    # Add user context
    permission_middleware,       # Check permissions
    feature_flag_middleware,     # Check feature availability
    rate_limiting_middleware,    # Apply rate limits
])
```

**Document filtering behavior:**
```python
@api.field
def sensitive_data(self, context: GraphQLContext) -> Optional[str]:
    """
    Returns sensitive data.

    Access Control:
    - Requires authentication
    - Only available to users with 'view_sensitive' permission
    - Returns None if access is denied (no error thrown)
    """
    user = getattr(context, 'current_user', None)
    if not user or not user.has_permission('view_sensitive'):
        return None

    return "Sensitive information"
```

Schema filtering ensures your GraphQL API maintains proper structure and security while providing flexible access control mechanisms that scale with your application's needs.