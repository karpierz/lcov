# Copyright (c) 2020-2022, Adam Karpierz
# Licensed under the BSD license
# https://opensource.org/licenses/BSD-3-Clause

"""
lcov

  This is a wrapper script which provides a single interface for accessing
  LCOV coverage data.

"""

# History:
#   2002-08-29 created by Peter Oberparleiter <Peter.Oberparleiter@de.ibm.com>
#                         IBM Lab Boeblingen
#   2002-09-05 / Peter Oberparleiter: implemented --kernel-directory +
#                multiple directories
#   2002-10-16 / Peter Oberparleiter: implemented --add-tracefile option
#   2002-10-17 / Peter Oberparleiter: implemented --extract option
#   2002-11-04 / Peter Oberparleiter: implemented --list option
#   2003-03-07 / Paul Larson: Changed to make it work with the latest gcov
#                kernel patch.  This will break it with older gcov-kernel
#                patches unless you change the value of $gcovmod in this script
#   2003-04-07 / Peter Oberparleiter: fixed bug which resulted in an error
#                when trying to combine .info files containing data without
#                a test name
#   2003-04-10 / Peter Oberparleiter: extended Paul's change so that LCOV
#                works both with the new and the old gcov-kernel patch
#   2003-04-10 / Peter Oberparleiter: added $gcov_dir constant in anticipation
#                of a possible move of the gcov kernel directory to another
#                file system in a future version of the gcov-kernel patch
#   2003-04-15 / Paul Larson: make info write to STDERR, not STDOUT
#   2003-04-15 / Paul Larson: added --remove option
#   2003-04-30 / Peter Oberparleiter: renamed --reset to --zerocounters
#                to remove naming ambiguity with --remove
#   2003-04-30 / Peter Oberparleiter: adjusted help text to include --remove
#   2003-06-27 / Peter Oberparleiter: implemented --diff
#   2003-07-03 / Peter Oberparleiter: added line checksum support, added
#                --no-checksum
#   2003-12-11 / Laurent Deniel: added --follow option
#   2004-03-29 / Peter Oberparleiter: modified --diff option to better cope with
#                ambiguous patch file entries, modified --capture option to use
#                modprobe before insmod (needed for 2.6)
#   2004-03-30 / Peter Oberparleiter: added --path option
#   2004-08-09 / Peter Oberparleiter: added configuration file support
#   2008-08-13 / Peter Oberparleiter: added function coverage support

#use strict;
#use warnings;

#use File::Basename;
#use File::Path;
#use File::Find;
#use File::Temp qw /tempdir/;
#use File::Spec::Functions qw / catdir catpath
#                  file_name_is_absolute rootdir splitdir splitpath/;
#use Getopt::Long;
#use Cwd qw //;

from typing import List, Dict, Optional
import argparse
import sys
import re
import shutil
from pathlib import Path

from .types import DB, LineData, BlockData, ChecksumData, InfoData, InfoEntry, BranchCountData
from .util import reverse_dict
from .util import read_file, write_file
from .util import apply_config
from .util import transform_pattern
from .util import system_no_output, NO_ERROR
from .util import strip_spaces_in_options
from .util import warn, die

# Global constants
tool_name    = Path(__file__).stem
lcov_version = "LCOV version " #+ `${abs_path(dirname($0))}/get_version.sh --full`
lcov_url     = "http://ltp.sourceforge.net/coverage/lcov.php"

# Specify coverage rate default precision
default_precision = 1

# Internal constants
GKV_PROC = 0  # gcov-kernel data in /proc via external patch
GKV_SYS  = 1  # gcov-kernel data in /sys via vanilla 2.6.31+
GKV_NAME = [
    "external",
    "upstream",
]
pkg_gkv_file   = ".gcov_kernel_version"
pkg_build_file = ".build_directory"

# Branch data combination types
BR_SUB = 0
BR_ADD = 1

# Global variables & initialization
options.gcov_dir:       Optional[Path] = None  # Directory containing gcov kernel files
options.tmp_dir:        Optional[Path] = None  # Where to create temporary directories
args.directory:         Optional[List] = None  # Specifies where to get coverage data from
args.kernel_directory:  Optional[List] = None  # If set, captures only from specified kernel subdirs
args.add_tracefile:     Optional[List] = None  # If set, reads in and combines all files in list
args.list:              Optional[str] = None   # If set, list contents of tracefile
args.extract:           Optional[str] = None   # If set, extracts parts of tracefile
args.remove:            Optional[str] = None   # If set, removes  parts of tracefile
args.diff:              Optional[str] = None   # If set, modifies tracefile according to diff
args.reset:             bool = False           # If set, reset all coverage data to zero
args.capture:           bool = False           # If set, capture data
args.output_filename:   Optional[str] = None   # Name for file to write coverage data to
args.test_name:         str = ""               # Test case name
args.quiet:             bool = False           # If set, suppress information messages
args.help:              bool = False           # Help option flag
args.version:           bool = False           # Version option flag
args.convert_filenames: bool = False           # If set, convert filenames when applying diff
args.strip:             Optional[int] = None   # If set, strip leading directories when applying diff
our $temp_dir_name;    # Name of temporary directory
args.follow:            bool =  False          # If set, indicates that find shall follow links
args.diff_path:         str = ""               # Path removed from tracefile when applying diff
options.fail_under_lines: int = 0
args.base_directory:    Optional[Path] = None  # Base directory (cwd of gcc during compilation)
args.checksum;        # If set, calculate a checksum for each line
args.no_checksum:       Optional[bool] = None  # If set, don't calculate a checksum for each line
args.compat_libtool:    Optional[bool] = None  # If set, indicates that libtool mode is to be enabled
args.no_compat_libtool: Optional[bool] = None  # If set, indicates that libtool mode is to be disabled
args.gcov_tool:         Optional[str] = None
args.ignore_errors:     List[str] = []         # Ignore certain error classes during processing
args.initial:           bool = False
args.include_patterns:  List[str] = []         # List of source file patterns to include
args.exclude_patterns:  List[str] = []         # List of source file patterns to exclude
args.no_recursion:      bool = False
args.to_package:        Optional[Path] = None
args.from_package:      Optional[Path] = None
args.no_markers:        bool = False
our $config;        # Configuration file contents
temp_dirs:              List[Path] = []
gcov_gkv:               int = ???""            # gcov kernel support version found on machine
args.derive_func_data:  Optional[???] = None
our opt.debug;
options.list_full_path: Optional[bool] = None
args.no_list_full_path: Optional[bool] = None
options.list_width:        int = 80
options.list_truncate_max: int = 20
args.external:          Optional[bool] = None
args.no_external:       Optional[bool] = None
args.config_file:       Optional[Path] = None
args.rc:                Dict[str, str] = {}
args.summary:           Optional[List] = None
args.compat:            Optional[str] = None
options.br_coverage:    bool = False
options.fn_coverage:    bool = True

ln_overall_found: Optional[int] = None
ln_overall_hit:   Optional[int] = None
fn_overall_found: Optional[int] = None
fn_overall_hit:   Optional[int] = None
br_overall_found: Optional[int] = None
br_overall_hit:   Optional[int] = None

cwd = Path.cwd()  # Current working directory

#
# Code entry point
#

# Check command line for a configuration file name
Getopt::Long::Configure("pass_through", "no_auto_abbrev")
GetOptions("config-file=s": \Path(args.config_file),
           "rc=s%":         \args.rc);
Getopt::Long::Configure("default");

# Remove spaces around rc options
args.rc = strip_spaces_in_options(args.rc)
# Read configuration file if available
$config = read_lcov_config_file(args.config_file)

if $config or args.rc:
    # Copy configuration file and --rc values to variables
    apply_config({
        "lcov_gcov_dir":          \Path(options.gcov_dir),
        "lcov_tmp_dir":           \options.tmp_dir,
        "lcov_list_full_path":    \options.list_full_path,
        "lcov_list_width":        \options.list_width,
        "lcov_list_truncate_max": \options.list_truncate_max,
        "lcov_branch_coverage":   \options.br_coverage,
        "lcov_function_coverage": \options.fn_coverage,
        "lcov_fail_under_lines":  \options.fail_under_lines,
    })

# Parse command line options
if (!GetOptions(
        "directory|d|di=s"     => \args.directory,
        "add-tracefile|a=s"    => \args.add_tracefile,
        "list|l=s"             => \args.list,
        "kernel-directory|k=s" => \args.kernel_directory,
        "extract|e=s"          => \args.extract,
        "remove|r=s"           => \args.remove,
        "diff=s"               => \args.diff,
        "convert-filenames"    => \args.convert_filenames,
        "strip=i"              => \args.strip,
        "capture|c"            => \args.capture,
        "output-file|o=s"      => \args.output_filename,
        "test-name|t=s"        => \args.test_name,
        "zerocounters|z"       => \args.reset,
        "quiet|q"              => \args.quiet,
        "help|h|?"             => \args.help,
        "version|v"            => \args.version,
        "follow|f"             => \args.follow,
        "path=s"               => \args.diff_path,
        "base-directory|b=s"   => \Path(args.base_directory),
        "checksum"             => \args.checksum,
        "no-checksum"          => \args.no_checksum,
        "compat-libtool"       => \args.compat_libtool,
        "no-compat-libtool"    => \args.no_compat_libtool,
        "gcov-tool=s"          => \args.gcov_tool,
        "ignore-errors=s"      => \args.ignore_errors,
        "initial|i"            => \args.initial,
        "include=s"            => \args.include_patterns,
        "exclude=s"            => \args.exclude_patterns,
        "no-recursion"         => \args.no_recursion,
        "to-package=s"         => \Path(args.to_package),
        "from-package=s"       => \Path(args.from_package),
        "no-markers"           => \args.no_markers,
        "derive-func-data"     => \args.derive_func_data,
        "debug"                => \args.debug,
        "list-full-path"       => \options.list_full_path,
        "no-list-full-path"    => \args.no_list_full_path,
        "external"             => \args.external,
        "no-external"          => \args.no_external,
        "summary=s"            => \args.summary,
        "compat=s"             => \args.compat,
        "config-file=s"        => \Path(args.config_file),
        "rc=s%"                => \args.rc,
        "fail-under-lines=s"   => \options.fail_under_lines,
        )):
    print(f"Use {tool_name} --help to get usage information", file=sys.stderr)
    sys.exit(1)

# Merge options
if args.no_checksum is not None:
    args.checksum = not args.no_checksum
if args.no_compat_libtool is not None:
    args.compat_libtool = not args.no_compat_libtool
    args.no_compat_libtool = None
if args.no_list_full_path is not None:
    options.list_full_path = not args.no_list_full_path
    del args.no_list_full_path
if args.no_external is not None:
    args.external = False
    del args.no_external

# Check for help option
if args.help:
    print_usage(sys.stdout)
    sys.exit(0)

# Check for version option
if args.version:
    print(f"{tool_name}: {lcov_version}")
    sys.exit(0)

# Check list width option
if options.list_width <= 40:
    die("ERROR: lcov_list_width parameter out of range (needs to be "
        "larger than 40)")

# Normalize --path text
args.diff_path = re.sub(r"/$", "", args.diff_path)

# Check for valid options
check_options()

# Only --extract, --remove and --diff allow unnamed parameters
if args.ARGV and not (args.extract is not None or
                      args.remove  is not None or
                      args.diff    is not None or
                      args.summary):
    die("Extra parameter found: '{}'\n".format(" ".join(args.ARGV)) +
        f"Use {tool_name} --help to get usage information")

# If set, indicates that data is written to stdout
# Check for output filename
data_to_stdout: bool = not (args.output_filename and args.output_filename != "-")

if args.capture:
    if data_to_stdout:
        # Option that tells geninfo to write to stdout
        args.output_filename = "-"

# Determine kernel directory for gcov data
if not args.from_package and not args.directory and (args.capture or args.reset):
    gcov_gkv, options.gcov_dir = setup_gkv()

our $exit_code = 0
# Check for requested functionality
if args.reset:
    data_to_stdout = False
    # Differentiate between user space and kernel reset
    if args.directory:
        userspace_reset()
    else:
        kernel_reset()
elif args.capture:
    # Capture source can be user space, kernel or package
    if args.from_package:
        package_capture()
    elif args.directory:
        userspace_capture()
    else:
        if args.initial:
            if args.to_package:
                die("ERROR: --initial cannot be used together with --to-package")
            kernel_capture_initial()
        else:
            kernel_capture()
