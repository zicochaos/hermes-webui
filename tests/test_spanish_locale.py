from pathlib import Path
import re
from tests.test_issue2147_profile_concept_help import PROFILE_CONCEPT_KEYS


REPO = Path(__file__).resolve().parent.parent
PROFILE_CONCEPT_FALLBACK_KEYS = {
    *PROFILE_CONCEPT_KEYS,
    "workspace_artifact_source_session",
}


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def locale_src(locale_key: str) -> str:
    """English lives inline in static/i18n.js; every other locale is a lazy
    per-locale bundle under static/i18n/ (i18n per-locale split)."""
    if locale_key == "en":
        return read(REPO / "static" / "i18n.js")
    return read(REPO / "static" / "i18n" / f"{locale_key}.js")


def test_spanish_locale_block_exists():
    src = locale_src("es")
    assert "window.LOCALES.es = {" in src
    assert "_label: 'Español'" in src
    assert "_speech: 'es-ES'" in src


def test_spanish_locale_includes_representative_translations():
    src = locale_src("es")
    expected = [
        "settings_title: 'Configuración'",
        "login_title: 'Iniciar sesión'",
        "approval_heading: 'Se requiere aprobación'",
        "tab_tasks: 'Tareas'",
        "tab_skills: 'Habilidades'",
        "tab_memory: 'Memoria'",
    ]
    for entry in expected:
        assert entry in src


def test_spanish_locale_covers_english_keys():
    en_src = locale_src("en")
    en_seg = en_src[en_src.index("LOCALES.en = {"):]
    en_seg = en_seg[:en_seg.index("\n  };")]
    assert en_seg, "English locale block not found"
    es_seg = locale_src("es")
    assert es_seg, "Spanish locale block not found"

    key_pattern = re.compile(r"^\s{4}([a-zA-Z0-9_]+):", re.MULTILINE)
    en_keys = set(key_pattern.findall(en_seg))
    es_keys = set(key_pattern.findall(es_seg))

    missing = sorted((en_keys - es_keys) - PROFILE_CONCEPT_FALLBACK_KEYS)
    assert not missing, f"Spanish locale missing keys: {missing}"
