---
title: "Remote GraphQL"
weight: 1
description: >
  Working with remote GraphQL services and building distributed architectures
---

# Remote GraphQL

`graphql-api` provides powerful capabilities for working with remote GraphQL services, enabling you to create distributed GraphQL architectures, proxy remote APIs, and build sophisticated microservices integrations.

## Overview

Remote GraphQL features allow you to:
- Connect to external GraphQL APIs
- Integrate remote services into your local schema
- Build API gateways and schema federation
- Create distributed GraphQL architectures
- Switch between local and remote implementations

## GraphQLRemoteExecutor

The `GraphQLRemoteExecutor` class connects to and executes queries against remote GraphQL services:

### Basic Usage

```python
from graphql_api.remote import GraphQLRemoteExecutor

# Connect to a remote GraphQL API
remote_api = GraphQLRemoteExecutor(
    url="https://api.example.com/graphql",
    http_method="POST",  # or "GET"
    verify=True,  # SSL certificate verification
    http_headers={
        "Authorization": "Bearer your-token",
        "Content-Type": "application/json"
    }
)

# Execute queries directly
result = remote_api.execute('''
    query {
        user(id: "123") {
            name
            email
            posts {
                title
                content
            }
        }
    }
''')

print(result.data)  # Access query results
if result.errors:
    print("Errors:", result.errors)
```

### Configuration Options

```python
remote_api = GraphQLRemoteExecutor(
    url="https://api.example.com/graphql",
    http_method="POST",           # HTTP method: "GET" or "POST"
    verify=True,                  # SSL certificate verification
    timeout=30,                   # Request timeout in seconds
    http_headers={                # Custom headers
        "Authorization": "Bearer token",
        "User-Agent": "MyApp/1.0",
        "X-API-Key": "api-key"
    }
)
```

## Integrating Remote APIs

### Basic Integration

Integrate remote APIs as fields in your local GraphQL schema:

```python
from graphql_api.api import GraphQLAPI
from graphql_api.remote import GraphQLRemoteExecutor, remote_execute
from graphql_api.context import GraphQLContext

api = GraphQLAPI()

# External API connection
external_api = GraphQLRemoteExecutor(
    url="https://api.external-service.com/graphql",
    http_headers={"API-Key": "your-api-key"}
)

@api.type(is_root_type=True)
class Root:
    @api.field
    def external_data(self, context: GraphQLContext) -> external_api:  # type: ignore[valid-type]
        """
        Forward queries to external API.

        The remote_execute helper automatically forwards the current query
        to the remote service, maintaining field selection and arguments.
        """
        return remote_execute(executor=external_api, context=context)

    @api.field
    def custom_external_query(self) -> dict:
        """Execute a specific query against the remote API."""
        result = external_api.execute('''
            query {
                specificData {
                    id
                    value
                    metadata {
                        created_at
                        updated_at
                    }
                }
            }
        ''')
        return result.data if result.data else {}
```

### Advanced Integration Patterns

```python
@api.type(is_root_type=True)
class Root:
    @api.field
    def user_profile(self, user_id: str) -> dict:
        """Combine local and remote data."""
        # Get local user data
        local_user = get_local_user(user_id)

        # Get remote profile data
        remote_result = external_api.execute(f'''
            query {{
                userProfile(id: "{user_id}") {{
                    preferences
                    settings
                    externalData
                }}
            }}
        ''')

        # Combine data
        return {
            "id": local_user.id,
            "name": local_user.name,
            "email": local_user.email,
            "profile": remote_result.data.get("userProfile", {})
        }

    @api.field
    def search_combined(self, query: str) -> dict:
        """Search across multiple remote services."""
        # Search users service
        users_result = user_service.execute(f'''
            query {{
                searchUsers(query: "{query}") {{
                    id
                    name
                    type
                }}
            }}
        ''')

        # Search content service
        content_result = content_service.execute(f'''
            query {{
                searchContent(query: "{query}") {{
                    id
                    title
                    type
                }}
            }}
        ''')

        return {
            "users": users_result.data.get("searchUsers", []),
            "content": content_result.data.get("searchContent", [])
        }
```

## Async Remote Execution

All remote operations support async execution for better performance:

