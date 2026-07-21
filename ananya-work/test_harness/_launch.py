"""
_launch.py <sqlite_path> <target_script.py> [args for target script...]
Installs sqlite_shim in this fresh subprocess, then runs the target
script exactly as if it had been invoked directly -- same __file__,
same argv (minus the two leading harness args), same __main__ guard.
"""

import runpy
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sqlite_shim  # noqa: E402

sqlite_path = sys.argv[1]
target_script = sys.argv[2]
target_args = sys.argv[3:]

sqlite_shim.install(sqlite_path)

sys.path.insert(0, os.path.dirname(os.path.abspath(target_script)))
sys.argv = [target_script] + target_args
runpy.run_path(target_script, run_name="__main__")
