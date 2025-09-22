---
title: "Performance and Best Practices"
weight: 3
description: >
  Optimizing GraphQL API performance and following development best practices
---

# Performance and Best Practices

Building high-performance GraphQL APIs requires understanding query execution patterns, optimizing resolver performance, and following proven development practices. This guide covers essential techniques for creating scalable `graphql-api` applications.

## Understanding GraphQL Performance

GraphQL's flexibility comes with performance considerations:
- **N+1 Query Problem**: Resolvers may trigger excessive database queries
- **Deep Queries**: Nested queries can cause exponential resource usage
- **Large Result Sets**: Unrestricted queries can overwhelm servers
- **Resolver Efficiency**: Each field resolution has performance implications

## Async Resolver Best Practices

### Batching Operations

Use `asyncio.gather()` to batch multiple async operations:

```python
import asyncio
from typing import List

@api.type(is_root_type=True)
class Root:
    @api.field
    async def batch_users(self, ids: List[str]) -> List[User]:
        """Batch multiple user fetches efficiently."""
        # ✅ Good: Batch multiple async operations
        tasks = [fetch_user_async(id) for id in ids]
        users = await asyncio.gather(*tasks)
        return users

    @api.field
    async def batch_posts_with_authors(self, post_ids: List[str]) -> List[Post]:
        """Fetch posts and their authors in batches."""
        # Fetch posts in parallel
        post_tasks = [fetch_post_async(id) for id in post_ids]
        posts = await asyncio.gather(*post_tasks)

        # Extract unique author IDs
        author_ids = list(set(post.author_id for post in posts))

        # Batch fetch authors
        author_tasks = [fetch_user_async(id) for id in author_ids]
        authors = await asyncio.gather(*author_tasks)

        # Create author lookup
        author_map = {author.id: author for author in authors}

        # Attach authors to posts
        for post in posts:
            post.author = author_map.get(post.author_id)

        return posts
```

### Resource Management

Use async context managers for proper resource handling:

```python
@api.type(is_root_type=True)
class Root:
    @api.field
    async def efficient_data(self) -> DataResponse:
        """Use async context managers for resources."""
        # ✅ Good: Async context manager automatically handles cleanup
        async with get_db_session() as session:
            data = await session.fetch_data()
            return DataResponse(data=data)

    @api.field
    async def concurrent_data_sources(self) -> dict:
        """Access multiple data sources efficiently."""
        async with get_db_session() as db, \
                   get_redis_client() as cache, \
                   get_http_client() as http:

            # Execute queries concurrently
            db_task = db.execute_query("SELECT * FROM users")
            cache_task = cache.get("user_stats")
            api_task = http.get("https://api.example.com/metrics")

            db_result, cache_result, api_result = await asyncio.gather(
                db_task, cache_task, api_task
            )

            return {
                "users": db_result,
                "stats": cache_result,
                "metrics": api_result
            }
```

### Avoiding Common Async Pitfalls

```python
@api.type(is_root_type=True)
class Root:
    @api.field
    async def optimized_user_posts(self, user_id: str) -> List[Post]:
        """Avoid sequential async calls."""
        # ❌ Bad: Sequential calls
        # user = await fetch_user_async(user_id)
        # posts = await fetch_user_posts_async(user_id)

        # ✅ Good: Parallel calls when possible
        user_task = fetch_user_async(user_id)
        posts_task = fetch_user_posts_async(user_id)

        user, posts = await asyncio.gather(user_task, posts_task)

        # Attach user to posts
        for post in posts:
            post.author = user

        return posts

    @api.field
    async def processed_data(self, data_ids: List[str]) -> List[ProcessedData]:
        """Handle async processing with semaphore for rate limiting."""
        semaphore = asyncio.Semaphore(5)  # Limit concurrent operations

        async def process_item(item_id: str):
            async with semaphore:
                return await expensive_processing(item_id)

        # Process with concurrency limit
        tasks = [process_item(id) for id in data_ids]
        results = await asyncio.gather(*tasks)
        return results
```

## Database Performance Optimization

### Efficient Data Loading

