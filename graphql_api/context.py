class GraphQLContext:

    def __init__(self, schema=None, meta=None, executor=None):

        if not meta:
            meta = {}

        # Server specific
        self.schema = schema
        self.meta = meta
        self.executor = executor

        # Request specific
        self.request = None

        # Request field specific
        self.field = None

        # resolve arg data
        self.resolve_args = {}

    def __copy__(self):
        context_copy = type(self)()
        context_copy.__dict__.update(self.__dict__)
        return context_copy
