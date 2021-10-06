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
use File::Basename;
use File::Path;
use File::Find;
use File::Temp qw /tempdir/;
use File::Spec::Functions qw /abs2rel canonpath catdir catfile catpath
                  file_name_is_absolute rootdir splitdir splitpath/;
use Getopt::Long;
use Cwd qw /abs_path getcwd/;

from typing import List
import argparse
import sys
import re
import shutil
from pathlib import Path

from .util import reverse_dict

# Global constants
tool_name    = Path(__file__).stem
our $tool_dir        = abs_path(dirname($0));
our $lcov_version    = 'LCOV version '.`$tool_dir/get_version.sh --full`;
our $lcov_url        = "http://ltp.sourceforge.net/coverage/lcov.php";

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

# Prototypes
from .util import strip_spaces_in_options
sub print_usage(*);
sub check_options();
sub remove();
sub list();
sub diff();
from .util import write_file
from .util import apply_config
sub info(@);
sub rate($$;$$$);
from .util import transform_pattern
from .util import system_no_output

# Global variables & initialization
options.gcov_dir:       Optional[Path] = None  # Directory containing gcov kernel files
options.tmp_dir:        Optional[Path] = None  # Where to create temporary directories
args.directory:         Optional[List] = None  # Specifies where to get coverage data from
args.kernel_directory:  Optional[List] = None  # If set, captures only from specified kernel subdirs
args.add_tracefile:     Optional[List] = None  # If set, reads in and combines all files in list
our $list;        # If set, list contents of tracefile
args.extract:           Optional[str] = None  # If set, extracts parts of tracefile
args.remove:            Optional[str] = None  # If set, removes  parts of tracefile
args.diff:              Optional[str] = None  # If set, modifies tracefile according to diff
our $reset;        # If set, reset all coverage data to zero
our $capture;        # If set, capture data
args.output_filename:   Optional[str] = None  # Name for file to write coverage data to
our $test_name = "";    # Test case name
args.quiet: bool = False  # If set, suppress information messages
our $help;        # Help option flag
our $version;        # Version option flag
args.convert_filenames: bool =  False  # If set, convert filenames when applying diff
args.strip:             Optional[int] = None  # If set, strip leading directories when applying diff
our $temp_dir_name;    # Name of temporary directory
our $cwd = `pwd`;    # Current working directory
args.follow:            bool =  False  # If set, indicates that find shall follow links
our $diff_path = "";    # Path removed from tracefile when applying diff
options.fail_under_lines: int = 0
args.base_directory:    Optional[str] = None  # Base directory (cwd of gcc during compilation)
args.checksum;        # If set, calculate a checksum for each line
args.no_checksum:       Optional[bool] = None  # If set, don't calculate a checksum for each line
args.compat_libtool:    Optional[bool] = None  # If set, indicates that libtool mode is to be enabled
args.no_compat_libtool: Optional[bool] = None  # If set, indicates that libtool mode is to be disabled
args.gcov_tool:         Optional[str] = None
our opt.ignore_errors;
args.initial:           bool = False
args.include_patterns:  List[str] = [] # List of source file patterns to include
args.exclude_patterns:  List[str] = [] # List of source file patterns to exclude
opt.no_recursion:       bool = False
args.to_package:        Optional[Path] = None
our $from_package;
our $maxdepth;
args.no_markers:        bool = False
our $config;        # Configuration file contents
chomp($cwd);
temp_dirs:              List[Path] = []
gcov_gkv:               str = ""  # gcov kernel support version found on machine
our opt.derive_func_data;
our opt.debug;
options.list_full_path: Optional[bool] = None
args.no_list_full_path: Optional[bool] = None
options.list_width:        int = 80
options.list_truncate_max: int = 20
args.external:         Optional[bool] = None
args.no_external:      Optional[bool] = None
our opt.config_file;
our opt.rc:           Optional[Dict];
args.summary:         Optional[List] = None
our opt.compat;
options.br_coverage:  bool = False
options.fn_coverage:  bool = True

ln_overall_found: Optional[int] = None
ln_overall_hit:   Optional[int] = None
fn_overall_found: Optional[int] = None
fn_overall_hit:   Optional[int] = None
br_overall_found: Optional[int] = None
br_overall_hit:   Optional[int] = None

#
# Code entry point
#