elif args.add_tracefile:
    (ln_overall_found, ln_overall_hit,
     fn_overall_found, fn_overall_hit,
     br_overall_found, br_overall_hit) = add_traces()
elif args.remove is not None:
    (ln_overall_found, ln_overall_hit,
     fn_overall_found, fn_overall_hit,
     br_overall_found, br_overall_hit) = remove()
elif args.extract is not None:
    (ln_overall_found, ln_overall_hit,
     fn_overall_found, fn_overall_hit,
     br_overall_found, br_overall_hit) = extract()
elif args.list:
    data_to_stdout = False
    listing()
elif args.diff is not None:
    if len(args.ARGV) != 1:
        die("ERROR: option --diff requires one additional argument!\n"
            f"Use {tool_name} --help to get usage information")
    (ln_overall_found, ln_overall_hit,
     fn_overall_found, fn_overall_hit,
     br_overall_found, br_overall_hit) = diff()
elif args.summary:
    data_to_stdout = False
    (ln_overall_found, ln_overall_hit,
     fn_overall_found, fn_overall_hit,
     br_overall_found, br_overall_hit) = summary()
    $exit_code = check_rates(ln_overall_found, ln_overall_hit)

temp_cleanup()

if ln_overall_found is not None:
    print_overall_rate(True, ln_overall_found, ln_overall_hit,
                       True, fn_overall_found, fn_overall_hit,
                       True, br_overall_found, br_overall_hit)
else:
    if not args.list and not args.capture:
        info("Done.")

sys.exit($exit_code)


def print_usage(fhandle):
    """Print usage information."""
    global tool_name, lcov_url
    print(f"""\
Usage: {tool_name} [OPTIONS]

Use lcov to collect coverage data from either the currently running Linux
kernel or from a user space application. Specify the --directory option to
get coverage data for a user space program.

Misc:
  -h, --help                      Print this help, then exit
  -v, --version                   Print version number, then exit
  -q, --quiet                     Do not print progress messages

Operation:
  -z, --zerocounters              Reset all execution counts to zero
  -c, --capture                   Capture coverage data
  -a, --add-tracefile FILE        Add contents of tracefiles
  -e, --extract FILE PATTERN      Extract files matching PATTERN from FILE
  -r, --remove FILE PATTERN       Remove files matching PATTERN from FILE
  -l, --list FILE                 List contents of tracefile FILE
      --diff FILE DIFF            Transform tracefile FILE according to DIFF
      --summary FILE              Show summary coverage data for tracefiles

Options:
  -i, --initial                   Capture initial zero coverage data
  -t, --test-name NAME            Specify test name to be stored with data
  -o, --output-file FILENAME      Write data to FILENAME instead of stdout
  -d, --directory DIR             Use .da files in DIR instead of kernel
  -f, --follow                    Follow links when searching .da files
  -k, --kernel-directory KDIR     Capture kernel coverage data only from KDIR
  -b, --base-directory DIR        Use DIR as base directory for relative paths
      --convert-filenames         Convert filenames when applying diff
      --strip DEPTH               Strip initial DEPTH directory levels in diff
      --path PATH                 Strip PATH from tracefile when applying diff
      --(no-)checksum             Enable (disable) line checksumming
      --(no-)compat-libtool       Enable (disable) libtool compatibility mode
      --gcov-tool TOOL            Specify gcov tool location
      --ignore-errors ERRORS      Continue after ERRORS (gcov, source, graph)
      --no-recursion              Exclude subdirectories from processing
      --to-package FILENAME       Store unprocessed coverage data in FILENAME
      --from-package FILENAME     Capture from unprocessed data in FILENAME
      --no-markers                Ignore exclusion markers in source code
      --derive-func-data          Generate function data from line data
      --list-full-path            Print full path during a list operation
      --(no-)external             Include (ignore) data for external files
      --config-file FILENAME      Specify configuration file location
      --rc SETTING=VALUE          Override configuration file setting
      --compat MODE=on|off|auto   Set compat MODE (libtool, hammer, split_crc)
      --include PATTERN           Include files matching PATTERN
      --exclude PATTERN           Exclude files matching PATTERN
      --fail-under-lines MIN      Exit with a status of 1 if the total line
                                  coverage is less than MIN (summary option).

For more information see: {lcov_url}""", file=fhandle)


def check_options():
    """Check for valid combination of command line options.
    Die on error."""
    global args

    # Count occurrence of mutually exclusive options
    options = (
        args.reset,
        args.capture,
        args.add_tracefile,
        args.extract,
        args.remove,
        args.list,
        args.diff,
        args.summary,
    )
    count = len([1 for item in options if item])

    if count == 0:
        die("Need one of options -z, -c, -a, -e, -r, -l, "
            "--diff or --summary\n"
            f"Use {tool_name} --help to get usage information")
    elif count > 1:
        die("ERROR: only one of -z, -c, -a, -e, -r, -l, "
            "--diff or --summary allowed!\n"
            f"Use {tool_name} --help to get usage information")


#class LCov:


def userspace_reset():
    """Reset coverage data found in DIRECTORY by deleting all contained .da files.

    Die on error.
    """
    global args

    follow = "-follow" if args.follow else "" # NOK

    for dir in args.directory:
        info("Deleting all .da files in {}{}".format(dir,
             ("" if args.no_recursion else " and subdirectories")))
        for ext in ('*.da', '*.gcda'):
            for filepath in (Path(dir).glob(ext)
                             if args.no_recursion else
                             Path(dir).rglob(ext)):
                try:
                    filepath.unlink()
                except:
                    die(f"ERROR: cannot remove file {filename}!")


def userspace_capture():
    """Capture coverage data found in DIRECTORY and write it to a package
    (if TO_PACKAGE specified) or to OUTPUT_FILENAME or sys.stdout.

    Die on error.
    """
    global args

    if not args.to_package:
        lcov_geninfo(*args.directory)
        return

    if len(args.directory) != 1:
        die("ERROR: -d may be specified only once with --to-package")

    dir   = Path(args.directory[0])
    build = args.base_directory if args.base_directory is not None else dir

    create_package(args.to_package, dir, build)


def kernel_reset():
    """Reset kernel coverage.

    Die on error.
    """
    global options

    info("Resetting kernel execution counters")
    if (options.gcov_dir/"vmlinux").exists():
        reset_file = options.gcov_dir/"vmlinux"
    elif (options.gcov_dir/"reset").exists():
        reset_file = options.gcov_dir/"reset"
    else:
        die(f"ERROR: no reset control found in {options.gcov_dir}")
    try:
        reset_file.write("0")
    except:
        die(f"ERROR: cannot write to {reset_file}!")


def lcov_find(dir: Path, func: Callable, data: object, patterns: Optional[List] = None):
    """Search dir for files and directories whose name matches patterns and
    run func for each match. If not patterns is specified, match all names.
    
    func has the following prototype:
      func(dir: Path, relative_name, data)
    
    Where:
      dir: the base directory for this search
      relative_name: the name relative to the base directory of this entry
      data: the data variable passed to lcov_find
    """
    result = None

    def find_cb():
        nolocal dir, func, data, patterns
        nolocal result

        if result is not None: return

        filename = $File::Find::name; # NOK
        filename = Path(filename).relative_to(dir)

        for patt in patterns:
            if re.???(patt, filename.as_posix()): # NOK
                result = func(dir, filename, data)
                return

    if not patterns: patterns = [".*"]

    find({ wanted => find_cb, no_chdir => 1 }, str(dir)) # NOK

    return result


def lcov_copy(path_from: Path, path_to: Path, subdirs: List[object]):
    """Copy all specified subdirs and files from directory path_from
    to directory path_to.
    For regular files, copy file contents without checking its size.
    This is required to work with seq_file-generated files."""
    patterns = [rf"^{subd}" for subd in subdirs]
    lcov_find(path_from, lcov_copy_fn, path_to, patterns)


def lcov_copy_fn(path_from: Path, rel: Path, path_to: Path):
    """Copy directories, files and links from/rel to to/rel."""
    abs_from = Path(os.path.normpath(path_from/rel))
    abs_to   = Path(os.path.normpath(path_to/rel))

    if (-d): # NOK
        if (not -d $abs_to): # NOK
            try:
                mkpath($abs_to) # NOK
            except:
                die(f"ERROR: cannot create directory {abs_to}")
            abs_to.chmod(0o0700)
    elif (-l): # NOK
        # Copy symbolic link
        try:
            link = os.readlink(abs_from)
        except Exception as exc:
            die(f"ERROR: cannot read link {abs_from}: {exc}!")
        try:
            symlink($link, $abs_to) # NOK
        except Exception as exc:
            die(f"ERROR: cannot create link {abs_to}: {exc}!")
    else:
        lcov_copy_single(abs_from, abs_to)
        abs_to.chmod(0o0600)

    return None


def lcov_copy_single(path_from: Path, path_to: Path):
    """Copy single regular file path_from to path_to without checking
    its size.
    This is required to work with special files generated by the kernel
    seq_file-interface.
    """
    try:
        content = path_from.read_text()
    except Exception as exc:
        die(f"ERROR: cannot read {path_from}: {exc}!")
    try:
        path_to.write_text(content or "")
    except Exception as exc:
        die(f"ERROR: cannot write {path_to}: {exc}!")


def lcov_geninfo(*dirs):
    """Call geninfo for the specified directories and with the parameters
    specified at the command line."""
    global args

    dir_list = [str(dir) for dir in dirs]

    # Capture data
    info("Capturing coverage data from {}".format(" ".join(dir_list)))

    param = [f'"{sys.executable}"', "-m", "lcov.geninfo"] + dir_list
    if args.output_filename:
        param += ["--output-filename", str(args.output_filename)]
    if args.test_name:
        param += ["--test-name", args.test_name]
    if args.follow:
        param += ["--follow"]
    if args.quiet:
        param += ["--quiet"]
    if args.checksum is not None:
        param += ["--checksum"] if args.checksum else ["--no-checksum"]
    if args.base_directory:
        param += ["--base-directory", str(args.base_directory)]
    if args.no_compat_libtool:
        param += ["--no-compat-libtool"]
    elif args.compat_libtool:
        param += ["--compat-libtool"]
    if args.gcov_tool is not None:
        param += ["--gcov-tool", args.gcov_tool]
    for err in args.ignore_errors:
        param += ["--ignore-errors", err]
    if args.no_recursion:
        param += ["--no-recursion"]
    if args.initial:
        param += ["--initial"]
    if args.no_markers:
        param += ["--no-markers"]
    if args.derive_func_data:
        param += ["--derive-func-data"]
    if args.debug:
        param += ["--debug"]
    if args.external is not None and args.external:
        param += ["--external"]
    if args.external is not None and not args.external:
        param += ["--no-external"]
    if args.compat is not None:
        param += ["--compat", args.compat]
    if args.rc:
        for key, val in args.rc.items():
            param += ["--rc", f"{key}={val}"]
    if args.config_file is not None:
        param += ["--config-file", str(args.config_file)]
    for patt in args.include_patterns:
        param += ["--include", patt]
    for patt in args.exclude_patterns:
        param += ["--exclude", patt]

    exit_code = os.system(" ".join(param))
    if exit_code != NO_ERROR:
        sys.exit($? >> 8) # NOK


def get_package(package_file: Path) -> Tuple[Path, Optional[Path], Optional[int]]:
    """Unpack unprocessed coverage data files from package_file to a temporary
    directory and return directory name, build directory and gcov kernel version
    as found in package.
    """
    global pkg_gkv_file, pkg_build_file

    dir = create_temp_dir()
    cwd = Path.cwd()
    try:
        info(f"Reading package {package_file}:")

        package_file = package_file.resolve()

        os.chdir(dir)
        try:
            tar_process = subprocess.run(["tar", "xvfz", f"'{package_file}'"],
                                         capture_output=True, encoding="utf-8",
                                         check=True)
        except:
            die(f"ERROR: could not process package {package_file}")
        count = 0
        for line in tar_process.stdout.splitlines():
            if any(line.endswith(ext) for ext in (".da", ".gcda")):
                count += 1
        if count == 0:
            die(f"ERROR: no data file found in package {package_file}")
        info(f"  data directory .......: {dir}")
        fpath = dir/pkg_build_file
        build = read_file(fpath)
        if build is not None:
            build = Path(build)
            info(f"  build directory ......: {build}")
        fpath = dir/pkg_gkv_file
        gkv = read_file(fpath)
        if gkv is not None:
            gkv = int(gkv)
            if gkv != GKV_PROC and gkv != GKV_SYS:
                die(f"ERROR: unsupported gcov kernel version found ({gkv})")
            info("  content type .........: kernel data")
            info("  gcov kernel version ..: %s", GKV_NAME[gkv])
        else:
            info("  content type .........: application data")
        info(f"  data files ...........: {count}")
    finally:
        os.chdir(cwd)

    return (dir, build, gkv)


