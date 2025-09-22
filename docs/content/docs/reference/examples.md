---
title: "Examples & Tutorials"
weight: 1
---

# Examples & Tutorials

This section provides practical examples and step-by-step tutorials to help you build real-world GraphQL APIs with `graphql-api`.

## Table of Contents

- [Basic Blog API](#basic-blog-api)
- [E-commerce API with Pydantic](#e-commerce-api-with-pydantic)
- [Real-time Chat with Subscriptions](#real-time-chat-with-subscriptions)
- [Microservices with Apollo Federation](#microservices-with-apollo-federation)
- [Todo App with Mutations](#todo-app-with-mutations)

---

## Basic Blog API

Let's build a simple blog API that demonstrates core GraphQL concepts.

### Setting Up the Data Model

```python
from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime
from graphql_api.api import GraphQLAPI
from graphql_api.decorators import field

@dataclass
class Author:
    id: int
    name: str
    email: str

@dataclass
class Post:
    id: int
    title: str
    content: str
    author_id: int
    published_at: Optional[datetime] = None
    
# Sample data
authors = [
    Author(1, "Alice Johnson", "alice@example.com"),
    Author(2, "Bob Smith", "bob@example.com"),
]

posts = [
    Post(1, "Getting Started with GraphQL", "GraphQL is a query language...", 1, datetime.now()),
    Post(2, "Python Type Hints", "Type hints make your code more readable...", 2, datetime.now()),
    Post(3, "Draft Post", "This is a draft post...", 1),  # No published_at
]

api = GraphQLAPI()
```

### Creating the Root Type

```python
@api.type(is_root_type=True)
class BlogAPI:
    @api.field
    def posts(self, published_only: bool = False) -> List[Post]:
        """Get all posts, optionally filtered by published status."""
        if published_only:
            return [p for p in posts if p.published_at is not None]
        return posts
    
    @api.field
    def post(self, post_id: int) -> Optional[Post]:
        """Get a specific post by ID."""
        return next((p for p in posts if p.id == post_id), None)
    
    @api.field
    def authors(self) -> List[Author]:
        """Get all authors."""
        return authors
    
    @api.field
    def author(self, author_id: int) -> Optional[Author]:
        """Get a specific author by ID."""
        return next((a for a in authors if a.id == author_id), None)
```

### Adding Methods for Related Data

```python
# Add methods to the dataclasses for related data
from graphql_api.decorators import field

@dataclass
class Post:
    id: int
    title: str
    content: str
    author_id: int
    published_at: Optional[datetime] = None
    
    @field
    def get_author(self) -> Optional[Author]:
        """Get the author for this post."""
        return next((a for a in authors if a.id == self.author_id), None)

@dataclass
class Author:
    id: int
    name: str
    email: str
    
    @field
    def get_posts(self) -> List[Post]:
        """Get posts written by this author."""
        return [p for p in posts if p.author_id == self.id]
```

### Testing the API

```python
# Query all published posts with their authors
query = """
    query {
        posts(publishedOnly: true) {
            id
            title
            content
            getAuthor {
                name
                email
            }
        }
    }
"""

result = api.execute(query)
print(result.data)
```

---

## E-commerce API with Pydantic

This example shows how to use Pydantic models for data validation and serialization.

### Pydantic Models

```python
from pydantic import BaseModel, EmailStr, validator
from typing import List, Optional
from enum import Enum
from decimal import Decimal

class OrderStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    SHIPPED = "shipped"
    DELIVERED = "delivered"

class Product(BaseModel):
    id: int
    name: str
    description: str
    price: Decimal
    in_stock: bool = True
    
    @validator('price')
    def price_must_be_positive(cls, v):
        if v <= 0:
            raise ValueError('Price must be positive')
        return v

class Customer(BaseModel):
    id: int
    name: str
    email: EmailStr
    address: Optional[str] = None

class OrderItem(BaseModel):
    product_id: int
    quantity: int
    unit_price: Decimal

class Order(BaseModel):
    id: int
    customer_id: int
    items: List[OrderItem]
    status: OrderStatus = OrderStatus.PENDING
    total: Optional[Decimal] = None
    
    @validator('total', always=True)
    def calculate_total(cls, v, values):
        if 'items' in values:
            return sum(item.quantity * item.unit_price for item in values['items'])
        return v

api = GraphQLAPI()
```

### Sample Data

```python
products = [
    Product(id=1, name="MacBook Pro", description="High-performance laptop", price=Decimal("1999.99")),
    Product(id=2, name="iPhone", description="Latest smartphone", price=Decimal("999.99")),
]

customers = [
    Customer(id=1, name="John Doe", email="john@example.com", address="123 Main St"),
    Customer(id=2, name="Jane Smith", email="jane@example.com"),
]

orders = []
```

### GraphQL Schema

```python
@api.type(is_root_type=True)
class EcommerceAPI:
    @api.field
    def products(self) -> List[Product]:
        """Get all products."""
        return products
    
    @api.field
    def product(self, product_id: int) -> Optional[Product]:
        """Get a specific product."""
        return next((p for p in products if p.id == product_id), None)
    
    @api.field
    def customers(self) -> List[Customer]:
        """Get all customers."""
        return customers
    
    @api.field
    def orders(self, customer_id: Optional[int] = None) -> List[Order]:
        """Get orders, optionally filtered by customer."""
        if customer_id:
            return [o for o in orders if o.customer_id == customer_id]
        return orders
    
    @api.field(mutable=True)
    def create_order(self, customer_id: int, items: List[dict]) -> Order:
        """Create a new order."""
        order_items = [
            OrderItem(
                product_id=item['product_id'],
                quantity=item['quantity'],
                unit_price=next(p.price for p in products if p.id == item['product_id'])
            )
            for item in items
        ]
        
        order = Order(
            id=len(orders) + 1,
            customer_id=customer_id,
            items=order_items
        )
        orders.append(order)
        return order
```

---

## Real-time Chat with Subscriptions

This example demonstrates GraphQL subscriptions for real-time functionality.

### Chat Models

```python
import asyncio
from typing import AsyncGenerator
from datetime import datetime

@dataclass
class Message:
    id: int
    room_id: str
    user_name: str
    content: str
    timestamp: datetime

@dataclass
class Room:
    id: str
    name: str
    description: Optional[str] = None

# In-memory storage
rooms = [
    Room("general", "General Discussion"),
    Room("tech", "Tech Talk"),
]
messages = []
message_subscribers = {}

api = GraphQLAPI()
```

### Subscription Implementation

```python
@api.type(is_root_type=True)
class ChatAPI:
    @api.field
    def rooms(self) -> List[Room]:
        """Get all chat rooms."""
        return rooms
    
    @api.field
    def messages(self, room_id: str, limit: int = 50) -> List[Message]:
        """Get recent messages from a room."""
        room_messages = [m for m in messages if m.room_id == room_id]
        return sorted(room_messages, key=lambda m: m.timestamp, reverse=True)[:limit]
    
    @api.field(mutable=True)
    def send_message(self, room_id: str, user_name: str, content: str) -> Message:
        """Send a message to a room."""
        message = Message(
            id=len(messages) + 1,
            room_id=room_id,
            user_name=user_name,
            content=content,
            timestamp=datetime.now()
        )
        messages.append(message)
        
        # Notify subscribers
        if room_id in message_subscribers:
            for queue in message_subscribers[room_id]:
                queue.put_nowait(message)
        
        return message
    
    @api.field
    async def message_added(self, room_id: str) -> AsyncGenerator[Message, None]:
        """Subscribe to new messages in a room."""
        if room_id not in message_subscribers:
            message_subscribers[room_id] = []
        
        queue = asyncio.Queue()
        message_subscribers[room_id].append(queue)
        
        try:
            while True:
                message = await queue.get()
                yield message
        finally:
            message_subscribers[room_id].remove(queue)
```

### Using the Subscription

```python
# In a real application, you'd use a WebSocket server like Starlette
async def chat_example():
    # Subscribe to messages
    subscription = """
        subscription {
            messageAdded(roomId: "general") {
                id
                userName
                content
                timestamp
            }
        }
    """
    
    # This would typically be handled by your WebSocket server
    async for result in api.subscribe(subscription):
        print(f"New message: {result.data}")

# Send a message (this would trigger the subscription)
mutation = """
    mutation {
        sendMessage(roomId: "general", userName: "Alice", content: "Hello everyone!") {
            id
            timestamp
        }
    }
"""
```

---

## Todo App with Mutations

A complete CRUD example showing how to handle mutations effectively.

### Todo Models

```python
from enum import Enum

class TodoStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    ARCHIVED = "archived"

@dataclass
class Todo:
    id: int
    title: str
    description: Optional[str] = None
    status: TodoStatus = TodoStatus.PENDING
    due_date: Optional[datetime] = None
    created_at: datetime = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()

# Storage
todos = []
next_id = 1

api = GraphQLAPI()
```

### CRUD Operations

```python
@api.type(is_root_type=True)
class TodoAPI:
    @api.field
    def todos(self, status: Optional[TodoStatus] = None) -> List[Todo]:
        """Get todos, optionally filtered by status."""
        if status:
            return [t for t in todos if t.status == status]
        return todos
    
    @api.field
    def todo(self, todo_id: int) -> Optional[Todo]:
        """Get a specific todo."""
        return next((t for t in todos if t.id == todo_id), None)
    
    @api.field(mutable=True)
    def create_todo(self, title: str, description: Optional[str] = None, 
                   due_date: Optional[datetime] = None) -> Todo:
        """Create a new todo."""
        global next_id
        todo = Todo(
            id=next_id,
            title=title,
            description=description,
            due_date=due_date
        )
        todos.append(todo)
        next_id += 1
        return todo
    
    @api.field(mutable=True)
    def update_todo(self, todo_id: int, title: Optional[str] = None,
                   description: Optional[str] = None, status: Optional[TodoStatus] = None,
                   due_date: Optional[datetime] = None) -> Optional[Todo]:
        """Update an existing todo."""
        todo = next((t for t in todos if t.id == todo_id), None)
        if not todo:
            return None
        
        if title is not None:
            todo.title = title
        if description is not None:
            todo.description = description
        if status is not None:
            todo.status = status
        if due_date is not None:
            todo.due_date = due_date
            
        return todo
    
    @api.field(mutable=True)
    def delete_todo(self, todo_id: int) -> bool:
        """Delete a todo."""
        global todos
        original_count = len(todos)
        todos = [t for t in todos if t.id != todo_id]
        return len(todos) < original_count
    
    @api.field(mutable=True)
    def complete_todo(self, todo_id: int) -> Optional[Todo]:
        """Mark a todo as completed."""
        return self.update_todo(todo_id, status=TodoStatus.COMPLETED)
```

### Example Usage

```python
# Create a new todo
create_mutation = """
    mutation {
        createTodo(title: "Learn GraphQL", description: "Complete the tutorial") {
            id
            title
            status
            createdAt
        }
    }
"""

# Update a todo
update_mutation = """
    mutation {
        updateTodo(todoId: 1, status: COMPLETED) {
            id
            title
            status
        }
    }
"""

# Query todos by status
query = """
    query {
        todos(status: PENDING) {
            id
            title
            description
            dueDate
        }
    }
"""
```

## Running the Examples

To run any of these examples:

1. Save the code to a Python file (e.g., `blog_example.py`)
2. Install the dependencies: `pip install graphql-api`
3. Run the script: `python blog_example.py`

For subscription examples, you'll need to integrate with an async web framework like FastAPI or Starlette to handle WebSocket connections.

## Next Steps

- Explore [Apollo Federation](./federation.html) for microservices
- Learn about [Advanced Topics](./advanced.html) like middleware and custom directives
- Check out the [API Reference](./api-reference.html) for complete documentation