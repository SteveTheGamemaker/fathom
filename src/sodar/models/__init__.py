# Import all models so they register with Base.metadata
from sodar.models.base import Base  # noqa: F401
from sodar.models.release import ParsedRelease  # noqa: F401
from sodar.models.indexer import Indexer  # noqa: F401
from sodar.models.quality import QualityProfile, QualityProfileItem  # noqa: F401
from sodar.models.media import Movie, Series, Season, Episode  # noqa: F401