```python
import asyncio
from graphql_api.remote import GraphQLRemoteExecutor

async def fetch_remote_data():
    remote_api = GraphQLRemoteExecutor(
        url="https://api.example.com/graphql",
        http_headers={"Authorization": "Bearer token"}
    )

    # Async execution
    result = await remote_api.execute_async('''
        query {
            users(first: 10) {
                id
                name
                email
            }
        }
    ''')

    return result.data

# Async field resolver
@api.type(is_root_type=True)
class Root:
    @api.field
    async def async_external_data(self) -> dict:
        """Async remote data fetching."""
        remote_api = GraphQLRemoteExecutor(
            url="https://api.external.com/graphql"
        )

        result = await remote_api.execute_async('''
            query {
                dashboard {
                    metrics
                    alerts
                    status
                }
            }
        ''')

        return result.data.get("dashboard", {})

    @api.field
    async def parallel_remote_calls(self) -> dict:
        """Make multiple remote calls in parallel."""
        # Create multiple remote executors
        service_a = GraphQLRemoteExecutor(url="https://service-a.com/graphql")
        service_b = GraphQLRemoteExecutor(url="https://service-b.com/graphql")
        service_c = GraphQLRemoteExecutor(url="https://service-c.com/graphql")

        # Execute in parallel
        results = await asyncio.gather(
            service_a.execute_async('query { dataA { value } }'),
            service_b.execute_async('query { dataB { value } }'),
            service_c.execute_async('query { dataC { value } }')
        )

        return {
            "serviceA": results[0].data,
            "serviceB": results[1].data,
            "serviceC": results[2].data
        }

# Usage
data = asyncio.run(fetch_remote_data())
```

## Federation and Schema Stitching

Combine multiple remote GraphQL APIs into a unified schema:

```python
api = GraphQLAPI()

# Multiple remote services
user_service = GraphQLRemoteExecutor(
    url="https://users.example.com/graphql",
    http_headers={"Service": "user-service"}
)

order_service = GraphQLRemoteExecutor(
    url="https://orders.example.com/graphql",
    http_headers={"Service": "order-service"}
)

product_service = GraphQLRemoteExecutor(
    url="https://products.example.com/graphql",
    http_headers={"Service": "product-service"}
)

@api.type(is_root_type=True)
class Root:
    @api.field
    def users(self, context: GraphQLContext) -> user_service:  # type: ignore[valid-type]
        """Forward user queries to user service."""
        return remote_execute(executor=user_service, context=context)

    @api.field
    def orders(self, context: GraphQLContext) -> order_service:  # type: ignore[valid-type]
        """Forward order queries to order service."""
        return remote_execute(executor=order_service, context=context)

    @api.field
    def products(self, context: GraphQLContext) -> product_service:  # type: ignore[valid-type]
        """Forward product queries to product service."""
        return remote_execute(executor=product_service, context=context)

    @api.field
    def user_with_orders(self, user_id: str) -> dict:
        """Combine data from multiple services."""
        # Get user data
        user_result = user_service.execute(f'''
            query {{
                user(id: "{user_id}") {{
                    id
                    name
                    email
                }}
            }}
        ''')

        # Get user's orders
        orders_result = order_service.execute(f'''
            query {{
                orders(userId: "{user_id}") {{
                    id
                    total
                    status
                    items {{
                        productId
                        quantity
                        price
                    }}
                }}
            }}
        ''')

        return {
            "user": user_result.data.get("user"),
            "orders": orders_result.data.get("orders", [])
        }

    @api.field
    async def enhanced_user_profile(self, user_id: str) -> dict:
        """Combine data from all services asynchronously."""
        # Execute queries in parallel
        user_task = user_service.execute_async(f'''
            query {{ user(id: "{user_id}") {{ id name email }} }}
        ''')

        orders_task = order_service.execute_async(f'''
            query {{ orders(userId: "{user_id}") {{ id total status }} }}
        ''')

        # Wait for all results
        user_result, orders_result = await asyncio.gather(user_task, orders_task)

        # Get product details for orders
        order_items = []
        if orders_result.data and orders_result.data.get("orders"):
            product_ids = []
            for order in orders_result.data["orders"]:
                for item in order.get("items", []):
                    product_ids.append(item["productId"])

            if product_ids:
                products_result = await product_service.execute_async(f'''
                    query {{
                        products(ids: {product_ids}) {{
                            id
                            name
                            price
                        }}
                    }}
                ''')
                order_items = products_result.data.get("products", [])

        return {
            "user": user_result.data.get("user"),
            "orders": orders_result.data.get("orders", []),
            "products": order_items
        }
```

## GraphQLRemoteObject

