"""Tests for the regex fallback parser."""

from fathom.llm.fallback import try_parse


def test_movie_bluray_1080p():
    r = try_parse("The.Matrix.1999.REMASTERED.1080p.BluRay.x265-RARBG")
    assert r is not None
    assert r.title == "The Matrix"
    assert r.year == 1999
    assert r.season is None
    assert r.episode is None
    assert r.quality == "bluray-1080p"
    assert r.codec == "h265"
    assert r.source == "bluray"
    assert r.resolution == "1080p"
    assert r.release_group == "RARBG"
    assert r.is_proper is False
    assert r.is_repack is False


def test_tv_episode_webdl():
    r = try_parse("Breaking.Bad.S05E16.Felina.720p.WEB-DL.DD5.1.H.264-BS")
    assert r is not None
    assert r.title == "Breaking Bad"
    assert r.season == 5
    assert r.episode == 16
    assert r.quality == "webdl-720p"
    assert r.codec == "h264"
    assert r.source == "webdl"
    assert r.resolution == "720p"
    assert r.release_group == "BS"


def test_tv_season_pack():
    r = try_parse("The.Office.US.S03.720p.BluRay.x264-DEMAND")
    assert r is not None
    assert r.title == "The Office US"
    assert r.season == 3
    assert r.episode is None
    assert r.quality == "bluray-720p"
    assert r.release_group == "DEMAND"


def test_movie_2160p_remux():
    r = try_parse("Dune.Part.Two.2024.2160p.REMUX.BluRay.x265-TrueHD")
    assert r is not None
    assert r.title == "Dune Part Two"
    assert r.year == 2024
    assert r.quality == "remux-2160p"
    assert r.resolution == "2160p"


def test_proper_repack():
    r = try_parse("Succession.S04E10.PROPER.REPACK.720p.HDTV.x264-FLEET")
    assert r is not None
    assert r.is_proper is True
    assert r.is_repack is True
    assert r.quality == "hdtv-720p"
    assert r.season == 4
    assert r.episode == 10


def test_webrip():
    r = try_parse("Spider-Man.No.Way.Home.2021.1080p.WEBRip.x265-RARBG")
    assert r is not None
    assert r.title == "Spider-Man No Way Home"
    assert r.year == 2021
    assert r.quality == "webrip-1080p"
    assert r.source == "webrip"


def test_no_quality_returns_none():
    r = try_parse("some random text with no quality info")
    assert r is None


def test_dvd():
    r = try_parse("The.Shawshank.Redemption.1994.DVDRip.x264-HANDJOB")
    assert r is not None
    assert r.quality == "dvd"
    assert r.source == "dvd"
    assert r.title == "The Shawshank Redemption"
    assert r.year == 1994


def test_4k_webdl():
    r = try_parse("Oppenheimer.2023.2160p.WEB-DL.DDP5.1.Atmos.H.265-FLUX")
    assert r is not None
    assert r.quality == "webdl-2160p"
    assert r.resolution == "2160p"
    assert r.codec == "h265"
    assert r.release_group == "FLUX"
