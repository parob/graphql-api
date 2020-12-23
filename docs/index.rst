.. _index:

.. highlight:: python

.. toctree::
    :hidden:

    Overview <self>
    quickstart
    installation
    schemas
    types
    execution
    remote
    models
    http
    examples
    api

GraphQL-API: A GraphQL server for Python
=====================================

**GraphQL-API** is a library for creating a GraphQL server with Python.

.. image:: https://gitlab.com/parob/graphql-api/badges/master/coverage.svg
   :target: https://gitlab.com/parob/graphql-api/commits/master

.. image:: https://gitlab.com/parob/graphql-api/badges/master/pipeline.svg
    :target: https://gitlab.com/parob/graphql-api/commits/master


GraphQL-API requires **Python 3.5** or newer.

-------------------

GraphQL-API uses Python **classes**, **methods** and **typehints** to create the **schemas** and **resolvers** for a GraphQL engine.

With GraphQL-API, the following Python class::

    schema = GraphQLAPI()

    @schema.type(root=True)
    class Calculator:

      @schema.field
      def add(self, number_one: float, number_two: float) -> float:
          return number_1 + number_2

can be automatically mapped into a GraphQL schema that would look something like::

    type Calculator {
        add(numberOne: Float!, numberTwo: Float!): Float!
    }

and like any normal GraphQL server it can be queried::

    executor = schema.executor()

    executor.execute("
        query {
            add(numberOne: 4.3, numberTwo: 7.1)
        }
    ")

    >>> {
        "add": 11.4
    }


Getting Started
---------------

Install GraphQL-API::

    pip install graphql-api

Simple Example:

.. code-block:: python

    from graphql_api import GraphQLAPI

    schema = GraphQLAPI()

    @schema.type(root=True)
    class Math:

        @schema.field
        def square_number(self, number: int) -> int:
            return number * number


    gql_query = '''
        query SquareNumberFive {
            fiveSquaredIs: squareNumber(number: 5)
        }
    '''

    result = schema.executor().execute(gql_query)

    print(result.data)


...run in terminal::

    $ python example.py
    >>> {'fiveSquaredIs': 25}
