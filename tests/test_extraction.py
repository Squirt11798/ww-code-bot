"""Tests for the generic HTML code extractor.

Fixtures mimic the shapes real sites use (tables, lists, bold tags) and include
realistic noise so we exercise the blocklist.
"""

from bot.sources.base import HtmlSource


def _extract(html: str) -> set[str]:
    return {c.code for c in HtmlSource(name="test", url="x").extract(html)}


def test_extracts_codes_from_table() -> None:
    html = """
    <h2>Active Wuthering Waves Codes</h2>
    <table>
      <tr><td><strong>WUTHERINGGIFT</strong></td><td>50 Astrite, 15000 Shell Credits</td></tr>
      <tr><td><strong>STRANGEVISITORS</strong></td><td>100 Astrite</td></tr>
      <tr><td><code>M5KJ5HV32T</code></td><td>Premium Resonance Potion</td></tr>
    </table>
    """
    assert _extract(html) == {"WUTHERINGGIFT", "STRANGEVISITORS", "M5KJ5HV32T"}


def test_extracts_codes_from_list() -> None:
    html = """
    <ul>
      <li><b>BEYONDTHEDOOR</b> – 100 Astrite, 40,000 Shell Credit</li>
      <li><b>SAYCHEESE</b> – 100 Astrite</li>
    </ul>
    """
    assert _extract(html) == {"BEYONDTHEDOOR", "SAYCHEESE"}


def test_blocklist_filters_noise() -> None:
    html = """
    <p>Redeem your ASTRITE rewards. Follow us on TWITTER and YOUTUBE.</p>
    <nav><span>SEARCH</span><span>LOGIN</span></nav>
    <table><tr><td><code>WUTHERINGGIFT</code></td></tr></table>
    """
    assert _extract(html) == {"WUTHERINGGIFT"}


def test_ignores_pure_numbers_and_short_tokens() -> None:
    html = "<li>50000 Shell Credits, code ABC (too short), 15000 credits</li>"
    # 50000 / 15000 are pure numbers; ABC is too short → nothing extracted.
    assert _extract(html) == set()


def test_dedupes_case_insensitively() -> None:
    html = "<td>WutheringGift</td><td>WUTHERINGGIFT</td>"
    assert _extract(html) == {"WUTHERINGGIFT"}


def test_codes_carry_source_link() -> None:
    src = HtmlSource(name="game8", url="https://example.com/codes")
    codes = src.extract("<td><code>WUTHERINGGIFT</code></td>")
    assert len(codes) == 1
    assert codes[0].source == "game8"
    assert codes[0].source_links == (("game8", "https://example.com/codes"),)


def test_skips_script_and_style() -> None:
    html = """
    <script>var TOKENABC = 'SECRETCODE';</script>
    <style>.SOMECLASS { color: red; }</style>
    <td><code>WUTHERINGGIFT</code></td>
    """
    assert _extract(html) == {"WUTHERINGGIFT"}
