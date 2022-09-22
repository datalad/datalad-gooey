
from pathlib import Path
from ..lsdir import GooeyLsDir
import stat
from unittest.mock import patch

from datalad.api import create
from datalad.support.exceptions import IncompleteResultsError
from datalad.tests.utils_pytest import (
    assert_equal,
    assert_in,
    assert_raises,
    get_deeply_nested_structure,
    with_tempfile,
    with_tree,
)

dataset_content = [
    {'path': 'directory_untracked', 'type': 'directory'},
    {'path': 'link2dir', 'type': 'symlink'},
    {'path': 'link2subdsdir', 'type': 'symlink'},
    {'path': 'link2subdsroot', 'type': 'symlink'},
    {'path': 'subdir', 'type': 'directory'},
    {'path': '.datalad', 'type': 'directory'},
    {'path': '.gitattributes', 'type': 'file'},
    {'path': '.gitmodules', 'type': 'file'},
    {'path': 'subds_modified', 'type': 'dataset'},
]

adjusted_content = [
    item for item in dataset_content if item.get('type') != 'symlink'
]


# Test _lsfiles with dataset
@with_tempfile
def test_lsfiles(path=None):
    ds = get_deeply_nested_structure(path)
    abnormal_filename = list(Path(path).glob('*file_modified_'))[0]
    abnormal_filename.unlink()
    # Since this is a dataset, check that _lsfiles is called and not _iterdir
    with patch("datalad_gooey.lsdir._iterdir") as _iterdir,\
        patch("datalad_gooey.lsdir._lsfiles") as _lsfiles:
        GooeyLsDir.__call__(ds.pathobj)
        _lsfiles.assert_called()
        _iterdir.assert_not_called()
    # Write results to list
    lsfiles_res = list(GooeyLsDir.__call__(ds.pathobj))
    # In case we are on a crippled filesystem, use content without symlinks
    adjusted = False
    content = dataset_content
    if ds.repo.is_managed_branch():
        content = adjusted_content
        adjusted = True
    # Test result outputs
    assert_equal(len(lsfiles_res), len(content))
    for item in lsfiles_res:
        assert_in(
            {
                'path': Path(item.get('path')).name,
                'type': item.get('type'),
            }, content)
    # test inaccessible directory
    if not adjusted:
        new_dir = Path(path) / 'interim_dir' / 'inaccessible_dir'
        new_dir.mkdir(parents=True)
        existing_permissions = stat.S_IMODE(new_dir.stat().st_mode)
        new_permissions = existing_permissions ^ stat.S_IXUSR ^ stat.S_IRUSR ^ stat.S_IWUSR
        new_dir.chmod(new_permissions)
        with assert_raises(IncompleteResultsError):
            res = list(GooeyLsDir.__call__(Path(path) / 'interim_dir'))
            assert_equal(len(res), 1)
            assert_equal(res[0].get('status'), 'error')
            assert_equal(res[0].get('message'), 'Permissions denied')
        

dir_tree = {
    "random_file1.txt": "some content",
    "some_dir": {
        "file_in_dir.txt": "some content in file in dir",
    },
    "subdataset": {
        "random_file2.txt": "some content in file in subdataset",
    }
}

directory_content = [
    {'path': 'random_file1.txt', 'type': 'file', 'state': 'untracked'},
    {'path': 'subdataset', 'type': 'dataset', 'state': 'untracked'},
    {'path': 'some_dir', 'type': 'directory', 'state': 'untracked'}
]

# Test _iterdir with directory tree not in dataset/git repo
@with_tree(tree=dir_tree)
def test_iterdir(root=None, mockdef=None):
    # Create and save subdataset
    sub_ds = create(Path(root) / "subdataset", force=True)
    sub_ds.save(to_git=True)
    # Since this is a directory (not git repo or dataset),
    # check that _iterdir is called
    with patch("datalad_gooey.lsdir._iterdir") as _iterdir:
        GooeyLsDir.__call__(Path(root))
        _iterdir.assert_called()
    # Write results to list and test outputs
    iterdir_res = list(GooeyLsDir.__call__(Path(root)))
    assert_equal(len(iterdir_res), len(directory_content))
    for item in iterdir_res:
        assert_in(
            {
                'path': Path(item.get('path')).name,
                'type': item.get('type'),
                'state': item.get('state'),
            }, directory_content)

# Test PermissionError directory

# Test .git
@with_tempfile(mkdir=True)
def test_git_directory(temp_dir_name: str = ""):
    new_dir = Path(temp_dir_name) / '.git'
    new_dir.mkdir()
    res = list(GooeyLsDir.__call__(Path(temp_dir_name)))
    assert_equal(len(res), 0)
