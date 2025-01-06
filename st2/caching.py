from os import makedirs
from os.path import join

from diskcache import Cache
from xdg import XDG_CACHE_HOME

cache_dir = join(XDG_CACHE_HOME, "st2")
makedirs(cache_dir, exist_ok=True)

# throw out least frequently used data after the cache has reached 1GB
cache = Cache(
    eviction_policy="least-frequently-used",
    size_limit=1_000_000_000,
    directory=cache_dir,
)