# Check command line for a configuration file name
Getopt::Long::Configure("pass_through", "no_auto_abbrev")
GetOptions("config-file=s": \args.config_file,
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
        "list|l=s"             => \$list,
        "kernel-directory|k=s" => \args.kernel_directory,
        "extract|e=s"          => \args.extract,
        "remove|r=s"           => \args.remove,
        "diff=s"               => \args.diff,
        "convert-filenames"    => \args.convert_filenames,
        "strip=i"              => \args.strip,
        "capture|c"            => \$capture,
        "output-file|o=s"      => \args.output_filename,
        "test-name|t=s"        => \$test_name,
        "zerocounters|z"       => \$reset,
        "quiet|q"              => \args.quiet,
        "help|h|?"             => \$help,
        "version|v"            => \$version,
        "follow|f"             => \args.follow,
        "path=s"               => \$diff_path,
        "base-directory|b=s"   => \args.base_directory,
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
        "from-package=s"       => \$from_package,
        "no-markers"           => \args.no_markers,
        "derive-func-data"     => \args.derive_func_data,
        "debug"                => \args.debug,
        "list-full-path"       => \options.list_full_path,
        "no-list-full-path"    => \args.no_list_full_path,
        "external"             => \args.external,
        "no-external"          => \args.no_external,
        "summary=s"            => \args.summary,
        "compat=s"             => \args.compat,
        "config-file=s"        => \args.config_file,
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
if $help:
    print_usage(sys.stdout)
    sys.exit(0)

# Check for version option
if $version:
    print(f"{tool_name}: {lcov_version}")
    sys.exit(0)

# Check list width option
if options.list_width <= 40:
    die("ERROR: lcov_list_width parameter out of range (needs to be "
        "larger than 40)\n")

# Normalize --path text
$diff_path =~ s/\/$//;

$maxdepth = "-maxdepth 1" if args.no_recursion else ""

# Check for valid options
check_options()

# Only --extract, --remove and --diff allow unnamed parameters
if @ARGV and !(args.extract is not None or args.remove is not None or args.diff or args.summary):
    die("Extra parameter found: '".join(" ", @ARGV)."'\n"
        f"Use {tool_name} --help to get usage information\n")

# If set, indicates that data is written to stdout
# Check for output filename
data_to_stdout: bool = not (args.output_filename and args.output_filename != "-")

if $capture:
    if data_to_stdout:
        # Option that tells geninfo to write to stdout
        args.output_filename = "-"

# Determine kernel directory for gcov data
if ! $from_package and not args.directory and ($capture or $reset):
    gcov_gkv, options.gcov_dir = setup_gkv()

our $exit_code = 0
# Check for requested functionality
if $reset:
    data_to_stdout = False
    # Differentiate between user space and kernel reset
    if args.directory:
        userspace_reset()
    else:
        kernel_reset()
elif $capture:
    # Capture source can be user space, kernel or package
    if $from_package:
        package_capture()
    elif args.directory:
        userspace_capture()
    else:
        if args.initial:
            if args.to_package:
                die("ERROR: --initial cannot be used together with --to-package\n")
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
elif $list:
    data_to_stdout = False
    list()
elif args.diff:
    if len(@ARGV) != 1:
        die("ERROR: option --diff requires one additional argument!\n"
            f"Use {tool_name} --help to get usage information\n")
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
    if ! $list and ! $capture:
        info("Done.\n")

sys.exit($exit_code)


# print_usage(handle)
#
# Print usage information.

# NOK
def print_usage(*HANDLE):

    print(HANDLE <<END_OF_USAGE);
Usage: $tool_name [OPTIONS]

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

For more information see: $lcov_url
END_OF_USAGE

# NOK
def check_options():
    """Check for valid combination of command line options.
    Die on error."""

    global args

    # Count occurrence of mutually exclusive options
    options = (
        $reset,
        $capture,
        args.add_tracefile,
        args.extract,
        args.remove,
        $list,
        args.diff,
        args.summary,
    )
    count = len([1 for item in options if item])
    
    if count == 0:
        die("Need one of options -z, -c, -a, -e, -r, -l, "
            "--diff or --summary\n"
            f"Use {tool_name} --help to get usage information\n")
    elif count > 1:
        die("ERROR: only one of -z, -c, -a, -e, -r, -l, "
            "--diff or --summary allowed!\n"
            f"Use {tool_name} --help to get usage information\n")

#class LCov:


def userspace_reset():
    """Reset coverage data found in DIRECTORY by deleting all contained .da files.

    Die on error.
    """
    global args

    follow = "-follow" if args.follow else = ""

    for dir in args.directory:
        info("Deleting all .da files in {}{}\n".format(dir,
             ("" if args.no_recursion else " and subdirectories")))
        file_list = `find "$dir" $maxdepth $follow -name \\*\\.da -type f -o -name \\*\\.gcda -type f 2>/dev/null` # NOK
        for filename in file_list.striplines():
            filename = Path(filename.strip())
            try:
                filename.unlink()
            except:
                die(f"ERROR: cannot remove file {filename}!\n")


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
        die("ERROR: -d may be specified only once with --to-package\n")

    dir   = Path(args.directory[0])
    build = args.base_directory if args.base_directory is not None else str(dir)

    create_package(args.to_package, dir, build)


def kernel_reset():
    """Reset kernel coverage.

    Die on error.
    """
    global options

    info("Resetting kernel execution counters\n")
    if (options.gcov_dir/"vmlinux").exists():
        reset_file = options.gcov_dir/"vmlinux"
    elif (options.gcov_dir/"reset").exists():
        reset_file = options.gcov_dir/"reset"
    else:
        die(f"ERROR: no reset control found in {options.gcov_dir}\n")
    try:
        reset_file.write("0")
    except:
        die(f"ERROR: cannot write to {reset_file}!\n")

# NOK
def lcov_find(dir: Path, func: Callable, $data, pattern: Optional[List] = None):
    # lcov_find(dir, function, data[, extension, ...)])

    # Search DIR for files and directories whose name matches PATTERN and run
    # FUNCTION for each match. If not pattern is specified, match all names.
    #
    # FUNCTION has the following prototype:
    #   function(dir: Path, relative_name, data)
    #
    # Where:
    #   dir: the base directory for this search
    #   relative_name: the name relative to the base directory of this entry
    #   data: the DATA variable passed to lcov_find

    result = None

    def find_cb():
        nolocal dir, func, $data, pattern
        nolocal result

        filename = $File::Find::name;

        if result is not None:
            return

        filename = abs2rel(filename, str(dir))
        for $patt in pattern:
            if filename =~ /$patt/:
                result = func(dir, filename, $data)
                return

    if len(pattern) == 0: pattern = [".*"]

    find({ wanted => find_cb, no_chdir => 1 }, str(dir))

    return result


def lcov_copy(path_from: Path, path_to: Path, subdirs: List[object]):
    # Copy all specified SUBDIRS and files from directory FROM to directory TO.
    # For regular files, copy file contents without checking its size.
    # This is required to work with seq_file-generated files.
    patterns = [rf"^{subd}" for subd in subdirs]
    lcov_find(path_from, lcov_copy_fn, path_to, patterns)

# NOK
def lcov_copy_fn(path_from: Path, $rel, path_to: Path):
    """Copy directories, files and links from/rel to to/rel."""

    abs_from = Path(canonpath(path_from/$rel))
    abs_to   = Path(canonpath(path_to/$rel))

    if (-d):
        if (! -d $abs_to):
            try:
                mkpath($abs_to)
            except:
                die(f"ERROR: cannot create directory {abs_to}\n")
            abs_to.chmod(0o0700)
    elif (-l):
        # Copy symbolic link
        try:
            link = readlink($abs_from)
        except Exception as exc:
            die(f"ERROR: cannot read link {abs_from}: {exc}!\n")
        try:
            symlink($link, $abs_to)
        except Exception as exc:
            die(f"ERROR: cannot create link {abs_to}: {exc}!\n")
    else:
        lcov_copy_single(abs_from, abs_to)
        abs_to.chmod(0o0600)

    return None


def lcov_copy_single(path_from: Path, path_to: Path):
    """Copy single regular file FROM to TO without checking its size.
    This is required to work with special files generated by the
    kernel seq_file-interface.
    """
    try:
        content = path_from.read_text()
    except Exception as exc:
        die(f"ERROR: cannot read {path_from}: {exc}!\n")
    try:
        path_to.write_text(content or "")
    except Exception as exc:
        die(f"ERROR: cannot write {path_to}: {exc}!\n")

# NOK
def lcov_geninfo(*dirs):
    # Call geninfo for the specified directories and with the parameters
    # specified at the command line.

    global args
    global tool_dir
    global opt
    $test_name

    dir_list = [str(dir) for dir in dirs]

    # Capture data
    info("Capturing coverage data from {}\n".format(" ".join(dir_list)))

    param = [f"{tool_dir}/geninfo"] + dir_list
    if args.output_filename:
        param += ["--output-filename", str(args.output_filename)]
    if $test_name:
        param += ["--test-name", $test_name]
    if args.follow:
        param += ["--follow"]
    if args.quiet:
        param += ["--quiet"]
    if args.checksum is not None:
        param += ["--checksum"] if args.checksum else ["--no-checksum"]
    if args.base_directory:
        param += ["--base-directory", args.base_directory]
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
        param += ["--config-file", args.config_file]
    for patt in args.include_patterns:
        param += ["--include", patt]
    for patt in args.exclude_patterns:
        param += ["--exclude", patt]

    os.system(@param)
        and sys.exit($? >> 8)

# NOK
def get_package(package_file: Path) -> Tuple[Path, object, object]:
    """Unpack unprocessed coverage data files from package_file to a temporary
    directory and return directory name, build directory and gcov kernel version
    as found in package.
    """
    global pkg_gkv_file, pkg_build_file

    dir = create_temp_dir()
    cwd = Path.cwd()
    try:
        my $gkv;
        info(f"Reading package {package_file}:\n")

        $package_file = abs_path(str(package_file))

        os.chdir(dir)
        try:
            fhandle = open("-|", "tar xvfz '$package_file' 2>/dev/null")
        except:
            die(f"ERROR: could not process package {package_file}\n")
        count = 0;
        with fhandle:
            while (<fhandle>):
                if (/\.da$/ or /\.gcda$/):
                    count += 1
        if count == 0:
            die(f"ERROR: no data file found in package {package_file}\n")
        info(f"  data directory .......: {dir}\n")
        fpath = dir/pkg_build_file
        build = read_file(fpath)
        if build is not None:
            info(f"  build directory ......: {build}\n")
        fpath = dir/pkg_gkv_file
        $gkv = read_file(fpath)
        if defined($gkv):
            $gkv = int($gkv)
            if $gkv != GKV_PROC and $gkv != GKV_SYS:
                die("ERROR: unsupported gcov kernel version found ($gkv)\n")
            info("  content type .........: kernel data\n")
            info("  gcov kernel version ..: %s\n", GKV_NAME[$gkv])
        else:
            info("  content type .........: application data\n")
        info(f"  data files ...........: {count}\n")
    finally:
        os.chdir(cwd)

    return (dir, build, $gkv)


def count_package_data(filename: Path) -> Optional[int]:
    """Count the number of coverage data files in the specified package file."""
    try:
        fhandle = open(f"tar tfz '{filename}'", "-|") # NOK
    except:
        return None
    count = 0
    with fhandle:
        for line in fhandle:
            line = line.rstrip()
            if any(line.endswith(ext) for ext in (".da", ".gcda")):
                count += 1
    return count

# NOK
def create_package(package_file: Path, dir: Path, $build: Optional, gkv: Optional[str] = None)
    # create_package(package_file, source_directory, build_directory[, kernel_gcov_version])
    global args
    global pkg_gkv_file, pkg_build_file

    # Store unprocessed coverage data files from source_directory to package_file.

    cwd = Path.cwd()
    try:
        # Check for availability of tar tool first
        system("tar --help > /dev/null")
            and die("ERROR: tar command not available\n")

        # Print information about the package
        info(f"Creating package {package_file}:\n")
        info(f"  data directory .......: {dir}\n")

        # Handle build directory
        if build is not None:
            info(f"  build directory ......: {build}\n")
            fpath = dir/pkg_build_file
            try:
                write_file(fpath, str(build))
            except:
                die(f"ERROR: could not write to {fpath}\n")

        # Handle gcov kernel version data
        if gkv is not None:
            info("  content type .........: kernel data\n");
            info("  gcov kernel version ..: %s\n", GKV_NAME[gkv])
            fpath = dir/pkg_gkv_file
            try:
                write_file(fpath, gkv)
            except:
                die(f"ERROR: could not write to {fpath}\n")
        else:
            info("  content type .........: application data\n")

        # Create package
        package_file = Path(abs_path(str(package_file)))
        os.chdir(dir);
        system("tar cfz {package_file} .")
            and die(f"ERROR: could not create package {package_file}\n")
    finally:
        os.chdir(cwd)

    # Remove temporary files
    (dir/pkg_build_file).unlink()
    (dir/pkg_gkv_file).unlink()

    # Show number of data files
    if not args.quiet:
        count = count_package_data(package_file)
        if count is not None:
            info(f"  data files ...........: {count}\n")

# NOK
def get_base(dir: Path) -> Tuple[Optional[Path], Optional[Path]]:
    # Return (BASE, OBJ), where
    #  - BASE: is the path to the kernel base directory relative to dir
    #  - OBJ:  is the absolute path to the kernel build directory

    marker = "kernel/gcov/base.gcno"

    marker_file = lcov_find(dir, find_link_fn, marker)
    if marker_file is None:
        return (None, None)

    # sys base is parent of parent of markerfile.
    sys_base = Path(abs2rel(str(marker_file.parent.parent.parent), str(dir)))

    # build base is parent of parent of markerfile link target.
    try:
        link = readlink(str(marker_file))
    except Exception as exc:
        die(f"ERROR: could not read {markerfile}\n")
    build = Path(link).parent.parent.parent

    return (sys_base, build)

# NOK
def find_link_fn(path_from: Path, rel, filename):
    abs_file = path_from/rel/filename
    return abs_file if (-l str(abs_file) else None

# NOK
def apply_base_dir($data: Path, $base: Optional[Path], $build, dirs: List) -> List:
    # apply_base_dir(data_dir, base_dir, build_dir, @directories)
    # Make entries in @directories relative to data_dir.
    global args

    $data = str($data)
    if $base is not None: $base = str($base)

    result: List = []

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
            if file_name_is_absolute(args.base_directory):
                $base = abs2rel(args.base_directory, rootdir())
            else:
                $base = args.base_directory
            if (-d catdir($data, $base, $dir)):
                result.append(catdir($base, $dir))
                continue

        # Relative to the build directory?
        if defined($build):
            if file_name_is_absolute($build):
                $base = abs2rel($build, rootdir())
            else:
                $base = $build
            if (-d catdir($data, $base, $dir)):
                result.append(catdir($base, $dir))
                continue

        die(f"ERROR: subdirectory {dir} not found\n"
            "Please use -b to specify the correct directory\n")

    return result


def copy_gcov_dir(dir: Path, subdirs: List[object] = []) -> Path:
    """Create a temporary directory and copy all or, if specified,
    only some subdirectories from dir to that directory.
    Return the name of the temporary directory.
    """
    tempdir = create_temp_dir()

    info(f"Copying data to temporary directory {tempdir}\n")
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
                "Please use -b to specify the build directory\n")
        build  = str(build)
        source = "auto-detected"

    info(f"Using {build} as kernel build directory ({source})\n")
    # Build directory needs to be passed to geninfo
    args.base_directory = build
    params = []
    if args.kernel_directory:
        for dir in args.kernel_directory:
            params.append(f"{build}/{dir}")
    else:
        params.append(build)

    lcov_geninfo(*params)


def adjust_kernel_dir(dir: Path, build: Optional[Path]) -> Path:
    """Adjust directories specified with -k so that they point to the
    directory relative to DIR.
    Return the build directory if specified or the auto-detected
    build-directory.
    """
    global args

    sys_base, build_auto = get_base(dir)
    if build is None:
        build = build_auto
    if build is None:
        die("ERROR: could not auto-detect build directory.\n"
            "Please use -b to specify the build directory\n")

    # Make kernel_directory relative to sysfs base
    if args.kernel_directory:
        args.kernel_directory = apply_base_dir(dir, sys_base, str(build),
                                               args.kernel_directory)
    return build

# NOK
def kernel_capture():

    global options
    global args
    global gcov_gkv

    build = args.base_directory
    if gcov_gkv == GKV_SYS:
        build = str(adjust_kernel_dir(options.gcov_dir, Path(build) if build is not None else None))

    data_dir = copy_gcov_dir(options.gcov_dir, args.kernel_directory)
    kernel_capture_from_dir(data_dir, gcov_gkv, build)

# NOK
def kernel_capture_from_dir(dir: Path, gcov_kernel_version: str, $build):
    """Perform the actual kernel coverage capturing from the specified directory
    assuming that the data was copied from the specified gcov kernel version."""
    global args

    # Create package or coverage file
    if args.to_package:
        create_package(args.to_package, dir, $build, gcov_kernel_version)
    else:
        # Build directory needs to be passed to geninfo
        args.base_directory = $build
        lcov_geninfo(dir)

# NOK
def link_data(targetdatadir: Path, targetgraphdir, *, create: bool):
    # If CREATE is non-zero, create symbolic links in GRAPHDIR for
    # data files found in DATADIR. Otherwise remove link in GRAPHDIR.

    targetdatadir  = abs_path(str(targetdatadir))
    targetgraphdir = abs_path(targetgraphdir)

    op_data_cb = link_data_cb if create else unlink_data_cb, 
    lcov_find(Path(targetdatadir), op_data_cb, Path(targetgraphdir), ["\.gcda$", "\.da$"])

# NOK
def link_data_cb($datadir: Path, $rel, $graphdir: Path):
    """Create symbolic link in GRAPDIR/REL pointing to DATADIR/REL."""

    $abs_from = catfile(str($datadir),  $rel)
    $abs_to   = catfile(str($graphdir), $rel)

    if (-e $abs_to):
        die(f"ERROR: could not create symlink at {abs_to}: "
            "File already exists!\n")
    if (-l $abs_to):
        # Broken link - possibly from an interrupted earlier run
        Path($abs_to).unlink()

    # Check for graph file
    $base = $abs_to;
    $base =~ s/\.(gcda|da)$//;
    if (! -e $base.".gcno" and ! -e $base.".bbg" and ! -e $base.".bb"):
        die("ERROR: No graph file found for {} in {}!\n".format(
            $abs_from, dirname($base)))

    try:
        symlink($abs_from, $abs_to)
    except:
        or die(f"ERROR: could not create symlink at {abs_to}: $!\n")

# NOK
def unlink_data_cb($datadir: Path, $rel, $graphdir: Path):
    """Remove symbolic link from GRAPHDIR/REL to DATADIR/REL."""

    abs_from = Path(catfile(str($datadir),  $rel))
    abs_to   = Path(catfile(str($graphdir), $rel))

    if (! -l abs_to):
        return
    try:
        target = readlink(abs_to)
    except:
        return
    if target != abs_from:
        return

    try:
        abs_to.unlink()
    except Exception as exc:
        warn(f"WARNING: could not remove symlink {abs_to}: {exc}!\n")

# NOK
def find_graph(dir: Path) -> bool:
    # Search DIR for a graph file.
    # Return True if one was found, False otherwise.

    count = 0

    def find_graph_cb($dir, $rel, $count_ref):
        # find_graph_cb(datadir, rel, count_ref)
        #
        # Count number of files found.
        ($$count_ref)++;

    lcov_find(dir, find_graph_cb, \$count, ["\.gcno$", "\.bb$", "\.bbg$"])

    return count > 0

# NOK
def package_capture():
    # Capture coverage data from a package of unprocessed coverage data files
    # as generated by lcov --to-package.
    global args
    global $from_package

    dir: Path, $build, $gkv = get_package(Path($from_package))

    # Check for build directory
    if args.base_directory is not None:
        if build is not None:
            info("Using build directory specified by -b.\n")
        $build = args.base_directory

    # Do the actual capture
    if $gkv is not None:
        if $gkv == GKV_SYS:
            $build = str(adjust_kernel_dir(dir, Path(build) if build is not None else None))
        if args.kernel_directory:
            dir = copy_gcov_dir(dir, args.kernel_directory)
        kernel_capture_from_dir(str($dir), $gkv, $build);
    else:
        # Build directory needs to be passed to geninfo
        args.base_directory = $build
        if find_graph(dir):
            # Package contains graph files - collect from there
            lcov_geninfo(dir)
        else:
            # No graph files found, link data files next to
            # graph files
            link_data(dir, args.base_directory, create=True)
            lcov_geninfo(args.base_directory)
            link_data(dir, args.base_directory, create=False)

# NOK
def info(@)
    # info(printf_parameter)
    #
    # Use printf to write PRINTF_PARAMETER to stdout only when the args.quiet
    # flag is not set.
    global args
    global data_to_stdout

    if args.quiet: return
    # Print info string
    if not data_to_stdout:
        printf(*args)
    else:
        # Don't interfere with the .info output to sys.stdout
        printf(*args, file=sys.stderr)


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
        die("ERROR: cannot create temporary directory\n")

    temp_dirs.append(dir)
    return dir


def compress_brcount(brcount: Dict[int, str]) -> Tuple[Dict[int, str], int, int]: 
    """ """
    db = brcount_to_db(brcount)
    return db_to_brcount(db, brcount)

# NOK
def read_info_file($tracefile) -> Dict[str, Dict[str, object]]:
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
    #        "found"   -> $lines_found (number of instrumented lines found in file)
    #        "hit"     -> $lines_hit (number of executed lines in file)
    #        "f_found" -> $fn_found (number of instrumented functions found in file)
    #        "f_hit"   -> $fn_hit (number of executed functions in file)
    #        "b_found" -> $br_found (number of instrumented branches found in file)
    #        "b_hit"   -> $br_hit (number of executed branches in file)
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

    result: Dict[str, Dict[str, object]] = {}  # Resulting hash: file -> data

    info("Reading tracefile $tracefile\n")

    # Check if file exists and is readable
    if not os.access($_[0], os.R_OK):
        die("ERROR: cannot read file $_[0]!\n")
    # Check if this is really a plain file
    fstatus = Path($_[0]).stat()
    if ! (-f _):
        die("ERROR: not a plain file: $_[0]!\n")

    # Check for .gz extension
    if ($_[0] =~ /\.gz$/):
        # Check for availability of GZIP tool
        system_no_output(1, "gunzip" ,"-h")
            and die("ERROR: gunzip command not available!\n")

        # Check integrity of compressed file
        system_no_output(1, "gunzip", "-t", $_[0])
            and die("ERROR: integrity check failed for ".
                "compressed file $_[0]!\n")

        # Open compressed file
        try:
            INFO_HANDLE = open("-|", "gunzip -c '$_[0]'")
        except:
            or die("ERROR: cannot start gunzip to decompress file $_[0]!\n")
    else:
        # Open decompressed file
        try:
            INFO_HANDLE = open("rt", $_[0])
        except:
            or die("ERROR: cannot read file $_[0]!\n")

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
                    $testcount    = $testdata[testname]
                    $testfnccount = $testfncdata[testname]
                    $testbrcount  = $testbrdata[testname]
                else:
                    $testcount    = {}
                    $testfnccount = {}
                    $testbrcount  = {}
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
                        die(f"ERROR: checksum mismatch at {filename}:$1\n")
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
                        $testdata[testname]    = $testcount
                        $testfncdata[testname] = $testfnccount
                        $testbrdata[testname]  = $testbrcount

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

    if len(result) == 0:
        die(f"ERROR: no valid records found in tracefile {tracefile}\n")
    if negative:
        warn(f"WARNING: negative counts found in tracefile {tracefile}\n")
    if changed_testname:
        warn(f"WARNING: invalid characters removed from testname in tracefile {tracefile}\n")

    return result


def get_info_entry(entry: Dict[str, object]) -> Tuple:
    """Retrieve data from an entry of the structure generated by read_info_file().
    Return a tuple of references to dicts:
    (test data  dict, sum count   dict, funcdata   dict, checkdata  dict,
    testfncdata dict, sumfnccount dict, testbrdata dict, sumbrcount dict,
    lines     found, lines     hit,
    functions found, functions hit,
    branches  found, branches  hit)
    """
    testdata    = entry.get("test")
    sumcount    = entry.get("sum")
    funcdata    = entry.get("func")
    checkdata   = entry.get("check")
    testfncdata = entry.get("testfnc")
    sumfnccount = entry.get("sumfnc")
    testbrdata  = entry.get("testbr")
    sumbrcount  = entry.get("sumbr")
    ln_found: int = entry.get("found")
    ln_hit:   int = entry.get("hit")
    fn_found: int = entry.get("f_found")
    fn_hit:   int = entry.get("f_hit")
    br_found: int = entry.get("b_found")
    br_hit:   int = entry.get("b_hit")

    return (testdata, sumcount, funcdata, checkdata,
            testfncdata, sumfnccount,
            testbrdata,  sumbrcount,
            ln_found, ln_hit,
            fn_found, fn_hit,
            br_found, br_hit)


def set_info_entry(entry: Dict[str, object],
                   testdata, sumcount, funcdata, checkdata,
                   testfncdata, sumfcncount,
                   testbrdata,  sumbrcount,
                   ln_found=None ln_hit=None
                   fn_found=None fn_hit=None
                   br_found=None br_hit=None):
    """Update the dict referenced by ENTRY with the provided data references."""
    entry["test"]    = testdata
    entry["sum"]     = sumcount
    entry["func"]    = funcdata
    entry["check"]   = checkdata
    entry["testfnc"] = testfncdata
    entry["sumfnc"]  = sumfcncount
    entry["testbr"]  = testbrdata  
    entry["sumbr"]   = sumbrcount
    if ln_found is not None: entry["found"]   = ln_found
    if ln_hit   is not None: entry["hit"]     = ln_hit
    if fn_found is not None: entry["f_found"] = fn_found
    if fn_hit   is not None: entry["f_hit"]   = fn_hit
    if br_found is not None: entry["b_found"] = br_found
    if br_hit   is not None: entry["b_hit"]   = br_hit


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


def merge_checksums(dict1: Dict[int, object],
                    dict2: Dict[int, object],
                    filename: str) -> Dict[int, object]:
    """dict1 and dict2 are dicts containing a mapping
    
      line number -> checksum
    
    Merge checksum lists defined in dict1 and dict2 and return resulting hash.
    Die if a checksum for a line is defined in both hashes but does not match.
    """
    result: Dict[int, object] = {}

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
            warn(f"WARNING: function data mismatch at {filename}:{line}\n")
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

# NOK
def brcount_db_combine(db1: Dict, db2: Dict, op: int):
    # db1 := db1 op db2, where
    #   db1, db2: brcount data as returned by brcount_to_db
    #   op:       one of BR_ADD and BR_SUB

    for line, ldata in db2.items():
        for block, bdata in ldata.items():
           for branch, taken in bdata.items():

                br_count = db1[line][block][branch]

                if !defined(br_count) or br_count == "-":
                    br_count = taken
                elif taken != "-":
                    if op == BR_ADD:
                        br_count += taken
                    elif op == BR_SUB:
                        br_count -= taken
                        if br_count < 0:
                            br_count = 0

                db1[line][block][branch] = br_count


def brcount_db_get_found_and_hit(db: Dict[int, Dict[object, Dict[object, object]]]) -> Tuple[int, int]:
    # Return (br_found, br_hit) for db.
    br_found, br_hit = 0, 0
    for line, ldata in db.items():
        for block, bdata in ldata.items():
            for branch, taken in bdata.items():
                br_found += 1
                if taken != "-" and taken > 0:
                    br_hit += 1
    return (br_found, br_hit)


def combine_brcount(brcount1: Dict[int, str],
                    brcount2: Dict[int, str],
                    op, *, inplace: bool = False) -> Tuple[Dict[int, str], int, int]:
    """If op is BR_ADD, add branch coverage data and return list brcount_added.
    If op is BR_SUB, subtract the taken values of brcount2 from brcount1 and
    return brcount_sub.
    If inplace is set, the result is inserted into brcount1.
    """
    db1 = brcount_to_db(brcount1)
    db2 = brcount_to_db(brcount2)
    brcount_db_combine(db1, db2, op)
    return db_to_brcount(db1, brcount1 if inplace else None)

# NOK
def brcount_to_db(brcount: Dict[int, str]) -> Dict[int, Dict[???, Dict[???, str]]]:
    """Convert brcount data to the following format:
     db:          line number    -> block dict
     block  dict: block number   -> branch dict
     branch dict: branch number  -> taken value
    """
    db: Dict[int, Dict[???, Dict[???, str]]] = {}

    # Add branches to database
    for line, brdata in brcount.items():
        for entry in brdata.split(":"):
            block, branch, taken = entry.split(",")
            if (line   not in db or
                block  not in db[line] or
                branch not in db[line][block] or
                db[line][block][branch] == "-"):
                if line not in db: db[line] = {}
                if block not in db[line]: db[line][block] = {}
                db[line][block][branch] = taken
            elif taken != "-":
                db[line][block][branch] += taken

    return db

# NOK
def db_to_brcount(db: Dict[int, Dict[???, Dict[???, str]]],
                  brcount: Optional[Dict[int, str]] = None) -> Tuple[Dict[int, str], int, int]:
    """Convert branch coverage data back to brcount format.
    If brcount is specified, the converted data is directly inserted in brcount.
    """
    if brcount is None: brcount = {}
    br_found = 0
    br_hit   = 0
    # Convert database back to brcount format
    for line in sorted({$a <=> $b} db.keys()):
        ldata: Dict[???, Dict[???, str]] = db[line]
        brdata = ""
        for block in sorted({$a <=> $b} ldata.keys()):
            bdata: Dict[???, str] = ldata[block]
            for branch in sorted({$a <=> $b} bdata.keys()):
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


def combine_info_files(info1: Dict[str, Dict[str, object]],
                       info2: Dict[str, Dict[str, object]]) -> Dict[str, Dict[str, object]]:
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


def combine_info_entries(entry1: Dict[str, object],
                         entry2: Dict[str, object],
                         filename: str) -> Dict[str, object]:
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
    result: Dict[str, object] = {}  # Hash containing combined entry
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

    info("Combining tracefiles.\n")

    total_trace: Dict[str, Dict[str, object]] = None
    for tracefile in args.add_tracefile:
        current = read_info_file(tracefile)
        total_trace = current if total_trace is None else combine_info_files(total_trace, current)

    # Write combined data
    if not data_to_stdout:
        info(f"Writing data to {args.output_filename}\n")
        try:
            with Path(args.output_filename).open("wt") as fhandle:
                result = write_info_file(fhandle, total_trace)
        except:
            die(f"ERROR: cannot write to {args.output_filename}!\n")
    else:
        result = write_info_file(sys.stdout, total_trace)

    return result


def write_info_file(fhandle, data: Dict[str, Dict[str, object]]) -> Tuple[int, int, int, int, int, int]:
    """ """
    global args

    ln_total_found = 0
    ln_total_hit   = 0
    fn_total_found = 0
    fn_total_hit   = 0
    br_total_found = 0
    br_total_hit   = 0

    for source_file in sorted(data.keys()):
        entry = data[source_file]

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

    data: Dict[str, Dict[str, object]] = read_info_file(args.extract)

    # Need perlreg expressions instead of shell pattern
    pattern_list: List[str] = [transform_pattern(elem) for elem in @ARGV] # NOK

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
            info(f"Extracting {filename}\n")
            extracted += 1

    # Write extracted data
    if not data_to_stdout:
        info(f"Extracted {extracted} files\n")
        info(f"Writing data to {args.output_filename}\n")
        try:
            with Path(args.output_filename).open("wt") as fhandle:
                result = write_info_file(fhandle, data)
        except:
            die(f"ERROR: cannot write to {args.output_filename}!\n")
    else:
        result = write_info_file(sys.stdout, data)

    return result


def remove() -> Tuple[int, int, int, int, int, int]:
    """ """
    global args
    global data_to_stdout

    data: Dict[str, Dict[str, object]] = read_info_file(args.remove)

    # Need perlreg expressions instead of shell pattern
    pattern_list: List[str] = [transform_pattern(elem) for elem in @ARGV] # NOK

    removed = 0
    # Filter out files that match the pattern
    for filename in sorted(data.keys()):
        match_found = False
        for pattern in pattern_list:
            match = re.match(rf"^{pattern}$", filename)
            match_found = match_found or match

        if match_found:
            del data[filename]
            info(f"Removing {filename}\n")
            removed += 1

    # Write data
    if not data_to_stdout:
        info(f"Deleted {removed} files\n")
        info(f"Writing data to {args.output_filename}\n")
        try:
            with Path(args.output_filename).open("wt") as fhandle:
                result = write_info_file(fhandle, data)
        except:
            die(f"ERROR: cannot write to {args.output_filename}!\n")
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
    foreach $path (@path_list):
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
def list():
    global options
    global args

    $data: Dict[str, Dict[str, object]] = read_info_file($list)

    my $filename;
    my $found;
    my $hit;
    my $prefix;
    my $format;
    my $heading1;
    my $heading2;
    my @footer;
    my $barlen;
    my $rate;
    my $fnrate;
    my $brrate;
    my $lastpath;

    F_LN_NUM  = 0
    F_LN_RATE = 1
    F_FN_NUM  = 2
    F_FN_RATE = 3
    F_BR_NUM  = 4
    F_BR_RATE = 5

    my @fwidth_narrow = (5, 5, 3, 5, 4, 5)
    my @fwidth_wide   = (6, 5, 5, 5, 6, 5)

    my @fwidth = @fwidth_wide;
    my $w;

    $max_width = options.list_width
    $max_long  = options.list_truncate_max

    my $fwidth_narrow_length;
    my $fwidth_wide_length;
    my $got_prefix = 0;
    my $root_prefix = 0;

    # Calculate total width of narrow fields
    $fwidth_narrow_length = 0;
    foreach $w (@fwidth_narrow) {
        $fwidth_narrow_length += $w + 1;
    }
    # Calculate total width of wide fields
    $fwidth_wide_length = 0;
    foreach $w (@fwidth_wide) {
        $fwidth_wide_length += $w + 1;
    }
    # Get common file path prefix
    $prefix = get_prefix($max_width - $fwidth_narrow_length, $max_long,
                 keys(%{$data}));
    if $prefix == rootdir(): $root_prefix = 1
    if (length($prefix) > 0):  $got_prefix  = 1
    $prefix =~ s/\/$//;

    # Get longest filename length
    $strlen = len("Filename")
    for $filename in (keys(%{$data})):
        if not options.list_full_path:
            if !$got_prefix or !$root_prefix and !($filename =~ s/^\Q$prefix\/\E//):
                $v, $d, $f = splitpath($filename)
                $filename = $f
        # Determine maximum length of entries
        if len($filename) > $strlen:
            $strlen = len($filename)

    if not options.list_full_path:
        my $blanks;

        $w = $fwidth_wide_length;
        # Check if all columns fit into max_width characters
        if ($strlen + $fwidth_wide_length > $max_width) {
            # Use narrow fields
            @fwidth = @fwidth_narrow;
            $w = $fwidth_narrow_length;
            if (($strlen + $fwidth_narrow_length) > $max_width) {
                # Truncate filenames at max width
                $strlen = $max_width - $fwidth_narrow_length;
            }
        }
        # Add some blanks between filename and fields if possible
        $blanks = int($strlen * 0.5);
        $blanks = 4 if ($blanks < 4);
        $blanks = 8 if ($blanks > 8);
        if ($strlen + $w + $blanks) < $max_width:
            $strlen += $blanks;
        else:
            $strlen = $max_width - $w;

    # Filename
    w = $strlen;
    $format   = "%-${w}s|"
    $heading1 = sprintf("%*s|",  w, "")
    $heading2 = sprintf("%-*s|", w, "Filename")
    $barlen   = w + 1
    # Line coverage rate
    w = $fwidth[$F_LN_RATE]
    $format   += "%${w}s "
    $heading1 += sprintf("%-*s |", w + $fwidth[$F_LN_NUM], "Lines")
    $heading2 += sprintf("%-*s ",  w, "Rate")
    $barlen   += w + 1
    # Number of lines
    w = $fwidth[$F_LN_NUM]
    $format   += "%${w}s|"
    $heading2 += sprintf("%*s|", w, "Num")
    $barlen   += w + 1
    # Function coverage rate
    w = $fwidth[$F_FN_RATE]
    $format   += "%${w}s "
    $heading1 += sprintf("%-*s|", w + $fwidth[$F_FN_NUM] + 1, "Functions")
    $heading2 += sprintf("%-*s ", w, "Rate")
    $barlen   += w + 1
    # Number of functions
    w = $fwidth[$F_FN_NUM]
    $format   += "%${w}s|"
    $heading2 += sprintf("%*s|", w, "Num")
    $barlen   += w + 1
    # Branch coverage rate
    w = $fwidth[$F_BR_RATE]
    $format   += "%${w}s "
    $heading1 += sprintf("%-*s",  w + $fwidth[$F_BR_NUM] + 1, "Branches")
    $heading2 += sprintf("%-*s ", w, "Rate")
    $barlen   += w + 1
    # Number of branches
    w = $fwidth[$F_BR_NUM]
    $format   += "%${w}s"
    $heading2 += sprintf("%*s", w, "Num")
    $barlen   += w
    # Line end
    $format   += "\n"
    $heading1 += "\n"
    $heading2 += "\n"

    # Print heading
    print($heading1);
    print($heading2);
    print(("="x$barlen)."\n");

    ln_total_found = 0
    ln_total_hit   = 0
    fn_total_found = 0
    fn_total_hit   = 0
    br_total_found = 0
    br_total_hit   = 0

    # Print per file information
    for $filename in sorted($data.keys()):

        my @file_data;
        my $print_filename = $filename;

        entry = $data->{$filename};
        if not options.list_full_path:
        {
            my $p;

            $print_filename = $filename;
            if (!$got_prefix or !$root_prefix and
                !($print_filename =~ s/^\Q$prefix\/\E//)):
                my ($v, $d, $f) = splitpath($filename);

                $p = catpath($v, $d, "");
                $p =~ s/\/$//;
                $print_filename = $f;
            else:
                $p = $prefix;

            if (!defined($lastpath) or $lastpath != $p) {
                print("\n") if (defined($lastpath));
                $lastpath = $p;
                print("[$lastpath/]\n") if (!$root_prefix);
            }
            $print_filename = shorten_filename($print_filename, $strlen);
        }

        (_, _, _, _, _, _, _, _,
         $found,    $hit,
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
        ln_total_found += found
        ln_total_hit   += hit
        # Add function coverage totals
        fn_total_found += fn_found
        fn_total_hit   += fn_hit
        # Add branch coverage totals
        br_total_found += br_found
        br_total_hit   += br_hit

        # Determine line coverage rate for this file
        rate = shorten_rate(hit, found, $fwidth[$F_LN_RATE]);
        # Determine function coverage rate for this file
        fnrate = shorten_rate(fn_hit, fn_found, $fwidth[$F_FN_RATE]);
        # Determine branch coverage rate for this file
        brrate = shorten_rate(br_hit, br_found, $fwidth[$F_BR_RATE]);

        # Assemble line parameters
        @file_data.append($print_filename);
        @file_data.append($rate);
        @file_data.append(shorten_number(found, $fwidth[$F_LN_NUM]));
        @file_data.append($fnrate);
        @file_data.append(shorten_number(fn_found, $fwidth[$F_FN_NUM]));
        @file_data.append($brrate);
        @file_data.append(shorten_number(br_found, $fwidth[$F_BR_NUM]));

        # Print assembled line
        printf($format, @file_data);

    # Determine total line coverage rate
    rate = shorten_rate(ln_total_hit, ln_total_found, $fwidth[$F_LN_RATE]);
    # Determine total function coverage rate
    fnrate = shorten_rate(fn_total_hit, fn_total_found, $fwidth[$F_FN_RATE]);
    # Determine total branch coverage rate
    brrate = shorten_rate(br_total_hit, br_total_found, $fwidth[$F_BR_RATE]);

    # Print separator
    print(("="x$barlen)."\n");

    # Assemble line parameters
    @footer.append(sprintf("%*s", $strlen, "Total:"));
    @footer.append($rate);
    @footer.append(shorten_number(ln_total_found, $fwidth[$F_LN_NUM]));
    @footer.append($fnrate);
    @footer.append(shorten_number(fn_total_found, $fwidth[$F_FN_NUM]));
    @footer.append($brrate);
    @footer.append(shorten_number(br_total_found, $fwidth[$F_BR_NUM]));

    # Print assembled line
    printf($format, @footer);


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

# NOK
def read_diff(diff_file: Path) -> Tuple[Dict, Dict]:
    # Read diff output from FILENAME to memory. The diff file has to follow the
    # format generated by 'diff -u'. Returns a list of hash references:
    #
    #   (mapping, path mapping)
    #
    #   mapping:   filename -> reference to line hash
    #   line hash: line number in new file -> corresponding line number in old file
    #
    #   path mapping:  filename -> old filename
    #
    # Die in case of error.
    global args

    my $mapping;        # Reference to current line hash
    my $num_old;        # Current line number in old file
    my $num_new;        # Current line number in new file
    my $file_old;        # Name of old file in diff section
    my $file_new;        # Name of new file in diff section
    my $filename;        # Name of common filename of diff section

    info(f"Reading diff {diff_file}\n")

    # Check if file exists and is readable
    if not os.access(diff_file, os.R_OK):
        die(f"ERROR: cannot read file {diff_file}!\n")
    # Check if this is really a plain file
    fstatus = diff_file.stat()
    if ! (-f _):
        die(f"ERROR: not a plain file: {diff_file}!\n")

    # Check for .gz extension
    if $diff_file =~ /\.gz$/:
        # Check for availability of GZIP tool
        system_no_output(1, "gunzip", "-h")
            and die("ERROR: gunzip command not available!\n")
        # Check integrity of compressed file
        system_no_output(1, "gunzip", "-t", str(diff_file))
            and die(f"ERROR: integrity check failed for compressed file {diff_file}!\n")
        # Open compressed file
        fhandle = open("-|", "gunzip -c 'str(diff_file)'")
            or die("ERROR: cannot start gunzip to decompress file $_[0]!\n")
    else:
        # Open decompressed file
        try:
            fhandle = diff_file.open("rt")
        except:
            or die("ERROR: cannot read file $_[0]!\n");

    # Parse diff file line by line
    diff:  Dict = {}  # Resulting mapping filename -> line hash
    paths: Dict = {}  # Resulting mapping old path -> new path
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
                if $filename:
                    diff[filename] = $mapping
                    $mapping = {}
                $file_new = strip_directories($1, args.strip)
                $filename = $file_old;
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
                    $mapping[num_new] = num_old
                    num_old += 1
                    num_new += 1
                continue

            # Unchanged line
            # <line starts with blank>
            match = re.match(r"^ ", line)
            if match:
                if not in_block: continue
                $mapping[num_new] = num_old
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
                $mapping[num_new] = num_old
                num_old += 1
                num_new += 1
                continue

    # Add final diff file section to resulting hash
    if $filename:
        diff[filename] = $mapping

    if ! %diff:
        die(f"ERROR: no valid diff data found in {diff_file}!\n"
            "Make sure to use 'diff -u' when generating the diff file.\n")

    return (%diff, %paths)


def strip_directories(path: str, depth: Optional[int] = None) -> str:
    """Remove depth leading directory levels from path."""
    if depth is not None and depth >= 1:
        for _ in range(depth):
            path = re.sub(r"^[^/]*/+(.*)$", r"\1", path)
    return path

# NOK
def apply_diff(count_data: Dict[int, object], line_hash: Dict[int, int]) -> Dict[int, object]:
    """Transform count data using a mapping of lines:
    
      count_data: reference to hash: line number -> data
      line_hash:  reference to hash: line number new -> line number old
    
    Return a reference to transformed count data.
    """
    result: Dict[int, object] = {}  # Resulting hash

    last_new: int = 0  # Last new line number found in line hash
    last_old: int = 0  # Last old line number found in line hash
    # Iterate all new line numbers found in the diff
    for last_new in sorted({$a <=> $b} line_hash.keys()):
        last_old = line_hash[last_new]
        # Is there data associated with the corresponding old line?
        if last_old in count_data:
            # Copy data to new hash with a new line number
            result[last_new] = count_data[last_old]

    # Transform all other lines which come after the last diff entry
    for line in sorted({$a <=> $b} count_data.keys()):
        if line <= last_old:
            # Skip lines which were covered by line hash
            continue
        # Copy data to new hash with an offset
        result[line + (last_new - last_old)] = count_data[line]

    return result


def apply_diff_to_brcount(brcount:  Dict[int, str],
                          linedata: Dict[int, int]) -> Tuple[Dict[int, str], int, int]:
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

# NOK
def get_line_hash(filename, diff_data: Dict, path_data: Dict) -> Optional[Tuple[?, ?, ?]]:
    # Find line hash in DIFF_DATA which matches FILENAME.
    # On success, return list line hash. or None in case of no match.
    # Die if more than one line hashes in DIFF_DATA match.

    my $conversion;
    my $old_path;
    my $new_path;
    my $diff_name;
    my $common;
    my $old_depth;
    my $new_depth;

    # Remove trailing slash from diff path
    $diff_path =~ s/\/$//;

    for $_ in keys(%{$diff_data}):
        $sep = ""
        if ! /^\//: $sep = "/"

        # Try to match diff filename with filename
        if ($filename =~ /^\Q$diff_path$sep$_\E$/):
            if $diff_name:
                # Two files match, choose the more specific one
                # (the one with more path components)
                $old_depth = ($diff_name =~ tr/\///);
                $new_depth = (tr/\///);
                if $old_depth == $new_depth:
                    die(f"ERROR: diff file contains ambiguous entries for {filename}\n")
                elif $new_depth > $old_depth:
                    $diff_name = $_;
            else:
                $diff_name = $_;

    if $diff_name:
        # Get converted path
        if $filename =~ /^(.*)$diff_name$/:
            $common, $old_path, $new_path = get_common_filename($filename,
                                                                $1 + $path_data->{$diff_name})
        return ($diff_data->{$diff_name}, $old_path, $new_path)
    else:
        return None

# NOK
def get_common_filename(filename1: str,
                        filename2: str) -> Optional[Tuple[str, str, str]]
    """Check for filename components which are common to FILENAME1 and FILENAME2.
    Upon success, return

      (common, path1, path2)

    or None in case there are no such parts.
    """
    # !!! przetestowac zgodnosc z Perlowa wersja !!!
    parts1 = filename1.split("/")
    parts2 = filename2.split("/")

    common = []
    # Work in reverse order, i.e. beginning with the filename itself
    while parts1 and parts2 and $parts1[$#parts1] == $parts2[$#parts2]:
        common_part = parts1.pop()
        parts2.pop()
        unshift(common, common_part)

    # Did we find any similarities?
    if common:
        return ("/".join(common), "/".join(parts1), "/".join(parts2))
    else:
        return None


def diff() -> Tuple[int, int, int, int, int, int]:
    """ """
    global args
    global data_to_stdout

    trace_data: Dict[str, Dict[str, object]] = read_info_file(args.diff)

    diff_data: Dict, path_data: Dict = read_diff(Path($ARGV[0])) # NOK

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

        line_hash, old_path, new_path = line_hash_result

        converted += 1
        if old_path and new_path and old_path != new_path:
            path_conversion_data[old_path] = new_path

        # Check for deleted files
        if len(line_hash) == 0:
            info(f"Removing {filename}\n")
            del trace_data[filename]
            continue

        info(f"Converting {filename}\n")
        entry = trace_data[filename]
        (testdata, sumcount, funcdata, checkdata,
         testfncdata, sumfnccount,
         testbrdata,  sumbrcount) = get_info_entry(entry)

        # Convert test data
        for testname in list(testdata.keys()):
            # Adjust line numbers of line coverage data
            testdata[testname] = apply_diff(testdata[testname], line_hash)
            # Adjust line numbers of branch coverage data
            testbrdata[testname] = apply_diff_to_brcount(testbrdata[testname], line_hash)
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
        sumcount = apply_diff(sumcount, line_hash)
        # Convert function data
        funcdata = apply_diff_to_funcdata(funcdata, line_hash)
        # Convert branch coverage data
        sumbrcount = apply_diff_to_brcount(sumbrcount, line_hash)
        # Update found/hit numbers
        # Convert checksum data
        checkdata = apply_diff(checkdata, line_hash)
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
         f"{unchanged} entr" + ("ies" if unchanged != 1 else "y") + " left unchanged.\n")

    # Write data
    if not data_to_stdout:
        info(f"Writing data to {args.output_filename}\n")
        try:
            with Path(args.output_filename).open("wt") as fhandle:
                result = write_info_file(fhandle, trace_data)
        except:
            die(f"ERROR: cannot write to {args.output_filename}!\n")
    else:
        result = write_info_file(sys.stdout, trace_data)

    return result

# NOK
def convert_paths($trace_data, path_conversion_data: Dict[str, str]):
    # Rename all paths in TRACE_DATA which show up in PATH_CONVERSION_DATA.

    if len(path_conversion_data) == 0:
        info("No path conversion data available.\n")
        return

    # Expand path conversion list
    for filename in list(path_conversion_data.keys()):
        new_path = path_conversion_data[filename]
        while (($filename =~ s/^(.*)\/[^\/]+$/$1/) and
               ($new_path =~ s/^(.*)\/[^\/]+$/$1/) and
               filename != new_path):
            path_conversion_data[filename] = new_path

    # Adjust paths
    FILENAME:
    for filename in list($trace_data.keys()):
        # Find a path in our conversion table that matches, starting
        # with the longest path
        for $_ in sorted({length($b) <=> length($a)} path_conversion_data.keys()):
            # Is this path a prefix of our filename?
            if ! ($filename =~ /^$_(.*)$/):
                continue

            new_path = $path_conversion_data->{$_}.$1;

            # Make sure not to overwrite an existing entry under
            # that path name
            if trace_data[new_path]:
                # Need to combine entries
                trace_data[new_path] = combine_info_entries(trace_data[filename],
                                                            trace_data[new_path],
                                                            filename)
            else:
                # Simply rename entry
                trace_data[new_path] = trace_data[filename]

            del trace_data[filename]
            next FILENAME;

        info(f"No conversion available for filename {filename}\n")


def summary() -> Tuple[int, int, int, int, int, int]:
    """ """
    global args

    total: Dict[str, Dict[str, object]] = None
    # Read and combine trace files
    for filename in args.summary:
        current = read_info_file(filename)
        total = current if total is None else combine_info_files(total, current)

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


def get_branch_found_and_hit(brcount: Dict[int, str]) -> Tuple[int, int]:
    """ """
    db = brcount_to_db(brcount)
    return brcount_db_get_found_and_hit(db)


def temp_cleanup():
    """ """
    global temp_dirs

    # Ensure temp directory is not in use by current process
    os.chdir("/")
    if temp_dirs:
        info("Removing temporary directories.\n")
        for dir in temp_dirs:
            shutil.rmtree(str(dir))
        temp_dirs.clear()


def setup_gkv_sys():
    system_no_output(3, "mount", "-t", "debugfs", "nodev", "/sys/kernel/debug")


def setup_gkv_proc():
    if (system_no_output(3, "modprobe", "gcov_proc")):
        system_no_output(3, "modprobe", "gcov_prof")


def setup_gkv() -> Tuple[int, Path]:
    """ """
    global options

    sys_dir  = Path("/sys/kernel/debug/gcov")
    proc_dir = Path("/proc/gcov")

    if options.gcov_dir is None:
        info("Auto-detecting gcov kernel support.\n")
        todo = ["cs", "cp", "ss", "cs", "sp", "cp"]
    elif re.search(r"proc", str(options.gcov_dir)):
        info(f"Checking gcov kernel support at {options.gcov_dir} (user-specified).\n")
        todo = ["cp", "sp", "cp", "cs", "ss", "cs"]
    else:
        info(f"Checking gcov kernel support at {options.gcov_dir} (user-specified).\n")
        todo = ["cs", "ss", "cs", "cp", "sp", "cp"]

    for action in todo:
        if action == "cs":
            # Check /sys
            dir = options.gcov_dir or sys_dir
            if check_gkv_sys(dir):
                info(f"Found {GKV_NAME[GKV_SYS]} gcov kernel support at {dir}\n")
                return (GKV_SYS, dir)
        elif action == "cp":
            # Check /proc
            dir = options.gcov_dir or proc_dir
            if check_gkv_proc(dir):
                info(f"Found {GKV_NAME[GKV_PROC]} gcov kernel support at {dir}\n")
                return (GKV_PROC, dir)
        elif action == "ss":
            # Setup /sys
            setup_gkv_sys()
        elif action == "sp":
            # Setup /proc
            setup_gkv_proc()
    else:
        if options.gcov_dir:
            die(f"ERROR: could not find gcov kernel data at {options.gcov_dir}\n")
        else:
            die("ERROR: no gcov kernel data found\n")


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
    info(title + "\n")
    if ln_do:
        info("  lines......: %s\n",
             get_overall_line(ln_found, ln_hit, "line", "lines"))
    if fn_do:
        info("  functions..: %s\n",
             get_overall_line(fn_found, fn_hit, "function", "functions"))
    if br_do:
        info("  branches...: %s\n",
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


def main(argv=sys.argv[1:]):

    def warn_handler(msg: str):
        global tool_name
        warn(f"{tool_name}: {msg}")

    def die_handler(msg: str):
        global tool_name
        temp_cleanup()
        die(f"{tool_name}: {msg}")

    def abort_handler(msg: str):
        temp_cleanup()
        return 1

    # $SIG{__WARN__} = warn_handler
    # $SIG{__DIE__}  = die_handler
    # $SIG{'INT'}    = abort_handler
    # $SIG{'QUIT'}   = abort_handler


if __name__.rpartition(".")[-1] == "__main__":
    sys.exit(main())
