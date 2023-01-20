import logging

from datalad.core.distributed import clone as mod_clone

lgr = logging.getLogger('datalad.core.distributed.clone')


def _pre_final_processing_(
    *,
    destds,
    cfg,
    gitclonerec,
    remote,
    reckless,
):
    yield from orig_pre_final_processing_(
        destds=destds,
        cfg=cfg,
        gitclonerec=gitclonerec,
        remote=remote,
        reckless=reckless,
    )
    # touch the root dir, such that our file watcher can pick this change up
    destds.pathobj.touch()


# apply patch
lgr.debug(
    'Apply datalad-gooey patch to clone.py:_pre_final_processing_')
# we need to preserve the original function to be able to call it in the patch
orig_pre_final_processing_ = mod_clone._pre_final_processing_
mod_clone._pre_final_processing_ = _pre_final_processing_
