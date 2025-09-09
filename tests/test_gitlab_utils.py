# ruff: noqa: ANN001, ANN201, D100, D103

import os

import pytest

from gitlab_migration_helper import gitlab_utils as na


@pytest.mark.skipif(
    os.environ.get("LOCAL_TESTING") != "True",
    reason="Not a local test setup.",
)
def test_get_origin_gitlab_instance():
    token = os.environ.get("ORIGIN_TOKEN")
    certificate = os.environ.get("ORIGIN_CERT")
    url = os.environ.get("ORIGIN_GITLAB")
    key = os.environ.get("ORIGIN_KEY")

    gitlab_instance = na.get_gitlab_instance(
        token=token,
        certificate=certificate,
        key=key,
        gitlab_url=url,
    )

    # then
    assert gitlab_instance.api_url == f"{url}/api/v4"


@pytest.mark.skipif(
    os.environ.get("LOCAL_TESTING") != "True",
    reason="Not a local test setup.",
)
def test_get_destination_gitlab_instance():
    # given
    token = os.environ.get("DESTINATION_TOKEN")
    certificate = os.environ.get("DESTINATION_CERT")
    url = os.environ.get("DESTINATION_GITLAB")
    key = os.environ.get("DESTINATION_KEY")

    gitlab_instance = na.get_gitlab_instance(
        token=token,
        certificate=certificate,
        key=key,
        gitlab_url=url,
    )

    # then
    assert gitlab_instance.api_url == f"{url}/api/v4"
