from __future__ import annotations

from sidereal_core.settings import DEFAULT_DIRECTUS_URL, directus_settings


def test_defaults_when_nothing_is_set() -> None:
    settings = directus_settings({})

    assert settings.url == DEFAULT_DIRECTUS_URL
    assert settings.token is None


def test_reads_the_environment_and_trims_a_trailing_slash() -> None:
    settings = directus_settings(
        {"SIDEREAL_DIRECTUS_URL": "https://directus.example/", "SIDEREAL_DIRECTUS_TOKEN": "tok"}
    )

    assert settings.url == "https://directus.example"
    assert settings.token == "tok"


def test_an_empty_token_is_no_token() -> None:
    assert directus_settings({"SIDEREAL_DIRECTUS_TOKEN": ""}).token is None
