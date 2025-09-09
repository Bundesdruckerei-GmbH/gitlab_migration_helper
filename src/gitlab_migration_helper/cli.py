"""Module providing the CLI feature."""

import functools
import logging
from collections.abc import Callable
from typing import Any

import click
from click_option_group import optgroup
from mypy_extensions import KwArg

from gitlab_migration_helper.gitlab_utils import get_gitlab_group, get_gitlab_instance
from gitlab_migration_helper.loggingconfig import setup_logging
from gitlab_migration_helper.main import main
from gitlab_migration_helper.pruning import PreservationPolicy


def gitlab_options(
    options: Callable[[...], None],  # type: ignore
) -> Callable[[...], None]:  # type: ignore
    """Extend CLI options with set of base options.

    Args:
        options: CLI options to extend.

    Returns:
        The extended options.
    """
    f = " !ATTENTION! Group names can be ambiguous; if in doubt use the group id!"

    @click.option(
        "--origin-gitlab",
        required=True,
        type=str,
        envvar="ORIGIN_GITLAB",
        show_default=True,
        default="https://partner.bdr.de/gitlab",
        help="URL of the origin Gitlab instance from where to migrate.",
    )
    @click.option(
        "--origin-certificate",
        required=True,
        type=str,
        envvar="ORIGIN_CERTIFICATE",
        help="SSL certificate for communication with the origin Gitlab instance.",
    )
    @click.option(
        "--origin-key",
        required=True,
        type=str,
        envvar="ORIGIN_KEY",
        help="SSL key for communication with the origin Gitlab instance.",
    )
    @click.option(
        "--origin-token",
        required=True,
        type=str,
        envvar="ORIGIN_TOKEN",
        help="Gitlab token for interaction with the origin Gitlab instance.",
    )
    @click.option(
        "--origin-group",
        required=True,
        type=str,
        envvar="ORIGIN_GROUP",
        help="Group in the origin Gitlab, which holds all repositories to migrate." + f,
    )
    @click.option(
        "--destination-gitlab",
        required=True,
        type=str,
        envvar="DESTINATION_GITLAB",
        show_default=True,
        default="https://gitlab.partner.bdr.de",
        help="URL of the destination Gitlab instance from where to migrate.",
    )
    @click.option(
        "--destination-certificate",
        required=True,
        type=str,
        envvar="DESTINATION_CERTIFICATE",
        help="SSL certificate for communication with the destination Gitlab instance.",
    )
    @click.option(
        "--destination-key",
        required=True,
        type=str,
        envvar="DESTINATION_KEY",
        help="SSL key for communication with the destination Gitlab instance.",
    )
    @click.option(
        "--destination-token",
        required=True,
        type=str,
        envvar="DESTINATION_TOKEN",
        help="Gitlab token for interaction with the destination Gitlab instance.",
    )
    @click.option(
        "--destination-group",
        required=True,
        type=str,
        envvar="DESTINATION_GROUP",
        help="Group in the destination Gitlab to migrate to." + f,
    )
    @click.option(
        "--no-dry-run",
        required=False,
        is_flag=True,
        default=False,
        help="If set, the projects will be pruned and migrated afterwards effectively.",
    )
    @click.option(
        "--exclude-subgroups",
        required=False,
        is_flag=True,
        default=False,
        help="If set, projects in subgroups will be excluded from the migration.",
    )
    @functools.wraps(options)
    def options_wrapper(*args, **kwargs):  # noqa: ANN202, ANN002, ANN003
        return options(*args, **kwargs)

    return options_wrapper


def add_project_options(
    options: Callable[[...], None],  # type: ignore
) -> Callable[[...], None]:  # type: ignore
    """Extend CLI options.

    Args:
        options: CLI options to extend.

    Returns:
        The extended options.
    """

    @click.option(
        "--include-archived",
        "include_archived",
        required=False,
        is_flag=True,
        default=False,
        show_default=True,
        help="Add this flag to also prune and migrate archived projects.",
    )
    @click.option(
        "--pb",
        "preserve_branches",
        envvar="PROTECTED_BRANCHES",
        required=False,
        type=click.STRING,
        multiple=True,
        help="Branches to keep other than 'main' and 'master'.",
    )
    @functools.wraps(options)
    def options_wrapper(*args, **kwargs):  # noqa: ANN202, ANN002, ANN003
        return options(*args, **kwargs)

    return options_wrapper


