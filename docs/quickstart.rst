.. _quickstart:

.. highlight:: python

Quickstart Guide
================

This quickstart guide is a brief overview of some of GraphQL-API's features, just to get you started.

For a full breakdown of each feature please refer to the **individual docs** (in the table of contents), or for specific implementation details check out the **API docs**.

What is GraphQLAPI
----------------

GraphQLAPI is a framework to help build a GraphQL server with Python. Before getting started it's recommended that you have a good understanding of `GraphQL <https://graphql.org/learn/>`_.

GraphQLAPI can build a **GraphQL schema** directly from **Python classes**.

.. figure:: images/python_to_graphql.png
    :align: center

    Each part of a Python class gets mapped to part of a GraphQL type type.

Installation
------------

GraphQLAPI requires **Python 3.5** or newer.

Install GraphQL-API first::

    pip install graphql-api


Creating a basic Schema
-----------------------

A **Schema** is used to describe a **GraphQL API**. GraphQL-API uses Python classes to create this **Schema**.

To get started we will create a very simple Python class:

.. code-block:: python
    :name: hello-py

    class HelloGraphQLAPI:

        def hello(self, name):
            return "hello " + name + "!"

``HelloGraphQLAPI`` is a typical Python class, and obviously we could use this just like any regular class:

.. code-block:: python

    hello_instance = HelloGraphQLAPI()

    print(hello_instance.hello("rob"))

    >>> hello rob!

But we need to slightly change ``HelloGraphQLAPI`` to make it suitable for creating a **Schema**:

.. code-block:: python
    :caption: hello.py
    :name: hello-py
    :emphasize-lines: 1,3,5,8

    from graphql_api import GraphQLAPI

    api = GraphQLAPI()

    @api.type(is_root_type=True)
    class HelloGraphQLAPI:

        @api.field
        def hello(self, name: str) -> str:
            return "hello " + name + "!"

What was changed?:

- An ``GraphQLAPI`` type was created.

- The ``@schema.field`` `decorator <https://realpython.com/primer-on-python-decorators/>`_ was imported and added. This labels the ``hello`` method as queryable via GraphQL.

- `Typehints <https://mypy.readthedocs.io/en/latest/cheat_sheet_py3.html>`_ were added to the ``hello`` method arguments and return type. This tells GraphQL-API what types it should expect.

|

.. code-block:: python
    :emphasize-lines: 12

    from graphql_api import GraphQLAPI

    api = GraphQLAPI()

    @api.type(is_root_type=True)
    class HelloGraphQLAPI:

        @api.field
        def hello(self, name: str) -> str:
            return "hello " + name + "!"

    executor = schema.executor()

|
Now we can run a GraphQL query on the ``GraphQLExecutor``:

.. code-block:: python
    :emphasize-lines: 14, 15

    from graphql_api import GraphQLAPI

    api = GraphQLAPI()

    @api.type(is_root_type=True)
    class HelloGraphQLAPI:

        @api.field
        def hello(self, name: str) -> str:
            return "hello " + name + "!"

    executor = schema.executor()

    test_query = '{ hello(name: "rob") }'
    print(executor.execute(test_query))

|
Executing ``hello.py`` in Python results in::

    $ python hello.py
    >>> { "hello": "hello rob!" }



So to recap:

- Python classes are mapped directly to GraphQL types.

- Any instance method on a Python class that is labeled with a ``@schema.type`` decorator is mapped to a field on the **Schema**.

- The `typehints <https://mypy.readthedocs.io/en/latest/cheat_sheet_py3.html>`_ on methods are mapped to field arguments and return types in the **Schema**.

- A Python class gets mapped to the **Root type** of a **Schema**.

- The **Schema** is then used to create a ``GraphQLExecutor``.


Types
-----

Type Mapping
````````````

GraphQL-API maps Python types directly to the equivalent GraphQL types.

This means you **must** specify all the type hints for any methods that are marked with the ``@schema.type`` decorator. If a type hint is not specified then that argument will be ignored.

Here are *some* of the types that GraphQL-API can map:

+-------------------+--------------------+
| Python Type       | GraphQL Type       |
+===================+====================+
| int               | Int                |
+-------------------+--------------------+
| float             | Float              |
+-------------------+--------------------+
| str               | String             |
+-------------------+--------------------+
| bool              | Boolean            |
+-------------------+--------------------+
| Class             | Object             |
+-------------------+--------------------+
| Enum              | Enum               |
+-------------------+--------------------+
| UUID              | UUID               |
+-------------------+--------------------+
| datetime          | DateTime           |
+-------------------+--------------------+
| NoneType          | null               |
+-------------------+--------------------+
| dict, list        | JSON               |
+-------------------+--------------------+

Type names
``````````

Python and GraphQL are slightly different with their naming conventions.


- Python uses *snake_case* for method names, eg ``this_is_a_method_name``

- GraphQL uses *camelCase* for field names, eg ``thisIsAFieldName``


Because of these different naming conventions; when a class or enum is mapped to a GraphQL type - all the type names get converted to *camelCase*.

For example a method named ``add_user`` is converted to ``addUser``.


