"""Collection adapters."""

from fbpipe.collect.base import Collector
from fbpipe.collect.import_collector import ImportCollector
from fbpipe.collect.synthetic import SyntheticCollector

__all__ = ["Collector", "ImportCollector", "SyntheticCollector"]
