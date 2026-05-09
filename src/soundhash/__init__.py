"""soundhash — deterministic musical hash."""

__version__ = "0.1.0"
SPEC_VERSION = "v1"

from .decode import hash_to_spec  # noqa: F401
from .spec import SongSpec  # noqa: F401
