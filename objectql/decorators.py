from objectql.schema import decorator


def query(meta=None):
    return decorator(None, meta, _type="query")


def mutation(meta=None):
    return decorator(None, meta, _type="mutation")


def object(meta=None):
    return decorator(None, meta, _type="object")


def interface(meta=None):
    return decorator(None, meta, _type="interface")


def abstract(meta=None):
    return decorator(None, meta, _type="abstract")
