#!/usr/bin/env python3
"""Safely create a candidate-neutral job-search workspace from templates."""

import argparse
import json
import os
from pathlib import Path
import shutil
import stat


SKILL_ROOT = Path(__file__).resolve().parents[1]
ASSET_MAPPING = {
    "README.md": "pipeline-template.md",
    "CAREER_FACTS.md": "career-facts-template.md",
    "NETWORK.md": "network-template.md",
    "POSITIONING_LOG.md": "positioning-log-template.md",
    "applications/APPLICATION_TEMPLATE.md": "application-template.md",
}
SECURE_DIRECTORY_TRAVERSAL_AVAILABLE = (
    hasattr(os, "O_DIRECTORY")
    and hasattr(os, "O_NOFOLLOW")
    and os.open in getattr(os, "supports_dir_fd", ())
    and os.mkdir in getattr(os, "supports_dir_fd", ())
)


def reject_symlink_components(path):
    """Reject a path when any existing lexical component is a symlink."""
    component = Path(path.anchor)
    for part in path.parts[1:]:
        component /= part
        try:
            metadata = os.lstat(component)
        except FileNotFoundError:
            break
        except OSError as error:
            raise ValueError(f"unsafe target: {error}") from error
        if stat.S_ISLNK(metadata.st_mode):
            raise ValueError("unsafe target")


def resolve_safe_target(target):
    """Expand and validate a workspace path before creating anything."""
    try:
        expanded_target = Path(target).expanduser()
        workspace = Path(os.path.abspath(os.fspath(expanded_target)))
    except (OSError, RuntimeError) as error:
        raise ValueError("unsafe target") from error
    reject_symlink_components(workspace)
    home = Path(os.path.abspath(os.fspath(Path.home())))
    if workspace == Path("/") or workspace == home or len(workspace.parts) < 4:
        raise ValueError("unsafe target")
    return workspace


def open_directory(path, directory_fd=None):
    """Open a directory without following a final symlink."""
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    if directory_fd is None:
        return os.open(path, flags)
    return os.open(path, flags, dir_fd=directory_fd)


def require_secure_directory_support():
    """Fail closed when descriptor-relative directory operations are unavailable."""
    if not SECURE_DIRECTORY_TRAVERSAL_AVAILABLE:
        raise ValueError("unsafe target: secure directory traversal unavailable")


def pin_workspace_path(workspace):
    """Create and pin each absolute workspace component without following links."""
    require_secure_directory_support()
    current_fd = open_directory(workspace.anchor)
    try:
        for component in workspace.parts[1:]:
            try:
                os.mkdir(component, 0o700, dir_fd=current_fd)
            except FileExistsError:
                pass
            next_fd = open_directory(component, current_fd)
            previous_fd = current_fd
            current_fd = next_fd
            os.close(previous_fd)
    except BaseException:
        os.close(current_fd)
        raise
    return current_fd


def copy_asset_exclusively(asset, destination_name, directory_fd):
    """Copy an asset only when the destination does not already exist."""
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(destination_name, flags, 0o600, dir_fd=directory_fd)
    except FileExistsError:
        return False
    with os.fdopen(descriptor, "wb") as destination_file:
        with asset.open("rb") as asset_file:
            shutil.copyfileobj(asset_file, destination_file)
    return True


def initialize_workspace(target):
    """Create missing workspace files and report created and preserved paths."""
    workspace = resolve_safe_target(target)

    created = []
    preserved = []
    workspace_fd = None
    applications_fd = None
    try:
        reject_symlink_components(workspace)
        workspace_fd = pin_workspace_path(workspace)
        for relative_path, asset_name in ASSET_MAPPING.items():
            if relative_path.startswith("applications/"):
                continue
            if copy_asset_exclusively(
                SKILL_ROOT / "assets" / asset_name, relative_path, workspace_fd
            ):
                created.append(relative_path)
            else:
                preserved.append(relative_path)
        try:
            os.mkdir("applications", 0o700, dir_fd=workspace_fd)
        except FileExistsError:
            pass
        applications_fd = open_directory("applications", workspace_fd)
        application_path = "applications/APPLICATION_TEMPLATE.md"
        if copy_asset_exclusively(
            SKILL_ROOT / "assets" / ASSET_MAPPING[application_path],
            "APPLICATION_TEMPLATE.md",
            applications_fd,
        ):
            created.append(application_path)
        else:
            preserved.append(application_path)
    except OSError as error:
        raise ValueError(f"unsafe target: {error}") from error
    finally:
        try:
            if applications_fd is not None:
                os.close(applications_fd)
        finally:
            if workspace_fd is not None:
                os.close(workspace_fd)

    return {"workspace": str(workspace), "created": created, "preserved": preserved}


def main():
    """Initialize a workspace specified on the command line."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", help="directory for the new workspace")
    arguments = parser.parse_args()
    try:
        result = initialize_workspace(arguments.target)
    except ValueError as error:
        parser.error(str(error))
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
