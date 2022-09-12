from datalad_next.tree import TreeCommand


def _parse_dir(path, depth=1, include_files=True):
    """Yield results on the target directory properties and its content"""
    # we use `tree()` and limit to immediate children of this node
    yield from TreeCommand.__call__(
        # start parsing in symlink target, if there is any
        path,
        depth=depth,
        include_files=include_files,
        result_renderer='disabled',
        return_type='generator',
        # permission issues may error, but we do not want to fail
        # TODO we would rather annotate the nodes with this info
        on_failure='ignore',
    )