Make local objects behave like remote GraphQL queries for testing or abstraction:

```python
from graphql_api.remote import GraphQLRemoteObject

api = GraphQLAPI()

@api.type(is_root_type=True)
class House:
    @api.field
    def number_of_doors(self) -> int:
        return 5

    @api.field
    def address(self) -> str:
        return "123 Main St"

    @api.field
    def rooms(self) -> List[str]:
        return ["kitchen", "bedroom", "bathroom"]

# Create a remote-like object that queries the local API
house: House = GraphQLRemoteObject(executor=api.executor(), api=api)

# Use like a regular object, but it executes GraphQL queries behind the scenes
doors = house.number_of_doors()  # Executes: query { numberOfDoors }
address = house.address()        # Executes: query { address }
rooms = house.rooms()           # Executes: query { rooms }

assert doors == 5
assert address == "123 Main St"
assert "kitchen" in rooms
```

**Use cases for GraphQLRemoteObject:**
- Testing with mock remote services
- Abstracting local vs remote data sources
- Development environments with local fallbacks
- Service migration scenarios

## Error Handling

Remote GraphQL operations handle errors gracefully:

```python
def handle_remote_errors():
    try:
        result = remote_api.execute('''
            query {
                user(id: "invalid") {
                    name
                }
            }
        ''')

        if result.errors:
            print("GraphQL errors:", result.errors)
            # Handle GraphQL-level errors

        if result.data:
            print("Data:", result.data)

    except Exception as e:
        print("Network or execution error:", e)
        # Handle network errors, timeouts, etc.

# Error handling in resolvers
@api.type(is_root_type=True)
class Root:
    @api.field
    def safe_remote_data(self) -> Optional[dict]:
        """Safe remote data fetching with error handling."""
        try:
            result = external_api.execute('''
                query {
                    criticalData {
                        value
                    }
                }
            ''')

            if result.errors:
                # Log errors but don't fail
                print(f"Remote API errors: {result.errors}")
                return None

            return result.data

        except Exception as e:
            # Network error - return None instead of failing
            print(f"Failed to fetch remote data: {e}")
            return None
```

## Best Practices

**Use connection pooling for performance:**
```python
# Reuse the same executor instance
class RemoteServices:
    def __init__(self):
        self.user_service = GraphQLRemoteExecutor(
            url="https://users.example.com/graphql"
        )
        self.order_service = GraphQLRemoteExecutor(
            url="https://orders.example.com/graphql"
        )

# Create once, use many times
services = RemoteServices()
```

**Handle authentication properly:**
```python
def get_remote_executor_with_auth(context: GraphQLContext):
    """Create authenticated remote executor."""
    user = getattr(context, 'current_user', None)

    headers = {"Content-Type": "application/json"}
    if user and user.api_token:
        headers["Authorization"] = f"Bearer {user.api_token}"

    return GraphQLRemoteExecutor(
        url="https://api.example.com/graphql",
        http_headers=headers
    )

@api.field
def authenticated_remote_data(self, context: GraphQLContext) -> dict:
    remote_api = get_remote_executor_with_auth(context)
    result = remote_api.execute('query { privateData { value } }')
    return result.data
```

**Implement caching for remote calls:**
```python
import time
from typing import Dict, Any

# Simple cache implementation
remote_cache: Dict[str, tuple] = {}
CACHE_TTL = 300  # 5 minutes

def cached_remote_execute(executor, query: str) -> Any:
    """Execute remote query with caching."""
    cache_key = f"{executor.url}:{hash(query)}"
    current_time = time.time()

    # Check cache
    if cache_key in remote_cache:
        cached_result, cached_time = remote_cache[cache_key]
        if current_time - cached_time < CACHE_TTL:
            return cached_result

    # Execute and cache
    result = executor.execute(query)
    remote_cache[cache_key] = (result, current_time)

    return result
```

**Monitor remote service health:**
```python
@api.field
def service_health(self) -> dict:
    """Check health of remote services."""
    services = {
        "users": user_service,
        "orders": order_service,
        "products": product_service
    }

    health_status = {}

    for name, service in services.items():
        try:
            result = service.execute('query { __schema { queryType { name } } }')
            health_status[name] = "healthy" if not result.errors else "degraded"
        except Exception:
            health_status[name] = "unhealthy"

    return health_status
```

Remote GraphQL capabilities enable building sophisticated distributed architectures while maintaining type safety and developer experience. They're essential for microservices, API gateways, and modern distributed systems.