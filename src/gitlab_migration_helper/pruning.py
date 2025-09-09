"""Components to prune Gitlab releases, pipelines and branches."""

import logging
from argparse import ArgumentError
from datetime import datetime, timedelta
from typing import Annotated, Literal, Self

from gitlab.base import RESTObject
from gitlab.v4.objects import Project, ProjectPipelineManager, ProjectReleaseManager
from pydantic import BaseModel, Field, computed_field, model_validator

logger = logging.getLogger(__name__)


class PreservationPolicy(BaseModel):
    """Configuration holding the limitation date or number of preserved items.

    Intended for releases and pipelines.

    After instantiation, use the property "minimum_allowed_created_at", which is
    the maximum resulting date from minimum_creation_date and the date calculated from
    maximum_age_in_days (based on today), ignoring None's.
    retain_number_of_instances declares a number of items to keep.

    Age-based preservation (i.e. minimum_allowed_created_at) and number-based
    preservation (i.e. retain_number_of_instances) are mutually exclusive within a
    policy to prevent confusion.
    """

    retain_number_of_instances: Annotated[int, Field(gt=0)] | None = Field(
        None,
        frozen=True,
    )
    maximum_age_in_days: Annotated[int, Field(ge=0)] | None = Field(
        None,
        frozen=True,
    )
    minimum_creation_date: datetime | None = Field(
        None,
        frozen=True,
    )

    @computed_field
    @property
    def minimum_allowed_created_at(self) -> datetime | None:
        """Gets the younger of provided dates from minimum_creation_date and max_age.

        Returns:
            The resulting date.
        """
        maximum_age_given = self.maximum_age_in_days is not None
        minimum_date_given = self.minimum_creation_date is not None

        if maximum_age_given and minimum_date_given:
            today = datetime.today()
            maximum_age_date = today - timedelta(days=self.maximum_age_in_days)  # type: ignore[arg-type]
            return max(maximum_age_date, self.minimum_creation_date)
        elif maximum_age_given:
            today = datetime.today()
            return today - timedelta(days=self.maximum_age_in_days)  # type: ignore[arg-type]
        elif minimum_date_given:
            return self.minimum_creation_date
        return None

    @model_validator(mode="after")
    def __check_mutual_exclusive(self) -> Self:
        max_age_given = self.maximum_age_in_days is not None
        min_creation_given = self.minimum_creation_date is not None
        number_of_items_given = self.retain_number_of_instances is not None
        if max_age_given or min_creation_given:
            if number_of_items_given:
                msg = "<retain_number_of_instances> is mutual exclusive with other "
                msg += "parameters!"
                raise ValueError(msg)
        elif not number_of_items_given:
            raise ValueError("At least one parameter must be set, i.e. not None!")
        return self


def delete_pipelines(
    project: Project,
    preservation_policy: PreservationPolicy,
    dry_run: bool = True,
) -> None:
    """Delete pipelines from the provided Gitlab project.

    If <maximum_age> and <minimum_creation_date> both are set, the later resulting
    date takes precedence, i.e. if the minimum creation date lies more days in the past
    than the maximum age, the maximum age is the limit. And vice versa.

    If <retain_x_latest> is set, the age-based deletion as described above is
    completely ignored.

    Args:
        project: Project from which the pipelines ought to be deleted.
        preservation_policy: Declares, which items to keep.
        dry_run: If True, the actual deletion is omitted.
    """
    logger.info("Deleting project pipelines.")
    pipelines_to_delete = extract_deletion_candidates(
        project=project,
        preservation_policy=preservation_policy,
        candidate_type="pipeline",
    )

    msg = f"The oldest {len(pipelines_to_delete)} pipelines are candidates for"
    msg += " deletion..."
    logger.debug(msg)
    if not dry_run:
        for pipeline in pipelines_to_delete:
            logger.debug(f"Deleting pipeline: {pipeline.id}...")
            pipeline.delete()
    logger.info("Pipelines deletion done.")


def extract_deletion_candidates(
    project: Project,
    preservation_policy: PreservationPolicy,
    candidate_type: Literal["pipeline", "release"] = "pipeline",
) -> list[RESTObject]:
    """Extract deletion candidates from the project's pipelines and releases.

    If <retain_latest_pipelines> is provided, the filter by <latest_creation_date> is
    fully ignored.

    Args:
        project: Project holding the pipelines or releases.
        preservation_policy: Declares, which items to keep.
        candidate_type: Type of the candidates to be extracted.

    Returns:
        The pipelines or releases, which fit the deletion marker criteria.
    """
    base: ProjectPipelineManager | ProjectReleaseManager
    match candidate_type:
        case "pipeline":
            base = project.pipelines
        case "release":
            base = project.releases
        case _:
            raise ValueError("Invalid candidate type!")

    dt_format = "%Y-%m-%dT%H:%M:%S.%fZ"
    all_candidates = sorted(  # noqa: C414
        list(
            base.list(
                iterator=True,
                per_page=100,
            )
        ),
        key=lambda x: datetime.strptime(
            x.created_at,
            dt_format,
        ),
        reverse=True,
    )
    deletion_candidates = []
    if preservation_policy.retain_number_of_instances is not None:
        number_of_instances = preservation_policy.retain_number_of_instances
        if number_of_instances < len(all_candidates):
            deletion_candidates = all_candidates[number_of_instances:]
    else:
        for candidate in all_candidates:
            candidate_created_at = datetime.strptime(
                candidate.created_at,
                dt_format,
            )
            if candidate_created_at < preservation_policy.minimum_allowed_created_at:  # type: ignore[operator]
                deletion_candidates.append(candidate)
    return deletion_candidates


