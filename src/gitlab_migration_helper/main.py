"""Main module bringing the pruning and migration parts together."""

import logging

from gitlab import Gitlab
from gitlab.v4.objects import Group

from gitlab_migration_helper.gitlab_utils import get_rectified_branches_refs
from gitlab_migration_helper.import_export import copy_variables, migrate_project
from gitlab_migration_helper.pruning import (
    PreservationPolicy,
    delete_branches,
    delete_non_protected_branch_pipelines,
    delete_pipelines,
    delete_releases,
)

logger = logging.getLogger(__name__)


def main(
    origin_gitlab: Gitlab,
    origin_group: Group,
    destination_group: Group,
    include_archived_projects: bool,
    prompt_every_project: bool,
    preservation_policy: PreservationPolicy,
    preserve_branches: list[str],
    exclude_subgroups: bool,
    dry_run: bool = True,
) -> None:
    """Core function executing the projects pruning and migration.

    Args:
        origin_gitlab: Instance from where to migrate. Needed for the pruning.
        origin_group: Gitlab group holding the projects to migrate.
        destination_group: Destination group to migrate to.
        include_archived_projects: Flag to control, if archived projects should be
            included in the pruning and migration as well.
        prompt_every_project: Flag to control, if every single project should be
            prompted for pruning and migration..
        preservation_policy: Preservation policy to apply to releases and pipelines
            pruning.
        preserve_branches: Branches, which should be exempted from deletion beyond
            'main' and 'master'.
        exclude_subgroups: If set to False, include subgroup projects as well.
        dry_run: Flag to control, if the pruning and migration should actually execute.
            Default is to just show candidates.
    """
    projects = list(
        origin_group.projects.list(
            get_all=True,
            include_subgroups=not exclude_subgroups,
            recursive=True,
        )
    )

    for group_project in projects:
        project = origin_gitlab.projects.get(
            group_project.id,
            statistics=True,
        )
        if project.archived and not include_archived_projects:
            continue

        logger.info(f"Processing project {project.name} ({project.id})...")

        msg = f"Do you want to migrate the project {project.name}? (y/n)"
        if prompt_every_project:
            answer = input(msg).lower()
            if answer not in ["n", "y"]:
                KeyError("Invalid answer option! Must be one of ['n', 'N', 'y', 'Y']!")
            if answer == "n":
                continue

        exclude_branch_refs = get_rectified_branches_refs(
            project=project,
            branches_to_validate=preserve_branches,
        )

        delete_non_protected_branch_pipelines(
            project=project,
            exclude_branch_refs=exclude_branch_refs,
            dry_run=dry_run,
        )

        delete_branches(
            project=project,
            exclude_branch_refs=exclude_branch_refs,
            dry_run=dry_run,
        )

        delete_pipelines(
            project=project,
            preservation_policy=preservation_policy,
            dry_run=dry_run,
        )

        delete_releases(
            project=project,
            preservation_policy=preservation_policy,
            dry_run=dry_run,
        )

        if not dry_run:
            destination_project = migrate_project(
                project=project,
                destination_group=destination_group,
            )
            copy_variables(
                origin_project=project,
                destination_project=destination_project.id,
                dry_run=dry_run,
            )
