from core.analysis import Analyzer
from core.models import SearchPage, SnapshotData
from core.search_core import build_postings, execute_search


class IndexSnapshot:
    def __init__(self, data: SnapshotData, config, analyzer: Analyzer | None = None) -> None:
        self._data = data
        self._config = config
        self._analyzer = analyzer or Analyzer(config)

    @property
    def generation(self) -> int:
        return self._data.generation

    @property
    def data(self) -> SnapshotData:
        return self._data

    def search(self, query_spec, options, analyzer: Analyzer | None = None, query_vector=None) -> SearchPage:
        if analyzer is not None and not callable(getattr(analyzer, "analyze", None)):
            if query_vector is None:
                query_vector = analyzer
            analyzer = None
        return execute_search(
            self._data,
            self._config,
            query_spec,
            options,
            analyzer or self._analyzer,
            query_vector,
        )


def build_snapshot(data: SnapshotData, config) -> IndexSnapshot:
    analyzer = Analyzer(config)
    if not data.postings:
        build_postings(data, analyzer)
    return IndexSnapshot(data, config, analyzer)