def count_package_data(filename: Path) -> Optional[int]:
    """Count the number of coverage data files in the specified package file."""
    try:
        tar_process = subprocess.run(["tar", "tfz", f"'{filename}'"],
                                     capture_output=True, encoding="utf-8",
                                     check=True)
    except:
        return None
    count = 0
    for line in tar_process.stdout.splitlines():
        if any(line.endswith(ext) for ext in (".da", ".gcda")):
            count += 1
    return count


def create_package(package_file: Path, dir: Path, build: Optional[Path],
                   gcov_kernel_version: Optional[int] = None)
    # ... , source_directory, build_directory, ...])
    """ """
    global args
    global pkg_gkv_file, pkg_build_file

    # Store unprocessed coverage data files from source_directory
    # to package_file.

    cwd = Path.cwd()
    try:
        # Check for availability of tar tool first
        try:
            subprocess.run(["tar", "--help"],
                           stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL,
                           check=True)
        exept
            die("ERROR: tar command not available")

        # Print information about the package
        info(f"Creating package {package_file}:")
        info(f"  data directory .......: {dir}")

        # Handle build directory
        if build is not None:
            info(f"  build directory ......: {build}")
            fpath = dir/pkg_build_file
            try:
                write_file(fpath, str(build))
            except:
                die(f"ERROR: could not write to {fpath}")

        # Handle gcov kernel version data
        if gcov_kernel_version is not None:
            info("  content type .........: kernel data")
            info("  gcov kernel version ..: %s", GKV_NAME[gcov_kernel_version])
            fpath = dir/pkg_gkv_file
            try:
                write_file(fpath, str(gcov_kernel_version))
            except:
                die(f"ERROR: could not write to {fpath}")
        else:
            info("  content type .........: application data")

        # Create package
        package_file = package_file.resolve()
        os.chdir(dir)
        try:
            subprocess.run(["tar", "cfz", f"'{package_file}'", "."],
                           check=True)
        except:
            die(f"ERROR: could not create package {package_file}")
    finally:
        os.chdir(cwd)

    # Remove temporary files
    (dir/pkg_build_file).unlink()
    (dir/pkg_gkv_file).unlink()

    # Show number of data files
    if not args.quiet:
        count = count_package_data(package_file)
        if count is not None:
            info(f"  data files ...........: {count}")


def get_base(dir: Path) -> Tuple[Optional[Path], Optional[Path]]:
    """Return (BASE, OBJ), where
     - BASE: is the path to the kernel base directory relative to dir
     - OBJ:  is the absolute path to the kernel build directory
    """

    marker = "kernel/gcov/base.gcno"

    marker_file = lcov_find(dir, find_link_fn, marker)
    if marker_file is None:
        return (None, None)

    # sys base is parent of parent of markerfile.
    sys_base = marker_file.parent.parent.parent.relative_to(dir)

    # build base is parent of parent of markerfile link target.
    try:
        link = Path(os.readlink(marker_file))
    except Exception as exc:
        die(f"ERROR: could not read {markerfile}")
    build = link.parent.parent.parent

    return (sys_base, build)


def find_link_fn(path_from: Path, rel: Path, filename) -> Optional[Path]:
    abs_file = path_from/rel/filename
    return abs_file if abs_file.is_symlink() else None

# NOK
def apply_base_dir($data: Path, $base: Optional[Path], $build: Optional[???], dirs: List[???]) -> List[???]:
    # apply_base_dir(data_dir, base_dir, build_dir, @directories)
    # Make entries in @directories relative to data_dir.
    global args

    $data = str($data)
    if $base is not None: $base = str($base)

    result: List[???] = []

    for $dir in dirs:

        # Is directory path relative to data directory?
        if (-d catdir($data, $dir)):
            result.append($dir)
            continue

        # Relative to the auto-detected base-directory?
        if $base is not None:
            if (-d catdir($data, $base, $dir)):
                result.append(catdir($base, $dir))
                continue

        # Relative to the specified base-directory?
        if args.base_directory is not None:
            if file_name_is_absolute(str(args.base_directory)):
                $base = args.base_directory.relative_to(rootdir())
            else:
                $base = args.base_directory
            $base = str($base)
            if (-d catdir($data, $base, $dir)):
                result.append(catdir($base, $dir))
                continue

        # Relative to the build directory?
        if $build is not None:
            if file_name_is_absolute($build):
                $base = str(Path($build).relative_to(rootdir()))
            else:
                $base = $build
            if (-d catdir($data, $base, $dir)):
                result.append(catdir($base, $dir))
                continue

        die(f"ERROR: subdirectory {dir} not found\n"
            "Please use -b to specify the correct directory")

    return result


def copy_gcov_dir(dir: Path, subdirs: List[object] = []) -> Path:
    """Create a temporary directory and copy all or, if specified,
    only some subdirectories from dir to that directory.
    Return the name of the temporary directory.
    """
    tempdir = create_temp_dir()

    info(f"Copying data to temporary directory {tempdir}")
    lcov_copy(dir, tempdir, subdirs)

    return tempdir


def kernel_capture_initial():
    """Capture initial kernel coverage data, i.e. create a coverage
    data file from static graph files which contains zero coverage data
    for all instrumented lines.
    """
    global options
    global args

    if args.base_directory is not None:
        build  = args.base_directory
        source = "specified"
    else:
        _, build = get_base(options.gcov_dir)
        if build is None:
            die("ERROR: could not auto-detect build directory.\n"
                "Please use -b to specify the build directory")
        source = "auto-detected"

    info(f"Using {build} as kernel build directory ({source})")
    # Build directory needs to be passed to geninfo
    args.base_directory = build
    params = []
    if args.kernel_directory:
        for dir in args.kernel_directory:
            params.append(build/dir)
    else:
        params.append(build)

    lcov_geninfo(*params)


def adjust_kernel_dir(dir: Path, build: Optional[Path]) -> Path:
    """Adjust directories specified with -k so that they point to the
    directory relative to dir.
    Return the build directory if specified or the auto-detected
    build-directory.
    """
    global args

    sys_base, build_auto = get_base(dir)
    if build is None:
        build = build_auto
    if build is None:
        die("ERROR: could not auto-detect build directory.\n"
            "Please use -b to specify the build directory")

    # Make kernel_directory relative to sysfs base
    if args.kernel_directory:
        args.kernel_directory = apply_base_dir(dir, sys_base, str(build),
                                               args.kernel_directory)
    return build


def kernel_capture():

    global options
    global args
    global gcov_gkv

    build = args.base_directory
    if gcov_gkv == GKV_SYS:
        build = adjust_kernel_dir(options.gcov_dir, build)

    data_dir = copy_gcov_dir(options.gcov_dir, args.kernel_directory)
    kernel_capture_from_dir(data_dir, gcov_gkv, build)


def kernel_capture_from_dir(dir: Path, gcov_kernel_version: int, build: Path):
    """Perform the actual kernel coverage capturing from the specified directory
    assuming that the data was copied from the specified gcov kernel version."""
    global args

    # Create package or coverage file
    if args.to_package:
        create_package(args.to_package, dir, build, gcov_kernel_version)
    else:
        # Build directory needs to be passed to geninfo
        args.base_directory = build
        lcov_geninfo(dir)


def link_data(targetdatadir: Path, targetgraphdir: Path, *, create: bool):
    # If CREATE is non-zero, create symbolic links in GRAPHDIR for
    # data files found in DATADIR. Otherwise remove link in GRAPHDIR.

    targetdatadir  = targetdatadir.resolve()
    targetgraphdir = targetgraphdir.resolve()

    op_data_cb = link_data_cb if create else unlink_data_cb,
    lcov_find(targetdatadir, op_data_cb, targetgraphdir, [r"\.gcda$", r"\.da$"])


def link_data_cb(datadir: Path, rel: Path, graphdir: Path):
    """Create symbolic link in graphdir/rel pointing to datadir/rel."""
    abs_from = datadir/rel
    abs_to   = graphdir/rel

    if abs_to.exists():
        die(f"ERROR: could not create symlink at {abs_to}: "
            "File already exists!")
    if abs_to.is_symlink():
        # Broken link - possibly from an interrupted earlier run
        abs_to.unlink()

    # Check for graph file
    base = re.sub(r"\.(gcda|da)$", "", str(abs_to))
    if (not Path(f"{base}.gcno").exists() and
        not Path(f"{base}.bbg").exists()  and
        not Path(f"{base}.bb").exists()):
        die("ERROR: No graph file found for {} in {}!".format(
            abs_from, dirname($base)))

    try:
        symlink(abs_from, abs_to) # NOK
    except Exception as exc:
        or die(f"ERROR: could not create symlink at {abs_to}: {exc}")


def unlink_data_cb(datadir: Path, rel: Path, graphdir: Path):
    """Remove symbolic link from graphdir/rel to datadir/rel."""
    abs_from = datadir/rel
    abs_to   = graphdir/rel

    if not abs_to.is_symlink():
        return
    try:
        target = Path(os.readlink(abs_to))
    except:
        return
    if target != abs_from:
        return

    try:
        abs_to.unlink()
    except Exception as exc:
        warn(f"WARNING: could not remove symlink {abs_to}: {exc}!")


def package_capture():
    """Capture coverage data from a package of unprocessed coverage data files
    as generated by lcov --to-package."""
    global args

    dir, build, gcov_kernel_version = get_package(args.from_package)
    # Check for build directory
    if args.base_directory is not None:
        if build is not None:
            info("Using build directory specified by -b.")
        build = args.base_directory

    # Do the actual capture
    if gcov_kernel_version is not None:
        if gcov_kernel_version == GKV_SYS:
            build = adjust_kernel_dir(dir, build)
        if args.kernel_directory:
            dir = copy_gcov_dir(dir, args.kernel_directory)
        kernel_capture_from_dir(dir, gcov_kernel_version, build)
    else:
        # Build directory needs to be passed to geninfo
        args.base_directory = build
        if find_graph(dir):
            # Package contains graph files - collect from there
            lcov_geninfo(dir)
        else:
            # No graph files found, link data files next to
            # graph files
            link_data(dir, args.base_directory, create=True)
            lcov_geninfo(args.base_directory)
            link_data(dir, args.base_directory, create=False)


def find_graph(dir: Path) -> bool:
    """Search dir for a graph file.
    Return True if one was found, False otherwise.
    """
    count = [0]
    lcov_find(dir, find_graph_cb, count, [r"\.gcno$", r"\.bb$", r"\.bbg$"])

    return count[0] > 0


def find_graph_cb(dir: Path, rel: Path, count: List[int]):
    """Count number of files found."""
    count[0] += 1


def create_temp_dir() -> Path:
    """Create a temporary directory and return its path.

    Die on error.
    """
    global options
    global temp_dirs

    try:
        if options.tmp_dir is not None:
            dir = Path(tempdir(DIR => str(options.tmp_dir), CLEANUP => 1)) # NOK
        else:
            dir = Path(tempdir(CLEANUP => 1)) # NOK
    except:
        die("ERROR: cannot create temporary directory")

    temp_dirs.append(dir)
    return dir


def compress_brcount(brcount: BranchCountData) -> Tuple[BranchCountData, int, int]:
    """ """
    db = brcount_to_db(brcount)
    return db_to_brcount(db, brcount)

