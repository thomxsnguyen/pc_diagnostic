from pc_diagnostic.providers.base import Provider
from pc_diagnostic.providers.lhm_provider import LhmProvider
from pc_diagnostic.providers.psutil_provider import PsutilProvider
from pc_diagnostic.providers.smc_provider import SmcProvider
from pc_diagnostic.providers.stub import StubProvider


def register_providers() -> list[Provider]:
    """Register and return available providers for the current system."""
    all_providers: list[Provider] = [
        StubProvider(),
        PsutilProvider(),
        LhmProvider(),
        SmcProvider(),
    ]
    return [p for p in all_providers if p.available()]
