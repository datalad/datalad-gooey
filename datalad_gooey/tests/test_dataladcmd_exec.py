from datalad.tests.utils_pytest import (
    assert_equal,
    assert_in,
    assert_result_count,
)

from ..dataladcmd_exec import GooeyDataladCmdExec


def test_GooeyDataladCmdExec(qtbot):

    executor = GooeyDataladCmdExec()

    cmd = 'nonsense'
    with qtbot.waitSignal(executor.execution_failed) as block_for_fail, \
            qtbot.assertNotEmitted(executor.execution_started), \
            qtbot.assertNotEmitted(executor.execution_finished), \
            qtbot.assertNotEmitted(executor.results_received):
        executor.execute(cmd, {}, {})

    # Note: blocker.args delivers the arguments to the signal
    assert_equal(block_for_fail.args[1], "nonsense")
    assert_in("module 'datalad.api' has no attribute 'nonsense'",
              block_for_fail.args[-1].format_short())

    cmd = 'wtf'
    # MultSignalBlocker via waitSignals() doesn't "work". It blocks
    # correctly, but signal args are inaccessible contrary to the pytest-qt
    # docs. Hence, use the uglier way here:
    with qtbot.waitSignal(executor.execution_started) as block_start, \
            qtbot.waitSignal(executor.execution_finished) as block_finish, \
            qtbot.waitSignal(executor.results_received) as block_result,  \
            qtbot.assertNotEmitted(executor.execution_failed):

        executor.execute(cmd, {}, {})

    # command
    assert_equal(block_start.args[1], "wtf")
    assert_equal(block_finish.args[1], "wtf")
    # thread_id matches:
    assert_equal(block_start.args[0], block_finish.args[0])
    # results received:
    # command class
    assert_equal(block_result.args[0].__qualname__,
                 'WTF')
    # actual results:
    res = block_result.args[1]
    assert_result_count(res, 1, action="wtf", status="ok")
