from typing import TypeVar, Callable, Generic

T = TypeVar('T')
R = TypeVar('R')

_order_tag = '#order#'


class Suffix(Generic[T, R]):
    def __init__(self, function: Callable[[T], R]):
        self.function = function

    def __ror__(self, other):
        return self.function(other)


def from_dato_path(path: str | None = None, localized: bool = False) -> Suffix[str, tuple[str, bool, str]]:
    return Suffix(lambda field: (field, localized, path))

position_in_parent = Suffix(lambda field: (field, False, _order_tag))

