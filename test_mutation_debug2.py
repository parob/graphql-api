from graphql_api.api import GraphQLAPI
from graphql_api.decorators import field

class Person:
    def __init__(self):
        self._name = ""

    @field
    def name(self) -> str:
        return self._name

    @field(mutable=True)
    def update_name(self, name: str) -> "Person":
        self._name = name
        return self

class Root:
    @field
    def person(self) -> Person:
        return Person()

    @field(mutable=True)
    def create_person(self, name: str) -> Person:
        person = Person()
        person._name = name
        return person

api = GraphQLAPI(root_type=Root)

# Add debugging by manually building the mutation mapper
from graphql_api.mapper import GraphQLTypeMapper
from graphql_api.reduce import GraphQLSchemaReducer

# Build mutation
mutation_registry = {}
mutation_mapper = GraphQLTypeMapper(
    as_mutable=True, suffix="Mutable", registry=mutation_registry, schema=api, max_docstring_length=api.max_docstring_length,
    single_root_mode=True
)
_mutation = mutation_mapper.map(api.root_type)

print('Built mutation type:', _mutation.name)
print('Built mutation fields:', list(_mutation.fields.keys()))

# Filter the mutation
filtered_mutation = GraphQLSchemaReducer.reduce_mutation(
    mutation_mapper, _mutation, filters=api.filters
)

print('Filtered mutation fields:', list(filtered_mutation.fields.keys()))

# Check validation
is_valid = mutation_mapper.validate(filtered_mutation, evaluate=True)
print('Mutation validation result:', is_valid)

schema, _ = api.build_schema()
print('Final mutation type:', schema.mutation_type and schema.mutation_type.name)