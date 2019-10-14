from graphql import GraphQLError


class ObjectQLError(GraphQLError):

    def __init__(
        self,
        message,
        nodes=None,
        source=None,
        positions=None,
        path=None,
        original_error=None,
        extensions=None
    ):

        super(ObjectQLError, self).__init__(
            message=message,
            nodes=nodes,
            source=source,
            positions=positions,
            path=path,
            original_error=original_error,
            extensions=extensions
        )
        self.extensions = extensions
