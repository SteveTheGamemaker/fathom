"""Systematic comparison of regex fallback vs LLM parsing.

Each test case has a release name and expected fields. We run both parsers
and report accuracy for each field and overall.

Usage:
    python -m tests.test_regex_vs_llm
"""

from __future__ import annotations

import asyncio
import sys
import time
from dataclasses import asdict

from fathom.llm.fallback import try_parse
from fathom.llm.parser import _llm_batch_parse

# (release_name, expected_dict)
# Only include fields you want to check — missing keys are skipped.
CASES: list[tuple[str, dict]] = [
    # === YEAR-IN-TITLE ===
    ("2001.A.Space.Odyssey.1968.2160p.UHD.BluRay.x265-B0MBARDiERS",
     {"title": "2001 A Space Odyssey", "year": 1968, "quality": "bluray-2160p", "codec": "h265"}),
    ("1917.2019.1080p.BluRay.x264-SPARKS",
     {"title": "1917", "year": 2019, "quality": "bluray-1080p", "codec": "h264"}),
    ("300.2006.1080p.BluRay.x264-REFiNED",
     {"title": "300", "year": 2006, "quality": "bluray-1080p"}),
    ("1984.1984.720p.BluRay.x264-AMIABLE",
     {"title": "1984", "year": 1984, "quality": "bluray-720p"}),
    ("2012.2009.1080p.BluRay.x264-MACHD",
     {"title": "2012", "year": 2009, "quality": "bluray-1080p"}),
    ("1408.2007.Directors.Cut.1080p.BluRay.x264-SECTOR7",
     {"title": "1408", "year": 2007, "quality": "bluray-1080p"}),

    # === MULTI-EPISODE ===
    ("Severance.S02E01E02.1080p.ATVP.WEB-DL.DDP5.1.H.264-NTb",
     {"title": "Severance", "season": 2, "episode": 1, "quality": "webdl-1080p"}),
    ("The.Simpsons.S35E01E02.720p.HULU.WEB-DL.DDP5.1.H.264-NTb",
     {"title": "The Simpsons", "season": 35, "episode": 1, "quality": "webdl-720p"}),
    ("Game.of.Thrones.S08E01-E03.1080p.BluRay.x264-DEMAND",
     {"title": "Game of Thrones", "season": 8, "episode": 1, "quality": "bluray-1080p"}),

    # === DAILY SHOWS ===
    ("The.Late.Show.with.Stephen.Colbert.2025.04.03.1080p.WEB.H.264-JEBAITED",
     {"title": "The Late Show with Stephen Colbert", "year": 2025, "quality": "webdl-1080p"}),
    ("Jimmy.Kimmel.Live.2024.11.15.1080p.WEB.H.264-JEBAITED",
     {"title": "Jimmy Kimmel Live", "year": 2024, "quality": "webdl-1080p"}),
    ("Last.Week.Tonight.with.John.Oliver.2024.03.10.720p.WEB.H.264-JEBAITED",
     {"title": "Last Week Tonight with John Oliver", "year": 2024, "quality": "webdl-720p"}),

    # === ANIME / ABSOLUTE NUMBERING ===
    ("One.Piece.1122.1080p.WEB.H.264-VARYG",
     {"title": "One Piece", "episode": 1122, "quality": "webdl-1080p"}),
    ("[SubsPlease] Dandadan - 12 (1080p) [A1B2C3D4].mkv",
     {"title": "Dandadan", "episode": 12}),
    ("[Erai-raws] Jujutsu Kaisen - 47 [1080p][Multiple Subtitle].mkv",
     {"title": "Jujutsu Kaisen", "episode": 47}),
    ("Naruto.Shippuden.489.720p.WEB.x264-ANiURL",
     {"title": "Naruto Shippuden", "episode": 489, "quality": "webdl-720p"}),
    ("[SubsPlease] One Piece - 1100 (720p) [DEADBEEF].mkv",
     {"title": "One Piece", "episode": 1100}),
    ("Dragon.Ball.Super.131.720p.WEB.x264-ANiURL",
     {"title": "Dragon Ball Super", "episode": 131, "quality": "webdl-720p"}),
    ("[Judas] Vinland Saga S2 - 24.mkv",
     {"title": "Vinland Saga", "season": 2, "episode": 24}),

    # === REMUX ===
    ("The Holdovers 2023 1080p BluRay REMUX AVC DTS-HD MA 5 1-FGT",
     {"title": "The Holdovers", "year": 2023, "quality": "remux-1080p", "source": "remux"}),
    ("Oppenheimer.2023.2160p.UHD.BluRay.REMUX.HDR.HEVC.Atmos-TRiToN",
     {"title": "Oppenheimer", "year": 2023, "quality": "remux-2160p", "source": "remux"}),
    ("Dune.Part.Two.2024.2160p.REMUX.BluRay.x265-TrueHD",
     {"title": "Dune Part Two", "year": 2024, "quality": "remux-2160p", "source": "remux"}),
    ("The.Batman.2022.1080p.BluRay.REMUX.AVC.DTS-HD.MA.7.1-FGT",
     {"title": "The Batman", "year": 2022, "quality": "remux-1080p", "source": "remux"}),

    # === SPECIAL CHARACTERS / UNICODE ===
    ("Léon.The.Professional.1994.REMASTERED.2160p.UHD.BluRay.x265-SURCODE",
     {"title": "Léon The Professional", "year": 1994, "quality": "bluray-2160p"}),
    ("Amélie.2001.1080p.BluRay.x264-AMIABLE",
     {"title": "Amélie", "year": 2001, "quality": "bluray-1080p"}),
    ("Crouching.Tiger.Hidden.Dragon.臥虎藏龍.2000.1080p.BluRay.x264",
     {"title": "Crouching Tiger Hidden Dragon", "year": 2000, "quality": "bluray-1080p"}),
    ("Papá.o.Mamá.2015.720p.BluRay.x264-USURY",
     {"title": "Papá o Mamá", "year": 2015, "quality": "bluray-720p"}),

    # === SEASON PACKS ===
    ("Squid.Game.S02.COMPLETE.1080p.NF.WEB-DL.DDP5.1.H.264-FLUX",
     {"title": "Squid Game", "season": 2, "episode": None, "quality": "webdl-1080p"}),
    ("Chernobyl.2019.S01E01-E05.COMPLETE.MINI.SERIES.1080p.BluRay.x264-ROVERS",
     {"title": "Chernobyl", "year": 2019, "season": 1, "episode": None, "quality": "bluray-1080p"}),
    ("Breaking.Bad.S01-S05.COMPLETE.1080p.BluRay.x264-MIXED",
     {"title": "Breaking Bad", "season": None, "episode": None, "quality": "bluray-1080p"}),
    ("The.Office.US.S03.720p.BluRay.x264-DEMAND",
     {"title": "The Office US", "season": 3, "episode": None, "quality": "bluray-720p"}),

    # === PROPER / REPACK ===
    ("Succession.S04E10.PROPER.REPACK.720p.HDTV.x264-FLEET",
     {"title": "Succession", "season": 4, "episode": 10, "is_proper": True, "is_repack": True}),
    ("The.Bear.S02E01.PROPER.1080p.HULU.WEB-DL.DDP5.1.H.264-NTb",
     {"title": "The Bear", "season": 2, "episode": 1, "is_proper": True, "is_repack": False}),
    ("House.of.the.Dragon.S01E07.REPACK.2160p.MAX.WEB-DL.DDP5.1.HDR.DoVi.H.265-NTb",
     {"title": "House of the Dragon", "season": 1, "episode": 7, "is_repack": True, "quality": "webdl-2160p"}),

    # === LONG / COMPLEX TITLES ===
    ("Mission.Impossible.Dead.Reckoning.Part.One.2023.2160p.WEB-DL.DDP5.1.Atmos.DV.HDR.H.265-FLUX",
     {"title": "Mission Impossible Dead Reckoning Part One", "year": 2023, "quality": "webdl-2160p"}),
    ("Everything.Everywhere.All.at.Once.2022.1080p.BluRay.x264-SCARE",
     {"title": "Everything Everywhere All at Once", "year": 2022, "quality": "bluray-1080p"}),
    ("Eternal.Sunshine.of.the.Spotless.Mind.2004.1080p.BluRay.x264-AMIABLE",
     {"title": "Eternal Sunshine of the Spotless Mind", "year": 2004, "quality": "bluray-1080p"}),
    ("The.Lord.of.the.Rings.The.Return.of.the.King.2003.EXTENDED.2160p.UHD.BluRay.x265-BOREDOR",
     {"title": "The Lord of the Rings The Return of the King", "year": 2003, "quality": "bluray-2160p"}),
    ("Spider-Man.Across.the.Spider-Verse.2023.1080p.WEB-DL.DDP5.1.Atmos.H.264-CMRG",
     {"title": "Spider-Man Across the Spider-Verse", "year": 2023, "quality": "webdl-1080p"}),

    # === NO YEAR (movies that omit it) ===
    ("Gladiator.II.2024.1080p.WEB-DL.DDP5.1.H.264-FLUX",
     {"title": "Gladiator II", "year": 2024, "quality": "webdl-1080p"}),
    ("Deadpool.and.Wolverine.2024.2160p.WEB-DL.DDP5.1.Atmos.DV.H.265-FLUX",
     {"title": "Deadpool and Wolverine", "year": 2024, "quality": "webdl-2160p"}),

    # === WEBRIP vs WEBDL distinction ===
    ("Spider-Man.No.Way.Home.2021.1080p.WEBRip.x265-RARBG",
     {"title": "Spider-Man No Way Home", "year": 2021, "quality": "webrip-1080p", "source": "webrip"}),
    ("The.Penguin.S01E05.1080p.WEB-DL.DDP5.1.H.264-NTb",
     {"title": "The Penguin", "season": 1, "episode": 5, "quality": "webdl-1080p", "source": "webdl"}),

    # === HDTV ===
    ("Jeopardy.2024.09.16.720p.HDTV.x264-NTb",
     {"title": "Jeopardy", "year": 2024, "quality": "hdtv-720p", "source": "hdtv"}),
    ("Wheel.of.Fortune.2024.01.08.720p.HDTV.x264-CROOKS",
     {"title": "Wheel of Fortune", "year": 2024, "quality": "hdtv-720p"}),

    # === DVD ===
    ("The.Shawshank.Redemption.1994.DVDRip.x264-HANDJOB",
     {"title": "The Shawshank Redemption", "year": 1994, "quality": "dvd", "source": "dvd"}),
    ("Schindlers.List.1993.DVDRip.x264-FRAGMENT",
     {"title": "Schindlers List", "year": 1993, "quality": "dvd"}),

    # === AV1 CODEC ===
    ("Furiosa.2024.2160p.WEB-DL.AV1.DDP5.1.Atmos-FLUX",
     {"title": "Furiosa", "year": 2024, "quality": "webdl-2160p", "codec": "av1"}),
    ("The.Brutalist.2024.1080p.WEB-DL.AV1.DDP5.1-CMRG",
     {"title": "The Brutalist", "year": 2024, "quality": "webdl-1080p", "codec": "av1"}),

    # === UNUSUAL GROUP NAMES / BRACKETS ===
    ("Alien.Romulus.2024.2160p.WEB-DL.DDP5.1.H.265-FLUX[rartv]",
     {"title": "Alien Romulus", "year": 2024, "group": "FLUX"}),
    ("The.Wild.Robot.2024.1080p.WEB-DL.H.264.AAC-YTS.MX",
     {"title": "The Wild Robot", "year": 2024, "quality": "webdl-1080p"}),
    ("Conclave.2024.1080p.WEB-DL.x264 [YTS.MX]",
     {"title": "Conclave", "year": 2024, "quality": "webdl-1080p"}),

    # === SPACES INSTEAD OF DOTS ===
    ("The Substance 2024 1080p WEB-DL DDP5 1 H 264-FLUX",
     {"title": "The Substance", "year": 2024, "quality": "webdl-1080p"}),
    ("Wicked 2024 2160p WEB-DL DDP5 1 Atmos H 265-FLUX",
     {"title": "Wicked", "year": 2024, "quality": "webdl-2160p"}),

    # === UNDERSCORES ===
    ("The_Matrix_1999_1080p_BluRay_x265-RARBG",
     {"title": "The Matrix", "year": 1999, "quality": "bluray-1080p", "codec": "h265"}),

    # === MULTI-SEASON EPISODES ===
    ("Fargo.S05E01.1080p.HULU.WEB-DL.DDP5.1.H.264-NTb",
     {"title": "Fargo", "season": 5, "episode": 1, "quality": "webdl-1080p"}),
    ("True.Detective.S04E06.Night.Country.Part.6.1080p.MAX.WEB-DL.DDP5.1.Atmos.H.264-FLUX",
     {"title": "True Detective", "season": 4, "episode": 6, "quality": "webdl-1080p"}),

    # === EPISODE TITLE IN NAME ===
    ("Breaking.Bad.S05E16.Felina.720p.WEB-DL.DD5.1.H.264-BS",
     {"title": "Breaking Bad", "season": 5, "episode": 16, "quality": "webdl-720p"}),
    ("The.Sopranos.S06E21.Made.in.America.1080p.BluRay.x264-DEMAND",
     {"title": "The Sopranos", "season": 6, "episode": 21, "quality": "bluray-1080p"}),

    # === 10BIT ===
    ("Your.Name.2016.1080p.BluRay.x265.10bit-RARBG",
     {"title": "Your Name", "year": 2016, "quality": "bluray-1080p", "codec": "h265"}),
    ("Weathering.with.You.2019.2160p.WEB-DL.x265.10bit.HDR-NAISU",
     {"title": "Weathering with You", "year": 2019, "quality": "webdl-2160p", "codec": "h265"}),

    # === FOREIGN LANGUAGE TITLES ===
    ("La.La.Land.2016.1080p.BluRay.x264-SPARKS",
     {"title": "La La Land", "year": 2016, "quality": "bluray-1080p"}),
    ("Das.Boot.1981.Directors.Cut.1080p.BluRay.x264-AMIABLE",
     {"title": "Das Boot", "year": 1981, "quality": "bluray-1080p"}),
    ("Trois.Couleurs.Bleu.1993.1080p.BluRay.x264-USURY",
     {"title": "Trois Couleurs Bleu", "year": 1993, "quality": "bluray-1080p"}),
    ("Cidade.de.Deus.2002.720p.BluRay.x264-AMIABLE",
     {"title": "Cidade de Deus", "year": 2002, "quality": "bluray-720p"}),
    ("El.Laberinto.del.Fauno.2006.1080p.BluRay.x264-AMIABLE",
     {"title": "El Laberinto del Fauno", "year": 2006, "quality": "bluray-1080p"}),

    # === HYBRID / DOUBLE SOURCE ===
    ("Interstellar.2014.IMAX.HYBRID.2160p.UHD.BluRay.x265-B0MBARDiERS",
     {"title": "Interstellar", "year": 2014, "quality": "bluray-2160p"}),
    ("Blade.Runner.2049.2017.HYBRID.1080p.BluRay.REMUX.AVC-SURCODE",
     {"title": "Blade Runner 2049", "year": 2017, "quality": "remux-1080p", "source": "remux"}),

    # === MINI-SERIES / SPECIALS ===
    ("Band.of.Brothers.S01E01-E10.COMPLETE.1080p.BluRay.x264-MIXED",
     {"title": "Band of Brothers", "season": 1, "episode": None, "quality": "bluray-1080p"}),
    ("Planet.Earth.III.S01.COMPLETE.2160p.iP.WEB-DL.DDP5.1.H.265-NTb",
     {"title": "Planet Earth III", "season": 1, "episode": None, "quality": "webdl-2160p"}),

    # === CONFUSING PATTERNS ===
    ("Se7en.1995.REMASTERED.1080p.BluRay.x264-AMIABLE",
     {"title": "Se7en", "year": 1995, "quality": "bluray-1080p"}),
    ("Thr3e.2006.720p.BluRay.x264-PSYCHD",
     {"title": "Thr3e", "year": 2006, "quality": "bluray-720p"}),
    ("District.9.2009.1080p.BluRay.x264-REFiNED",
     {"title": "District 9", "year": 2009, "quality": "bluray-1080p"}),
    ("Apollo.13.1995.1080p.BluRay.x264-AMIABLE",
     {"title": "Apollo 13", "year": 1995, "quality": "bluray-1080p"}),
    ("Catch.Me.If.You.Can.2002.1080p.BluRay.x264-SPARKS",
     {"title": "Catch Me If You Can", "year": 2002, "quality": "bluray-1080p"}),
    ("The.X-Files.S01E01.1080p.BluRay.x264-DEMAND",
     {"title": "The X-Files", "season": 1, "episode": 1, "quality": "bluray-1080p"}),

    # === DOLBY VISION / HDR TAGS ===
    ("Dune.2021.2160p.WEB-DL.DDP5.1.Atmos.DV.HDR.H.265-FLUX",
     {"title": "Dune", "year": 2021, "quality": "webdl-2160p", "codec": "h265"}),
    ("No.Time.to.Die.2021.2160p.UHD.BluRay.x265.HDR.DV-B0MBARDiERS",
     {"title": "No Time to Die", "year": 2021, "quality": "bluray-2160p"}),

    # === SEASON+EPISODE WITH TITLE ===
    ("Peaky.Blinders.S06E06.Lock.and.Key.1080p.iP.WEB-DL.DDP5.1.H.264-TOMMY",
     {"title": "Peaky Blinders", "season": 6, "episode": 6, "quality": "webdl-1080p"}),
    ("Stranger.Things.S04E09.The.Piggyback.2160p.NF.WEB-DL.DDP5.1.Atmos.DV.H.265-FLUX",
     {"title": "Stranger Things", "season": 4, "episode": 9, "quality": "webdl-2160p"}),

    # === NUMBERED SEQUELS ===
    ("John.Wick.Chapter.4.2023.2160p.WEB-DL.DDP5.1.Atmos.H.265-FLUX",
     {"title": "John Wick Chapter 4", "year": 2023, "quality": "webdl-2160p"}),
    ("Scream.VI.2023.1080p.WEB-DL.DDP5.1.Atmos.H.264-CMRG",
     {"title": "Scream VI", "year": 2023, "quality": "webdl-1080p"}),
    ("Fast.and.Furious.6.2013.EXTENDED.1080p.BluRay.x264-SPARKS",
     {"title": "Fast and Furious 6", "year": 2013, "quality": "bluray-1080p"}),
    ("Saw.X.2023.1080p.WEB-DL.DDP5.1.H.264-FLUX",
     {"title": "Saw X", "year": 2023, "quality": "webdl-1080p"}),
    ("Rocky.IV.1985.1080p.BluRay.x264-AMIABLE",
     {"title": "Rocky IV", "year": 1985, "quality": "bluray-1080p"}),

    # === RESOLUTION EDGE CASES ===
    ("Nosferatu.2024.PROPER.2160p.AMZN.WEB-DL.DDP5.1.DV.H.265-FLUX",
     {"title": "Nosferatu", "year": 2024, "quality": "webdl-2160p", "is_proper": True}),
    ("A.Quiet.Place.Day.One.2024.480p.WEB-DL.x264-CMRG",
     {"title": "A Quiet Place Day One", "year": 2024, "quality": "webdl-480p"}),

    # === TV WITH YEAR (show disambiguation) ===
    ("Charmed.2018.S03E05.1080p.WEB-DL.DDP5.1.H.264-NTb",
     {"title": "Charmed", "year": 2018, "season": 3, "episode": 5, "quality": "webdl-1080p"}),
    ("Battlestar.Galactica.2003.S04E20.1080p.BluRay.x264-DEMAND",
     {"title": "Battlestar Galactica", "year": 2003, "season": 4, "episode": 20}),

    # === COMPLETE SERIES ===
    ("Mr.Robot.S01-S04.COMPLETE.1080p.BluRay.x264-MIXED",
     {"title": "Mr Robot", "season": None, "episode": None, "quality": "bluray-1080p"}),
    ("The.Wire.COMPLETE.SERIES.1080p.BluRay.x264-DEMAND",
     {"title": "The Wire", "season": None, "episode": None, "quality": "bluray-1080p"}),

    # === REALLY SHORT TITLES ===
    ("Up.2009.1080p.BluRay.x264-AMIABLE",
     {"title": "Up", "year": 2009, "quality": "bluray-1080p"}),
    ("It.2017.1080p.BluRay.x264-SPARKS",
     {"title": "It", "year": 2017, "quality": "bluray-1080p"}),
    ("Us.2019.2160p.UHD.BluRay.x265-TERMiNAL",
     {"title": "Us", "year": 2019, "quality": "bluray-2160p"}),
    ("Her.2013.1080p.BluRay.x264-SPARKS",
     {"title": "Her", "year": 2013, "quality": "bluray-1080p"}),
    ("IO.2019.1080p.NF.WEB-DL.DDP5.1.x264-NTG",
     {"title": "IO", "year": 2019, "quality": "webdl-1080p"}),
    ("Pi.1998.1080p.BluRay.x264-AMIABLE",
     {"title": "Pi", "year": 1998, "quality": "bluray-1080p"}),

    # === MIXED SEPARATORS ===
    ("The-Matrix-1999-1080p-BluRay-x265-RARBG",
     {"title": "The Matrix", "year": 1999, "quality": "bluray-1080p"}),
    ("Top Gun Maverick (2022) [1080p] [WEB-DL] [5.1] [YTS.MX]",
     {"title": "Top Gun Maverick", "year": 2022, "quality": "webdl-1080p"}),
    ("Barbie (2023) [2160p] [WEB-DL] [x265] [HEVC] [10bit] [HDR] [5.1] [YTS.MX]",
     {"title": "Barbie", "year": 2023, "quality": "webdl-2160p", "codec": "h265"}),
]

