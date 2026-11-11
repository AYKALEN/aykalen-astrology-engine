"""Standalone astrological calculations. No clients, reports or AI services."""

__version__ = "0.5.2"


def calculate(request):
    """Compute a JSON-serializable natal/annual data packet (see README)."""
    from .api import calculate as run
    return run(request)
