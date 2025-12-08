import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import functools

def configure_fastf1_retries():
    """
    Configure specific retry logic for FastF1 / Ergast API to handle 429s.
    We apply this globally by patching requests.Session because FastF1 manages its own sessions internally.
    """
    retry_strategy = Retry(
        total=10,  # High retry count for rate limits
        backoff_factor=1,  # 1s, 2s, 4s, 8s...
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "OPTIONS"],
        raise_on_status=False
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    
    # 1. Patch requests.Session to ensure every new session gets this adapter
    # This captures FastF1's internal session creation
    original_init = requests.Session.__init__

    @functools.wraps(original_init)
    def new_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        self.mount("https://", adapter)
        self.mount("http://", adapter)
        # Also set headers to look like a browser/legit app to perhaps reduce strictness
        self.headers.update({
            "User-Agent": "F1Hub-Analytics/1.0 (Education Project)"
        })

    requests.Session.__init__ = new_init
    
    print("✅ Configured global API retries with exponential backoff for all new sessions.")