```python
from dataclasses import dataclass
from typing import Dict, List, Optional

@dataclass
class DataLoader:
    """Simple data loader to batch database queries."""

    def __init__(self):
        self._user_cache: Dict[str, User] = {}
        self._pending_user_ids: set = set()

    async def load_user(self, user_id: str) -> Optional[User]:
        """Load user with batching and caching."""
        if user_id in self._user_cache:
            return self._user_cache[user_id]

        self._pending_user_ids.add(user_id)

        # Batch load on next tick
        await asyncio.sleep(0)
        await self._flush_users()

        return self._user_cache.get(user_id)

    async def _flush_users(self):
        """Batch load pending users."""
        if not self._pending_user_ids:
            return

        ids_to_load = list(self._pending_user_ids)
        self._pending_user_ids.clear()

        # Single database query for all users
        users = await db_batch_load_users(ids_to_load)

        for user in users:
            self._user_cache[user.id] = user

# Use in context
data_loader = DataLoader()

@api.type
class Post:
    @api.field
    async def author(self) -> Optional[User]:
        """Load author efficiently using data loader."""
        return await data_loader.load_user(self.author_id)
```

### Query Optimization

```python
@api.type(is_root_type=True)
class Root:
    @api.field
    async def optimized_posts(
        self,
        limit: int = 10,
        include_author: bool = False,
        include_comments: bool = False
    ) -> List[Post]:
        """Optimize database queries based on requested fields."""
        # Build query based on what's requested
        query = select(Post).limit(limit)

        # Only join if author data is requested
        if include_author:
            query = query.options(joinedload(Post.author))

        # Only join if comments are requested
        if include_comments:
            query = query.options(joinedload(Post.comments))

        async with get_db_session() as session:
            result = await session.execute(query)
            return result.scalars().all()

    @api.field
    async def posts_with_counts(self) -> List[PostWithCounts]:
        """Use database aggregation instead of N+1 queries."""
        # ✅ Good: Single query with aggregation
        query = """
            SELECT
                p.id, p.title, p.content,
                COUNT(c.id) as comment_count,
                COUNT(l.id) as like_count
            FROM posts p
            LEFT JOIN comments c ON p.id = c.post_id
            LEFT JOIN likes l ON p.id = l.post_id
            GROUP BY p.id, p.title, p.content
        """

        async with get_db_session() as session:
            result = await session.execute(text(query))
            return [
                PostWithCounts(
                    id=row.id,
                    title=row.title,
                    content=row.content,
                    comment_count=row.comment_count,
                    like_count=row.like_count
                )
                for row in result
            ]
```

## Caching Strategies

### Field-Level Caching

```python
import time
from typing import Dict, Any

# Simple in-memory cache (use Redis in production)
field_cache: Dict[str, tuple] = {}
CACHE_TTL = 300  # 5 minutes

def cached_field(ttl: int = 300):
    """Decorator for caching field results."""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Create cache key
            cache_key = f"{func.__name__}:{hash(str(args) + str(kwargs))}"
            current_time = time.time()

            # Check cache
            if cache_key in field_cache:
                cached_result, cached_time = field_cache[cache_key]
                if current_time - cached_time < ttl:
                    return cached_result

            # Execute and cache
            result = await func(*args, **kwargs)
            field_cache[cache_key] = (result, current_time)

            return result
        return wrapper
    return decorator

@api.type(is_root_type=True)
class Root:
    @api.field
    @cached_field(ttl=600)  # Cache for 10 minutes
    async def expensive_calculation(self, input_data: str) -> str:
        """Expensive operation that should be cached."""
        # Simulate expensive operation
        await asyncio.sleep(2)
        return f"Processed: {input_data}"

    @api.field
    @cached_field(ttl=60)  # Cache for 1 minute
    async def live_metrics(self) -> dict:
        """Live metrics with short cache TTL."""
        async with get_metrics_client() as client:
            return await client.get_current_metrics()
```

### Context-Based Caching

```python
def caching_middleware(next_, root, info, **args):
    """Middleware for intelligent caching."""
    cache_key = f"{info.field_name}:{hash(str(args))}"

    # Check if this field should be cached
    cache_config = getattr(info.field_definition, 'cache_config', None)
    if not cache_config:
        return next_(root, info, **args)

    ttl = cache_config.get('ttl', 300)
    enabled = cache_config.get('enabled', True)

    if not enabled:
        return next_(root, info, **args)

    # Check cache
    cached_result = get_from_cache(cache_key)
    if cached_result is not None:
        return cached_result

    # Execute and cache
    result = next_(root, info, **args)
    set_in_cache(cache_key, result, ttl=ttl)

    return result

# Usage with field metadata
@api.field({'cache_config': {'ttl': 3600, 'enabled': True}})
def cached_user_profile(self, user_id: str) -> UserProfile:
    return get_user_profile(user_id)
```

## Query Complexity and Rate Limiting

### Query Depth Limiting

