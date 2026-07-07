"""App package — early warning suppressions live here so they take effect
BEFORE any submodule (e.g. config, hdfs_client, crawlers/base) triggers
``import requests`` (which emits the RequestsDependencyWarning at import time).

IMPORTANT: do NOT import from ``requests`` here — that would emit the warning
BEFORE the filter is in place.  Use message-based matching only.
"""

import warnings as _warnings

# Silence the urllib3/chardet mismatch warning emitted by ``requests.__init__``:
#   "urllib3 (2.x) or chardet (...) doesn't match a supported version!"
# Match by message text only — do NOT import RequestsDependencyWarning here.
_warnings.filterwarnings(
    "ignore",
    message=r".*doesn't match a supported version.*",
)

# Silence InsecureRequestWarning globally — some crawlers (e.g. FIFA)
# deliberately pass verify=False to work around TLS quirks.
# (urllib3 is safe to import here because it doesn't emit warnings on import.)
try:
    from urllib3.exceptions import InsecureRequestWarning as _IRW
    _warnings.filterwarnings("ignore", category=_IRW)
except ImportError:
    pass