def assume_yes_option(
    options: Callable[[...], None],  # type: ignore
) -> Callable[[...], None]:  # type: ignore
    """Extend CLI options with an optional prompt skip.

    Args:
        options: CLI options to extend.

    Returns:
        The extended options.
    """

    @click.option(
        "--prompt",
        required=False,
        is_flag=True,
        default=False,
        show_default=True,
        help="If not set, skip the prompting per project, assuming 'yes' as answer.",
    )
    @functools.wraps(options)
    def options_wrapper(*args, **kwargs):  # noqa: ANN202, ANN002, ANN003
        return options(*args, **kwargs)

    return options_wrapper


def add_default_preservation_policy_option(
    options: Callable[[KwArg(Any)], None],
) -> Callable[[...], None]:  # type: ignore
    """Extend CLI options.

    Args:
        options: CLI options to extend.

    Returns:
        The extended options.
    """
    msg = "These parameters control how project pipelines and releases are kept. "
    msg += "At least one has to be set. "
    msg += "If '--keep-latest-items ...' is set, other parameters are ignored. "
    msg += "If both '--minimum-creation-date ...' and '--keep-latest-items ...' are "
    msg += "set, the later result date is picked."

    @optgroup.group(
        "Project preservation parameters",
        help=msg,
    )
    @optgroup.option(
        "--minimum-creation-date",
        required=False,
        type=click.DateTime(),
        default=None,
        help="Keep items, that have been created latest at this date.",
    )
    @optgroup.option(
        "--maximum-age-in-days",
        required=False,
        type=int,
        default=None,
        help="Keep items, that are maximum this old.",
    )
    @optgroup.option(
        "--keep-latest-items",
        required=False,
        type=int,
        default=None,
        help="Keep the last x items from project releases and pipelines.",
    )
    @functools.wraps(options)
    def options_wrapper(*args, **kwargs):  # noqa: ANN202, ANN002, ANN003
        return options(*args, **kwargs)

    return options_wrapper


@click.command()
@gitlab_options
@add_project_options
@assume_yes_option
@add_default_preservation_policy_option
def commandline_interface(**params) -> None:  # noqa: ANN003
    """Core function of the CLI, bringing the arguments to the core feature function.

    Args:
        **params: See the decorating functions.
    """
    setup_logging()
    origin_gitlab = get_gitlab_instance(
        gitlab_url=params["origin_gitlab"],
        token=params["origin_token"],
        certificate=params["origin_certificate"],
        key=params["origin_key"],
    )

    origin_group = get_gitlab_group(
        gl=origin_gitlab,
        group_id=attempt_coersion_to_int(params["origin_group"]),
    )

    destination_gitlab = get_gitlab_instance(
        gitlab_url=params["destination_gitlab"],
        token=params["destination_token"],
        certificate=params["destination_certificate"],
        key=params["destination_key"],
    )

    destination_group = get_gitlab_group(
        gl=destination_gitlab,
        group_id=attempt_coersion_to_int(params["destination_group"]),
    )

    preservation_policy = PreservationPolicy(
        retain_number_of_instances=params["keep_latest_items"],
        minimum_creation_date=params["minimum_creation_date"],
        maximum_age_in_days=params["maximum_age_in_days"],
    )

    main(
        origin_gitlab=origin_gitlab,
        origin_group=origin_group,
        destination_group=destination_group,
        include_archived_projects=params["include_archived"],
        prompt_every_project=params["prompt"],
        preservation_policy=preservation_policy,
        preserve_branches=params["preserve_branches"],
        exclude_subgroups=params["exclude_subgroups"],
        dry_run=not params["no_dry_run"],
    )


def attempt_coersion_to_int(
    group_id: str,
) -> str | int:
    """Coerces the provided group ID to integer.

    If the coercion fails, a group name is assumed.

    Args:
        group_id: Gitlab group ID or name.

    Returns:
        The id as integer, if the coercion is successful, the unchanged input value.
    """
    try:
        return int(group_id)
    except ValueError:
        logging.info(
            f"Could not coerce '{group_id}' into an integer. Assuming a group name.",
        )
        return group_id


if __name__ == "__main__":
    commandline_interface()
