.. _schemas:

.. highlight:: python

Building Schemas
================

    A GraphQL **schema** defines a set of **types** which completely describe the set of possible data you can query.
    When a GraphQL query comes in, it is validated and executed against that **schema**.

ObjectQL can build an entire GraphQL **schema** from Python classes.

.. figure:: images/python_to_graphql.png
    :align: center

    Each part of a Python class gets mapped to part of a GraphQL type type.

This works because the *type/fields* pattern in GraphQL is very similar to the *type/methods* pattern in Python.

In practise, a Python class needs some **additional information** to map to a GraphQL type, which we will go through in this guide.

Building a Schema
-----------------

Root Type
`````````
Any **schema** must always have a **Root type** (often called the *Query type*).
The **Root type** sits at the top level of the **schema** and acts an an entry point for all queries.

For example:

.. code-block:: python
    :emphasize-lines: 3, 9

        from objectql import ObjectQLSchema

        schema = ObjectQLSchema()

        class Human:

            @schema.query
            def name(self) -> str:
                return "Tom"

        @schema.root
        class Root:

            @schema.query
            def hello_world(self) -> str:
                return "Hello world!"

            @schema.query
            def a_person(self) -> Human:
                return Human()

    graphql_schema, meta = schema_builder.graphql_schema()


The ``.graphql_schema()`` method can be called to get the underlying ``GraphQLSchema``.
Child type types from the root (such as the ``Human`` type type) will be discovered by the ``ObjectQLSchema`` at runtime.

This works as long as all the type hints have been specified.

Root Value
``````````

Every GraphQL server has a **Root Value** at the top level. The **Root Value** is the entry type that all queries will pass through.

By default the **Root Value** is created by calling the constructor of the **Root Type** above.

A custom **Root Value** can be used by passing one in as an argument to the ``ObjectQLSchema`` constructor.

Method Decorators
-----------------

Classes will often have functionality that shouldn't exposed in the GraphQL schema.

To handle this, only methods that are labeled with specific `decorators <https://realpython.com/primer-on-python-decorators/>`_ are mapped.

There are 2 decorators available that can label methods.

    - ``@query``
    - ``@mutation``

Query
`````

The ``@query`` decorator is used to label a **method** that should be exposed as a **query** field on the GraphQL schema, for example:

.. code-block:: python
    :linenos:
    :emphasize-lines: 5

    from objectql import ObjectQLSchema

    schema = ObjectQLSchema()

    @schema.root
    class ExampleQueryDecorator:

        @schema.query
        def hello(self, name: str) -> str:
            return self.hidden_hello(name)

        def hidden_hello(self, name: str) -> str:
            return "hello " + name + "!"

In the above example (when mapped to a schema) the *hello* **method** will be exposed as a field on the ``ExampleQueryDecorator`` GraphQL type type.

In contrast, the *hidden_hello* **method** wont be exposed on the schema. Although the *hidden_hello* method could still be called from Python, for example above on **line 7** (inside the *hello* **method**).


Mutation
````````

The ``@schema.mutation`` decorator is almost identical to the ``@schema.query`` decorator, except it labels a **method** that should be exposed as a **mutation** field on the GraphQL schema.

The ``@schema.mutation`` decorator should only be used on **methods** that mutate or modify data.

|

    Its **very important** to only use the ``@schema.query`` decorator for **methods** that fetch data and the ``@schema.mutation`` decorator for
    **methods** that mutate data. The reasons why are explained in the **Schema Filtering** section below.

|

Class Decorators
----------------

There are 2 additional decorators that are used to label classes.

    - ``@schema.type_interface``
    - ``@schema.type_abstract``

Interface
`````````

The ``@schema.interface`` decorator can be used on a **class** to create a GraphQL interface type (instead of an type type).

The interface functionality closely mirrors `GraphQL interfaces <http://graphql.github.io/learn/schema/#interfaces>`_.

For example the ``@schema.interface`` decorator is being used here:

.. code-block:: python

    from objectql import ObjectQLSchema

    schema = ObjectQLSchema()

    @schema.interface
    class Animal:

        @schema.query
        def name(self) -> str:
            return "John Doe"

    class Human(Animal):

        @schema.query
        def name(self) -> str:
            return "Thomas"

        @schema.query
        def social_security_number(self) -> str:
            return "111-11-1111"

    class Dog(Animal):

        @schema.query
        def name(self, name: str) -> str:
            return "Spot"

        @schema.query
        def favourite_toy(self) -> str:
            return "Ball"

In the above example, the ``Animal`` interface is implemented by both the ``Human`` and ``Dog``, so they all share the ``name`` field.

This example would map to these types in the schema::

    interface Animal {
        name: String!
    }

    type Human implements Animal {
        socialSecurityNumber: String!
    }

    type Dog implements Animal {
        favouriteToy: String!
    }


Its also worth noting that if the ``Human`` or ``Dog`` class above didn't implement the ``name`` method,
then class inheritance would kick in and the ``name`` method on ``Animal`` would still get called.

Abstract
````````

The ``@schema.type(abstract=True)`` decorator can be used to indicate that a **class** should not be mapped by ObjectQL.

GraphQL does not support type *inheritance* (only `interfaces <http://graphql.github.io/learn/schema/#interfaces>`_)
so ``@schema.type(abstract=True)`` allows us to still use class *inheritance* in Python.

