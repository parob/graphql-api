# ObjectQL
Python framework for building a GraphQL execution server from Python Objects

[![coverage report](https://gitlab.com/kiwi-ninja/objectql/badges/master/coverage.svg)](https://gitlab.com/kiwi-ninja/pygql/commits/master)

[![pipeline status](https://gitlab.com/kiwi-ninja/objectql/badges/master/pipeline.svg)](https://gitlab.com/kiwi-ninja/pygql/commits/master)

## Installation
ObjectQL is a Python package, and is compatible with `Python 3` only (for now). It can be installed through `pip`.

##### Pip
```
pip install objectql
```

## Run the Unit Tests
To run the tests.
```
pip install pipenv
pipenv install --dev
pipenv run python -m pytest tests --cov=objectql
```

## Docs

The documentation is public, and is generated using Sphinx.

[ObjectQL Documentation](http://www.objectql.com)

##### Build documentation
To build a local static HTML version of the documentation.
```
pip install pipenv
pipenv install sphinx
pipenv run sphinx-build docs ./public -b html
```

## Simple Example
``` python
from objectql import ObjectQLSchemaBuilder, query

schema = ObjectQLSchemaBuilder()


class Math:

    @query
    def square_number(self, number: int) -> int:
        return number * number


schema.root = Math

gql_query = '''
    query SquareNumberFive {
        fiveSquaredIs: squareNumber(number: 5)
    }
'''

result = schema.executor().execute(gql_query)

print(result.data)
```

``` text
$ python example.py
>>> {'fiveSquaredIs': 25}
```