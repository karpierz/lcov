# Copyright (c) 2020-2022, Adam Karpierz
# Licensed under the BSD license
# https://opensource.org/licenses/BSD-3-Clause

"""
util

"""

from typing import List, Dict, Iterable
import os
import re
from pathlib import Path

from natsort import natsorted


def reverse_dict(dict: Dict) -> Dict:
    return {val: key for key, val in dict.items()}


def unique(iterable: Iterable) -> List:
    """Return list without duplicate entries."""
    result = []
    known  = set()
    for item in iterable:
        if item not in known:
            known.add(item)
            result.append(item)
    return result


def sort_unique(iterable: Iterable) -> List:
    """Return list in numerically ascending order and without
    duplicate entries."""
    unique = set(iterable)
    return natsorted(unique)


def sort_unique_lex(iterable: Iterable) -> List:
    """Return list in lexically ascending order and without
    duplicate entries."""
    unique = set(iterable)
    return sorted(unique)


def remove_items_from_dict(dict: Dict, fns: List):
    """ """
    for fn in fns:
        dict.pop(fn, None)


NO_ERROR = 0

def system_no_output(mode: int, *args) -> Tuple[int, Optional["???"], Optional["???"]]:
    """Call an external program using ARGS while suppressing
    depending on the value of MODE:

      MODE & 1: suppress sys.stdout
      MODE & 2: suppress sys.stderr

    Return 0 on success, non-zero otherwise.
    """
    # Save previous stdout and stderr handles
    if mode & 1: prev_stdout = sys.stdout
    if mode & 2: prev_stderr = sys.stderr
    if mode & 4:
        pass
    else:
        # Redirect to /dev/null
        if mode & 1: sys.stdout = open(os.devnull, "wb")
        if mode & 2: sys.stderr = open(os.devnull, "wb")
    try:
        result = os.system(*args)
    finally:
        # Close redirected handles
        if mode & 1: sys.stdout.close()
        if mode & 2: sys.stderr.close()
        # Restore previous handles
        if mode & 1: sys.stdout = prev_stdout
        if mode & 2: sys.stderr = prev_stderr

    return (result, )

# NOK
def read_file(filename: Path) -> Optional[str]:
    """Return the contents of the file defined by filename."""
    try:
        return filename.read_text()
    except:
        return None


def write_file(filename: Path, content: str):
    """Create a file named filename and write the specified content to it."""
    filename.write_text(content)


def read_lcov_config_file(config_file: Optional[Path] = None) -> Dict:
    """Read lcov configuration file"""
    if config_file is not None:
        return read_config(config_file)
    HOME = os.environ.get("HOME")
    if HOME is not None:
        lcovrc = Path(HOME)/".lcovrc"
        if os.access(lcovrc, os.R_OK):
            return read_config(lcovrc)
    lcovrc = Path("/etc/lcovrc")
    if os.access(lcovrc, os.R_OK):
        return read_config(lcovrc)
    lcovrc = Path("/usr/local/etc/lcovrc")
    if os.access(lcovrc, os.R_OK):
        return read_config(lcovrc)
    return None


def read_config(filename: Path) -> Dict[str, object]:
    """Read configuration file FILENAME and return a reference
    to a dict containing all valid key=value pairs found.
    """
    try:
        file = filename.open("rt")
    except:
        warn(f"WARNING: cannot read configuration file {filename}\n")
        return None

    result = {}
    with file:
        for idx, line in enumerate(file):
            line = line.rstrip("\n")
            # Skip comments
            line = re.sub(r"#.*", "", line)
            # Remove leading and trailing blanks
            line = line.strip()
            if not line:
                continue
            key, val = re.split(r"\s*=\s*", line, 1)
            if key and val:
                result[key] = val
            else:
                warn(f"WARNING: malformed statement in line {idx + 1} "
                     f"of configuration file {filename}\n")

    return result

# NOK
def apply_config(ref: Dict):
    # REF is a reference to a dict containing the following mapping:
    #
    #   key_string => var_ref
    #
    # where KEY_STRING is a keyword and VAR_REF is a reference to an
    # associated variable. If the global configuration dicts OPT_RC
    # or CONFIG contain a value for keyword KEY_STRING, VAR_REF
    # will be assigned the value for that keyword.

    global opt_rc, config

    for key in ref.keys():
        if key in opt_rc:
            ref[key] = opt_rc[key]
        elif key in config:
            ref[key] = config[key]


def parse_ignore_errors(ignore_errors: Optional[List], ignore: Dict[int, bool]):
    """Parse user input about which errors to ignore."""

    # Defaults
    for item_id in ERROR_ID.values():
        ignore[item_id] = False

    if not ignore_errors: return

    items = []
    for item in ignore_errors:
        item = re.sub(r"\s", r"", item)
        if "," in item:
            # Split and add comma-separated parameters
            items += item.split(",")
        else:
            # Add single parameter
            items.append(item)

    for item in items:
        lc_item = item.lower()
        if lc_item not in ERROR_ID:
            die(f"ERROR: unknown argument for --ignore-errors: {item}")
        item_id = ERROR_ID[lc_item]
        ignore[item_id] = True


def strip_spaces_in_options(opt_dict: Dict[str, str]):
    """Remove spaces around options"""
    return {key.strip(): value.strip() for key, value in opt_dict.items()}

# NOK
def transform_pattern(pattern: str) -> str:
    """Transform shell wildcard expression to equivalent Perl regular expression.
    Return transformed pattern."""

    # Escape special chars
    pattern = re.sub("\\", "\\\\", pattern)
    pattern = re.sub("\/", "\\\/", pattern)
    pattern = re.sub("\^", "\\\^", pattern)
    pattern = re.sub("\$", "\\\$", pattern)
    pattern = re.sub("\(", "\\\(", pattern)
    pattern = re.sub("\)", "\\\)", pattern)
    pattern = re.sub("\[", "\\\[", pattern)
    pattern = re.sub("\]", "\\\]", pattern)
    pattern = re.sub("\{", "\\\{", pattern)
    pattern = re.sub("\}", "\\\}", pattern)
    pattern = re.sub("\.", "\\\.", pattern)
    pattern = re.sub("\,", "\\\,", pattern)
    pattern = re.sub("\|", "\\\|", pattern)
    pattern = re.sub("\+", "\\\+", pattern)
    pattern = re.sub("\!", "\\\!", pattern)

    # Transform ? => (.) and * => (.*)
    pattern = re.sub("\*", "\(\.\*\)", pattern)
    pattern = re.sub("\?", "\(\.\)",   pattern)

    return pattern

# NOK
def get_date_string() -> str:
    """Return the current date in the form: yyyy-mm-dd"""
    date_epoch = os.environ.get("SOURCE_DATE_EPOCH")
    if date_epoch is not None:
        timeresult = gmtime(date_epoch)
    else:
        timeresult = localtime()
    year, month, day, hour, min, sec = timeresult[5, 4, 3, 2, 1, 0]
    return "%d-%02d-%02d %02d:%02d:%02d" % (1900+year, month+1, day, hour, min, sec)


def warn(message, *, end="\n"):
    """ """
    import warnings
    warnings.warn(message + end)


def die(message, *, end="\n"):
    """ """
    import sys
    sys.exit(message + end)
