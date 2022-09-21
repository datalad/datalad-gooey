"""DataLad GUI ls-dir helper"""

__docformat__ = 'restructuredtext'

import stat
import logging
from pathlib import Path

from datalad.interface.base import Interface
from datalad.interface.base import build_doc
from datalad.support.param import Parameter
from datalad.support.exceptions import CapturedException
from datalad.interface.utils import eval_results
from datalad.interface.results import get_status_dict

from datalad.runner import (
    GitRunner,
    StdOutCapture,
    CommandError,
)
from datalad.dataset.gitrepo import GitRepo

lgr = logging.getLogger('datalad.ext.gooey.lsdir')


@build_doc
class GooeyLsDir(Interface):
    """Internal helper for datalad-gooey"""
    _params_ = dict(
        path=Parameter(
            args=("path", ),
            doc="""""",
        )
    )

    @staticmethod
    @eval_results
    def __call__(path: Path or str):
        # This needs to be keep simple and as fast as anyhow possible.
        # anything that is not absolutely crucial to have should have
        # an inexpensive switch to turn it off (or be off by default.
        # This command is an internal helper of gooey, it has no ambition
        # to generalize, although the components it uses internally
        # might have applicability in a broader scope.

        # - this takes a single path as a mandatory argument
        # - this path must be a directory, if it exists
        # - this directory can be inside or outside of a dataset
        # - a result is returned for each item inside that is considered
        #   "relevant" for gooey (ie. no content inside `.git` or `.git` itself
        #   etc.

        path = Path(path)
        if not path.is_absolute():
            # make absolute
            # this is not a datasetmethod, we do not have to take the
            # "relative-to-dsroot" case into account
            path = Path.cwd() / path
        # for each item we report
        # - type (symlink, file, directory, dataset)
        # - state (untracked, clean, ...)
        for r in _list(path):
            r.update(action='gooey-lsdir')
            if 'status' not in r:
                r.update(status='ok')
            if r.get('type') == 'directory':
                # a directory could still be an untracked dataset,
                # run the cheapest possible standard test to tell them apart.
                try:
                    is_repo = GitRepo.is_valid(r['path'])
                except PermissionError as e:
                    ce = CapturedException(e)
                    # could be read-protected
                    r['status'] = 'error'
                    r['exception'] = ce
                    r['message'] = 'Permissions denied'
                    yield r
                    continue
                r['type'] = 'dataset' if is_repo else 'directory'
            yield r


def _list(path: Path):
    try:
        yield from _lsfiles(path)
    # TODO dedicated exception?
    except CommandError as e:
        # not in a dataset
        ce = CapturedException(e)
        lgr.debug(
            'git-ls-files failed, falling back on manual inspection: %s',
            ce)
        # TODO apply standard filtering of results
        yield from _iterdir(path)
    except PermissionError as e:
        yield get_status_dict(
            path=str(path),
            status='error',
            exception=CapturedException(e),
        )


def _lsfiles(path: Path):
    from datalad.support.gitrepo import GitRepo
    import re

    # just to be able use _get_content_info_line_helper
    # without a GitRepo instance
    class _Dummy:
        def __init__(self, path):
            self.pathobj = path

    # stolen from GitRepo.get_content_info()
    props_re = re.compile(
        r'(?P<type>[0-9]+) (?P<sha>.*) (.*)\t(?P<fname>.*)$')

    # we use a plain runner to avoid the overhead of a GitRepo instance
    runner = GitRunner()
    ret = runner.run(
        ['git', 'ls-files',
         # we want them all
         '--cached', '--deleted', '--modified', '--others',
         # we want the type info
         '--stage',
         # given that we only want the immediate directory content
         # there is little point in exploring the content of subdir.
         # however, we still want to be able to list directories
         # that are wholly untracked, but still have content
         '--directory',
         # don't show the stuff that a user didn't want to see
         '--exclude-standard',
         # to satisfy the needs of _get_content_info_line_helper()
         '-z'],
        protocol=StdOutCapture,
        # run in the directory we want info on
        # and do not pass further path constraints
        # work around https://github.com/datalad/datalad/issues/7040
        cwd=str(path),
    )
    info = dict()
    GitRepo._get_content_info_line_helper(
        _Dummy(path),
        None,
        info,
        ret['stdout'].split('\0'),
        props_re,
    )
    subdirs_reported = set()
    entirely_untracked_dir = False
    for p, props in info.items():
        rpath_parts = p.relative_to(path).parts
        if len(rpath_parts) > 1:
            # subdirectory content: regret the time it took to process
            # it (ls-files cannot be prevented to list it)
            if rpath_parts[0] in subdirs_reported:
                # we had the pleasure already, nothing else todo
                continue
            yield dict(
                path=path / rpath_parts[0],
                type='directory',
            )
            # and ignore now
            subdirs_reported.add(rpath_parts[0])
            continue
        # we should never get a report on the parent dir we are listing.
        # this only happens, when it is itself entirely untracked.
        # setting this flag catches this condition (there will be no other
        # result), and enable mitigation
        entirely_untracked_dir = p == path
        if not entirely_untracked_dir:
            yield dict(
                path=str(p),
                type=props['type'],
            )
    if entirely_untracked_dir:
        # fall back on _iterdir() for wholly untracked directories
        yield from _iterdir(path)


def _iterdir(path: Path):
    # anything reported from here will be state=untracked
    # figure out the type, as far as we need it
    # right now we do not detect a subdir to be a dataset
    # vs a directory, only directories
    for c in path.iterdir():
        if c.name == '.git':
            # we do not report on this special name
            continue
        # c could disappear while this is running. Example: temp files managed
        # by other processes.
        try:
            cmode = c.lstat().st_mode
        except FileNotFoundError as e:
            CapturedException(e)
            continue
        if stat.S_ISLNK(cmode):
            ctype = 'symlink'
        elif stat.S_ISDIR(cmode):
            ctype = 'directory'
        else:
            # the rest is a file
            # there could be fifos and sockets, etc.
            # but we do not recognize them here
            ctype = 'file'
        props = dict(
            path=str(c),
            type=ctype,
        )
        if type != 'directory':
            props['state'] = 'untracked'
        yield props
