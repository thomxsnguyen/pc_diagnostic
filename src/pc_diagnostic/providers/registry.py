from pc_diagnostic.providers.base import Provider
from pc_diagnostic.providers.stub import StubProvider


def register_providers() -> list[Provider]:
    """Register and return available providers for the current system."""
    all_providers: list[Provider] = [
        StubProvider(),
    ]
    return [p for p in all_providers if p.available()]
