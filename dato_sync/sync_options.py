from abc import ABC, abstractmethod


class DatoFieldPath:
    def __init__(
            self,
            django_field_name: str,
            path: str | None = None,
            is_localized: bool = False,
            is_absolute: bool = False,
    ):
        self.django_field_name = django_field_name
        self.path = path or django_field_name
        self.is_localized = is_localized
        self.is_absolute = is_absolute


class SyncOptions(ABC):
    @property
    @abstractmethod
    def dato_model_path(self) -> str:
        pass

    @property
    @abstractmethod
    def field_mappings(self) -> list[str | DatoFieldPath]:
        pass