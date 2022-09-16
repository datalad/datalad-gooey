"""DataLad GUI status helper"""

__docformat__ = 'restructuredtext'

import logging
from pathlib import (
    Path,
    PurePosixPath,
)

from datalad.interface.base import Interface
from datalad.interface.base import build_doc
from datalad.support.param import Parameter
from datalad.interface.utils import eval_results
from datalad.distribution.dataset import (
    EnsureDataset,
    resolve_path,
    require_dataset,
)

from datalad.support.constraints import (
    EnsureNone,
)
from datalad.utils import ensure_list

from .lsdir import GooeyLsDir

lgr = logging.getLogger('datalad.ext.gooey.status_light')


@build_doc
class GooeyStatusLight(Interface):
    """Internal helper for datalad-gooey"""
    _params_ = dict(
        dataset=Parameter(
            args=("-d", "--dataset"),
            doc="""specify the dataset to query.  If
            no dataset is given, an attempt is made to identify the dataset
            based on the current working directory""",
            constraints=EnsureDataset() | EnsureNone()),
        path=Parameter(
            args=("path", ),
            doc="""""",
        )
    )

    @staticmethod
    @eval_results
    def __call__(dataset=None,
                 path: Path or str or None = None,
    ):
        # This needs to be keep simple and as fast as anyhow possible.
        # anything that is not absolutely crucial to have should have
        # an inexpensive switch to turn it off (or be off by default.
        # This command is an internal helper of gooey, it has no ambition
        # to generalize, although the components it uses internally
        # might have applicability in a broader scope.

        ds = require_dataset(
            dataset,
            # in-principle a good thing, but off for speed
            check_installed=False,
            purpose='report status',
        )
        repo = ds.repo
        repo_path = repo.pathobj
        # normalize paths according to standard datalad rules
        paths = [resolve_path(p, dataset) for p in ensure_list(path)]
        # recode paths with repo reference for low-level API
        repo_paths = [repo_path / p.relative_to(ds.pathobj) for p in paths]

        assert len(paths) == 1

        # mapping:: repo_path -> current type
        modified = _get_worktree_modifications(
            repo,
            # put in repo paths!!
            repo_paths,
        )
        # put in repo paths!!
        untracked = _get_untracked(repo, repo_paths)

        # put in repo paths!!
        annex = _get_annexinfo(repo, repo_paths[0]) \
            if hasattr(repo, 'call_annex_records') else {}

        class _NoValue:
            pass

        for r in GooeyLsDir.__call__(
                # we put in repo paths! match against those!
                repo_paths[0],
                return_type='generator',
                on_failure='ignore',
                result_renderer='disabled'):
            # the status mapping use Path objects
            path = Path(r['path'])
            moreprops = dict(
                action='status',
                refds=ds.path,
            )
            modtype = modified.get(path, _NoValue)
            if modtype is not _NoValue:
                # we have a modification
                moreprops['state'] = \
                    'deleted' if modtype is None else 'modified'
                if modtype:
                    # if it is None (deleted), keep the old one
                    # as an annotation of what it was previously.
                    # apply directly, to simplify logic below
                    r['type'] = modtype
            if 'state' not in moreprops and r['type'] != 'directory':
                # there is not really a state for a directory in Git.
                # assigning one in this annotate-a-single-dir approach
                # would make the impression that everything underneath
                # is clean, which we simply do not know
                # there was no modification detected, so we either
                # have it clean or untracked
                moreprops['state'] = \
                    'untracked' if path in untracked else 'clean'
            # recode path into the dataset domain
            moreprops['path'] = str(ds.pathobj / path.relative_to(repo_path))
            r.update(moreprops)
            # pull in annex info, if there is any
            r.update(annex.get(path, {}))
            if 'key' in r and r.get('type') == 'symlink':
                # a symlink with a key is an annexed file
                r['type'] = 'file'
            yield r


# lifted from https://github.com/datalad/datalad/pull/6797
# mode identifiers used by Git (ls-files, ls-tree), mapped to
# type identifiers as used in command results
GIT_MODE_TYPE_MAP = {
    '100644': 'file',
    # we do not distinguish executables
    '100755': 'file',
    '040000': 'directory',
    '120000': 'symlink',
    '160000': 'dataset',
}