assert len(CASES) == 100, f"Expected 100 cases, got {len(CASES)}"

FIELDS = ["title", "year", "season", "episode", "quality", "codec", "source",
           "release_group", "is_proper", "is_repack"]


def normalize(val):
    """Normalize for comparison."""
    if val is None:
        return None
    if isinstance(val, str):
        # Normalize unicode, case, and punctuation for title comparison
        return val.lower().strip()
    return val


def score_parser(name: str, parsed: dict | None, expected: dict) -> dict:
    """Return {field: True/False} for each expected field."""
    results = {}
    if parsed is None:
        for f in expected:
            results[f] = False
        return results
    for field, exp_val in expected.items():
        # Handle alias: "group" -> "release_group"
        lookup = "release_group" if field == "group" else field
        got = parsed.get(lookup)
        results[field] = normalize(got) == normalize(exp_val)
    return results


def regex_parse(name: str) -> dict | None:
    r = try_parse(name)
    if r is None:
        return None
    d = asdict(r)
    d["raw_title"] = name
    return d


async def main():
    print(f"Running {len(CASES)} test cases...\n")

    # --- Regex ---
    regex_results = {}
    for name, _ in CASES:
        regex_results[name] = regex_parse(name)

    # --- LLM (batch) ---
    batch_size = 30
    all_names = [name for name, _ in CASES]
    llm_results = {}
    print("Calling LLM...", end=" ", flush=True)
    t0 = time.perf_counter()
    for i in range(0, len(all_names), batch_size):
        batch = all_names[i:i + batch_size]
        results = await _llm_batch_parse(batch)
        for r in results:
            llm_results[r["raw_title"]] = r
    llm_time = time.perf_counter() - t0
    print(f"done in {llm_time:.1f}s\n")

    # --- Score ---
    regex_field_correct = {f: 0 for f in FIELDS}
    regex_field_total = {f: 0 for f in FIELDS}
    llm_field_correct = {f: 0 for f in FIELDS}
    llm_field_total = {f: 0 for f in FIELDS}

    regex_case_perfect = 0
    llm_case_perfect = 0
    regex_total_correct = 0
    llm_total_correct = 0
    total_checks = 0

    mismatches = []

    for name, expected in CASES:
        r_scores = score_parser(name, regex_results.get(name), expected)
        l_scores = score_parser(name, llm_results.get(name), expected)

        r_all_correct = all(r_scores.values())
        l_all_correct = all(l_scores.values())
        if r_all_correct:
            regex_case_perfect += 1
        if l_all_correct:
            llm_case_perfect += 1

        for field in r_scores:
            f = "release_group" if field == "group" else field
            regex_field_total[f] += 1
            llm_field_total[f] += 1
            total_checks += 1
            if r_scores[field]:
                regex_field_correct[f] += 1
                regex_total_correct += 1
            if l_scores[field]:
                llm_field_correct[f] += 1
                llm_total_correct += 1

        # Log cases where regex failed but LLM succeeded (or vice versa)
        if not r_all_correct or not l_all_correct:
            entry = {"name": name, "expected": expected}
            rp = regex_results.get(name)
            lp = llm_results.get(name)
            entry["regex"] = {f: rp.get("release_group" if f == "group" else f)
                              for f in expected} if rp else "FAILED"
            entry["llm"] = {f: lp.get("release_group" if f == "group" else f)
                            for f in expected} if lp else "FAILED"
            entry["regex_ok"] = r_all_correct
            entry["llm_ok"] = l_all_correct
            mismatches.append(entry)

    # --- Report ---
    print("=" * 70)
    print(f"{'FIELD':<20} {'REGEX':>12} {'LLM':>12}")
    print("-" * 70)
    for f in FIELDS:
        if regex_field_total[f] == 0:
            continue
        r_pct = regex_field_correct[f] / regex_field_total[f] * 100
        l_pct = llm_field_correct[f] / llm_field_total[f] * 100
        r_str = f"{regex_field_correct[f]}/{regex_field_total[f]} ({r_pct:.0f}%)"
        l_str = f"{llm_field_correct[f]}/{llm_field_total[f]} ({l_pct:.0f}%)"
        winner = ""
        if l_pct > r_pct:
            winner = " <-- LLM"
        elif r_pct > l_pct:
            winner = " <-- Regex"
        print(f"  {f:<18} {r_str:>16} {l_str:>16}{winner}")

    print("-" * 70)
    r_overall = regex_total_correct / total_checks * 100
    l_overall = llm_total_correct / total_checks * 100
    print(f"  {'FIELD ACCURACY':<18} {r_overall:>15.1f}% {l_overall:>15.1f}%")
    print(f"  {'PERFECT CASES':<18} {regex_case_perfect:>11}/{len(CASES)} {llm_case_perfect:>11}/{len(CASES)}")
    print(f"  {'LLM TIME':<18} {'':>16} {llm_time:>14.1f}s")
    print("=" * 70)

    # --- Show mismatches ---
    only_llm = [m for m in mismatches if m["llm_ok"] and not m["regex_ok"]]
    only_regex = [m for m in mismatches if m["regex_ok"] and not m["llm_ok"]]
    both_fail = [m for m in mismatches if not m["regex_ok"] and not m["llm_ok"]]

    if only_llm:
        print(f"\nLLM correct, Regex wrong ({len(only_llm)} cases):")
        for m in only_llm:
            print(f"  {m['name']}")
            print(f"    expected: {m['expected']}")
            print(f"    regex:    {m['regex']}")
            print()

    if only_regex:
        print(f"\nRegex correct, LLM wrong ({len(only_regex)} cases):")
        for m in only_regex:
            print(f"  {m['name']}")
            print(f"    expected: {m['expected']}")
            print(f"    llm:      {m['llm']}")
            print()

    if both_fail:
        print(f"\nBoth wrong ({len(both_fail)} cases):")
        for m in both_fail:
            print(f"  {m['name']}")
            print(f"    expected: {m['expected']}")
            print(f"    regex:    {m['regex']}")
            print(f"    llm:      {m['llm']}")
            print()


if __name__ == "__main__":
    asyncio.run(main())
