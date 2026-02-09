from typing import TypeVar, Callable, Generic

from dato_sync.sync_options import DatoFieldPath

T = TypeVar('T')
R = TypeVar('R')

_order_tag = '#order#'
_flattened_order_tag = '#flattened_order#'


class Suffix(Generic[T, R]):
    def __init__(self, function: Callable[[T], R]):
        self.function = function

    def __ror__(self, other):
        return self.function(other)


def from_dato_path(path: str | None = None, localized: bool = False, absolute: bool = False) -> Suffix[str, DatoFieldPath]:
    return Suffix(lambda field: DatoFieldPath(field, path, localized, absolute))

position_in_parent = Suffix(lambda field: DatoFieldPath(django_field_name=field, path=_order_tag))
flattened_position = Suffix(lambda field: DatoFieldPath(django_field_name=field, path=_flattened_order_tag))

def to_camel_case(snake_str):
    if snake_str.startswith('_'):
        return snake_str
    camel_string = "".join(x[0].upper() + x[1:] for x in snake_str.split("_"))
    return snake_str[0].lower() + camel_string[1:]