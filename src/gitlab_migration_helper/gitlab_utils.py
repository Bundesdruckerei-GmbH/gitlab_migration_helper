"""General utilities to interact with Gitlab, i.e. instantiation of Groups."""

import logging
from argparse import ArgumentError

import requests
from gitlab import Gitlab
from gitlab.exceptions import (
    GitlabGetError,
)
from gitlab.v4.objects import Group, Project

from gitlab_migration_helper.pruning import validate_branch_list

logger = logging.getLogger(__name__)


def get_gitlab_instance(
    gitlab_url: str,
    token: str,
    certificate: str,
    key: str,
) -> Gitlab:
    """Get a Gitlab instance.

    Args:
        gitlab_url: Address of the Gitlab instance to work against.
        token: Gitlab token.
        certificate: Sunray certificate necessary to reach the Gitlab instance.
        key: Respective key for the certificate.

    Returns:
        Reference object to the target Gitlab instance.
    """
    session = requests.Session()
    session.cert = (
        certificate,
        key,
    )

    return Gitlab(
        url=gitlab_url,
        private_token=token,
        session=session,
    )


def get_gitlab_group(
    gl: Gitlab,
    group_id: str | int,
) -> Group:
    """Produce the Gitlab group object associated with an ID or name.

    Args:
        gl: Gitlab object containing the group.
        group_id: ID (integer) or name of the group to be returned.

    Returns:
        Group object associated with the id/name.

    Raises:
        GitlabGetError, if no group or more then one matching group was found.
    """
    if isinstance(group_id, int):
        group = gl.groups.get(group_id)
    else:
        available_groups = gl.groups.list(get_all=True)
        match matching_groups := list(
            filter(
                lambda g: g.name == group_id,
                available_groups,
            )
        ):
            case [single_group]:
                group = gl.groups.get(single_group.id)
            case []:
                raise GitlabGetError(f"No group with name '{group_id}' found.")
            case _:
                msg = f"Found multiple matching groups:\n{matching_groups}"
                raise GitlabGetError(msg)
    return group


def get_rectified_branches_refs(
    project: Project,
    branches_to_validate: list[str],
    extend_with_defaults: bool = True,
) -> list[str]:
    """Validate a list of given branch names of a project removing non-existent ones.

    Args:
        project: Project supposedly holding the branches.
        branches_to_validate: Branch names to validate.
        extend_with_defaults: If True, 'main' and 'master' branch are added to the list.

    Returns:
        The list of existing branches, plus defaults if parameterized.
    """
    branch_ref_candidates = list(branches_to_validate)
    branch_refs = []
    for branch in branch_ref_candidates:
        try:
            branch_refs += validate_branch_list(
                project=project,
                branch=branch,
            )
        except ArgumentError:
            logger.warning(
                f"Omitting branch '{branch}' from protection list. Not existing."
            )
    if extend_with_defaults:
        logger.debug("Adding also the default branches.")
        branch_refs += ["main", "master"]
    return branch_refs
