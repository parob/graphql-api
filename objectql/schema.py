import inspect

from typing import List, Callable, Any, Type, Dict, Tuple

from graphql import (
    GraphQLSchema,
    GraphQLObjectType,
    GraphQLField,
    GraphQLString
)
from graphql.execution.base import ExecutionResult

from objectql.decorators import object_decorator_factory

from objectql.executor import ObjectQLExecutor, ObjectQLBaseExecutor
from objectql.context import ObjectQLContext
from objectql.reduce import ObjectQLSchemaReducer, ObjectQLFilter
from objectql.mapper import ObjectQLTypeMapper


class ObjectQLFieldContext:

    def __init__(self, meta, query=None):
        self.meta = meta
        self.query = query

    def __str__(self):
        query_str = ""
        if self.query:
            query_str = f', query: {query_str}' if self.query else ''
        return f"<Node meta: {self.meta}{query_str}>"


class ObjectQLRequestContext:

    def __init__(self, args, info):
        self.args = args
        self.info = info


class ObjectQLSchema(ObjectQLBaseExecutor):

    query = object_decorator_factory("query", schema=True)
    mutation = object_decorator_factory("mutation", schema=True)
    interface = object_decorator_factory("interface", schema=True)
    abstract = object_decorator_factory("abstract", schema=True)

    def __init__(
        self,
        root: Type = None,
        middleware: List[Callable[[Callable, ObjectQLContext], Any]] = None,
        filters: List[ObjectQLFilter] = None
    ):
        super().__init__()
        if middleware is None:
            middleware = []

        self.root_type = root
        self.middleware = middleware
        self.filters = filters
        self.query_mapper = None
        self.mutation_mapper = None

    def root(self, root_type):
        self.root_type = root_type
        return root_type

    def graphql_schema(self) -> Tuple[GraphQLSchema, Dict, Any]:
        schema_args = {}
        meta = {}

        root_class = self.root_type
        root_value = self.root_type

        if not inspect.isclass(root_class):
            root_class = type(root_class)

        if root_value and callable(root_value):
            root_value = root_value()

        if self.root_type:
            # Create the root query
            query_mapper = ObjectQLTypeMapper(schema=self)
            query: GraphQLObjectType = query_mapper.map(root_class)

            # Filter the root query
            filtered_query = ObjectQLSchemaReducer.reduce_query(
                query_mapper,
                query,
                filters=self.filters
            )

            if query_mapper.validate(filtered_query, evaluate=True):
                schema_args['query'] = filtered_query
                query_types = query_mapper.types()
                registry = query_mapper.registry

            else:
                query_types = set()
                registry = None

            # Create the root mutation
            mutation_mapper = ObjectQLTypeMapper(
                as_mutable=True,
                suffix="Mutable",
                registry=registry,
                schema=self
            )
            mutation: GraphQLObjectType = mutation_mapper.map(root_class)

            # Filter the root mutation
            filtered_mutation = ObjectQLSchemaReducer.reduce_mutation(
                mutation_mapper,
                mutation
            )

            if mutation_mapper.validate(filtered_mutation, evaluate=True):
                schema_args['mutation'] = filtered_mutation
                mutation_types = mutation_mapper.types()
            else:
                mutation_types = set()

            schema_args['types'] = list(query_types | mutation_types)
            meta = {**query_mapper.meta, **mutation_mapper.meta}

            self.query_mapper = query_mapper
            self.mutation_mapper = mutation_mapper

        # Create a placeholder query (every GraphQL schema must have a query)
        if 'query' not in schema_args:
            placeholder = GraphQLField(
                type=GraphQLString,
                resolver=lambda *_: ''
            )
            schema_args['query'] = GraphQLObjectType(
                name='PlaceholderQuery',
                fields={'placeholder': placeholder}
            )

        schema = GraphQLSchema(**schema_args)

        return schema, meta, root_value

    def execute(
        self,
        query,
        variables=None,
        operation_name=None
    ) -> ExecutionResult:
        return self.executor().execute(
            query=query,
            variables=variables,
            operation_name=operation_name
        )

    def executor(self) -> ObjectQLExecutor:
        schema, meta, root_value = self.graphql_schema()
        return ObjectQLExecutor(
            schema=schema,
            meta=meta,
            middleware=self.middleware,
            root=root_value
        )
