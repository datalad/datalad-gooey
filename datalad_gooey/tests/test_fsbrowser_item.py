from pathlib import Path

from ..fsbrowser_item import (
    FSBrowserItem,
    QTreeWidgetItem,
)

from datalad.distribution.dataset import Dataset
from datalad.tests.utils_pytest import (
    assert_equal,
    assert_in,
    assert_not_in,
    assert_raises,

)
from PySide6.QtCore import (
    Qt,
)

from ..status_light import GooeyStatusLight


def test_FSBrowserItem():
    fsb_item = FSBrowserItem(Path.cwd())
    assert_equal(fsb_item.pathobj, Path.cwd())
    assert_equal(fsb_item.__str__(), f'FSBrowserItem<{Path.cwd()}>')


def test_pathobj_none():
    with assert_raises(RuntimeError):
        FSBrowserItem(None).pathobj()


item_types = ['directory', 'symlink', 'file', 'dataset']
lsdir_results = [
    {
        'path': f'some_{t}.txt',
        'type': t,
        'action': 'gooey-lsdir',
        'status': 'ok'
    }
    for t in item_types
]
lsdir_results+=\
    [
        {
            'path': 'test_error_no_message',
            'type': 'file',
            'action': 'gooey-lsdir',
            'status': 'error',
            'message': ''
        },
        {
            'path': 'test_error_with_message',
            'type': 'file',
            'action': 'gooey-lsdir',
            'status': 'error',
            'message': 'Permissions denied'
        },
    ]
#def test_update_from_lsdir_result():
#    for res in lsdir_results:
#        fsb_item = FSBrowserItem(res['path'])
#        fsb_item.update_from_lsdir_result(res)
#        # check if item type is same as result type
#        assert_equal(fsb_item.datalad_type, res['type'])
#        # test status 'error'
#        if res['status'] == 'error'\
#            and res['message'] == 'Permissions denied':
#                # test isDisabled is correct
#                assert_equal(fsb_item.isDisabled(), True)
#        # test status 'ok'
#        if res['status'] == 'ok':
#            # test isDisabled is correct
#            assert_equal(fsb_item.isDisabled(), False)
#            # test childIndicatorPolicy 
#            if res['type'] in ('directory', 'dataset'):
#                assert_equal(
#                    fsb_item.childIndicatorPolicy(),
#                    QTreeWidgetItem.ShowIndicator)
#            # test directory state is None
#            if res['type'] == 'directory':
#                assert_equal(fsb_item.data(2, Qt.EditRole), None)


states = ['untracked', 'clean', 'modified', 'deleted', 'unknown', 'added']
status_light_results = [
    {
        'path': f'dataset/some_file_{i}.txt',
        'type': 'file',
        'action': 'status',
        'status': 'ok',
        'refds': 'dataset',
        'state': state
    }
    for i, state in enumerate(states)
]
status_light_results+=\
    [
        {
            'path': 'dataset/some_dir',
            'type': 'directory',
            'action': 'status',
            'status': 'ok',
            'refds': 'dataset'
        },
        {
            'path': 'dataset/some_other_file.txt',
            'type': 'file',
            'action': 'status',
            'status': 'error',
            'message': 'something_went_wrong',
            'refds': 'dataset'
        },
    ]
def test_update_from_status_result():
    """"""
    for res in status_light_results:
        fsb_item = FSBrowserItem(res['path'])
        fsb_item.update_from_status_result(res)
        state = res.get('state')
        if state is None:
            if res.get('status') == 'error' and 'message' in res:
                assert_equal(fsb_item.data(2, Qt.EditRole), res.get('message'))
        else:
            assert_equal(fsb_item.data(2, Qt.EditRole), state) 
        if state == 'deleted':
            assert_equal(
                fsb_item.childIndicatorPolicy(),
                QTreeWidgetItem.DontShowIndicator)
        # test item type
        assert_equal(fsb_item.data(1, Qt.EditRole), res.get('type'))


res1 = {
    'path': 'parent_dir/child1',
    'type': 'directory',
    'action': 'gooey-lsdir',
    'status': 'ok'
}
res2 = {
    'path': 'parent_dir/child2',
    'type': 'file',
    'action': 'gooey-lsdir',
    'status': 'ok'
}
def test_item_children():
    # create parent item and two child items
    fsb_parent = FSBrowserItem(Path('parent_dir'))
    fsb_child1 = FSBrowserItem.from_lsdir_result(res1, parent=fsb_parent)
    fsb_child2 = FSBrowserItem.from_lsdir_result(res2, parent=fsb_parent)
    # check that child items are in fact children of parent
    children = list(fsb_parent.children_())
    assert_in(fsb_child1, children)
    assert_in(fsb_child2, children)
    # remove a child and check result
    fsb_parent.removeChild(fsb_child1)
    children = list(fsb_parent.children_())
    assert_not_in(fsb_child1, children)
    assert_in(fsb_child2, children)
