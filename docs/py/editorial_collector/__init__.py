"""editorial-collector: collect Japanese newspaper editorials (free-access scope)."""

from .collector import EditorialCollector
from .config import PUBLISHERS
from .models import EditorialArchive
from .report import export_html
from .storage import JsonStorage

__version__ = "0.1.2"

__all__ = [
    "EditorialCollector",
    "EditorialArchive",
    "JsonStorage",
    "PUBLISHERS",
    "export_html",
    "__version__",
]
