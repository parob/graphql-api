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

ObjectQL: A GraphQL server for Python
=====================================

**ObjectQL** is a library for creating a GraphQL server with Python.

.. image:: https://gitlab.com/kiwi-ninja/objectql/badges/master/coverage.svg
   :target: https://gitlab.com/kiwi-ninja/objectql/commits/master

.. image:: https://gitlab.com/kiwi-ninja/objectql/badges/master/pipeline.svg
    :target: https://gitlab.com/kiwi-ninja/objectql/commits/master


ObjectQL requires **Python 3.5** or newer.

-------------------

ObjectQL uses Python **classes**, **methods** and **typehints** to create the **schemas** and **resolvers** for a GraphQL engine.

With ObjectQL, the following Python class::

    schema = ObjectQLSchema()

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

Install ObjectQL::

    pip install objectql

Simple Example:

.. code-block:: python

    from objectql import ObjectQLSchema

    schema = ObjectQLSchema()


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
