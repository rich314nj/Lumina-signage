"""YouTube and Vimeo URL parsing.

These parsers are mirrored in templates/player.html. They have drifted apart
before — when changing either, change both.
"""
import pytest

import app as lumina

VIDEO_ID = "dQw4w9WgXcQ"


@pytest.mark.parametrize("url", [
    f"https://www.youtube.com/watch?v={VIDEO_ID}",
    f"https://youtube.com/watch?v={VIDEO_ID}",
    f"https://m.youtube.com/watch?v={VIDEO_ID}",
    f"https://music.youtube.com/watch?v={VIDEO_ID}",
    f"https://youtu.be/{VIDEO_ID}",
    f"https://www.youtube.com/embed/{VIDEO_ID}",
    f"https://www.youtube.com/shorts/{VIDEO_ID}",
    f"https://www.youtube.com/live/{VIDEO_ID}",
    f"https://www.youtube.com/v/{VIDEO_ID}",
])
def test_youtube_id_extracted_from_supported_forms(url):
    assert lumina.extract_youtube_id(url) == VIDEO_ID


def test_youtube_id_survives_extra_query_parameters():
    url = f"https://www.youtube.com/watch?list=PL123&v={VIDEO_ID}&t=30s"
    assert lumina.extract_youtube_id(url) == VIDEO_ID


def test_youtube_id_extracted_from_bare_text():
    # Falls back to regex parsing when the value is not a well-formed URL.
    assert lumina.extract_youtube_id(f"youtu.be/{VIDEO_ID}") == VIDEO_ID


@pytest.mark.parametrize("url", [
    "https://www.youtube.com/watch?v=tooshort",
    "https://www.youtube.com/watch",
    "https://example.com/watch?v=" + VIDEO_ID,   # wrong host
    "https://vimeo.com/123456789",
    "not a url at all",
    "",
    None,
    12345,
])
def test_youtube_id_rejects_unsupported_input(url):
    assert lumina.extract_youtube_id(url) is None


@pytest.mark.parametrize("url,expected", [
    ("https://vimeo.com/123456789", "123456789"),
    ("https://www.vimeo.com/123456789", "123456789"),
    ("https://player.vimeo.com/video/123456789", "123456789"),
    ("https://vimeo.com/channels/staffpicks/123456789", "123456789"),
    ("https://vimeo.com/groups/shortfilms/videos/123456789", "123456789"),
])
def test_vimeo_id_extracted_from_supported_forms(url, expected):
    assert lumina.extract_vimeo_id(url) == expected


@pytest.mark.parametrize("url", [
    "https://example.com/123456789",   # wrong host
    "https://vimeo.com/notanumber",
    "",
    None,
    12345,
])
def test_vimeo_id_rejects_unsupported_input(url):
    assert lumina.extract_vimeo_id(url) is None


# ── Asset type detection depends on both parsers ──────────────────────────────

@pytest.mark.parametrize("value,expected", [
    (f"https://youtu.be/{VIDEO_ID}", "youtube"),
    (f"https://www.youtube.com/shorts/{VIDEO_ID}", "youtube"),
    ("https://vimeo.com/123456789", "vimeo"),
    ("https://example.com/some/page", "url"),
    ("holiday.jpg", "image"),
    ("promo.MP4", "video"),
    ("menu.pdf", "pdf"),
    ("mystery.xyz", "url"),
])
def test_asset_type_detection(value, expected):
    assert lumina.get_asset_type(value) == expected