# NOK
def read_info_file($tracefile) -> InfoData:
    # read_info_file(info_filename)
    #
    # Read in the contents of the .info file specified by INFO_FILENAME. Data will
    # be returned as a reference to a hash containing the following mappings:
    #
    # result: for each filename found in file -> \%data
    #
    # %data: "test"    -> \%testdata
    #        "sum"     -> \%sumcount
    #        "func"    -> \%funcdata
    #        "found"   -> $ln_found (number of instrumented lines found in file)
    #        "hit"     -> $ln_hit   (number of executed lines in file)
    #        "f_found" -> $fn_found (number of instrumented functions found in file)
    #        "f_hit"   -> $fn_hit   (number of executed functions in file)
    #        "b_found" -> $br_found (number of instrumented branches found in file)
    #        "b_hit"   -> $br_hit   (number of executed branches in file)
    #        "check"   -> \%checkdata
    #        "testfnc" -> \%testfncdata
    #        "sumfnc"  -> \%sumfnccount
    #        "testbr"  -> \%testbrdata
    #        "sumbr"   -> \%sumbrcount
    #
    # %testdata   : name of test affecting this file -> \%testcount
    # %testfncdata: name of test affecting this file -> \%testfnccount
    # %testbrdata:  name of test affecting this file -> \%testbrcount
    #
    # %testcount   : line number   -> execution count for a single test
    # %testfnccount: function name -> execution count for a single test
    # %testbrcount : line number   -> branch coverage data for a single test
    # %sumcount    : line number   -> execution count for all tests
    # %sumfnccount : function name -> execution count for all tests
    # %sumbrcount  : line number   -> branch coverage data for all tests
    # %funcdata    : function name -> line number
    # %checkdata   : line number   -> checksum of source code line
    # $brdata      : text "block,branch,taken:..."
    #
    # Note that .info file sections referring to the same file and test name
    # will automatically be combined by adding all execution counts.
    #
    # Note that if INFO_FILENAME ends with ".gz", it is assumed that the file
    # is compressed using GZIP. If available, GUNZIP will be used to decompress
    # this file.
    #
    # Die on error.

    global options

    my $data;            # Data handle for current entry
    my $testdata;        #       "             "
    my $testcount;       #       "             "
    my $sumcount;        #       "             "
    my $funcdata;        #       "             "
    my $checkdata;       #       "             "
    my $testfncdata;
    my $testfnccount;
    my $sumfnccount;
    my $testbrcount;
    my $sumbrcount;
    my $line;            # Current line read from .info file
    my $filename;            # Current filename
    my $count;            # Execution count of current line

    negative         = False  # If set, warn about negative counts
    changed_testname = False  # If set, warn about changed testname

    result: InfoData = {}  # Resulting hash: file -> data

    info("Reading tracefile $tracefile")

    # Check if file exists and is readable
    if not os.access($_[0], os.R_OK):
        die("ERROR: cannot read file $_[0]!")
    # Check if this is really a plain file
    fstatus = Path($_[0]).stat()
    if ! (-f _):
        die("ERROR: not a plain file: $_[0]!")

    # Check for .gz extension
    if $_[0] =~ /\.gz$/:
        # Check for availability of GZIP tool
        if system_no_output(1, "gunzip" ,"-h")[0] != NO_ERROR:
            die("ERROR: gunzip command not available!")

        # Check integrity of compressed file
        if system_no_output(1, "gunzip", "-t", $_[0])[0] != NO_ERROR:
            die("ERROR: integrity check failed for "
                "compressed file $_[0]!")

        # Open compressed file
        try:
            INFO_HANDLE = open("-|", "gunzip -c '$_[0]'")
        except:
            die("ERROR: cannot start gunzip to decompress file $_[0]!")
    else:
        # Open decompressed file
        try:
            INFO_HANDLE = open("rt", $_[0])
        except:
            die("ERROR: cannot read file $_[0]!")

    testname = ""  # Current test name
    with INFO_HANDLE:
        for line in INFO_HANDLE:
            line = line.rstrip("\n")

            match = re.match(r"^TN:([^,]*)(,diff)?", line)
            if match:
                # Test name information found
                testname = defined($1) ? $1 : "";
                if (testname =~ s/\W/_/g):
                    changed_testname = True
                testname .= $2 if (defined($2));
                continue

            match = re.match(r"^[SK]F:(.*)", line)
            if match:
                # Filename information found
                # Retrieve data for new entry
                $filename = $1;

                $data: Dict[str, object] = $result{$filename}
                ($testdata, $sumcount, $funcdata, $checkdata,
                 $testfncdata, $sumfnccount,
                 $testbrdata,  $sumbrcount,
                 _, _, _, _, _, _) = get_info_entry(data)

                if defined($testname):
                    testcount    = $testdata[testname]
                    testfnccount = $testfncdata[testname]
                    testbrcount  = $testbrdata[testname]
                else:
                    testcount    = {}
                    testfnccount = {}
                    testbrcount  = {}
                continue

            match = re.match(r"^DA:(\d+),(-?\d+)(,[^,\s]+)?", line)
            if match:
                # Fix negative counts
                $count = $2 < 0 ? 0 : $2;
                if $2 < 0:
                    negative = True
                # Execution count found, add to structure
                # Add summary counts
                $sumcount->{$1} += $count

                # Add test-specific counts
                if defined($testname):
                    $testcount->{$1} += $count

                # Store line checksum if available
                if defined($3):
                    line_checksum = $3[1:]
                    # Does it match a previous definition
                    if $1 in $checkdata and $checkdata->{$1} != line_checksum:
                        die(f"ERROR: checksum mismatch at {filename}:$1")
                    $checkdata->{$1} = line_checksum
                continue

            match = re.match(r"^FN:(\d+),([^,]+)", line)
            if match:
                if options.fn_coverage:
                    # Function data found, add to structure
                    $funcdata->{$2} = $1;

                    # Also initialize function call data
                    if (!defined($sumfnccount->{$2}))
                        $sumfnccount->{$2} = 0;

                    if defined($testname):
                        if (!defined($testfnccount->{$2}))
                            $testfnccount->{$2} = 0;
                continue

            match = re.match(r"^FNDA:(\d+),([^,]+)", line)
            if match:
                 if options.fn_coverage:
                    # Function call count found, add to structure
                    # Add summary counts
                    $sumfnccount->{$2} += $1;

                    # Add test-specific counts
                    if defined($testname):
                        $testfnccount->{$2} += $1;
                continue

            match = re.match(r"^BRDA:(\d+),(\d+),(\d+),(\d+|-)", line)
            if match:
                # Branch coverage data found
                if options.br_coverage:
                    lino, block, branch, taken = ($1, $2, $3, $4)
                    brcount = f"{block},{branch},{taken}:"
                    sumbrcount[lino] += brcount
                    # Add test-specific counts
                    if defined($testname):
                        testbrcount[lino] += brcount
                continue

            match = re.match(r"^end_of_record", line)
            if match:
                # Found end of section marker
                if $filename:
                    # Store current section data
                    if defined($testname):
                        testdata[testname]    = testcount
                        testfncdata[testname] = testfnccount
                        testbrdata[testname]  = testbrcount

                    set_info_entry($data,
                                   $testdata, $sumcount, $funcdata, $checkdata,
                                   $testfncdata, $sumfnccount,
                                   $testbrdata,  $sumbrcount)
                    $result{$filename} = $data
                    continue

    # Calculate hit and found values for lines and functions of each file
    for filename in list(result.keys()):
        data: Dict[str, object] = result[filename]

        (testdata, sumcount, _, _,
         testfncdata, sumfnccount,
         testbrdata,  sumbrcount,
         _, _, _, _, _, _) = get_info_entry(data)

        # Filter out empty files
        if len(sumcount) == 0:
            del result[filename]
            continue

        # Filter out empty test cases
        for testname in list(testdata.keys()):
            if testdata[testname] is None or len(testdata[testname]) == 0:
                del testdata[testname]
                delete($testfncdata[testname])

        hitcount = 0
        for count in sumcount.values():
            if count > 0:
                hitcount += 1
        data["found"] = len(sumcount)
        data["hit"]   = hitcount

        # Get found/hit values for function call data
        hitcount = 0
        for count in sumfnccount.values():
            if count > 0:
                hitcount += 1
        data["f_found"] = len(sumfnccount)
        data["f_hit"]   = hitcount

        # Combine branch data for the same branches
        _, data["b_found"], data["b_hit"] = compress_brcount(sumbrcount)
        for testname in testbrdata.keys():
            compress_brcount(testbrdata[testname])

    if no result:
        die(f"ERROR: no valid records found in tracefile {tracefile}")
    if negative:
        warn(f"WARNING: negative counts found in tracefile {tracefile}")
    if changed_testname:
        warn(f"WARNING: invalid characters removed from testname in tracefile {tracefile}")

    return result


def get_info_entry(info_entry: InfoEntry) -> Tuple:
    """Retrieve data from an info_entry of the structure generated by
    read_info_file().
    Return a tuple of references to dicts:
    (test data  dict, sum count   dict, funcdata   dict, checkdata  dict,
    testfncdata dict, sumfnccount dict, testbrdata dict, sumbrcount dict,
    lines     found, lines     hit,
    functions found, functions hit,
    branches  found, branches  hit)
    """
    testdata    = info_entry.get("test")
    sumcount    = info_entry.get("sum")
    funcdata    = info_entry.get("func")
    checkdata   = info_entry.get("check")
    testfncdata = info_entry.get("testfnc")
    sumfnccount = info_entry.get("sumfnc")
    testbrdata  = info_entry.get("testbr")
    sumbrcount  = info_entry.get("sumbr")
    ln_found: int = info_entry.get("found")
    ln_hit:   int = info_entry.get("hit")
    fn_found: int = info_entry.get("f_found")
    fn_hit:   int = info_entry.get("f_hit")
    br_found: int = info_entry.get("b_found")
    br_hit:   int = info_entry.get("b_hit")

    return (testdata, sumcount, funcdata, checkdata,
            testfncdata, sumfnccount,
            testbrdata,  sumbrcount,
            ln_found, ln_hit,
            fn_found, fn_hit,
            br_found, br_hit)


def set_info_entry(info_entry: InfoEntry,
                   testdata, sumcount, funcdata, checkdata,
                   testfncdata, sumfcncount,
                   testbrdata,  sumbrcount,
                   ln_found=None ln_hit=None
                   fn_found=None fn_hit=None
                   br_found=None br_hit=None):
    """Update the dict referenced by ENTRY with the provided data references."""
    info_entry["test"]    = testdata
    info_entry["sum"]     = sumcount
    info_entry["func"]    = funcdata
    info_entry["check"]   = checkdata
    info_entry["testfnc"] = testfncdata
    info_entry["sumfnc"]  = sumfcncount
    info_entry["testbr"]  = testbrdata
    info_entry["sumbr"]   = sumbrcount
    if ln_found is not None: info_entry["found"]   = ln_found
    if ln_hit   is not None: info_entry["hit"]     = ln_hit
    if fn_found is not None: info_entry["f_found"] = fn_found
    if fn_hit   is not None: info_entry["f_hit"]   = fn_hit
    if br_found is not None: info_entry["b_found"] = br_found
    if br_hit   is not None: info_entry["b_hit"]   = br_hit


def add_counts(data1: Dict[int, int],
               data2: Dict[int, int]) -> Tuple[Dict[int, int], int, int]:
    """DATA1 and DATA2 are references to hashes containing a mapping

      line number -> execution count

    Return a list (RESULT, LINES_FOUND, LINES_HIT) where RESULT is
    a reference to a hash containing the combined mapping in which
    execution counts are added.
    """

    result: Dict[int, int] = {}  # Resulting hash
    found  = 0  # Total number of lines found
    hit    = 0  # Number of lines with a count > 0

    for line, data1_count in data1.items():
        # Add counts if present in both hashes
        if line in data2:
            data1_count += data2[line]

        # Store sum in result
        result[line] = data1_count

        found += 1
        if data1_count > 0:
            hit += 1

    # Add lines unique to data2
    for line, data2_count in data2.items():
        # Skip lines already in data1
        if line in data1:
            continue

        # Copy count from data2
        result[line] = data2_count

        found += 1
        if data2_count > 0:
            hit += 1

    return (result, found, hit)


def merge_checksums(dict1: ChecksumData,
                    dict2: ChecksumData,
                    filename: str) -> ChecksumData:
    """dict1 and dict2 are dicts containing a mapping

      line number -> checksum

    Merge checksum lists defined in dict1 and dict2 and return resulting hash.
    Die if a checksum for a line is defined in both hashes but does not match.
    """
    result: ChecksumData = {}

    for line, val1 in dict1.items():
        if line in dict2 and val1 != dict2[line]:
            die(f"ERROR: checksum mismatch at {filename}:{line}")
        result[line] = val1

    for line, val2 in dict2.items():
          result[line] = val2

    return result