For example:

.. code-block:: python

    from objectql import ObjectQLSchema

    schema = ObjectQLSchema()

    @schema.type(abstract=True)
    class Animal:

        @schema.field
        def age(self) -> int:
            return 25

    @schema.type(abstract=True)
    class Human(Animal):

        @schema.field
        def social_security_number(self) -> str:
            return "111-11-1111"

    class Student(Human):

        @schema.field
        def college(self) -> str:
            return "Exeter"

``Animal`` and ``Human`` are marked as ``@abstract`` (they are ignored), so the above example would map to just one type in the schema::

    type Student {
        age: Int!
        socialSecurityNumber: String!
        college: String!
    }

The methods from the parent classes (``Animal`` and ``Human``) are still reflected in the schema on the ``Student`` type.

Metadata
--------

`Decorators <https://realpython.com/primer-on-python-decorators/>`_ are also used to attach **metadata** to a class or method.

The **metadata** is a dictionary that can specify *addition configuration* for the corresponding class or method, for example:

.. code-block:: python
    :emphasize-lines: 7,8,9,10,11,12

    from objectql import ObjectQLSchema

    schema = ObjectQLSchema()

    class Hello:

        @schema.field({
            "custom_dict_key": {
                "hello": "here is custom metadata",
            },
            "custom_value_key": 42
        })
        def hello(self, name: str) -> str:
            return "hey"

When resolving a query, a fields **metadata** can be accessed through the **context**.

There are some **metadata** keys that are reserved for used by ObjectQL:

- ``RESOLVE_TO_MUTABLE``
- ``RESOLVE_TO_SELF``
- ``NATIVE_MIDDLEWARE``

Schema Filtering
----------------

A GraphQL service *normally* has two separate schemas with two separate **Root types**; one for **fetching data**, and another for **updating data**.

This is because **data fetches** can be run in parallel, whereas **data updates** must always run sequentially.

ObjectQL uses just one **Root class**, and the ``@schema.query`` and ``@schema.mutation`` decorators are used to filter the fields into two **Root types**.

Here is an example to see exactly how the **Root class** gets mapped into two **Root types**:

.. code-block:: python

    from objectql import ObjectQLSchema

    schema = ObjectQLSchema()

    class User:

        @schema.field
        def name(self) -> str:
            pass

        @schema.field
        def update_name(self) -> 'User':
            pass


    class Post:

        @schema.field(mutable=True)
        def like(self) -> Post:
            pass

        @schema.field
        def message(self) -> str:
            pass

        @schema.query
        def likes(self) -> int:
            pass

        @schema.query
        def author(self) -> User:
            pass


    @schema.type(root=True)
    class Root:

        @schema.field
        def posts(self) -> List[Post]:
            pass

        @schema.field
        def post_count(self) -> int:
            pass

        @schema.field
        def me(self) -> User:
            pass


Lets walk through the main features of these classes:

- There are two models; ``User`` and ``Post``, as well as a **Root class** called ``Root``.

- The **Root class** (``Root``) has methods that return to all the *posts*, the *count of the posts* and the *current user* (the ``posts``, ``post_count`` and ``me`` methods).

- The ``Post`` class has methods that return the *author*, the *message* and the number of *likes*.

- A ``Post`` can be *liked* with the ``like`` method.

- The ``User`` class has a method to returns the users *name*.

- A ``Users`` name can be *updated* with the ``update_name`` method.


When built into a schema, these classes will map to a set of **Query** types and a set of **Mutable** types:

.. figure:: images/schema_structure.png
    :align: center
    :scale: 70%

    The ``green`` shapes are *types*, the ``blue`` shapes are **query** *fields* and the ``orange`` shapes are **mutable** *fields*

The above example as a GraphQL schema would look like this:

.. code-block::
    :linenos:

    type Root {
        posts: [Post]!
        postCount: Int!
        me: User!
    }

    type Post {
        message: String!
        likes: Int!
        author: User!
    }

    type User {
        name: String!
    }



    type RootMutable {
        posts: [PostMutable]!
        me: UserMutable!
    }

    type PostMutable {
        like: Post!
    }

    type UserMutable {
        updateName: User!
    }

These rules were followed to create the two types and filter the fields:

1. Each ``Query`` type is duplicated to create a ``Mutable`` type, which is suffixed with ``Mutable``.
2. All ``@schema.field(mutable=True)`` fields are removed from all ``Query`` types.
3. Any ``@schema.field`` fields that never lead to a ``Mutable`` type are removed from the ``Mutable`` types.

After the above rules are applied there are a few things worth noting:

- **Line 18:** Any ``@schema.field`` fields that still remain on a ``Mutable`` type will always return a ``Mutable`` type.

|

- **Line 23:** ``@schema.field(mutable=True)`` fields on a ``Mutable`` type will by default return a ``Query`` type (unless otherwise specified, see *Mutation recursion* below).

Mutation recursion
``````````````````

Middleware
----------


Compatibility
-------------


ObjectQL is actually based on the `GraphQL-core <https://github.com/graphql-python/graphql-core>`_ Python library,
which also powers another popular frontend `Graphene <https://github.com/graphql-python/graphene>`_.

For this reason ObjectQL produces a schema identical to that of Graphene.
