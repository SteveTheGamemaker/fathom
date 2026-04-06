# Import all models so they register with Base.metadata
from fathom.models.base import Base  # noqa: F401
from fathom.models.release import ParsedRelease  # noqa: F401
from fathom.models.indexer import Indexer  # noqa: F401
from fathom.models.quality import QualityProfile, QualityProfileItem  # noqa: F401
from fathom.models.media import Movie, Series, Season, Episode  # noqa: F401
from fathom.models.download import DownloadClient, DownloadRecord  # noqa: F401