def delete_non_protected_branch_pipelines(
    project: Project,
    exclude_branch_refs: str | list[str] | None = None,
    dry_run: bool = True,
) -> None:
    """Delete all pipelines from all branches but the provided list of exclusions.

    Args:
        project: The project to prune.
        exclude_branch_refs: Pipelines belonging to these branches are left out.
        dry_run: If True, the actual deletion is omitted.
    """
    if exclude_branch_refs is None:
        exclude_branch_refs = ["main", "master"]

    protected_list = validate_branch_list(
        branch=exclude_branch_refs,
        project=project,
    )

    pipelines = list(
        project.pipelines.list(
            iterator=True,
            per_page=100,
        )
    )

    logger.info(f"Searching for pipelines in branches != {exclude_branch_refs}...")
    deletion_candidates = filter(
        lambda x: x.ref not in protected_list,
        pipelines,
    )
    logger.debug(
        f"Identified {len(list(deletion_candidates))} candidates for deletion.",
    )

    if not dry_run:
        for pipeline in deletion_candidates:
            logger.debug(f"Deleting pipeline: {pipeline.id}...")
            pipeline.delete()
    logger.info("Pipelines deletion done.")


def validate_branch_list(
    branch: str | list[str],
    project: Project,
) -> list[str]:
    """Assert that the branch or branches exist, and coerce them into a list.

    'main' or 'master' as value are removed, if not existing in the project, not
    resulting in an error.

    Args:
        branch: Single branch name or list of branch names.
        project: Gitlab project holding the branches.

    Returns:
        The branch or branches as a list.

    Raises:
        ArgumentError, if a non-existing branch is listed, except for 'main' or
            'master'.
    """
    if len(branch) < 1:
        msg = "There has to be at least one branch, that should not be cleaned."
        raise ArgumentError(
            argument=None,
            message=msg,
        )
    branch_list: list[str] = [branch] if isinstance(branch, str) else branch

    existing_branches = []
    for candidate in list(
        project.branches.list(
            iterator=True,
            per_page=100,
        )
    ):
        existing_branches.append(candidate.name)
    for b in list(branch_list):  # list needed to the remove work
        if b not in existing_branches:
            if b in ["main", "master"]:
                branch_list.remove(b)
                continue
            msg = f"The branch name '{b}' could not be found in the refs:\n"
            msg += str(existing_branches)
            raise ArgumentError(
                argument=None,
                message=msg,
            )
    return branch_list


def delete_releases(
    project: Project,
    preservation_policy: PreservationPolicy,
    dry_run: bool = True,
) -> None:
    """Delete releases from the provided Gitlab project.

    If <maximum_age> and <minimum_creation_date> both are set, the later resulting
    date takes precedence, i.e. if the minimum creation date lies more days in the past
    than the maximum age, the maximum age is the limit. And vice versa.

    If <retain_x_latest> is set, the age-based deletion as described above is
    completely ignored.

    Args:
        project: Project from which the releases ought to be deleted.
        preservation_policy: Declares, which items to keep.
        dry_run: If True, the actual deletion is omitted.
    """
    releases_to_delete = extract_deletion_candidates(
        project=project,
        preservation_policy=preservation_policy,
        candidate_type="release",
    )

    msg = f"The oldest {len(releases_to_delete)} releases are candidates for"
    msg += " deletion..."
    logger.info(msg)
    if not dry_run:
        for release in releases_to_delete:
            logger.debug(f"Deleting releases: {release.encoded_id}...")
            project.releases.delete(release.tag_name)
    logger.info("Releases deletion done.")


def delete_branches(
    project: Project,
    exclude_branch_refs: str | list[str] | None = None,
    dry_run: bool = True,
) -> None:
    """Delete all but the excluded branches from the project.

    Args:
        project: Project to be pruned.
        exclude_branch_refs: Branches to be excluded from the deletion.
        dry_run: If True, the actual deletion is omitted.

    Raises:
        ArgumentError, if a non-existing branch is listed, except for 'main' or
            'master'.
    """
    if exclude_branch_refs is None:
        exclude_branch_refs = ["main", "master"]

    logger.info("Looking for branches to delete...")
    protected_branches = validate_branch_list(
        branch=exclude_branch_refs,
        project=project,
    )

    all_branches = list(
        project.branches.list(
            iterator=True,
            per_page=100,
        )
    )

    deletion_candidates = []
    for b in all_branches:
        if b.name not in protected_branches:
            deletion_candidates.append(b)

    logger.debug(f"The following branches would be deleted:\n {deletion_candidates}")

    if not dry_run:
        for branch in deletion_candidates:
            logger.debug(f"Deleting branch '{b.name}'...")
            branch.delete()
    logger.info("Branch deletion done.")