def merge_func_data(funcdata1: Optional[Dict[object, int]],
                    funcdata2: Dict[object, int],
                    filename: str) -> Dict[object, int]:
    """ """
    result: Dict[object, int] = funcdata1.copy() if funcdata1 is not None else {}
    for func, line in funcdata2.items():
        if func in result and line != result[func]:
            warn(f"WARNING: function data mismatch at {filename}:{line}")
            continue
        result[func] = line

    return result


def add_fnccount(fnccount1: Optional[Dict[object, int]],
                 fnccount2: Dict[object, int]) -> Tuple[Dict[object, int], int, int]:
    """Add function call count data.
    Return list (fnccount_added, fn_found, fn_hit)
    """
    result: Dict[object, int] = fnccount1.copy() if fnccount1 is not None else {}
    for func, ccount in fnccount2.items():
        result[func] += ccount

    fn_found = len(result)
    fn_hit   = 0
    for ccount in result.values():
        if ccount > 0:
            fn_hit += 1

    return (result, fn_found, fn_hit)


def add_testfncdata(testfncdata1: Dict[str, Tuple[Dict[object, int], int, int]],
                    testfncdata2: Dict[str, Tuple[Dict[object, int], int, int]]) -> Dict[str, Tuple[Dict[object, int], int, int]]:
    """Add function call count data for several tests.
    Return reference to added_testfncdata.
    """
    result: Dict[str, Tuple[Dict[object, int], int, int]] = {}

    for testname in testfncdata1.keys():
        if testname in testfncdata2:
            # Function call count data for this testname exists
            # in both data sets: merge
            result[testname] = add_fnccount(testfncdata1[testname],
                                            testfncdata2[testname])
        else:
            # Function call count data for this testname is unique to
            # data set 1: copy
            result[testname] = testfncdata1[testname]

    # Add count data for testnames unique to data set 2
    for testname in testfncdata2.keys():
        if testname not in result:
            result[testname] = testfncdata2[testname]

    return result


def brcount_db_combine(db1: DB, db2: DB, op: int):
    """db1 := db1 op db2, where
      db1, db2: brcount data as returned by brcount_to_db
      op:       one of BR_ADD and BR_SUB
    """
    for line, ldata in db2.items():
        for block, bdata in ldata.items():
           for branch, taken in bdata.items():
                if (line   not in db1 or
                    block  not in db1[line] or
                    branch not in db1[line][block] or
                    br_count == "-"):
                    if line  not in db1: db1[line] = {}
                    if block not in db1[line]: db1[line][block] = {}
                    db1[line][block][branch] = taken
                elif taken != "-":
                    if op == BR_ADD:
                        db1[line][block][branch] += taken
                    elif op == BR_SUB:
                        db1[line][block][branch] -= taken
                        if db1[line][block][branch] < 0:
                            db1[line][block][branch] = 0


def brcount_db_get_found_and_hit(db: DB) -> Tuple[int, int]:
    # Return (br_found, br_hit) for db.
    br_found, br_hit = 0, 0
    for line, ldata in db.items():
        for block, bdata in ldata.items():
            for branch, taken in bdata.items():
                br_found += 1
                if taken != "-" and taken > 0:
                    br_hit += 1
    return (br_found, br_hit)


def combine_brcount(brcount1: BranchCountData,
                    brcount2: BranchCountData,
                    op, *, inplace: bool = False) -> Tuple[BranchCountData, int, int]:
    """If op is BR_ADD, add branch coverage data and return list brcount_added.
    If op is BR_SUB, subtract the taken values of brcount2 from brcount1 and
    return brcount_sub.
    If inplace is set, the result is inserted into brcount1.
    """
    db1 = brcount_to_db(brcount1)
    db2 = brcount_to_db(brcount2)
    brcount_db_combine(db1, db2, op)
    return db_to_brcount(db1, brcount1 if inplace else None)


def brcount_to_db(brcount: BranchCountData) -> DB:
    """Convert brcount data to the following format:
     db:          line number    -> block dict
     block  dict: block number   -> branch dict
     branch dict: branch number  -> taken value
    """
    db: DB = {}
    # Add branches to database
    for line, brdata in brcount.items():
        for entry in brdata.split(":"):
            block, branch, taken = entry.split(",")
            if (line   not in db or
                block  not in db[line] or
                branch not in db[line][block] or
                db[line][block][branch] == "-"):
                if line  not in db: db[line] = {}
                if block not in db[line]: db[line][block] = {}
                db[line][block][branch] = taken
            elif taken != "-":
                db[line][block][branch] += taken

    return db


def db_to_brcount(db: DB,
                  brcount: Optional[BranchCountData] = None) -> Tuple[BranchCountData, int, int]:
    """Convert branch coverage data back to brcount format.
    If brcount is specified, the converted data is directly inserted in brcount.
    """
    if brcount is None: brcount = {}
    br_found = 0
    br_hit   = 0
    # Convert database back to brcount format
    for line in sorted(db.keys()):
        ldata: LineData = db[line]
        brdata = ""
        for block in sorted({$a <=> $b} ldata.keys()): # NOK
            bdata: BlockData = ldata[block]
            for branch in sorted({$a <=> $b} bdata.keys()): # NOK
                taken = bdata[branch]
                br_found += 1
                if taken != "-" and int(taken) > 0:
                    br_hit += 1
                brdata += f"{block},{branch},{taken}:"
        brcount[line] = brdata

    return (brcount, br_found, br_hit)


def add_testbrdata(testbrdata1: Dict,
                   testbrdata2: Dict) -> Dict:
    """Add branch coverage data for several tests.
    Return reference to added_testbrdata.
    """
    result = {}

    for testname in testbrdata1.keys():
        if testname in testbrdata2:
            # Branch coverage data for this testname exists
            # in both data sets: add
            result[testname] = combine_brcount(testbrdata1[testname],
                                               testbrdata2[testname],
                                               BR_ADD)
        else:
            # Branch coverage data for this testname is unique to
            # data set 1: copy
            result[testname] = testbrdata1[testname]

    # Add count data for testnames unique to data set 2
    for testname in testbrdata2.keys():
        if testname not in result:
            result[testname] = testbrdata2[testname]

    return result


def combine_info_files(info1: InfoData,
                       info2: InfoData) -> InfoData:
    """Combine .info data in infos referenced by INFO_REF1 and INFO_REF2.
    Return reference to resulting info."""

    info1 = info1.copy()

    for filename in info2.keys():
        if filename in info1:
            # Entry already exists in info1, combine them
            info1[filename] = combine_info_entries(info1[filename],
                                                   info2[filename],
                                                   filename)
        else:
            # Entry is unique in both infos, simply add to
            # resulting info
            info1[filename] = info2[filename]

    return info1


def combine_info_entries(entry1: InfoEntry,
                         entry2: InfoEntry,
                         filename: str) -> InfoEntry:
    """Combine .info data entry hashes referenced by ENTRY1 and ENTRY2.
    Return reference to resulting hash."""

    # Retrieve data
    (testdata1, _, funcdata1, checkdata1,
     testfncdata1, sumfnccount1,
     testbrdata1,  sumbrcount1,
     _, _, _, _, _, _) = get_info_entry(entry1)
    (testdata2, _, funcdata2, checkdata2,
     testfncdata2, sumfnccount2,
     testbrdata2,  sumbrcount2,
     _, _, _, _, _, _) = get_info_entry(entry2)

    # Merge checksums
    result_checkdata = merge_checksums(checkdata1, checkdata2, filename)

    # Combine funcdata
    result_funcdata = merge_func_data(funcdata1, funcdata2, filename)

    # Combine function call count data
    result_testfncdata = add_testfncdata(testfncdata1, testfncdata2)
    result_sumfnccount, fn_found, fn_hit = add_fnccount(sumfnccount1,
                                                        sumfnccount2)
    # Combine branch coverage data
    result_testbrdata = add_testbrdata(testbrdata1, testbrdata2)
    result_sumbrcount, br_found, br_hit = combine_brcount(sumbrcount1,
                                                          sumbrcount2,
                                                          BR_ADD)
    # Combine testdata

    result_testdata: Dict[object, Tuple[Dict[int, int], int, int]] = {}
    result_sumcount: Dict[int, int] = {}

    for testname in testdata1.keys():
        if testname in testdata2:
            # testname is present in both entries, requires combination
            result_testdata[testname] = add_counts(testdata1[testname],
                                                   testdata2[testname])
        else:
            # testname only present in entry1, add to result
            result_testdata[testname] = testdata1[testname]
        # update sum count hash
        result_sumcount, ln_found, ln_hit = add_counts(result_sumcount,
                                                       result_testdata[testname])

    for testname in testdata2.keys():
        # Skip testnames already covered by previous iteration
        if testname in testdata1:
            continue
        # testname only present in entry2, add to result hash
        result_testdata[testname] = testdata2[testname]
        # update sum count hash
        result_sumcount, ln_found, ln_hit = add_counts(result_sumcount,
                                                       result_testdata[testname])
    # Calculate resulting sumcount

    # Store result
    result: InfoEntry = {}  # Hash containing combined entry
    set_info_entry(result,
                   result_testdata, result_sumcount, result_funcdata, result_checkdata,
                   result_testfncdata, result_sumfnccount,
                   result_testbrdata,  result_sumbrcount,
                   ln_found, ln_hit,
                   fn_found, fn_hit,
                   br_found, br_hit)

    return result


def add_traces() -> Tuple[int, int, int, int, int, int]:
    """ """
    global args
    global data_to_stdout

    info("Combining tracefiles.")

    total_trace: InfoData = None
    for tracefile in args.add_tracefile:
        current = read_info_file(tracefile)
        total_trace = (current if total_trace is None
                       else combine_info_files(total_trace, current))

    # Write combined data
    if not data_to_stdout:
        info(f"Writing data to {args.output_filename}")
        try:
            with Path(args.output_filename).open("wt") as fhandle:
                result = write_info_file(fhandle, total_trace)
        except:
            die(f"ERROR: cannot write to {args.output_filename}!")
    else:
        result = write_info_file(sys.stdout, total_trace)

    return result


def write_info_file(fhandle, info_data: InfoData) -> Tuple[int, int, int, int, int, int]:
    """ """
    global args

    ln_total_found = 0
    ln_total_hit   = 0
    fn_total_found = 0
    fn_total_hit   = 0
    br_total_found = 0
    br_total_hit   = 0

    for source_file in sorted(info_data.keys()):
        entry = info_data[source_file]

        (testdata,    sumcount, funcdata, checkdata,
         testfncdata, sumfnccount,
         testbrdata,  sumbrcount,
         ln_found,    ln_hit,
         fn_found,    fn_hit,
         br_found,    br_hit) = get_info_entry(entry)

        # Add to totals
        ln_total_found += ln_found
        ln_total_hit   += hit
        fn_total_found += fn_found
        fn_total_hit   += fn_hit
        br_total_found += br_found
        br_total_hit   += br_hit

        for testname in sorted(testdata.keys()):

            testlncount  = testdata[testname]
            testfnccount = testfncdata[testname]
            testbrcount  = testbrdata[testname]

            print(f"TN:{testname}",    file=fhandle)
            print(f"SF:{source_file}", file=fhandle)

            # Write function related data
            for func in sorted({funcdata[$a] <=> funcdata[$b]} funcdata.keys()): # NOK
                fndata = funcdata[func]
                print(f"FN:{fndata},{func}", file=fhandle)

            for func, ccount in testfnccount.items():
                print(f"FNDA:{ccount},{func}", file=fhandle)

            fn_found, fn_hit = get_func_found_and_hit(testfnccount)
            print(f"FNF:{fn_found}", file=fhandle)
            print(f"FNH:{fn_hit}",   file=fhandle)

            # Write branch related data
            br_found = 0
            br_hit   = 0
            for line in sorted({$a <=> $b} testbrcount.keys()): # NOK
                brdata = testbrcount[line]
                for brentry in brdata.split(":"):
                    block, branch, taken = brentry.split(",")
                    print(f"BRDA:{line},{block},{branch},{taken}", file=fhandle)
                    br_found += 1
                    if taken != "-" and int(taken) > 0:
                        br_hit += 1

            if br_found > 0:
                print(f"BRF:{br_found}", file=fhandle)
                print(f"BRH:{br_hit}",   file=fhandle)

            # Write line related data
            ln_found = 0
            ln_hit   = 0
            for line in sorted({$a <=> $b} testlncount.keys()): # NOK
                lndata = testlncount[line]
                print(f"DA:{line},{lndata}" +
                      (("," + checkdata[line]) if line in checkdata and args.checksum else ""),
                      file=fhandle)
                ln_found += 1
                if lndata > 0:
                    ln_hit += 1

            print(f"LF:{ln_found}", file=fhandle)
            print(f"LH:{ln_hit}",   file=fhandle)
            print("end_of_record",  file=fhandle)

    return (ln_total_found, ln_total_hit,
            fn_total_found, fn_total_hit,
            br_total_found, br_total_hit)


