from typing import Type, TypeVar, Callable

from django.db import models

from dato_sync.sync_options import SyncOptions


_OptionsTypeT = TypeVar("_OptionsTypeT", bound=type[SyncOptions])

def fetch_from_dato(model_class: Type[models.Model]) -> Callable[[_OptionsTypeT], _OptionsTypeT]:
    """
    Populate the model with objects managed in the dato CMS.
    """
    def wrapper(opts_class: _OptionsTypeT) -> _OptionsTypeT:
        if not issubclass(opts_class, SyncOptions):
            raise ValueError("Wrapped class must subclass SyncOptions.")

        return opts_class

    return wrapper
