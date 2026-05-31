from contextlib import contextmanager
@contextmanager
def noop_lock(name:str):
    yield
