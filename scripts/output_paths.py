"""Preflight generated files against source paths and filesystem aliases before publication."""
from pathlib import Path


def protect_outputs(outputs, inputs):
    """Refuse source/output aliases, aliased siblings and unusable destination paths.

    Resolve spelling and directory-link aliases, then compare existing device/inode identities for hardlinks.
    This checks a stable local filesystem before writing; it is not a lock against concurrent path changes.
    No directories or files are created here. Only files actually read by the caller belong in inputs.
    """
    identities = {}

    def describe(path):
        resolved = Path(path).resolve()
        if resolved not in identities:
            try:
                info = resolved.stat()
            except FileNotFoundError:
                identity = None
            else:
                if not info.st_ino:
                    raise ValueError("filesystem does not expose a reliable file identity for output checks")
                identity = (info.st_dev, info.st_ino)
            identities[resolved] = identity
        return resolved, identities[resolved]

    try:
        sources = [describe(path) for path in inputs if path is not None]
        source_names = {name for name, _ in sources}
        source_ids = {identity for _, identity in sources if identity is not None}
        output_names, output_ids = set(), set()
        for path in outputs:
            path = Path(path)
            name, identity = describe(path)
            if name in source_names or identity is not None and identity in source_ids:
                raise ValueError("output aliases an input; choose a separate output path")
            if name in output_names or identity is not None and identity in output_ids:
                raise ValueError("generated output files alias each other; choose separate output paths")
            if (path.exists() or path.is_symlink()) and not path.is_file():
                raise ValueError("output is not a regular file; choose a separate output path")
            for parent in path.parents:
                if (parent.exists() or parent.is_symlink()) and not parent.is_dir():
                    raise ValueError("output parent is not a directory; choose a separate output path")
            output_names.add(name)
            if identity is not None:
                output_ids.add(identity)
    except (OSError, RuntimeError) as exc:
        raise ValueError(f"cannot check output paths: {exc}") from exc