```python
def depth_limiting_middleware(next_, root, info, **args):
    """Limit query depth to prevent abuse."""
    MAX_DEPTH = 10

    def get_query_depth(info):
        """Calculate query depth from GraphQL info."""
        depth = 0
        current = info
        while current:
            depth += 1
            current = getattr(current, 'parent_info', None)
        return depth

    query_depth = get_query_depth(info)
    if query_depth > MAX_DEPTH:
        raise GraphQLError(f"Query depth {query_depth} exceeds maximum {MAX_DEPTH}")

    return next_(root, info, **args)

api = GraphQLAPI(middleware=[depth_limiting_middleware])
```

### Query Complexity Analysis

```python
def complexity_analysis_middleware(next_, root, info, **args):
    """Analyze and limit query complexity."""
    complexity_score = calculate_field_complexity(info)
    max_complexity = get_user_complexity_limit(info.context)

    if complexity_score > max_complexity:
        raise GraphQLError(f"Query complexity {complexity_score} exceeds limit {max_complexity}")

    return next_(root, info, **args)

def calculate_field_complexity(info):
    """Calculate complexity score for field."""
    # Base complexity
    complexity = 1

    # Add complexity for arguments
    if hasattr(info, 'args') and info.args:
        complexity += len(info.args)

    # Add complexity for list fields
    if is_list_field(info.field_definition):
        complexity *= 2

    # Add complexity for expensive operations
    if info.field_name in ['search', 'aggregate', 'report']:
        complexity *= 3

    return complexity

def get_user_complexity_limit(context):
    """Get complexity limit based on user tier."""
    user = getattr(context, 'current_user', None)
    if not user:
        return 50  # Anonymous users

    if user.is_premium:
        return 500  # Premium users
    else:
        return 100  # Regular users
```

## Schema Organization Best Practices

### Modular Schema Design

```python
# users/schema.py
@api.type
class User:
    @api.field
    def id(self) -> str:
        return self._id

    @api.field
    def name(self) -> str:
        return self._name

    @api.field
    def posts(self) -> List['Post']:  # Forward reference
        return get_user_posts(self._id)

# posts/schema.py
@api.type
class Post:
    @api.field
    def id(self) -> str:
        return self._id

    @api.field
    def title(self) -> str:
        return self._title

    @api.field
    def author(self) -> User:
        return get_user(self.author_id)

# main.py - Bring everything together
@api.type(is_root_type=True)
class Root:
    @api.field
    def user(self, id: str) -> Optional[User]:
        return get_user(id)

    @api.field
    def posts(self, limit: int = 10) -> List[Post]:
        return get_recent_posts(limit)
```

### Environment-Specific Configuration

```python
import os

DEBUG = os.getenv('DEBUG', 'false').lower() == 'true'
ENVIRONMENT = os.getenv('ENVIRONMENT', 'development')

# Development configuration
if DEBUG:
    api = GraphQLAPI(
        error_protection=False,  # Get full stack traces
        middleware=[timing_middleware, debug_middleware]
    )
else:
    # Production configuration
    api = GraphQLAPI(
        error_protection=True,   # Hide internal errors
        middleware=[
            auth_middleware,
            rate_limiting_middleware,
            complexity_analysis_middleware,
            logging_middleware
        ]
    )

# Environment-specific middleware
def get_middleware_stack():
    """Get appropriate middleware for environment."""
    middleware = [auth_middleware]

    if ENVIRONMENT == 'development':
        middleware.extend([timing_middleware, debug_middleware])
    elif ENVIRONMENT == 'staging':
        middleware.extend([logging_middleware, timing_middleware])
    elif ENVIRONMENT == 'production':
        middleware.extend([
            rate_limiting_middleware,
            complexity_analysis_middleware,
            logging_middleware
        ])

    return middleware

api = GraphQLAPI(middleware=get_middleware_stack())
```

## Development and Debugging Tips

### Performance Monitoring

```python
def performance_monitoring_middleware(next_, root, info, **args):
    """Monitor resolver performance."""
    import time
    import logging

    start_time = time.time()
    field_name = info.field_name

    try:
        result = next_(root, info, **args)
        execution_time = time.time() - start_time

        # Log slow resolvers
        if execution_time > 1.0:  # 1 second threshold
            logging.warning(
                f"Slow resolver: {field_name} took {execution_time:.3f}s",
                extra={
                    'field': field_name,
                    'execution_time': execution_time,
                    'args': args
                }
            )

        # Track metrics
        track_resolver_performance(field_name, execution_time)

        return result

    except Exception as e:
        execution_time = time.time() - start_time
        logging.error(
            f"Resolver error: {field_name} failed after {execution_time:.3f}s",
            extra={
                'field': field_name,
                'error': str(e),
                'execution_time': execution_time
            }
        )
        raise

def track_resolver_performance(field_name: str, execution_time: float):
    """Track performance metrics."""
    # Send to monitoring system (e.g., DataDog, New Relic)
    # metrics.histogram('graphql.resolver.duration', execution_time, tags=[f'field:{field_name}'])
    pass
```

