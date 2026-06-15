from __future__ import annotations

from emotes.providers.base import ThirdPartyEmote
from emotes.registry import _merge_third_party_emotes


def test_merge_third_party_priority() -> None:
    emotes = [
        ThirdPartyEmote(id="1", name="Pepe", image_url="https://7tv/pepe.webp", source="7tv"),
        ThirdPartyEmote(id="2", name="Pepe", image_url="https://bttv/pepe.png", source="bttv"),
    ]
    merged = _merge_third_party_emotes(emotes)
    assert merged["Pepe"] == "https://bttv/pepe.png"
