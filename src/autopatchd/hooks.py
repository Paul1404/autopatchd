"""
autopatchd.hooks
----------------
Execute pre- and post-run hook scripts located in
/etc/autopatchd/hooks/pre.d/ and /etc/autopatchd/hooks/post.d/.

Each hook must be executable (chmod +x).
Execution order is lexical (sorted by filename).
"""

import os
import subprocess
import logging
from typing import Literal


def run_hooks(dirpath: str, stage: Literal["pre", "post"]) -> None:
    """
    Run all executable hook scripts in dirpath.

    Args:
        dirpath: Directory path containing hook scripts.
        stage:   "pre" or "post", used only for logging.

    Notes:
        - Hooks are executed in lexicographic order.
        - Failures do not abort autopatchd; errors are logged.
    """
    if not os.path.isdir(dirpath):
        logging.debug("No %s hooks directory: %s", stage, dirpath)
        return

    entries = sorted(os.listdir(dirpath))
    if not entries:
        logging.debug("No %s hooks found in %s", stage, dirpath)
        return

    logging.info("Running %s hooks from %s", stage, dirpath)

    for name in entries:
        path = os.path.join(dirpath, name)
        if not os.access(path, os.X_OK) or os.path.isdir(path):
            continue  # skip non-executables and subdirs

        logging.info("Executing hook [%s]: %s", stage, path)
        try:
            subprocess.run([path], check=False)
        except Exception as e:
            logging.error("Hook %s failed: %s", path, e)