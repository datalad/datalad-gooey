from datalad.tests.utils_pytest import assert_result_count


def test_register():
    import datalad.api as da
    assert hasattr(da, 'gooey')
    assert_result_count(
        da.gooey(),
        1,
        action='demo')

