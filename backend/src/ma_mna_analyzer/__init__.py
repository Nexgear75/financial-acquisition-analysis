"""European public-company M&A opportunity analyzer."""

from .models import AnalyzeRequest, AnalyzeResponse

__all__ = ["AnalyzeRequest", "AnalyzeResponse", "MnaAnalyzer"]


def __getattr__(name: str):
    if name == "MnaAnalyzer":
        from .orchestrator import MnaAnalyzer

        return MnaAnalyzer
    raise AttributeError(name)
