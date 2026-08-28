"""Structural RED/GREEN tests for the per-locale i18n bundle split.

static/i18n.js used to inline all 15 locale objects (~1.7MB eager-parsed on
every boot). After the split it ships ONLY English plus the t()/setLocale
runtime; every other locale is a static/i18n/<code>.js bundle loaded lazily:
index.html document.writes the saved locale before the deferred scripts, and
setLocale() fetches missing bundles on demand.

These tests pin the split's file layout. Behavioral translation pins live in
the existing tests/test_*_locale.py files.
"""
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

I18N_JS = (REPO / "static" / "i18n.js").read_text(encoding="utf-8")
INDEX_HTML = (REPO / "static" / "index.html").read_text(encoding="utf-8")
SW_JS = (REPO / "static" / "sw.js").read_text(encoding="utf-8")
BUNDLE_DIR = REPO / "static" / "i18n"
SHARED_JS = (REPO / "static" / "i18n_shared.js").read_text(encoding="utf-8")
PANELS_JS = (REPO / "static" / "panels.js").read_text(encoding="utf-8")

# Every non-English locale that must ship as its own lazy bundle.
EXPECTED_BUNDLE_CODES = (
    "it", "ja", "ru", "es", "de", "zh", "zh-Hant", "pt",
    "ko", "fr", "cs", "tr", "pl", "vi",
)


# Canonical codes pinned by static/i18n.js KNOWN_LOCALES: English + every bundle.
KNOWN_LOCALES = ("en",) + EXPECTED_BUNDLE_CODES
GUARD_LINE = "window.LOCALES = window.LOCALES || {};"


def _assignment(code: str) -> str:
    """The registration line a bundle for `code` must contain."""
    if re.fullmatch(r"[A-Za-z][A-Za-z0-9]*", code):
        return f"window.LOCALES.{code} = {{"
    return f"window.LOCALES['{code}'] = {{"


def test_every_expected_locale_has_a_bundle_file():
    for code in EXPECTED_BUNDLE_CODES:
        path = BUNDLE_DIR / f"{code}.js"
        assert path.is_file(), f"missing lazy locale bundle: static/i18n/{code}.js"


def test_bundles_use_the_guard_and_registration_shape():
    for code in EXPECTED_BUNDLE_CODES:
        src = (BUNDLE_DIR / f"{code}.js").read_text(encoding="utf-8")
        lines = src.splitlines()
        assert lines[1] == GUARD_LINE, (
            f"static/i18n/{code}.js line 2 must be the {GUARD_LINE!r} guard"
        )
        assert _assignment(code) in src, (
            f"static/i18n/{code}.js must register the locale via {_assignment(code)!r}"
        )


def test_bundle_directory_holds_exactly_the_expected_bundles():
    files = sorted(p.name for p in BUNDLE_DIR.glob("*.js"))
    assert files == sorted(f"{code}.js" for code in EXPECTED_BUNDLE_CODES), (
        f"unexpected bundle set: {files}"
    )


def test_i18n_js_has_no_inline_top_level_locale_entries():
    """After the split only the `LOCALES.en = {` assignment may remain in
    static/i18n.js — no `  <code>: {` top-level entries (2-space indent)."""
    leftovers = re.findall(r"^  ('[^']+'|[A-Za-z][A-Za-z0-9-]*)\s*:\s*\{", I18N_JS, re.M)
    assert leftovers == [], (
        f"static/i18n.js still inlines locale blocks: {leftovers} — they belong "
        f"in static/i18n/<code>.js"
    )
    assert re.search(r"^LOCALES\.en = \{", I18N_JS, re.M), (
        "static/i18n.js must keep English inline via `LOCALES.en = {`"
    )


def test_i18n_js_keeps_en_fallback_and_lazy_loader_runtime():
    # t() must still fall back to English unconditionally.
    assert "?? LOCALES.en[key]" in I18N_JS, (
        "t() fallback contract broken: `?? LOCALES.en[key]` missing from static/i18n.js"
    )
    # The on-demand bundle loader must exist alongside setLocale.
    assert "function _loadLocaleBundle(" in I18N_JS
    assert "static/i18n/' + encodeURIComponent(code) + '.js'" in I18N_JS


