"""Wrappers to provide importing and exporting projects capability."""

import io
import logging
import time
import typing
from pathlib import Path
from tempfile import TemporaryDirectory

from gitlab import GitlabCreateError
from gitlab.v4.objects import Group, Project

logger = logging.getLogger(__name__)


def export_project_to_file(
    project: Project,
    file_descriptor: typing.BinaryIO,
) -> None:
    """Export a given Gitlab project into a file.

    Args:
        project: The project to be exported.
        file_descriptor: The file to write the content to.
    """
    if not file_descriptor.name.endswith(".tgz"):
        msg = "The file to write to has end on '.tgz.' to recognized as proper "
        msg += "Gitlab export file!\n"
        msg += f"Provided file name: {file_descriptor.name}"
        raise ValueError()
    logger.info(
        f"Attempting to export {project.path} into {file_descriptor.name}...",
    )
    export = project.exports.create()

    export.refresh()
    while export.export_status != "finished":
        logger.debug("Export ongoing...")
        time.sleep(1)
        export.refresh()

    logger.info("Writing export back to file...")
    export.download(
        streamed=True,
        action=file_descriptor.write,
    )
    logger.info("Export completed.")


def import_project_from_file(
    file_descriptor: io.BufferedReader,
    project: Project,
    group: Group,
) -> Project:
    """Import the project to a Gitlab group using its file content.

    Args:
        file_descriptor: Holding the project's exported content.
        project: Gitlab project to import. Needed for metadata.
        group: The destination group, under which the project is imported. Can be in
            a separate Gitlab instance.

    Returns:
        The project created in the destination group.
    """
    gl = group.manager.gitlab

    msg = f"Attempting import of project '{project.name}' "
    msg += f"stored in file '{file_descriptor.name}' into {group.full_path}..."
    logger.info(msg)
    output = gl.projects.import_project(
        file_descriptor,
        namespace=group.full_path,
        path=project.path,
        name=project.name,
    )

    # Get a ProjectImport object to track the import status
    new_project = gl.projects.get(
        output["id"],  # type: ignore[index]
        lazy=True,
    )
    project_import = new_project.imports.get()
    while project_import.import_status != "finished":
        if project_import.import_status == "failed":
            msg = "Could not import the project!\n"
            msg += f"Error: {project_import.import_error}"
            raise GitlabCreateError(msg)
        logger.debug("Import ongoing...")
        time.sleep(1)
        project_import.refresh()

    logger.info("Import completed.")
    return new_project


def migrate_project(
    project: Project,
    destination_group: Group,
) -> Project:
    """Export a given Gitlab project and import it into the provided group.

    Project and group do not need to exist in the same Gitlab instance.

    Args:
        project: Project from an origin Gitlab instance.
        destination_group: Group in a destination Gitlab, where the project is to
            be imported to.
    """
    with TemporaryDirectory() as temporary_directory:
        file_path = Path(temporary_directory) / f"{project.path}.tgz"
        with open(file_path, "wb") as file_descriptor:
            export_project_to_file(
                project=project,
                file_descriptor=file_descriptor,
            )

        with open(file_path, "rb") as file_descriptor:
            destination_project = import_project_from_file(
                project=project,
                file_descriptor=file_descriptor,
                group=destination_group,
            )
    return destination_project


def copy_variables(
    origin_project: Project,
    destination_project: Project,
    dry_run: bool = True,
) -> None:
    """Copy CI/CD variables from one project to another.

    Args:
        origin_project: Holding the variables to copy.
        destination_project: Project to receive the copied variables.
        dry_run: Flag to only show information without actually copying anything.
    """
    logger.info("Copying variables from origin project to destination project.")
    project_variables = origin_project.variables.list(get_all=True)
    if dry_run:
        logger.debug(
            "The following variables would be copied:\n",
            project_variables,
        )
    else:
        for var in project_variables:
            destination_project.variables.create(var._attrs)


def export_local(
    project: Project,
    export_path: Path,
) -> None:
    """Write Gitlab project to path project_root/exports at local disc.

    The “exports” folder will be created if not present.

    The copy of the Gitlab project will be persisted as *.tgz file.

    Args:
        project: Project from an origin Gitlab instance.
        export_path: Path, under which the project export is stored.
    """
    export_url = export_path / f"{project.path}.tgz"
    logger.info(
        "Exporting project '%s' to '%s'",
        project.name,
        export_url,
    )
    with open(export_url, "wb") as file_descriptor:
        export_project_to_file(
            project=project,
            file_descriptor=file_descriptor,
        )
