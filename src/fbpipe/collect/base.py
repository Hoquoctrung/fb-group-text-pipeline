"""Collector adapter contract."""

from abc import ABC, abstractmethod
from collections.abc import Iterator

from fbpipe.schema import RawPost


class Collector(ABC):
    """Abstract source adapter; downstream stages only consume RawPost."""

    name: str

    @abstractmethod
    def iter_posts(self) -> Iterator[RawPost]:
        """Yield validated posts from the source."""
        raise NotImplementedError
