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
    
    # Add a root-level mutable field
    @field(mutable=True)
    def create_person(self, name: str) -> Person:
        person = Person()
        person._name = name
        return person

api = GraphQLAPI(root_type=Root)
schema, _ = api.build_schema()

print('Query type:', schema.query_type and schema.query_type.name)
print('Mutation type:', schema.mutation_type and schema.mutation_type.name)
print('Query fields:', list(schema.query_type.fields.keys()) if schema.query_type else 'None')
print('Mutation fields:', list(schema.mutation_type.fields.keys()) if schema.mutation_type else 'None')

if schema.mutation_type:
    print('Has mutation type - mutation should work')
else:
    print('No mutation type - this is the problem')