def extract() -> Tuple[int, int, int, int, int, int]:
    """ """
    global args
    global data_to_stdout

    data: InfoData = read_info_file(args.extract)

    # Need perlreg expressions instead of shell pattern
    pattern_list: List[str] = [transform_pattern(elem) for elem in args.ARGV]

    # Filter out files which do not match any pattern
    extracted = 0
    for filename in sorted(data.keys()):
        keep = False
        for pattern in pattern_list:
            match = re.match(rf"^{pattern}$", filename)
            keep = keep or match

        if not keep:
            del data[filename]
        else:
            info(f"Extracting {filename}")
            extracted += 1

    # Write extracted data
    if not data_to_stdout:
        info(f"Extracted {extracted} files")
        info(f"Writing data to {args.output_filename}")
        try:
            with Path(args.output_filename).open("wt") as fhandle:
                result = write_info_file(fhandle, data)
        except:
            die(f"ERROR: cannot write to {args.output_filename}!")
    else:
        result = write_info_file(sys.stdout, data)

    return result


def remove() -> Tuple[int, int, int, int, int, int]:
    """ """
    global args
    global data_to_stdout

    data: InfoData = read_info_file(args.remove)

    # Need perlreg expressions instead of shell pattern
    pattern_list: List[str] = [transform_pattern(elem) for elem in args.ARGV]

    removed = 0
    # Filter out files that match the pattern
    for filename in sorted(data.keys()):
        match_found = False
        for pattern in pattern_list:
            match = re.match(rf"^{pattern}$", filename)
            match_found = match_found or match

        if match_found:
            del data[filename]
            info(f"Removing {filename}")
            removed += 1

    # Write data
    if not data_to_stdout:
        info(f"Deleted {removed} files")
        info(f"Writing data to {args.output_filename}")
        try:
            with Path(args.output_filename).open("wt") as fhandle:
                result = write_info_file(fhandle, data)
        except:
            die(f"ERROR: cannot write to {args.output_filename}!")
    else:
        result = write_info_file(sys.stdout, data)

    return result

# NOK
def get_prefix($max_width, $max_long, @path_list):
    # get_prefix(max_width, max_percentage_too_long, path_list)
    #
    # Return a path prefix that satisfies the following requirements:
    # - is shared by more paths in path_list than any other prefix
    # - the percentage of paths which would exceed the given max_width length
    #   after applying the prefix does not exceed max_percentage_too_long
    #
    # If multiple prefixes satisfy all requirements, the longest prefix is
    # returned. Return an empty string if no prefix could be found.

    $ENTRY_NUM  = 0
    $ENTRY_LONG = 1

    %prefix = {}
    # Build prefix hash
    for $path in @path_list:
        $v, $d, $f = splitpath($path)
        @dirs  = splitdir($d)
        $p_len = length($path)

        # Remove trailing '/'
        if $dirs[len(@dirs) - 1] == '':
            pop(@dirs)
        for ($i = 0; $i < len(@dirs); $i++):
            $subpath = catpath($v, catdir(@dirs[0..$i]), '')
            $entry   = $prefix{$subpath}

            if ! defined($entry): $entry = [ 0, 0 ]
            $entry->[$ENTRY_NUM] += 1
            if ($p_len - length($subpath) - 1) > $max_width:
                $entry->[$ENTRY_LONG] += 1
            $prefix{$subpath} = $entry;

    # Find suitable prefix (sort descending by two keys: 1. number of
    # entries covered by a prefix, 2. length of prefix)
    for $path in (sort {($prefix{$a}->[$ENTRY_NUM] ==
                         $prefix{$b}->[$ENTRY_NUM]) ?
                             length($b) <=> length($a) :
                             $prefix{$b}->[$ENTRY_NUM] <=> $prefix{$a}->[$ENTRY_NUM]}
                         keys(%prefix)):
        my ($num, $long) = @{$prefix{$path}};

        # Check for additional requirement: number of filenames
        # that would be too long may not exceed a certain percentage
        if $long <= $num * $max_long / 100:
            return $path;

    return ""

