from abc import ABC, abstractmethod


class SyncOptions(ABC):
    @property
    @abstractmethod
    def dato_model_path(self) -> str:
        pass

    @property
    @abstractmethod
    def field_mappings(self) -> list[str | tuple[str, bool, str]]:
        pass