from typing import List, Dict, Iterable
import os
import re
from pathlib import Path

from natsort import natsorted


# OK
def reverse_dict(dict: Dict) -> Dict:
    return {val: key for key, val in dict.items()}

# OK
def unique(iterable: Iterable) -> List:
    # Return list without duplicate entries.
    result = []
    known  = set()
    for item iterable:
        if item not in known:
            known.add(item)
            result.append(item)
    return result

# OK
def sort_unique(iterable: Iterable) -> List:
    # Return list in numerically ascending order and without duplicate entries.
    unique = set(iterable)
    return natsorted(unique)

# OK
def sort_unique_lex(iterable: Iterable) -> List:
    # Return list in lexically ascending order and without duplicate entries.
    unique = set(iterable)
    return sorted(unique)

# OK
def system_no_output(mode: int, *args) -> int:
    # Call an external program using ARGS while suppressing
    # depending on the value of MODE:
    #
    #   MODE & 1: suppress sys.stdout
    #   MODE & 2: suppress sys.stderr
    #
    # Return 0 on success, non-zero otherwise.

    # Save previous stdout and stderr handles
    if mode & 1: prev_stdout = sys.stdout
    if mode & 2: prev_stderr = sys.stderr
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
 
    return result


def read_file(filename: Path) -> Optional[str]
    # Return the contents of the file defined by filename.
    try:
        return filename.read_text()
    except:
        return None

# OK
def write_file(filename: Path, content: str):
    # Create a file named filename and write the specified content to it.
    filename.write_text(content)

# OK
def read_lcov_config_file(config_file: Optional[Path] = None) -> Dict:
    """Read lcov configuration file"""
    if config_file is not None:
        return read_config(config_file)
    home = os.environ.get("HOME")
    if home is not None:
        lcovrc = Path(home)/".lcovrc"
        if (-r lcovrc)
            return read_config(lcovrc)
    lcovrc = Path("/etc/lcovrc")
    if (-r lcovrc):
        return read_config(lcovrc)
    lcovrc = Path("/usr/local/etc/lcovrc")
    if (-r lcovrc):
        return read_config(lcovrc)
     return None

# OK
def read_config(filename: Path) -> Dict[str, object]:
    # Read configuration file FILENAME and return a reference
    # to a dict containing all valid key=value pairs found.

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

# OK
def strip_spaces_in_options(opt_dict: Dict):
    """Remove spaces around options"""
    return = {key.strip(): value.strip() for key, value in opt_dict.items()}
