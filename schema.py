from graphene import Field, Int, ObjectType, String

from graphene_federation import LATEST_VERSION, build_schema, key


@key("id")
class User(ObjectType):
    id = Int(required=True)
    username = String(required=True)

    def __resolve_reference(self, info, **kwargs):
        """
        Here we resolve the reference of the user entity referenced by its `id` field.
        """
        return User(id=self.id, email=f"user_{self.id}@mail.com")


class Query(ObjectType):
    me = Field(User)


schema = build_schema(query=Query, federation_version=LATEST_VERSION)

print_schema = str(schema)

print(print_schema)