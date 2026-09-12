from __future__ import annotations

from sidereal_core.settings import DEFAULT_DIRECTUS_URL, directus_settings


def test_settings_default_read_the_environment_and_treat_an_empty_value_as_unset() -> None:
    default = directus_settings({})
    set_up = directus_settings(
        {"SIDEREAL_DIRECTUS_URL": "https://directus.example/", "SIDEREAL_DIRECTUS_TOKEN": "tok"}
    )

    assert (default.url, default.token) == (DEFAULT_DIRECTUS_URL, None)
    assert (set_up.url, set_up.token) == ("https://directus.example", "tok")
    assert directus_settings({"SIDEREAL_DIRECTUS_TOKEN": ""}).token is None
