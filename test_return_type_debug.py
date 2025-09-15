from graphql_api.api import GraphQLAPI
from graphql_api.decorators import field
import typing

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

# Check the type hints
type_hints = typing.get_type_hints(Root.update_used)
print("Type hints for update_used:", type_hints)
print("Return type:", type_hints.get('return'))
print("Return type type:", type(type_hints.get('return')))