# NOK
def listing():
    """ """
    global options
    global args

    F_LN_NUM  = 0
    F_LN_RATE = 1
    F_FN_NUM  = 2
    F_FN_RATE = 3
    F_BR_NUM  = 4
    F_BR_RATE = 5

    fwidth_narrow = (5, 5, 3, 5, 4, 5)
    fwidth_wide   = (6, 5, 5, 5, 6, 5)

    data: InfoData = read_info_file(args.list)

    fwidth = fwidth_wide

    max_width = options.list_width
    max_long  = options.list_truncate_max

    got_prefix  = False
    root_prefix = False

    # Calculate total width of narrow fields
    fwidth_narrow_length = 0
    for width in fwidth_narrow:
        fwidth_narrow_length += width + 1
    # Calculate total width of wide fields
    fwidth_wide_length = 0
    for width in fwidth_wide:
        fwidth_wide_length += width + 1
    # Get common file path prefix
    prefix = get_prefix(max_width - fwidth_narrow_length, max_long, list(data.keys()))
    if len(prefix) > 0:     got_prefix  = True
    if prefix == rootdir(): root_prefix = True
    prefix =~ s/\/$//; # NOK

    # Get longest filename length
    strlen = len("Filename")
    for filename in data.keys():
        if not options.list_full_path:
            if not got_prefix or not root_prefix and ! (filename =~ s/^\Q{prefix}\/\E//):
                $v, $d, $f = splitpath(filename)
                filename = $f
        # Determine maximum length of entries
        strlen = max(strlen, len(filename))

    if not options.list_full_path:
        width = fwidth_wide_length
        # Check if all columns fit into max_width characters
        if strlen + fwidth_wide_length > max_width:
            # Use narrow fields
            fwidth = fwidth_narrow
            width = fwidth_narrow_length
            if strlen + fwidth_narrow_length > max_width:
                # Truncate filenames at max width
                strlen = max_width - fwidth_narrow_length

        # Add some blanks between filename and fields if possible
        blanks = int(strlen * 0.5)
        if blanks < 4: blanks = 4
        if blanks > 8: blanks = 8
        if strlen + width + blanks < max_width:
            strlen += blanks
        else:
            strlen = max_width - width

    # Filename
    w = strlen
    format   = f"%-${w}s|"
    heading1 = "%*s|"  % (w, "")
    heading2 = "%-*s|" % (w, "Filename")
    barlen   = w + 1
    # Line coverage rate
    w = fwidth[F_LN_RATE]
    format   += f"%${w}s "
    heading1 += "%-*s |" % (w + fwidth[F_LN_NUM], "Lines")
    heading2 += "%-*s "  % (w, "Rate")
    barlen   += w + 1
    # Number of lines
    w = fwidth[F_LN_NUM]
    format   += f"%${w}s|"
    heading2 += "%*s|" % (w, "Num")
    barlen   += w + 1
    # Function coverage rate
    w = fwidth[F_FN_RATE]
    format   += f"%${w}s "
    heading1 += "%-*s|" % (w + fwidth[F_FN_NUM] + 1, "Functions")
    heading2 += "%-*s " % (w, "Rate")
    barlen   += w + 1
    # Number of functions
    w = fwidth[F_FN_NUM]
    format   += f"%${w}s|"
    heading2 += "%*s|" % (w, "Num")
    barlen   += w + 1
    # Branch coverage rate
    w = fwidth[F_BR_RATE]
    format   += f"%${w}s "
    heading1 += "%-*s"  % (w + fwidth[F_BR_NUM] + 1, "Branches")
    heading2 += "%-*s " % (w, "Rate")
    barlen   += w + 1
    # Number of branches
    w = fwidth[F_BR_NUM]
    format   += f"%${w}s"
    heading2 += "%*s" % (w, "Num")
    barlen   += w
    # Line end
    format   += "\n"
    heading1 += "\n"
    heading2 += "\n"

    # Print heading
    print(heading1)
    print(heading2)
    # Print separator
    print("=" * barlen + "\n")

    ln_total_found = 0
    ln_total_hit   = 0
    fn_total_found = 0
    fn_total_hit   = 0
    br_total_found = 0
    br_total_hit   = 0

    # Print per file information
    lastpath = None
    for filename in sorted(data.keys()):
        entry = data[filename]
        print_filename = filename

        if not options.list_full_path:
            if not got_prefix or not root_prefix and ! (print_filename =~ s/^\Q{prefix}\/\E//):
                $v, $d, $f = splitpath(filename)
                $p = catpath($v, $d, "");
                $p =~ s/\/$//;
                print_filename = $f;
            else:
                $p = prefix

            if lastpath is None or lastpath != $p:
                if lastpath is not None: print()
                lastpath = $p;
                if not root_prefix:
                    print(f"[{lastpath}/]")
            print_filename = shorten_filename(print_filename, strlen)

        (_, _, _, _, _, _, _, _,
         ln_found, ln_hit,
         fn_found, fn_hit,
         br_found, br_hit) = get_info_entry(entry)

        # Assume zero count if there is no function data for this file
        if fn_found is None or fn_hit is None:
            fn_found = 0
            fn_hit   = 0
        # Assume zero count if there is no branch data for this file
        if br_found is None or br_hit is None:
            br_found = 0
            br_hit   = 0

        # Add line coverage totals
        ln_total_found += ln_found
        ln_total_hit   += ln_hit
        # Add function coverage totals
        fn_total_found += fn_found
        fn_total_hit   += fn_hit
        # Add branch coverage totals
        br_total_found += br_found
        br_total_hit   += br_hit

        # Determine line coverage rate for this file
        lnrate = shorten_rate(ln_hit, ln_found, fwidth[F_LN_RATE])
        # Determine function coverage rate for this file
        fnrate = shorten_rate(fn_hit, fn_found, fwidth[F_FN_RATE])
        # Determine branch coverage rate for this file
        brrate = shorten_rate(br_hit, br_found, fwidth[F_BR_RATE])

        # Assemble line parameters
        file_data = []
        file_data.append(print_filename)
        file_data.append(lnrate)
        file_data.append(shorten_number(ln_found, fwidth[F_LN_NUM]))
        file_data.append(fnrate)
        file_data.append(shorten_number(fn_found, fwidth[F_FN_NUM]))
        file_data.append(brrate)
        file_data.append(shorten_number(br_found, fwidth[F_BR_NUM]))
        # Print assembled line
        print(format % file_data)

    # Determine total line coverage rate
    lnrate = shorten_rate(ln_total_hit, ln_total_found, fwidth[F_LN_RATE])
    # Determine total function coverage rate
    fnrate = shorten_rate(fn_total_hit, fn_total_found, fwidth[F_FN_RATE])
    # Determine total branch coverage rate
    brrate = shorten_rate(br_total_hit, br_total_found, fwidth[F_BR_RATE])

    # Print separator
    print("=" * barlen + "\n")

    # Assemble line parameters
    footer = []
    footer.append("%*s", % (strlen, "Total:"))
    footer.append(lnrate)
    footer.append(shorten_number(ln_total_found, fwidth[F_LN_NUM]))
    footer.append(fnrate)
    footer.append(shorten_number(fn_total_found, fwidth[F_FN_NUM]))
    footer.append(brrate)
    footer.append(shorten_number(br_total_found, fwidth[F_BR_NUM]))
    # Print assembled line
    printf(format % footer)


def shorten_filename(filename: str, width: int) -> str:
    """Truncate filename if it is longer than width characters."""
    # !!! przetestowac zgodnosc z Perlowa wersja !!!
    l = len(filename)
    if l <= width:
        return filename
    e = (width - 3) // 2
    s = (width - 3) - e
    return filename[:s] + "..." + filename[l - e:]


def shorten_number(number: int, width: int) -> str:
    """ """
    result = "%*d" % (width, number)
    if len(result) <= width:
        return result
    number //= 1000;
    result = "%*dk" % (width - 1, number)
    if len(result) <= width:
        return result
    number //= 1000;
    result = "%*dM" % (width - 1, number)
    if len(result) <= width:
        return result
    return "#"


def shorten_rate(hit: int, found: int, width: int) -> str:
    """ """
    result = rate(hit, found, "%", 1, width)
    if len(result) <= width:
        return result
    result = rate(hit, found, "%", 0, width)
    if len(result) <= width:
        return result
    return "#"


def strip_directories(path: str, depth: Optional[int] = None) -> str:
    """Remove depth leading directory levels from path."""
    if depth is not None and depth >= 1:
        for _ in range(depth):
            path = re.sub(r"^[^/]*/+(.*)$", r"\1", path)
    return path


def apply_diff_to_brcount(brcount:  BranchCountData,
                          linedata: Dict[int, int]) -> Tuple[BranchCountData, int, int]:
    """Adjust line numbers of branch coverage data according to linedata.

    Convert brcount to db format
    """
    db = brcount_to_db(brcount)
    # Apply diff to db format
    db = apply_diff(db, linedata)
    # Convert db format back to brcount format
    return db_to_brcount(db)


def apply_diff_to_funcdata(funcdata: Dict[object, int],
                           linedata: Dict[int, int]) -> Dict[object, int]:
    """ """
    last_new  = get_dict_max(linedata)
    last_old  = linedata[last_new]
    line_diff = reverse_dict(linedata)

    result: Dict[object, int] = {}
    for func, line in funcdata.items():
        if line in line_diff:
            result[func] = line_diff[line]
        elif line > last_old:
            result[func] = line + (last_new - last_old)

    return result


def get_dict_max(dict: Dict[int, int]) -> int:
    """Return the highest integer key from hash."""
    key_max = None
    for key, val in dict.items():
        if key_max is None or val > key_max:
            key_max = key
    return key_max


def diff() -> Tuple[int, int, int, int, int, int]:
    """ """
    global args
    global data_to_stdout

    trace_data: InfoData = read_info_file(args.diff)
    diff_data, path_data = read_diff(Path(args.ARGV[0]))

    path_conversion_data: Dict[str, str] = {}
    unchanged = 0
    converted = 0
    for filename in sorted(trace_data.keys()):

        # Find a diff section corresponding to this file
        line_hash_result = get_line_hash(filename, diff_data, path_data)
        if line_hash_result is None:
            # There's no diff section for this file
            unchanged += 1
            continue

        line_data, old_path, new_path = line_hash_result

        converted += 1
        if old_path and new_path and old_path != new_path:
            path_conversion_data[old_path] = new_path

        # Check for deleted files
        if len(line_data) == 0:
            info(f"Removing {filename}")
            del trace_data[filename]
            continue

        info(f"Converting {filename}")
        entry = trace_data[filename]
        (testdata, sumcount, funcdata, checkdata,
         testfncdata, sumfnccount,
         testbrdata,  sumbrcount) = get_info_entry(entry)

        # Convert test data
        for testname in list(testdata.keys()):
            # Adjust line numbers of line coverage data
            testdata[testname] = apply_diff(testdata[testname], line_data)
            # Adjust line numbers of branch coverage data
            testbrdata[testname] = apply_diff_to_brcount(testbrdata[testname], line_data)
            # Remove empty sets of test data
            if len(testdata[testname]) == 0:
                del testdata[testname]
                delete(testfncdata[testname]) # NOK
                del testbrdata[testname]

        # Rename test data to indicate conversion
        for testname in list(testdata.keys()):
            # Skip testnames which already contain an extension
            if testname =~ r",[^,]+$": continue # NOK
            testname_diff = testname + ",diff"

            # Check for name conflict
            if testname_diff in testdata:
                # Add counts
                testdata[testname] = add_counts(testdata[testname],
                                                testdata[testname_diff])
                del testdata[testname_diff]
                # Add function call counts
                testfncdata[testname] = add_fnccount(testfncdata[testname],
                                                     testfncdata[testname_diff])
                del testfncdata[testname_diff]
                # Add branch counts
                combine_brcount(testbrdata[testname],
                                testbrdata[testname_diff],
                                BR_ADD, inplace=True)
                del testbrdata[testname_diff]

            # Move test data to new testname
            testdata[testname_diff] = testdata[testname]
            del testdata[testname]
            # Move function call count data to new testname
            testfncdata[testname_diff] = testfncdata[testname]
            del testfncdata[testname]
            # Move branch count data to new testname
            testbrdata[testname_diff] = testbrdata[testname]
            del testbrdata[testname]

        # Convert summary of test data
        sumcount = apply_diff(sumcount, line_data)
        # Convert function data
        funcdata = apply_diff_to_funcdata(funcdata, line_data)
        # Convert branch coverage data
        sumbrcount = apply_diff_to_brcount(sumbrcount, line_data)
        # Update found/hit numbers
        # Convert checksum data
        checkdata = apply_diff(checkdata, line_data)
        # Convert function call count data
        adjust_fncdata(funcdata, testfncdata, sumfnccount)
        fn_found, fn_hit = get_func_found_and_hit(sumfnccount)
        br_found, br_hit = get_branch_found_and_hit(sumbrcount)

        # Update found/hit numbers
        ln_found = 0
        ln_hit   = 0
        for count in sumcount.values():
            ln_found += 1
            if count > 0:
                ln_hit += 1

        if ln_found > 0:
            # Store converted entry
            set_info_entry(entry,
                           testdata, sumcount, funcdata, checkdata,
                           testfncdata, sumfnccount,
                           testbrdata,  sumbrcount,
                           ln_found, ln_hit,
                           fn_found, fn_hit,
                           br_found, br_hit)
        else:
            # Remove empty data set
            del trace_data[filename]

    # Convert filenames as well if requested
    if args.convert_filenames:
        convert_paths(trace_data, path_conversion_data)

    info(f"{converted} entr" + ("ies" if converted != 1 else "y") + " converted, " +
         f"{unchanged} entr" + ("ies" if unchanged != 1 else "y") + " left unchanged.")

    # Write data
    if not data_to_stdout:
        info(f"Writing data to {args.output_filename}")
        try:
            with Path(args.output_filename).open("wt") as fhandle:
                result = write_info_file(fhandle, trace_data)
        except:
            die(f"ERROR: cannot write to {args.output_filename}!")
    else:
        result = write_info_file(sys.stdout, trace_data)

    return result

# NOK
def read_diff(diff_file: Path) -> Tuple[Dict[str, Dict[int, int]], Dict[str, str]]:
    """Read diff output from diff_file to memory. The diff file has to follow
    the format generated by 'diff -u'. Returns a list of hash references:

      (mapping, path mapping)

      mapping:   filename -> line hash
      line hash: line number in new file -> corresponding line number in old file

      path mapping:  filename -> old filename

    Die in case of error.
    """
    global args

    my $num_old;         # Current line number in old file
    my $num_new;         # Current line number in new file
    my $file_old;        # Name of old file in diff section
    my $file_new;        # Name of new file in diff section

    info(f"Reading diff {diff_file}")

    # Check if file exists and is readable
    if not os.access(diff_file, os.R_OK):
        die(f"ERROR: cannot read file {diff_file}!")
    # Check if this is really a plain file
    fstatus = diff_file.stat()
    if ! (-f _):
        die(f"ERROR: not a plain file: {diff_file}!")

    # Check for .gz extension
    if re.match(r"\.gz$", str(diff_file)):
        # Check for availability of GZIP tool
        if system_no_output(1, "gunzip", "-h")[0] != NO_ERROR:
            die("ERROR: gunzip command not available!")
        # Check integrity of compressed file
        if system_no_output(1, "gunzip", "-t", str(diff_file))[0] != NO_ERROR:
            die(f"ERROR: integrity check failed for compressed file {diff_file}!")
        # Open compressed file
        try:
            fhandle = open("-|", "gunzip -c 'str(diff_file)'")
        except:
            or die("ERROR: cannot start gunzip to decompress file $_[0]!")
    else:
        # Open decompressed file
        try:
            fhandle = diff_file.open("rt")
        except:
            die("ERROR: cannot read file $_[0]!")

    # Parse diff file line by line
    filename: Optional[str] = None            # Name of common filename of diff section
    mapping:  Dict[int, int]            = {}  # Reference to current line hash
    diff:     Dict[str, Dict[int, int]] = {}  # Resulting mapping filename -> line hash
    paths:    Dict[str, str]            = {}  # Resulting mapping old path -> new path
    in_block = False
    with fhandle:
        for line in fhandle:
            line = line.rstrip("\n")

            # Filename of old file:
            # --- <filename> <date>
            match = re.match(r"^--- (\S+)", line)
            if match:
                $file_old = strip_directories($1, args.strip)
                continue

            # Filename of new file:
            # +++ <filename> <date>
            match = re.match(r"^\+\+\+ (\S+)", line)
            if match:
                # Add last file to resulting hash
                if filename:
                    diff[filename] = mapping
                    mapping = {}
                $file_new = strip_directories($1, args.strip)
                filename = $file_old;
                paths[filename] = file_new
                num_old = 1
                num_new = 1
                continue

            # Start of diff block:
            # @@ -old_start,old_num, +new_start,new_num @@
            match = re.match(r"^\@\@\s+-(\d+),(\d+)\s+\+(\d+),(\d+)\s+\@\@$", line)
            if match:
                in_block = True  # we are inside a diff block
                while num_old < $1:
                    mapping[num_new] = num_old
                    num_old += 1
                    num_new += 1
                continue

            # Unchanged line
            # <line starts with blank>
            match = re.match(r"^ ", line)
            if match:
                if not in_block: continue
                mapping[num_new] = num_old
                num_old += 1
                num_new += 1
                continue

            # Line as seen in old file
            # <line starts with '-'>
            match = re.match(r"^-", line)
            if match:
                if not in_block: continue
                num_old += 1
                continue

            # Line as seen in new file
            # <line starts with '+'>
            match = re.match(r"^\+", line)
            if match:
                if not in_block: continue
                num_new += 1
                continue

            # Empty line
            match = re.match(r"^$", line)
            if match:
                if not in_block: continue
                mapping[num_new] = num_old
                num_old += 1
                num_new += 1
                continue

    # Add final diff file section to resulting hash
    if filename:
        diff[filename] = mapping

    if not diff:
        die(f"ERROR: no valid diff data found in {diff_file}!\n"
            "Make sure to use 'diff -u' when generating the diff file.")

    return (diff, paths)


def get_line_hash(filename: str,
                  diff_data: Dict[str, Dict[int, int]],
                  path_data: Dict[str, str]) -> Optional[Tuple[Dict[int, int], str, str]]:
    """Find line hash in diff_data which matches filename.
    On success, return list line hash. or None in case of no match.
    Die if more than one line hashes in diff_data match.
    """
    global args
    # Remove trailing slash from diff path
    diff_path = re.sub(r"/$", "", args.diff_path)

    diff_name = None
    for fname in diff_data.keys():
        sep = "" if re.match(r"^/", fname) else "/"
        # Try to match diff filename with filename
        if re.match(rf"^\Q{diff_path}{sep}{fname}\E$", filename):
            if diff_name:
                # Two files match, choose the more specific one
                # (the one with more path components)
                $old_depth = (diff_name =~ tr/\///); # NOK
                $new_depth = (tr/\///);              # NOK
                if old_depth == new_depth:
                    die(f"ERROR: diff file contains ambiguous entries for {filename}")
                elif new_depth > old_depth:
                    diff_name = fname
            else:
                diff_name = fname

    if not diff_name:
        return None

    old_path: Optional[str] = None
    new_path: Optional[str] = None
    # Get converted path
    match = re.match(rf"^(.*){diff_name}$", filename)
    if match:
        _, old_path, new_path = get_common_filename(Path(filename),
                                                    Path(match.group(1) + path_data[diff_name]))
    return (diff_data[diff_name], old_path, new_path)


def convert_paths(info_data: InfoData, path_conversion_data: Dict[str, str]):
    """Rename all paths in info_data which show up in path_conversion_data."""

    if len(path_conversion_data) == 0:
        info("No path conversion data available.")
        return

    # Expand path conversion list
    for path in list(path_conversion_data.keys()):
        new_path = path_conversion_data[path]
        while True:
            path     = re.sub(r"^(.*)/[^/]+$", r"\1", path)
            new_path = re.sub(r"^(.*)/[^/]+$", r"\1", new_path)
            if not path or not new_path or path == new_path:
                break
            path_conversion_data[path] = new_path

    # Adjust paths
    repeat = True
    while repeat:
        repeat = False
        for filename in list(info_data.keys()):
            # Find a path in our conversion table that matches, starting
            # with the longest path
            for path in sorted({length($b) <=> length($a)} path_conversion_data.keys()): # NOK
                # Is this path a prefix of our filename? Skip if not
                match = re.match(rf"^{path}(.*)$", filename)
                if not match: continue
                new_path = path_conversion_data[path] + match.group(1)

                # Make sure not to overwrite an existing entry under
                # that path name
                if new_path in info_data:
                    # Need to combine entries
                    info_data[new_path] = combine_info_entries(info_data[filename],
                                                               info_data[new_path],
                                                               filename)
                else:
                    # Simply rename entry
                    info_data[new_path] = info_data[filename]

                del info_data[filename]
                repeat = True
                break
            if repeat: break

            info(f"No conversion available for filename {filename}")


def apply_diff(count_data: Dict[int, object],
               line_data: Dict[int, int]) -> Dict[int, object]:
    """Transform count data using a mapping of lines:

      count_data: line number -> data
      line_data:  line number new -> line number old

    Return a reference to transformed count data.
    """
    result: Dict[int, object] = {}  # Resulting hash

    last_new: int = 0  # Last new line number found in line hash
    last_old: int = 0  # Last old line number found in line hash
    # Iterate all new line numbers found in the diff
    for last_new in sorted(line_data.keys()):
        last_old = line_data[last_new]
        # Is there data associated with the corresponding old line?
        if last_old in count_data:
            # Copy data to new hash with a new line number
            result[last_new] = count_data[last_old]

    # Transform all other lines which come after the last diff entry
    for line in sorted(count_data.keys()):
        # Skip lines which w ere covered by line hash
        if line <= last_old: continue
        # Copy data to new hash with an offset
        result[line + (last_new - last_old)] = count_data[line]

    return result


def get_common_filename(filename1: Path,
                        filename2: Path) -> Optional[Tuple[str, str, str]]
    """Check for filename components which are common to filename1 and
    filename2. Upon success, return

      (common, path1, path2)

    or None in case there are no such parts.
    """
    parts1 = filename1.parts
    parts2 = filename2.parts

    common = []
    # Work in reverse order, i.e. beginning with the filename itself
    while parts1 and parts2 and parts1[-1] == parts2[-1]:
        common_part = parts1.pop()
        parts2.pop()
        common.insert(0, common_part)

    # Did we find any similarities?
    if common:
        return ("/".join(common), "/".join(parts1), "/".join(parts2))
    else:
        return None


def summary() -> Tuple[int, int, int, int, int, int]:
    """ """
    global args

    total: InfoData = None
    # Read and combine trace files
    for filename in args.summary:
        current = read_info_file(filename)
        total = (current if total is None
                 else combine_info_files(total, current))

    ln_total_found = 0
    ln_total_hit   = 0
    fn_total_found = 0
    fn_total_hit   = 0
    br_total_found = 0
    br_total_hit   = 0
    # Calculate coverage data
    for filename, entry in total.items():
        (_, _, _, _, _, _, _, _,
         ln_found, ln_hit,
         fn_found, fn_hit,
         br_found, br_hit) = get_info_entry(entry)

        # Add to totals
        ln_total_found += ln_found
        ln_total_hit   += ln_hit
        fn_total_found += fn_found
        fn_total_hit   += fn_hit
        br_total_found += br_found
        br_total_hit   += br_hit

    return (ln_total_found, ln_total_hit,
            fn_total_found, fn_total_hit,
            br_total_found, br_total_hit)


def adjust_fncdata(funcdata:    Dict[object, object],
                   testfncdata: Dict[object, object],
                   sumfnccount: Dict[object, object]):
    """Remove function call count data from testfncdata and sumfnccount
    which is no longer present in funcdata."""

    # Remove count data in testfncdata for functions which are no longer
    # in funcdata
    for testname, fnccount in testfncdata.items():
        for func in list(fnccount.keys()):
            if func not in funcdata:
                fnccount.pop(func, None)

    # Remove count data in sumfnccount for functions which are no longer
    # in funcdata
    for func in list(sumfnccount.keys()):
        if func not in funcdata:
            sumfnccount.pop(func, None)


def get_line_found_and_hit(dict: Dict[int, int]) -> Tuple[int, int]:
    """Return the count for entries (found) and entries with an execution count
    greater than zero (hit) in a dict (linenumber -> execution count) as
    a list (found, hit)"""
    found = len(dict)
    hit   = sum(1 for count in dict.values() if count > 0)
    return (found, hit)


def get_func_found_and_hit(sumfnccount: Dict[object, int]) -> Tuple[int, int]:
    """Return (fn_found, fn_hit) for sumfnccount"""
    fn_found = len(sumfnccount)
    fn_hit   = sum(1 for ccount in sumfnccount.values() if ccount > 0)
    return (fn_found, fn_hit)


def get_branch_found_and_hit(brcount: BranchCountData) -> Tuple[int, int]:
    """ """
    db = brcount_to_db(brcount)
    return brcount_db_get_found_and_hit(db)


def temp_cleanup():
    """ """
    global temp_dirs

    # Ensure temp directory is not in use by current process
    os.chdir("/")
    if temp_dirs:
        info("Removing temporary directories.")
        for dir in temp_dirs:
            shutil.rmtree(str(dir))
        temp_dirs.clear()


def setup_gkv_sys():
    system_no_output(3, "mount", "-t", "debugfs", "nodev", "/sys/kernel/debug")


def setup_gkv_proc():
    if system_no_output(3,  "modprobe", "gcov_proc") != NO_ERROR:
        system_no_output(3, "modprobe", "gcov_prof")


def setup_gkv() -> Tuple[int, Path]:
    """ """
    global options

    sys_dir  = Path("/sys/kernel/debug/gcov")
    proc_dir = Path("/proc/gcov")

    if options.gcov_dir is None:
        info("Auto-detecting gcov kernel support.")
        todo = ["cs", "cp", "ss", "cs", "sp", "cp"]
    elif re.search(r"proc", str(options.gcov_dir)):
        info(f"Checking gcov kernel support at {options.gcov_dir} (user-specified).")
        todo = ["cp", "sp", "cp", "cs", "ss", "cs"]
    else:
        info(f"Checking gcov kernel support at {options.gcov_dir} (user-specified).")
        todo = ["cs", "ss", "cs", "cp", "sp", "cp"]

    for action in todo:
        if action == "cs":
            # Check /sys
            dir = options.gcov_dir or sys_dir
            if check_gkv_sys(dir):
                info(f"Found {GKV_NAME[GKV_SYS]} gcov kernel support at {dir}")
                return (GKV_SYS, dir)
        elif action == "cp":
            # Check /proc
            dir = options.gcov_dir or proc_dir
            if check_gkv_proc(dir):
                info(f"Found {GKV_NAME[GKV_PROC]} gcov kernel support at {dir}")
                return (GKV_PROC, dir)
        elif action == "ss":
            # Setup /sys
            setup_gkv_sys()
        elif action == "sp":
            # Setup /proc
            setup_gkv_proc()
    else:
        if options.gcov_dir:
            die(f"ERROR: could not find gcov kernel data at {options.gcov_dir}")
        else:
            die("ERROR: no gcov kernel data found")


def check_gkv_sys(dir: Path) -> bool:
    """ """
    if (dir/"reset").exists():
        return True
    return False


def check_gkv_proc(dir: Path) -> bool:
    """ """
    if (dir/"vmlinux").exists():
        return True
    return False


def print_overall_rate(ln_do: bool, ln_found: int, ln_hit: int,
                       fn_do: bool, fn_found: int, fn_hit: int,
                       br_do: bool, br_found: int, br_hit: int,
                       *, title: str = "Summary coverage rate:"):
    """Print overall coverage rates for the specified coverage types."""
    info(title)
    if ln_do:
        info("  lines......: %s",
             get_overall_line(ln_found, ln_hit, "line", "lines"))
    if fn_do:
        info("  functions..: %s",
             get_overall_line(fn_found, fn_hit, "function", "functions"))
    if br_do:
        info("  branches...: %s",
             get_overall_line(br_found, br_hit, "branch", "branches"))


def get_overall_line(found: Optional[int], hit: int,
                     name_singular: str, name_plural: str):
    # Return a string containing overall information for the specified
    # found/hit data.
    #
    if found is None or found == 0:
        return "no data found"
    name = name_singular if found == 1 else name_plural
    return rate(hit, found, f"% ({hit} of {found} {name})")


def check_rates(ln_found: int, ln_hit: int) -> int:
    """Check line coverage if it meets a specified threshold."""
    global options

    if options.fail_under_lines <= 0:
        return 0

    if ln_found == 0:
        return 1

    actual_rate   = ln_hit / ln_found
    expected_rate = options.fail_under_lines / 100

    if actual_rate < expected_rate:
        return 1

    return 0


def rate(hit: int, found: Optional[int],
         suffix: Optional[str] = None,
         precision: Optional[int] = None,
         width: Optional[int] = None) -> str:
    """Return the coverage rate [0..100] for HIT and FOUND values.
    0 is only returned when HIT is 0. 100 is only returned when HIT equals FOUND.
    PRECISION specifies the precision of the result. SUFFIX defines a
    string that is appended to the result if FOUND is non-zero. Spaces
    are added to the start of the resulting string until it is at least
    WIDTH characters wide.
    """
    global default_precision

    # Assign defaults if necessary
    if precision is None: precision = default_precision
    if suffix    is None: suffix    = ""
    if width     is None: width     = 0

    if found is None: or found == 0:
        return "%*s" % (width, "-")

    rate = "%.*f" % (precision, hit * 100 / found)
    # Adjust rates if necessary
    if int(rate) == 0 and hit > 0:
        rate = "%.*f" % (precision, 1 / 10 ** precision)
    elif int(rate) == 100 and hit != found:
        rate = "%.*f" % (precision, 100 - 1 / 10 ** precision)

    return "%*s" % (width, rate + suffix)


def info(format, *pars, *, end="\n"):
    """Use printf to write to stdout only when the args.quiet flag
    is not set."""
    global args
    global data_to_stdout
    if args.quiet: return
    # Print info string
    if data_to_stdout:
        # Don't interfere with the .info output to sys.stdout
        print(format % pars, end=end, file=sys.stderr)
    else:
        print(format % pars, end=end)


def main(argv=sys.argv[1:]):
    """\
    """
    global tool_name, lcov_version, lcov_url

    def warn_handler(msg: str):
        global tool_name
        import warnings
        warnings.warn(f"{tool_name}: {msg}")

    def die_handler(msg: str):
        global tool_name
        temp_cleanup()
        import sys
        sys.exit(f"{tool_name}: {msg}")

    def abort_handler(msg: str):
        temp_cleanup()
        return 1

    # $SIG{__WARN__} = warn_handler
    # $SIG{__DIE__}  = die_handler
    # $SIG{'INT'}    = abort_handler
    # $SIG{'QUIT'}   = abort_handler

    # Parse command line options
    parser = argparse.ArgumentParser(prog=tool_name, description=main.__doc__,
                                     epilog=f"For more information see: {lcov_url}",
                                     add_help=False)
    parser.add_argument("filename", type=str,
        metavar="SOURCEFILE", help="SOURCEFILE")
    parser.add_argument("-h", "-?", "--help", action="help",
        help="Print this help, then exit")
    parser.add_argument("-v", "--version", action="version",
        version=f"%(prog)s: {lcov_version}",
        help="Print version number, then exit")
    parser.add_argument("-t", "--tab-size", type=int, default=4,
        metavar="TABSIZE", help="Use TABSIZE spaces in place of tab")
    parser.add_argument("-w", "--width", type=int, default=80,
        metavar="WIDTH", help="Set width of output image to WIDTH pixel")
    parser.add_argument("-o", "--output-filename", type=str,
        metavar="FILENAME", help="Write image to FILENAME")

    args = parser.parse_args(argv)
    # Check for output filename
    if not args.output_filename:
        args.output_filename = f"{args.filename}.png"

    try:
    except BaseException as exc:
        return str(exc)


if __name__.rpartition(".")[-1] == "__main__":
    sys.exit(main())
