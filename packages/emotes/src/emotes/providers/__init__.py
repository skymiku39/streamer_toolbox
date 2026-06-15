from __future__ import annotations

from emotes.providers.bttv import BTTVProvider
from emotes.providers.ffz import FFZProvider
from emotes.providers.seventv import SevenTVProvider

ALL_PROVIDERS = (BTTVProvider, FFZProvider, SevenTVProvider)

__all__ = ["ALL_PROVIDERS", "BTTVProvider", "FFZProvider", "SevenTVProvider"]
