---
title: "Federation"
linkTitle: "Federation"
weight: 2
description: >
  Build distributed GraphQL services with Federation
---

# Federation

`graphql-api` provides built-in support for Federation, allowing you to build a distributed graph by composing multiple independent GraphQL services. This is essential for large-scale applications where different teams manage different parts of the overall API.

## Creating a Federated Service

To create a federated service, you need to use the `FederatedGraphQLAPI` class instead of the standard `GraphQLAPI`.

```python
from graphql_api.federation import FederatedGraphQLAPI

# Instead of GraphQLAPI(), use FederatedGraphQLAPI()
api = FederatedGraphQLAPI()
```

This will automatically add the necessary federation types (`_Service`, `_Entity`, etc.) and resolvers to your schema, making it compatible with a federated gateway.

The gateway is responsible for introspecting all of your federated services and composing them into a single, unified graph. When a query comes in, the gateway creates a query plan to fetch the necessary data from the appropriate services.

## Defining Entities

In a federated architecture, an "entity" is a type that can be extended by multiple services. To define an entity, you need to:

1.  Use the `@api.federation.entity` decorator on your class.
2.  Define a `resolve_reference` class method that tells the gateway how to fetch that entity by its primary key.

### Example

Let's say you have a `User` service and a `Reviews` service. The `User` type can be an entity shared between them.

Here's how you might define the `User` entity in the `User` service:

```python
from graphql_api.federation import FederatedGraphQLAPI
from pydantic import BaseModel

api = FederatedGraphQLAPI()

# A simple "database" of users
USERS = {
    "1": {"id": "1", "username": "test_user"},
}

@api.federation.entity(fields=["id"])
class User(BaseModel):
    id: str
    username: str

    @classmethod
    def resolve_reference(cls, representation):
        # This method tells the gateway how to fetch a User by its `id`
        user_id = representation.get("id")
        return User.model_validate(USERS.get(user_id))

@api.type(is_root_type=True)
class Query:
    pass # Other queries can go here
```

### Extending Entities

Now, another service (e.g., the `Reviews` service) can extend the `User` entity to add new fields.

```python
from graphql_api.federation import FederatedGraphQLAPI, external
from pydantic import BaseModel

api = FederatedGraphQLAPI()

class Review(BaseModel):
    id: str
    body: str

@api.federation.entity(fields=["id"])
class User(BaseModel):
    id: str = external() # Mark the `id` as external

    @api.field
    def get_reviews(self) -> list[Review]:
        # In a real app, you would fetch reviews for this user
        return [Review(id="1", body="A great product!")]

    @classmethod
    def resolve_reference(cls, representation):
        # This service only needs the user's ID to add its own fields
        return User(id=representation.get("id"))
```

In this example:

-   The `User` type is an extension of the original entity.
-   The `id` field is marked as `@external` because it's defined and owned by another service (the `User` service).
-   The `Reviews` service adds a new field, `reviews`, to the `User` entity.

When the federated gateway combines these services, clients will be able to query a `User` and get their `id`, `username`, and `reviews` in a single request, even though the data comes from two separate services.

## Advanced Federation: `@requires` and `@provides`

For more complex scenarios, you might need to manage dependencies between fields across different services. Apollo Federation provides directives like `@requires` and `@provides` to handle this.

-   `@provides`: Used on a field in an extending service to indicate that it can provide a field that is `@external` in another service. This can optimize queries by allowing the gateway to fetch data from a single service.
-   `@requires`: Used on a field to declare that it depends on another field that is defined in a different service. The gateway will ensure that the required fields are fetched first.

### Example with `@requires`

Imagine the `Reviews` service needs the user's name to format a review title, but the `username` field is owned by the `User` service.

```python
# In the Reviews service
from graphql_api.federation import FederatedGraphQLAPI, external, requires
from pydantic import BaseModel

api = FederatedGraphQLAPI()

@api.federation.entity(fields=["id"])
class User(BaseModel):
    id: str = external()
    username: str = external() # Also owned by the User service

    @api.field
    @requires(fields=["username"])
    def get_formatted_reviews(self) -> list[str]:
        # Because we used @requires, `self.username` will be populated
        # by the gateway before this resolver is called.
        return [f"Review by {self.username}: A great product!"]

    @classmethod
    def resolve_reference(cls, representation):
        # We can receive the required fields in the representation
        return User.model_validate(representation)
```

In this case:

1.  The `User` entity in the `Reviews` service declares that it has a `get_formatted_reviews` field.
2.  This field `@requires` the `username` field.
3.  When a client queries for `getFormattedReviews`, the federated gateway sees the `@requires` directive. It will first query the `User` service to get the `username`, then pass that information to the `Reviews` service to resolve `getFormattedReviews`.

This powerful pattern allows you to create computed fields that depend on data from multiple services while keeping the services themselves decoupled.