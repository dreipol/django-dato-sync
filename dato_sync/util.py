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
    return Suffix(lambda field: (field, localized, path or field))

position_in_parent = Suffix(lambda field: (field, False, _order_tag))

def to_camel_case(snake_str):
    return "".join(x.capitalize() for x in snake_str.lower().split("_"))

def to_lower_camel_case(snake_str):
    # We capitalize the first letter of each component except the first one
    # with the 'capitalize' method and join them together.
    camel_string = to_camel_case(snake_str)
    return snake_str[0].lower() + camel_string[1:]