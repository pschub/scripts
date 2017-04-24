"""My implementation of shutil.

Implements a subset of the standard shutil library. Uses the native shell
functions, so the commands behave exactly as you expect. (python shutil library
says it cannot copy all file metadata).

Additionally, this library supports sandboxing by default. Any write activities
must occur within the sandbox or its subdirectories.

Functions:
    set_sandbox(path): set sandbox directory.
    is_sandboxed(path): returns true if path is within sandbox.
    standardize_path(path): Expand path into absolute form.
    copy(source, dest, sandbox): performs command 'cp -pr source dest'.
    mkdir(path, sandbox): performs command 'mkdir path'.
    rm(path, sandbox): performs command 'rm -rf path'.
"""

# April 2017 v1
#
# Copyright (C) 2017 Patrick Schubert
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>


from os.path import realpath
from pathlib import Path
import subprocess
import logging

# Path to sandbox. See set_sandbox.
__SANDBOX = None


def set_sandbox(path):
    """Set the sandbox boundaries.

    Any writes using myshutil will check if the write destination is within
    these bounds. Raises FileNotFoundError if path doesn't exist.
    """
    global __SANDBOX
    path = standardize_path(path)
    if not path.exists():
        raise FileNotFoundError(str(path))
    __SANDBOX = path
    return


def standardize_path(path):
    """Expand path into absolute form."""
    # use os.realpath instead of Path.resolve bc resolve fails for nonexistent
    # files, whereas realpath just rolls with it. Py 3.6 adds strict=False
    # to resolve to allow this capability, but we're stuck on 3.5 here.
    path = path.expanduser()
    path = Path(realpath(str(path)))
    return path


def is_sandboxed(path):
    """Return true if path is within sandbox."""
    path = standardize_path(path)
    for p in path.parents:
        if p == __SANDBOX:
            return True
    return False


def copy(source, dest, sandbox=True):
    """Perform cp -r operation, preserving timestamps, permissions.

    Copies source to dest. sandbox=False will disable sandbox check.
    Returns false on error.
    """
    if sandbox and not is_sandboxed(dest):
        _log_err("copy", "destination not sandboxed.", locals())
        return False
    source = str(source)
    dest = str(dest)
    ret = _run(['cp', '-pr', source, dest])
    if (ret.returncode is not 0):
        _log_err("copy", "cp returned error: {0}".format(ret.returncode),
                 locals())
        return False
    else:
        return True


def mkdir(path, sandbox=True):
    """Make a directory at path.

    sandbox=False will disable sandbox check.
    Returns false on error.
    """
    if sandbox and not is_sandboxed(path):
        _log_err("mkdir", "destination not sandboxed.", locals())
        return False
    path = str(path)
    ret = _run(['mkdir', path])
    if (ret.returncode is not 0):
        logg_err("mkdir", "mkdir returned error: {0}".format(ret.returncode),
                 locals())
        return False
    else:
        return True


def rm(path, sandbox=True):
    """Remove path.

    Very dangerous. Calls 'rm -rf path'. sandbox=False will disable sandbox
    check.
    Returns false on error.
    """
    if sandbox and not is_sandboxed(path):
        _log_err("rm", "destination not sandboxed.", locals())
        return False
    path = str(path)
    ret = _run(['rm', '-rf', path])
    if (ret.returncode is not 0):
        _log_err("rm", "rm returned error: {0}".format(ret.returncode),
                 locals())
        return False
    else:
        return True


def _log_err(func, err, args):
    """Log myshutil error."""
    error_str = '{f} {e}'.format(f=func, e=err)
    for key in args.keys():
        error_str = error_str + '\n\t\t{k}:{v}'.format(k=key, v=args[key])
    logging.error(error_str)
    return


def _run(args):
    """Run myshutil command using subprocess.run.

    Captures stdout/stderr by default.
    Returns subprocess.CompletedProcess.
    """
    return subprocess.run(args,
                          stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT)
