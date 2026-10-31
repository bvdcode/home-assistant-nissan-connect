"""Check complete translations and their loading by Home Assistant."""

import json
from pathlib import Path
from string import Formatter

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers.translation import async_get_translations

from custom_components.mynissan.const import DOMAIN

INTEGRATION = Path(__file__).resolve().parents[1] / "custom_components" / DOMAIN
TRANSLATIONS = sorted((INTEGRATION / "translations").glob("*.json"))
LANGUAGES = {"cs", "da", "de", "en", "es", "fr", "it", "nl", "pl", "pt-BR", "ru", "sv", "zh-Hans"}


def _flatten(node: object, prefix: str = "") -> dict[str, str]:
    if isinstance(node, str):
        return {prefix: node}
    assert isinstance(node, dict), prefix
    result: dict[str, str] = {}
    for key, value in node.items():
        result.update(_flatten(value, f"{prefix}.{key}" if prefix else key))
    return result


def _load(path: Path) -> dict[str, str]:
    return _flatten(json.loads(path.read_text(encoding="utf-8")))


def _placeholders(text: str) -> set[str]:
    return {name for _, name, _, _ in Formatter().parse(text) if name is not None}


def test_languages_and_english_source() -> None:
    """Package all supported languages with an identical English source."""
    assert {path.stem for path in TRANSLATIONS} == LANGUAGES
    assert _load(INTEGRATION / "strings.json") == _load(INTEGRATION / "translations/en.json")


@pytest.mark.parametrize("path", TRANSLATIONS, ids=lambda path: path.stem)
def test_complete_translation(path: Path) -> None:
    """Translate every string while preserving all formatting placeholders."""
    source = _load(INTEGRATION / "strings.json")
    translated = _load(path)
    assert translated.keys() == source.keys()
    for key, text in translated.items():
        assert text.strip(), key
        assert _placeholders(text) == _placeholders(source[key]), key


@pytest.mark.parametrize("language", sorted(LANGUAGES))
async def test_home_assistant_loads_entity_names(hass: HomeAssistant, language: str) -> None:
    """Home Assistant resolves packaged names in every supported language."""
    translated = await async_get_translations(hass, language, "entity", {DOMAIN})
    source = _load(INTEGRATION / "translations" / f"{language}.json")
    assert (
        translated[f"component.{DOMAIN}.entity.sensor.odometer.name"]
        == source["entity.sensor.odometer.name"]
    )
    assert (
        translated[f"component.{DOMAIN}.entity.button.refresh.name"]
        == source["entity.button.refresh.name"]
    )