# lifted from https://github.com/datalad/datalad/pull/6797
def _get_worktree_modifications(self, paths=None):
    """Report working tree modifications

    Parameters
    ----------
    paths : list or None
      If given, limits the query to the specified paths. To query all
      paths specify `None`, not an empty list.

    Returns
    -------
    dict
      Mapping of modified Paths to type labels from GIT_MODE_TYPE_MAP.
      Deleted paths have type `None` assigned.
    """
    # because of the way git considers smudge filters in modification
    # detection we have to consult two commands to get a full picture, see
    # https://github.com/datalad/datalad/issues/6791#issuecomment-1193145967

    # low-level code cannot handle pathobjs
    consider_paths = [str(p) for p in paths] if paths else None

    # first ask diff-files which can report typechanges. it gives a list with
    # interspersed diff info and filenames
    mod = list(self.call_git_items_(
        ['diff-files',
         # without this, diff-files would run a full status (recursively)
         # but we are at most interested in a subproject commit
         # change within the scope of this repo
         '--ignore-submodules=dirty',
         # hopefully making things faster by turning off features
         # we would not benefit from (at least for now)
         '--no-renames',
         '-z'
        ],
        files=consider_paths,
        sep='\0',
        read_only=True,
    ))
    # convert into a mapping path to type
    modified = dict(zip(
        # paths are every other element, starting from the second
        mod[1::2],
        # mark `None` for deletions, and take mode reports otherwise
        # (for simplicity keep leading ':' in prev mode for now)
        (None if spec.endswith('D') else spec.split(' ', maxsplit=2)[:2]
         for spec in mod[::2])
    ))
    # `diff-files` cannot give us the full answer to "what is modified"
    # because it won't consider what smudge filters could do, for this
    # we need `ls-files --modified` to exclude any paths that are not
    # actually modified
    modified_files = set(
        p for p in self.call_git_items_(
            # we need not look for deleted files, diff-files did that
            ['ls-files', '-z', '-m'],
            files=consider_paths,
            sep='\0',
            read_only=True,
        )
        # skip empty lines
        if p
    )
    modified = {
        # map to the current type, in case of a typechange
        # keep None for a deletion
        k: v if v is None else v[1]
        for k, v in modified.items()
        # a deletion
        if v is None
        # a typechange, strip the leading ":" for a valid comparison
        or v[0][1:] != v[1]
        # a plain modification after running possible smudge filters
        or k in modified_files
    }
    # convenience-map to type labels, leave raw mode if unrecognized
    # (which really should not happen)
    modified = {
        self.pathobj / PurePosixPath(k):
        GIT_MODE_TYPE_MAP.get(v, v) for k, v in modified.items()
    }
    return modified


# lifted from https://github.com/datalad/datalad/pull/6797
def _get_untracked(self, paths=None):
    """Report untracked content in the working tree

    Parameters
    ----------
    paths : list or None
      If given, limits the query to the specified paths. To query all
      paths specify `None`, not an empty list.

    Returns
    -------
    set
      of Path objects
    """
    # because of the way git considers smudge filters in modification
    # detection we have to consult two commands to get a full picture, see
    # https://github.com/datalad/datalad/issues/6791#issuecomment-1193145967

    # low-level code cannot handle pathobjs
    consider_paths = [str(p) for p in paths] if paths else None

    untracked_files = set(
        self.pathobj / PurePosixPath(p)
        for p in self.call_git_items_(
            ['ls-files', '-z', '-o'],
            files=consider_paths,
            sep='\0',
            read_only=True,
        )
        # skip empty lines
        if p
    )
    return untracked_files


def _get_annexinfo(self, path):
    rpath = str(path.relative_to(self.path))
    match_prefix = f'{rpath}/' if rpath != '.' else ''
    return {
        self.pathobj / PurePosixPath(r['file']):
        # include the hashdirs, to enable a consumer to do a
        # "have-locally" check
        {k: r[k] for k in ('bytesize', 'key', 'hashdirlower', 'hashdirmixed')}
        for r in self.call_annex_records(
            ['find',
             # include any
             '--include', f'{match_prefix}*',
             # exclude any records within subdirs of rpath
             '--exclude', f'{match_prefix}*/*',
            ],
            files=[rpath],
        )
    }
