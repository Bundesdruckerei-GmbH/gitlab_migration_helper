# ruff: noqa: ANN001, ANN201, D100, D103

import os

import pytest

from gitlab_migration_helper import gitlab_utils as na


@pytest.mark.skipif(
    os.environ.get("LOCAL_TESTING") != "True",
    reason="Not a local test setup.",
)
@pytest.fixture
def origin_gitlab():
    token = os.environ.get("ORIGIN_TOKEN")
    certificate = os.environ.get("ORIGIN_CERT")
    url = os.environ.get("ORIGIN_GITLAB")
    key = os.environ.get("ORIGIN_KEY")

    return na.get_gitlab_instance(
        token=token,
        certificate=certificate,
        key=key,
        gitlab_url=url,
    )


@pytest.mark.skipif(
    os.environ.get("LOCAL_TESTING") != "True",
    reason="Not a local test setup.",
)
@pytest.fixture
def destination_gitlab():
    token = os.environ.get("DESTINATION_TOKEN")
    certificate = os.environ.get("DESTINATION_CERT")
    url = os.environ.get("DESTINATION_GITLAB")
    key = os.environ.get("DESTINATION_KEY")

    return na.get_gitlab_instance(
        token=token,
        certificate=certificate,
        key=key,
        gitlab_url=url,
    )


@pytest.mark.skipif(
    os.environ.get("LOCAL_TESTING") != "True",
    reason="Not a local test setup.",
)
@pytest.fixture
def group_origin(origin_gitlab):
    group_id = 1100
    return na.get_gitlab_group(
        gl=origin_gitlab,
        group_id=group_id,
    )


@pytest.mark.skipif(
    os.environ.get("LOCAL_TESTING") != "True",
    reason="Not a local test setup.",
)
@pytest.fixture
def group_destination(origin_gitlab):
    group_id = 1102
    return na.get_gitlab_group(
        gl=origin_gitlab,
        group_id=group_id,
    )


@pytest.mark.skipif(
    os.environ.get("LOCAL_TESTING") != "True",
    reason="Not a local test setup.",
)
@pytest.fixture
def group_tdmdas_migration_target_kfe(destination_gitlab):
    group_id = 11000
    return na.get_gitlab_group(
        gl=destination_gitlab,
        group_id=group_id,
    )
