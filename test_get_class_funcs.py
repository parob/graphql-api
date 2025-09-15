from graphql_api.api import GraphQLAPI
from graphql_api.decorators import field
from graphql_api.mapper import get_class_funcs, get_value

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

# Check what get_class_funcs returns
print("Getting class funcs for mutable=True:")
class_funcs = get_class_funcs(Root, api, mutable=True, single_root_mode=True)

for key, func in class_funcs:
    field_type = get_value(func, api, "graphql_type")
    print(f"  {key}: type = '{field_type}'")