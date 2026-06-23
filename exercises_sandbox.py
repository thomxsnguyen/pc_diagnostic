import random
from abc import ABC, abstractmethod
from pc_diagnostic.models import MetricReading, MetricUnit
from pc_diagnostic.providers.base import Provider

# ==============================================================================
# EXERCISE 1 & 2: Implement the contract & Feel the polymorphism
# ==============================================================================


class RandomProvider(Provider):
    @property
    def name(self) -> str:
        return "random"

    def available(self) -> bool:
        return True

    # TODO: For Exercise 1, comment this method out to see the TypeError
    def read(self) -> list[MetricReading]:
        return [
            MetricReading(
                metric="random.value",
                value=random.random(),
                unit=MetricUnit.PERCENT,
                source=self.name,
            )
        ]



class ConstantProvider(Provider):
    @property
    def name(self) -> str:
        return "constant"

    def available(self) -> bool:
        return True

    def read(self) -> list[MetricReading]:
        return [
            MetricReading(
                metric="constant.value",
                value=1.0,
                unit=MetricUnit.PERCENT,
                source=self.name,
            )
        ]


# ==============================================================================
# EXERCISE 3: Break the property
# ==============================================================================


class BrokenPropertyProvider(Provider):
    # Without @property decorator
    def name(self) -> str:  # type: ignore[override]
        return "broken"

    def available(self) -> bool:
        return True

    def read(self) -> list[MetricReading]:
        return []


# ==============================================================================
# EXERCISE 4: Add to the contract (Uncomment this ABC to test Exercise 4)
# ==============================================================================

# class ExtendedProvider(ABC):
#     @property
#     @abstractmethod
#     def name(self) -> str:
#         pass
#
#     @abstractmethod
#     def available(self) -> bool:
#         pass
#
#     @abstractmethod
#     def read(self) -> list[MetricReading]:
#         pass
#
#     @abstractmethod
#     def health(self) -> str:
#         """A new contract method that every subclass must implement."""
#         pass


def run_exercises() -> None:
    print("--- Running Exercise 2: Polymorphism ---")
    providers: list[Provider] = [RandomProvider(), ConstantProvider()]
    for p in providers:
        if p.available():
            print(f"Provider '{p.name}' read: {p.read()}")

    print("\n--- Running Exercise 3: Break the property ---")
    broken = BrokenPropertyProvider()
    try:
        # Accessing .name as a property (as defined in base interface)
        print(f"Accessing .name: {broken.name}")
    except Exception as e:
        print(f"Error caught accessing property name: {type(e).__name__}: {e}")

    try:
        # Calling name as a method
        print(f"Calling name(): {broken.name()}")
    except Exception as e:
        print(f"Error caught calling name(): {type(e).__name__}: {e}")


if __name__ == "__main__":
    run_exercises()
