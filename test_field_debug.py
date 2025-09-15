from graphql_api.api import GraphQLAPI
from graphql_api.decorators import field
from graphql_api.mapper import get_value

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

api = GraphQLAPI()
api.type(UsedType)
api.type(Root, is_root_type=True)

# Check field types
import inspect
for name, method in inspect.getmembers(Root, predicate=inspect.isfunction):
    if hasattr(method, '__wrapped__'):  # This is a decorated field
        field_type = get_value(method, api, "graphql_type")
        print(f"Field '{name}': type = '{field_type}'")