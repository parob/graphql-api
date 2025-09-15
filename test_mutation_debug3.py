from graphql_api.api import GraphQLAPI
from graphql_api.decorators import field

class UsedType:
    def __init__(self):
        self._value = "used"

    @field
    def value(self) -> str:
        return self._value

class Root:
    @field
    def used_object(self) -> UsedType:
        """Query field that returns UsedType"""
        return UsedType()

    @field(mutable=True)
    def update_used(self, value: str) -> UsedType:
        """Only mutable operation - only UsedType should get a mutable version"""
        obj = UsedType()
        obj._value = value
        return obj

# Test the tracking
api = GraphQLAPI()
api.type(UsedType)
api.type(Root, is_root_type=True)

# Build mutation mapper manually to see what's tracked
from graphql_api.mapper import GraphQLTypeMapper

mutation_registry = {}
mutation_mapper = GraphQLTypeMapper(
    as_mutable=True, suffix="Mutable", registry=mutation_registry, schema=api, 
    max_docstring_length=api.max_docstring_length, single_root_mode=True
)

print("Before mapping root:")
print("Types needing mutable variants:", mutation_mapper.types_needing_mutable_variants)

_mutation = mutation_mapper.map(api.root_type)

print("After mapping root:")
print("Types needing mutable variants:", mutation_mapper.types_needing_mutable_variants)
print("Mutation type fields:", list(_mutation.fields.keys()) if hasattr(_mutation, 'fields') else 'No fields')

schema, _ = api.build_schema()
print('Final mutation type:', schema.mutation_type and schema.mutation_type.name)