from abc import ABC, abstractmethod

from pc_diagnostic.models import MetricReading


class Provider(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """Return the unique identifier name of the provider."""
        pass

    @abstractmethod
    def available(self) -> bool:
        """Check if this provider is available on the current system."""
        pass

    @abstractmethod
    def read(self) -> list[MetricReading]:
        """Produce the metric readings in the normalized schema."""
        pass
