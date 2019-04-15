from graphql import GraphQLError


class ObjectQLError(GraphQLError):

    def __init__(
        self,
        message,
        extensions=None,
        nodes=None,
        stack=None,
        source=None,
        positions=None,
        locations=None
    ):
        super(ObjectQLError, self).__init__(
            message=message,
            nodes=nodes,
            stack=stack,
            source=source,
            positions=positions,
            locations=locations
        )
        self.extensions = extensions
