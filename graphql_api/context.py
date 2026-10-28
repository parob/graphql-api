class GraphQLFieldContext:
    def __init__(self, meta, query=None):
        self.meta = meta
        self.query = query

    def __str__(self):
        query_str = ""
        if self.query:
            query_str = f", query: {query_str}" if self.query else ""
        return f"<Node meta: {self.meta}{query_str}>"


class GraphQLRequestContext:
    def __init__(self, args, info):
        self.args = args
        self.info = info


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
