from graphql import GraphQLError as GraphQLError_


class GraphQLError(GraphQLError_):

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
        super(GraphQLError, self).__init__(
            message=message,
            nodes=nodes,
            stack=stack,
            source=source,
            positions=positions,
            locations=locations
        )
        self.extensions = extensions