Queries and Mutations
`````````````````````

GraphQL **Queries** and **Mutations** are separate types. This is am important distinction because queries can be run in parallel, whereas mutations must always run sequentially.

    GraphQLAPI uses a single Python class to build both the **Query** and **Mutation** GraphQL types, the fields are separated out when the schema is generated.

For example a single class (with both queryable and mutable fields)::

    from graphql_api import GraphQLAPI

    api = GraphQLAPI()

    @api.type(is_root_type=True)
    class Example:

        @api.field
        def example_query_field() -> str:
            return "query complete"

        @api.field(mutable=True)
        def example_mutable_field() -> str:
            # do something with the database
            return "mutation complete"

Will get mapped to two types in the **Schema**::

    type Example {
        exampleQueryField: str!
    }

    type ExampleMutable {
        exampleMutableField: str!
    }



In order to avoid any naming conflicts, any mutable types get the **Mutable** suffix added to their name (for example see **ExampleMutable** above).


Type Modifiers
``````````````

**Modifiers** are used in GraphQL to indicate *Non-Null* type or a *List* of a certain type.

In GraphQL-API this is done using `typehints <https://mypy.readthedocs.io/en/latest/cheat_sheet_py3.html>`_, for example:

.. code-block:: python
   :emphasize-lines: 6,10

    from graphql_api import GraphQLAPI

    api = GraphQLAPI()

    class ExampleModifiers:

    @api.field
    def example_list() -> List[str]:
        return ["hello", "world"]

    @api.field(mutable=True)
    def example_nullable() -> Optional[str]:
        return None

Is mapped to:

.. code-block:: python
   :emphasize-lines: 3,5

    type ExampleModifiers {

        exampleList: [String]!

        exampleNullable: String

    }

+--------------------+---------------------+-------------------------+
| Python Return Type | GraphQL Return Type | Meaning                 |
+====================+=====================+=========================+
| List[str]          | [String]!           | Non-null List of Strings|
+--------------------+---------------------+-------------------------+
| Optional[str]      | String              | Nullable String         |
+--------------------+---------------------+-------------------------+


Object Type
-----------

In GraphQL a field on an **Object** can either return a **Scalar** value, or another **Object**.

Similarly with Python, a method can either return a **Scalar** value, or another **Object**.

Here is an example::

    # note: the methods are not implemented here

    from graphql_api import GraphQLAPI

    api = GraphQLAPI()

    @api.type(is_root_type=True)
    class Folder:

        @api.field
        def name() -> str:
            pass

        @api.field
        def children(self) -> List[Folder]:
            pass


Notice that the ``children`` method returns a list of ``Folders``.

A GraphQL query for the **Schema** from this class might look like this::

    {
        name
        children {
            name
            children {
                name
            }
        }
    }


By combining multiple classes together, this nesting pattern can be used to build up more complex **Schemas**.

For example here is a set of Python classes that will produce a **Schema** for a comments system::

    # note: the methods are not implemented here

    from graphql_api import GraphQLAPI

    api = GraphQLAPI()

    class User:

        @api.field
        def id() -> int:
            pass

        @api.field
        def name() -> str:
            pass

    class Comment:

        @api.field
        def message() -> str:
            pass

        @api.field
        def author() -> User:
            pass

    @api.type(is_root_type=True)
    class MainController:

        @api.field
        def users() -> List[User]:
            pass

        @api.field
        def comments() -> List[Comments]:
            pass

The ``Controller`` suffix (seen above in the ``MainController`` class), is a good *optional* convention to adopt. It can be used to identify that a class manages other classes/models.


HTTP
----

Once you've built your **Schema**, you'll probably want to make it accessible over the internet through a webserver.

The GraphQL-API library *does not* have a built in webserver, but the **Schema** that GraphQL-API produces is identical to the **Schema** used in other Python GraphQL frameworks.
This means that we can use existing HTTP GraphQL tools with the **Schema** to create a web server.

Here are some examples with some popular web frameworks.


Werkzeug
````````

One of the simplest ways to serve a **Schema** is with ``Werkzeug`` and `werkzeug-graphql <https://gitlab.com/kiwi-ninja/werkzeug-graphql>`_::

    from graphql_http_server import GraphQLHTTPServer

    from graphql_api import GraphQLAPI

    api = GraphQLAPI()

    @api.type(is_root_type=True)
    class HelloWorld:

        @api.field
        def hello(self) -> str:
            return "Hello World!"

    server = GraphQLHTTPServer.from_api(api=api)

    if __name__ == "__main__":
        server.run()

Flask
`````

If you are using ``Flask`` you could use `flask-graphql <https://github.com/graphql-python/flask-graphql>`_::

    from flask import Flask
    from flask_graphql import GraphQLView

    from graphql_api import GraphQLAPI

    app = Flask(__name__)

    api = GraphQLAPI()

    @api.type(is_root_type=True)
    class HelloWorld:

        @api.field
        def hello(self) -> str:
            return "Hello World!"

    graphql_schema, _, _ = api.graphql_schema()
    root_value = HelloWorld()

    app.add_url_rule('/graphql', view_func=GraphQLView.as_view('graphql', schema=graphql_schema, root_value=root_value, graphiql=True))

    if __name__ == "__main__":
        app.run()
