"""content_library.py — static content-asset inventory tests."""

import pytest

from ica.generator.content_library import (
    CONTENT_LIBRARY,
    assets_by_channel,
    assets_by_theme,
    assets_for,
    get_asset,
)
from ica.taxonomy import (
    ALL_ASSETS,
    ASSET_CHANNEL,
    ASSET_THEME,
    Channel,
    Persona,
)


def test_library_covers_every_taxonomy_asset():
    assert {asset.slug for asset in CONTENT_LIBRARY} == set(ALL_ASSETS)


def test_library_size_matches_taxonomy():
    assert len(CONTENT_LIBRARY) == len(ALL_ASSETS)


def test_channel_and_theme_match_taxonomy():
    """SSOT: slug/channel/theme are not redeclared — they mirror taxonomy."""
    for asset in CONTENT_LIBRARY:
        assert asset.channel == ASSET_CHANNEL[asset.slug], asset.slug
        assert asset.theme == ASSET_THEME[asset.slug], asset.slug


def test_every_asset_has_a_title():
    for asset in CONTENT_LIBRARY:
        assert asset.title.strip(), asset.slug


def test_target_personas_are_valid_personas():
    for asset in CONTENT_LIBRARY:
        for persona in asset.target_personas:
            assert isinstance(persona, Persona)


def test_get_asset_roundtrips_every_slug():
    for slug in ALL_ASSETS:
        assert get_asset(slug).slug == slug


@pytest.mark.parametrize("channel", list(Channel))
def test_assets_by_channel_matches_taxonomy(channel: Channel):
    got = assets_by_channel(channel)
    expected = {slug for slug in ALL_ASSETS if ASSET_CHANNEL[slug] == channel}
    assert {asset.slug for asset in got} == expected
    assert all(asset.channel == channel for asset in got)


def test_assets_for_channel_theme_cell():
    for asset in CONTENT_LIBRARY:
        if asset.theme is None:
            continue
        cell = assets_for(asset.channel, asset.theme)
        assert asset in cell
        assert all(
            other.channel == asset.channel and other.theme == asset.theme
            for other in cell
        )


def test_assets_by_theme_is_consistent():
    for asset in CONTENT_LIBRARY:
        if asset.theme is None:
            continue
        assert asset in assets_by_theme(asset.theme)
