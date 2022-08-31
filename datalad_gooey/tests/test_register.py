

def test_register():
    import datalad.api as da
    assert hasattr(da, 'gooey')
    # do not actually run this, because headless CI systems do not support
    # GUI launching
    #assert_result_count(
    #    da.gooey(),
    #    1,
    #    action='demo')