### Query Analysis

```python
def query_analysis_middleware(next_, root, info, **args):
    """Analyze query patterns for optimization."""
    query_hash = hash(str(info.operation.loc.source.body))

    # Track query frequency
    track_query_frequency(query_hash, info.operation.loc.source.body)

    # Analyze field usage
    track_field_usage(info.field_name, info.path)

    return next_(root, info, **args)

def track_query_frequency(query_hash: int, query_body: str):
    """Track how often specific queries are executed."""
    # Store in analytics database
    pass

def track_field_usage(field_name: str, path):
    """Track field access patterns."""
    # Identify unused fields, popular fields, etc.
    pass
```

## Testing Performance

### Load Testing

```python
import asyncio
import time
from concurrent.futures import ThreadPoolExecutor

async def load_test_resolver():
    """Load test a specific resolver."""
    query = '''
        query {
            users(first: 100) {
                id
                name
                posts(first: 10) {
                    title
                    comments(first: 5) {
                        content
                    }
                }
            }
        }
    '''

    tasks = []
    for i in range(100):  # 100 concurrent requests
        task = api.execute_async(query)
        tasks.append(task)

    start_time = time.time()
    results = await asyncio.gather(*tasks)
    end_time = time.time()

    print(f"Executed 100 queries in {end_time - start_time:.2f} seconds")
    print(f"Average: {(end_time - start_time) / 100:.3f} seconds per query")

    # Analyze results
    successful = sum(1 for result in results if not result.errors)
    print(f"Success rate: {successful}/100")

# Run load test
asyncio.run(load_test_resolver())
```

### Benchmarking

```python
def benchmark_resolver_performance():
    """Benchmark resolver performance."""
    import timeit

    # Test different query patterns
    simple_query = 'query { user(id: "1") { name } }'
    complex_query = '''
        query {
            user(id: "1") {
                name
                posts {
                    title
                    comments {
                        content
                        author { name }
                    }
                }
            }
        }
    '''

    # Benchmark simple query
    simple_time = timeit.timeit(
        lambda: api.execute(simple_query),
        number=1000
    )

    # Benchmark complex query
    complex_time = timeit.timeit(
        lambda: api.execute(complex_query),
        number=100
    )

    print(f"Simple query (1000x): {simple_time:.3f}s average: {simple_time/1000:.6f}s")
    print(f"Complex query (100x): {complex_time:.3f}s average: {complex_time/100:.6f}s")
```

## Key Performance Guidelines

**1. Use database-level pagination:**
```python
# ✅ Good: Database pagination
query.offset(offset).limit(limit)

# ❌ Avoid: Application-level pagination
all_records = query.all()
page = all_records[offset:offset+limit]
```

**2. Batch database operations:**
```python
# ✅ Good: Single query with IN clause
users = session.query(User).filter(User.id.in_(user_ids)).all()

# ❌ Avoid: Multiple individual queries
users = [session.query(User).get(id) for id in user_ids]
```

**3. Use appropriate data structures:**
```python
# ✅ Good: Dictionary lookup O(1)
user_map = {user.id: user for user in users}
user = user_map.get(user_id)

# ❌ Avoid: List search O(n)
user = next((u for u in users if u.id == user_id), None)
```

**4. Implement intelligent caching:**
```python
# Cache based on data volatility
@cached_field(ttl=3600)  # 1 hour for stable data
def user_profile(self): pass

@cached_field(ttl=60)    # 1 minute for frequently changing data
def live_stats(self): pass
```

**5. Monitor and measure:**
- Use APM tools (New Relic, DataDog, etc.)
- Track resolver execution times
- Monitor database query patterns
- Analyze query complexity trends

Following these practices will help you build GraphQL APIs that scale efficiently and provide excellent performance for your users.

## Advanced Topics

For larger scale deployments, consider these specialized areas:

**Distributed systems:**
- [Remote GraphQL](remote-graphql/) - Integrate with remote GraphQL services
- [Federation](federation/) - Scale with microservices architecture
- [Relay Pagination](pagination-relay/) - Advanced client integration patterns

**Reference materials:**
- [Examples](examples/) - Real-world implementation patterns
- [API Reference](api-reference/) - Complete API documentation
- [Contributing](contributing/) - Help improve graphql-api