def test_index_html_bootstraps_the_saved_locale_synchronously():
    assert "static/i18n/' + m + '.js?v=__WEBUI_VERSION__" in INDEX_HTML, (
        "index.html must document.write the saved locale's bundle before the "
        "deferred scripts"
    )
    # The bootstrap must read the same localStorage key setLocale() persists.
    assert "localStorage.getItem('hermes-lang')" in INDEX_HTML
    # Canonical locale codes are not all lowercase — resolveLocale() maps
    # zh-TW/zh-HK/zh-MO/zh-hant to 'zh-Hant'. A case-sensitive pattern would
    # silently drop those users back to the async path (English flash).
    assert "/^[a-z][a-z0-9-]*$/i.test(m)" in INDEX_HTML


def test_sw_js_precaches_i18n_runtime_but_not_locale_bundles():
    assert "'./static/i18n.js' + VQ" in SW_JS, (
        "sw.js must keep precaching static/i18n.js (English + runtime)"
    )
    for code in EXPECTED_BUNDLE_CODES:
        assert f"static/i18n/{code}.js" not in SW_JS, (
            f"sw.js must not precache the lazy bundle static/i18n/{code}.js — "
            f"first fetch populates the runtime cache"
        )


def test_i18n_shared_defines_every_helper_bundles_reference():
    referenced = set()
    for bundle in BUNDLE_DIR.glob("*.js"):
        referenced |= set(re.findall(r"_i18n[A-Za-z0-9]*", bundle.read_text(encoding="utf-8")))
    defined = set(re.findall(r"^function (_i18n[A-Za-z0-9]*)", SHARED_JS, re.M))
    assert referenced, "expected the locale bundles to reference shared helpers"
    missing = sorted(referenced - defined)
    assert missing == [], (
        f"bundles reference helpers missing from static/i18n_shared.js: {missing}"
    )


def test_i18n_js_no_longer_defines_the_moved_helpers():
    """Single source: _i18n* helper definitions live only in i18n_shared.js."""
    assert "function _i18n" not in I18N_JS, (
        "static/i18n.js still defines _i18n* helpers — they moved to "
        "static/i18n_shared.js and must not be duplicated"
    )


def test_index_html_loads_shared_helpers_before_the_locale_bootstrap():
    assert "static/i18n_shared.js?v=__WEBUI_VERSION__" in INDEX_HTML, (
        "index.html must load static/i18n_shared.js"
    )
    shared = INDEX_HTML.index("static/i18n_shared.js?v=__WEBUI_VERSION__")
    bootstrap = INDEX_HTML.index("static/i18n/' + m + '.js?v=__WEBUI_VERSION__")
    assert shared < bootstrap, (
        "index.html must load static/i18n_shared.js parser-blocking BEFORE the "
        "locale bootstrap inline script"
    )


def test_known_locales_pins_exactly_the_canonical_codes():
    match = re.search(r"^const KNOWN_LOCALES = \[([^\]]*)\];", I18N_JS, re.M)
    assert match, "static/i18n.js must define KNOWN_LOCALES"
    assert re.findall(r"'([^']+)'", match.group(1)) == list(KNOWN_LOCALES), (
        "KNOWN_LOCALES drifted from the canonical locale set"
    )


def test_sw_js_precaches_the_shared_helpers():
    assert "'./static/i18n_shared.js' + VQ" in SW_JS, (
        "sw.js must precache static/i18n_shared.js alongside static/i18n.js"
    )


def test_language_dropdown_enumerates_known_locales_not_loaded_bundles():
    assert "typeof KNOWN_LOCALES!=='undefined'" in PANELS_JS, (
        "panels.js language dropdown must guard on KNOWN_LOCALES"
    )
    assert "for(const [code,bundle] of Object.entries(LOCALES))" not in PANELS_JS, (
        "language dropdown must not enumerate only-loaded LOCALES — with just "
        "'en' loaded, English users could never switch language"
    )
