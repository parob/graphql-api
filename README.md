# GraphQL-API
Framework for building a GraphQL API with Python

[![coverage report](https://gitlab.com/parob/graphql-api/badges/master/coverage.svg)](https://gitlab.com/parob/graphql-api/commits/master)

[![pipeline status](https://gitlab.com/parob/graphql-api/badges/master/pipeline.svg)](https://gitlab.com/parob/graphql-api/commits/master)

## Installation
GraphQL-API is a Python package, and is compatible with `Python 3` only (for now). It can be installed through `pip`.

##### Pip
```
pip install graphql-api
```

## Run the Unit Tests
To run the tests.
```
pip install pipenv
pipenv install --dev
pipenv run python -m pytest tests --cov=graphql_api
```

## Docs

The documentation is public, and is generated using Sphinx.

[GraphQL-API Documentation](http://parob.gitlab.io/graphql-api/)

##### Build documentation
To build a local static HTML version of the documentation.
```
pip install pipenv
pipenv install sphinx
pipenv run sphinx-build docs ./public -b html
```

## Simple Example
``` python
from graphql_api import GraphQLAPI

schema = GraphQLAPI()


@schema.type(root=True)
class Math:

    @schema.query
    def square_number(self, number: int) -> int:
        return number * number


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