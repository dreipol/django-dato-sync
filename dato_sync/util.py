from typing import TypeVar, Callable, Generic

T = TypeVar('T')
R = TypeVar('R')


class Suffix(Generic[T, R]):
    def __init__(self, function: Callable[[T], R]):
        self.function = function

    def __ror__(self, other):
        return self.function(other)


def from_dato_path(path: str) -> Suffix[str, tuple[str, str]]:
    return Suffix(lambda field: (field, path))