# CCopyright (c) 2020-2022, Adam Karpierz
# Licensed under the BSD license
# https://opensource.org/licenses/BSD-3-Clause

"""
geninfo

  This script generates .info files from data files as created by code
  instrumented with gcc's built-in profiling mechanism. Call it with
  --help and refer to the geninfo man page to get information on usage
  and available options.

"""

# Authors:
#   2002-08-23 created by Peter Oberparleiter <Peter.Oberparleiter@de.ibm.com>
#                         IBM Lab Boeblingen
#        based on code by Manoj Iyer <manjo@mail.utexas.edu> and
#                         Megan Bock <mbock@us.ibm.com>
#                         IBM Austin
#   2002-09-05 / Peter Oberparleiter: implemented option that allows file list
#   2003-04-16 / Peter Oberparleiter: modified read_gcov so that it can also
#                parse the new gcov format which is to be introduced in gcc 3.3
#   2003-04-30 / Peter Oberparleiter: made info write to STDERR, not STDOUT
#   2003-07-03 / Peter Oberparleiter: added line checksum support, added
#                --no-checksum
#   2003-09-18 / Nigel Hinds: capture branch coverage data from GCOV
#   2003-12-11 / Laurent Deniel: added --follow option
#                workaround gcov (<= 3.2.x) bug with empty .da files
#   2004-01-03 / Laurent Deniel: Ignore empty .bb files
#   2004-02-16 / Andreas Krebbel: Added support for .gcno/.gcda files and
#                gcov versioning
#   2004-08-09 / Peter Oberparleiter: added configuration file support
#   2008-07-14 / Tom Zoerner: added --function-coverage command line option
#   2008-08-13 / Peter Oberparleiter: modified function coverage
#                implementation (now enabled per default)

#use strict;
#use warnings;
#use File::Basename;
#use File::Spec::Functions qw /catdir file_name_is_absolute splitdir
#                  splitpath catpath/;
#use File::Temp qw(tempdir);
#use File::Copy qw(copy);
#use Getopt::Long;
#use Digest::MD5 qw(md5_base64);
if $^O == "msys":
    require File::Spec::Win32;

from typing import List, Dict, Optional
import argparse
import sys
import re
from pathlib import Path
import gzip

from .util import unique
from .util import sort_unique
from .util import sort_unique_lex
from .util import remove_items_from_dict
from .util import apply_config
from .util import system_no_output, NO_ERROR
from .util import transform_pattern
from .util import strip_spaces_in_options
from .util import parse_ignore_errors
from .util import warn, die

# Constants
tool_name    = Path(__file__).stem
lcov_version = "LCOV version " #+ `${abs_path(dirname($0))}/get_version.sh --full`
lcov_url     = "http://ltp.sourceforge.net/coverage/lcov.php"

GCOV_VERSION_8_0_0 = 0x80000
GCOV_VERSION_4_7_0 = 0x40700
GCOV_VERSION_3_4_0 = 0x30400
GCOV_VERSION_3_3_0 = 0x30300

GCNO_FUNCTION_TAG  = 0x01000000
GCNO_LINES_TAG     = 0x01450000
GCNO_FILE_MAGIC    = 0x67636e6f
BBG_FILE_MAGIC     = 0x67626267

# Error classes which users may specify to ignore during processing
ERROR_GCOV   = 0
ERROR_SOURCE = 1
ERROR_GRAPH  = 2
ERROR_ID = {
    "gcov":   ERROR_GCOV,
    "source": ERROR_SOURCE,
    "graph":  ERROR_GRAPH,
}

EXCL_START = "LCOV_EXCL_START"
EXCL_STOP  = "LCOV_EXCL_STOP"

# Marker to exclude branch coverage but keep function and line coverage
EXCL_BR_START = "LCOV_EXCL_BR_START"
EXCL_BR_STOP  = "LCOV_EXCL_BR_STOP"

# Marker to exclude exception branch coverage but keep function,
# line coverage and non-exception branch coverage
EXCL_EXCEPTION_BR_START = "LCOV_EXCL_EXCEPTION_BR_START"
EXCL_EXCEPTION_BR_STOP  = "LCOV_EXCL_EXCEPTION_BR_STOP"

# Compatibility mode values
COMPAT_VALUE_OFF  = 0
COMPAT_VALUE_ON   = 1
COMPAT_VALUE_AUTO = 2

# Compatibility mode value names
COMPAT_NAME_TO_VALUE = {
    "off":  COMPAT_VALUE_OFF,
    "on":   COMPAT_VALUE_ON,
    "auto": COMPAT_VALUE_AUTO,
}

# Compatiblity modes
COMPAT_MODE_LIBTOOL   = 1 << 0
COMPAT_MODE_HAMMER    = 1 << 1
COMPAT_MODE_SPLIT_CRC = 1 << 2

# Compatibility mode names
COMPAT_NAME_TO_MODE = {
    "libtool":       COMPAT_MODE_LIBTOOL,
    "hammer":        COMPAT_MODE_HAMMER,
    "split_crc":     COMPAT_MODE_SPLIT_CRC,
    "android_4_4_0": COMPAT_MODE_SPLIT_CRC,
}

# Map modes to names
COMPAT_MODE_TO_NAME = {
    COMPAT_MODE_LIBTOOL:   "libtool",
    COMPAT_MODE_HAMMER:    "hammer",
    COMPAT_MODE_SPLIT_CRC: "split_crc",
}

# Compatibility mode default values
COMPAT_MODE_DEFAULTS = {
    COMPAT_MODE_LIBTOOL:   COMPAT_VALUE_ON,
    COMPAT_MODE_HAMMER:    COMPAT_VALUE_AUTO,
    COMPAT_MODE_SPLIT_CRC: COMPAT_VALUE_AUTO,
}

# Compatibility mode auto-detection routines
COMPAT_MODE_AUTO = {
    COMPAT_MODE_HAMMER:    compat_hammer_autodetect,
    COMPAT_MODE_SPLIT_CRC: 1,  # will be done later
}

BR_LINE        = 0
BR_BLOCK       = 1
BR_BRANCH      = 2
BR_TAKEN       = 3
BR_VEC_ENTRIES = 4
BR_VEC_WIDTH   = 32
BR_VEC_MAX     = vec(pack("b*", 1 x $BR_VEC_WIDTH), 0, BR_VEC_WIDTH)

UNNAMED_BLOCK = -1

# Global variables
options.gcov_tool: str = "gcov"
gcov_version: int
gcov_version_string: str
graph_file_extension: str
data_file_extension:  str
our @data_directory;
our $test_name = "";
args.quiet: bool = False  # If set, suppress information messages
args.help:  bool = False  # Help option flag
args.output_filename: Optional[str] = None
$base_directory: Optional = None
args.version: bool = False  # Version option flag
args.follow:  bool = False
our $checksum;
options.no_checksum:    Optional[bool] = None  # If set, don't calculate a checksum for each line
options.compat_libtool: Optional[bool] = None
args.no_compat_libtool: Optional[bool] = None
options.adjust_src_path: str = None  # Regexp specifying parts to remove from source path
adjust_src_pattern: Optional[???] = None
adjust_src_replace: Optional[???] = None
options.adjust_testname: bool = False
our $config;        # Configuration file contents
args.ignore_errors:    List[str] = []  # List of errors to ignore (parameter)
ignore: Dict[int, bool] = {}  # List of errors to ignore (array)
args.initial = False
args.include_patterns: List[str] = []  # List of source file patterns to include
args.exclude_patterns: List[str] = []  # List of source file patterns to exclude
excluded_files: Set[???] = set()  # Files excluded due to include/exclude options
args.no_recursion: bool = False
args.no_markers:   bool = False
options.derive_func_data: bool = False
options.external: bool = True
our $opt_no_external;
args.debug = False
gcov_capabilities: Set[str] = set()
internal_dirs: List[str] = []
our $opt_config_file;
options.gcov_all_blocks: bool = True
opt_compat: Optional[str] = None
our %opt_rc;
compat_value: Dict[int, int] = {}
gcno_split_crc: Optional[bool] = None
our $fn_coverage = 1
our $br_coverage = 0
options.no_exception_br: bool = False
options.auto_base: bool = True
intermediate: bool = False
options.intermediate: str = "auto"
options.excl_line:              str = "LCOV_EXCL_LINE"
options.excl_br_line:           str = "LCOV_EXCL_BR_LINE"
options.excl_exception_br_line: str = "LCOV_EXCL_EXCEPTION_BR_LINE"

gcov_options = []

cwd = Path.cwd()  # Current working directory
$cwd = `pwd`;
chomp($cwd);

#
# Code entry point
#

# Set LC_ALL so that gcov output will be in a unified format
$ENV{"LC_ALL"} = "C";

# Check command line for a configuration file name
Getopt::Long::Configure("pass_through", "no_auto_abbrev");
GetOptions("config-file=s" => \$opt_config_file,
       "rc=s%" => \%opt_rc);
Getopt::Long::Configure("default");

# Remove spaces around rc options
%opt_rc = strip_spaces_in_options(%opt_rc)
# Read configuration file if available
$config = read_lcov_config_file($opt_config_file)

if $config or %opt_rc:

    # Copy configuration file and --rc values to variables
    apply_config({
        "geninfo_gcov_tool"           => \options.gcov_tool,
        "geninfo_adjust_testname"     => \options.adjust_testname,
        "geninfo_checksum"            => \$checksum,
        "geninfo_no_checksum"         => \options.no_checksum, # deprecated
        "geninfo_compat_libtool"      => \options.compat_libtool,
        "geninfo_external"            => \options.external,
        "geninfo_gcov_all_blocks"     => \options.gcov_all_blocks,
        "geninfo_compat"              => \opt_compat,
        "geninfo_adjust_src_path"     => \options.adjust_src_path,
        "geninfo_auto_base"           => \options.auto_base,
        "geninfo_intermediate"        => \options.intermediate,
        "geninfo_no_exception_branch" => \options.no_exception_br,
        "lcov_function_coverage"      => \$fn_coverage,
        "lcov_branch_coverage"        => \$br_coverage,
        "lcov_excl_line"              => \options.excl_line,
        "lcov_excl_br_line"           => \options.excl_br_line,
        "lcov_excl_exception_br_line" => \options.excl_exception_br_line,
    });

    # Merge options
    if options.no_checksum is not None:
        $checksum = (0 if options.no_checksum else 1)
        options.no_checksum = None

    # Check regexp
    if options.adjust_src_path is not None:
        my ($pattern, $replace) = split(/\s*=>\s*/, options.adjust_src_path)
        local $SIG{__DIE__};
        eval '$adjust_src_pattern = qr>'.$pattern.'>;';
        if adjust_src_pattern is None:
            my $msg = $@;
            $msg = $msg.rstrip("\n")
            $msg =~ s/at \(eval.*$//;
            warn(f"WARNING: invalid pattern in geninfo_adjust_src_path: $msg")
        elif ! defined($replace):
            # If no replacement is specified, simply remove pattern
            adjust_src_replace = ""
        else:
            adjust_src_replace = $replace

    for my $regexp in (options.excl_line, options.excl_br_line, options.excl_exception_br_line):
        eval 'qr/'.$regexp.'/';
        my $error = $@;
        chomp($error);
        $error =~ s/at \(eval.*$//;
        if $error:
            die(f"ERROR: invalid exclude pattern: {error}", end="")

# Parse command line options
if (!GetOptions(
        "test-name|t=s"       => \$test_name,
        "output-filename|o=s" => \args.output_filename,
        "checksum"            => \$checksum,
        "no-checksum"         => \options.no_checksum,
        "base-directory|b=s"  => \args.base_directory,
        "version|v"           => \args.version,
        "quiet|q"             => \args.quiet,
        "help|h|?"            => \args.help,
        "follow|f"            => \args.follow,
        "compat-libtool"      => \options.compat_libtool,
        "no-compat-libtool"   => \args.no_compat_libtool,
        "gcov-tool=s"         => \options.gcov_tool,
        "ignore-errors=s"     => \args.ignore_errors,
        "initial|i"           => \args.initial,
        "include=s"           => \args.include_patterns,
        "exclude=s"           => \args.exclude_patterns,
        "no-recursion"        => \args.no_recursion,
        "no-markers"          => \args.no_markers,
        "derive-func-data"    => \options.derive_func_data,
        "debug"               => \args.debug,
        "external|e"          => \options.external,
        "no-external"         => \opt_no_external,
        "compat=s"            => \opt_compat,
        "config-file=s"       => \$opt_config_file,
        "rc=s%"               => \%opt_rc,
        )):
    print(f"Use {tool_name} --help to get usage information", file=sys.stderr)
    sys.exit(1)

# Merge options
if options.no_checksum is not None:
    $checksum = not options.no_checksum
if args.no_compat_libtool is not None:
    options.compat_libtool = not args.no_compat_libtool
if $opt_no_external is not None:
    options.external = False
if args.include_patterns:
    # Need perlreg expressions instead of shell pattern
    args.include_patterns = [transform_pattern(elem) for elem in args.include_patterns]
if args.exclude_patterns:
    # Need perlreg expressions instead of shell pattern
    args.exclude_patterns = [transform_pattern(elem) for elem in args.exclude_patterns]

@data_directory = @ARGV;

debug(f"{lcov_version}\n")

# Check for help option
if args.help:
    print_usage(sys.stdout)
    sys.exit(0)

# Check for version option
if args.version:
    print(f"{tool_name}: {lcov_version}")
    sys.exit(0)

# Check gcov tool
if system_no_output(3, options.gcov_tool, "--help")[0] != NO_ERROR:
    die(f"ERROR: need tool {options.gcov_tool}!")

gcov_version, gcov_version_string = get_gcov_version()
gcov_capabilities = get_gcov_capabilities()

# Determine intermediate mode
if options.intermediate == "0":
    intermediate = False
elif options.intermediate == "1":
    intermediate = True
elif options.intermediate.lower() == "auto":
    # Use intermediate format if supported by gcov and not conflicting with
    # exception branch exclusion
    intermediate = (("intermediate-format" in gcov_capabilities and not options.no_exception_br) or
                    "json-format" in gcov_capabilities)
else:
    die("ERROR: invalid value for geninfo_intermediate: "
        r"'{options.intermediate}'")

if intermediate:
    info("Using intermediate gcov format")
    if options.derive_func_data:
        warn("WARNING: --derive-func-data is not compatible with ".
             "intermediate format - ignoring")
        options.derive_func_data = False
    if options.no_exception_br and "json-format" not in gcov_capabilities:
        die("ERROR: excluding exception branches is not compatible with ".
            "text intermediate format")

if options.no_exception_br and gcov_version < GCOV_VERSION_3_3_0:
    die("ERROR: excluding exception branches is not compatible with ".
        "gcov versions older than 3.3")

# Determine gcov options
if "branch-probabilities" in gcov_capabilities and ($br_coverage or $fn_coverage):
    gcov_options.append("-b")
if "branch-counts" in gcov_capabilities and $br_coverage:
    gcov_options.append("-c")
if "all-blocks" in gcov_capabilities and options.gcov_all_blocks and $br_coverage and not intermediate:
    gcov_options.append("-a")
if "hash-filenames" in gcov_capabilities:
    gcov_options.append("-x");
elif "preserve-paths" in gcov_capabilities:
    gcov_options.append("-p")

# Determine compatibility modes
parse_compat_modes(opt_compat, compat_value)
# Determine which errors the user wants us to ignore
parse_ignore_errors(args.ignore_errors, ignore)

# Make sure test names only contain valid characters
if $test_name =~ s/\W/_/g:
    warn("WARNING: invalid characters removed from testname!")

# Adjust test name to include uname output if requested
if options.adjust_testname:
    $test_name += "__".`uname -a`;
    $test_name =~ s/\W/_/g;

# Make sure base_directory contains an absolute path specification
if args.base_directory:
    args.base_directory = solve_relative_path(cwd, args.base_directory)

# Determine checksum mode (default is off)
$checksum = bool($checksum) if $checksum is not None else False

# Check for directory name
if ! @data_directory:
    die(f"No directory specified\n"
        f"Use {tool_name} --help to get usage information")

for entry in @data_directory:
    if not os.access(entry, os.R_OK):
        die(f"ERROR: cannot read {entry}!")

if gcov_version >= GCOV_VERSION_3_4_0:
    data_file_extension  = ".gcda"
    graph_file_extension = ".gcno"
elif is_compat($COMPAT_MODE_HAMMER):
    data_file_extension  = ".da"
    graph_file_extension = ".bbg"
else:
    data_file_extension  = ".da"
    graph_file_extension = ".bb"

# Check output filename
if args.output_filename and args.output_filename != "-":
    # Initially create output filename, data is appended
    # for each data file processed
    try:
        with Path(args.output_filename).open("wb"):
            pass
    except:
        die("ERROR: cannot create {output_filename}!")

    # Make args.output_filename an absolute path because we're going
    # to change directories while processing files
    if not (args.output_filename =~ /^\/(.*)$/):
        args.output_filename = $cwd."/".args.output_filename

# Build list of directories to identify external files
for entry in (@data_directory + [args.base_directory]):
    if entry is not None:
        internal_dirs.append(solve_relative_path(cwd, entry))

# Do something
for entry in @data_directory:
    gen_info(entry)

if args.initial and $br_coverage and not intermediate:
    warn("Note: --initial does not generate branch coverage data")

info("Finished .info-file creation")

sys.exit(0)


def print_usage(fhandle):
    """Print usage information."""
    global tool_name, lcov_url
    print(f"""\
Usage: {tool_name} [OPTIONS] DIRECTORY

Traverse DIRECTORY and create a .info file for each data file found. Note
that you may specify more than one directory, all of which are then processed
sequentially.

  -h, --help                        Print this help, then exit
  -v, --version                     Print version number, then exit
  -q, --quiet                       Do not print progress messages
  -i, --initial                     Capture initial zero coverage data
  -t, --test-name NAME              Use test case name NAME for resulting data
  -o, --output-filename OUTFILE     Write data only to OUTFILE
  -f, --follow                      Follow links when searching .da/.gcda files
  -b, --base-directory DIR          Use DIR as base directory for relative paths
      --(no-)checksum               Enable (disable) line checksumming
      --(no-)compat-libtool         Enable (disable) libtool compatibility mode
      --gcov-tool TOOL              Specify gcov tool location
      --ignore-errors ERROR         Continue after ERROR (gcov, source, graph)
      --no-recursion                Exclude subdirectories from processing
      --no-markers                  Ignore exclusion markers in source code
      --derive-func-data            Generate function data from line data
      --(no-)external               Include (ignore) data for external files
      --config-file FILENAME        Specify configuration file location
      --rc SETTING=VALUE            Override configuration file setting
      --compat MODE=on|off|auto     Set compat MODE (libtool, hammer, split_crc)
      --include PATTERN             Include files matching PATTERN
      --exclude PATTERN             Exclude files matching PATTERN

For more information see: {lcov_url}""", file=fhandle)

# NOK
def gen_info(directory: str):
    """Traverse DIRECTORY and create a .info file for each data file found.
    The .info file contains TEST_NAME in the following format:

      TN:<test name>

    For each source file name referenced in the data file, there is a section
    containing source code and coverage data:

      SF:<absolute path to the source file>
      FN:<line number of function start>,<function name> for each function
      DA:<line number>,<execution count> for each instrumented line
      LH:<number of lines with an execution count> greater than 0
      LF:<number of instrumented lines>

    Sections are separated by:

      end_of_record

    In addition to the main source code file there are sections for each
    #included file containing executable code. Note that the absolute path
    of a source file is generated by interpreting the contents of the respective
    graph file. Relative filenames are prefixed with the directory in which the
    graph file is found. Note also that symbolic links to the graph file will be
    resolved so that the actual file path is used instead of the path to a link.
    This approach is necessary for the mechanism to work with the /proc/gcov
    files.

    Die on error.
    """
    global args
    global graph_file_extension, data_file_extension
    global intermediate
    global excluded_files

    maxdepth = "-maxdepth 1" if args.no_recursion else ""
    follow   = "-follow"     if args.follow       else ""

    if args.initial:
        type = "graph"
        ext  = graph_file_extension
    else:
        type = "data"
        ext  = data_file_extension

    file_list = []
    if (-d $directory):
        info(f"Scanning {directory} for {ext} files ...")
        # find files and inks: "*.$ext" in $dir
        @file_list = `find "$directory" $maxdepth $follow -name \\*$ext -type f -o -name \\*$ext -type l 2>/dev/null`;
        chomp(@file_list);
        if not file_list:
            warn(f"WARNING: no {ext} files found in {directory} - skipping!")
            return
        prefix = get_common_prefix(1, file_list)
        info("Found %d %s files in %s", $#file_list+1, $type, directory)
    else:
        file_list = [directory]
        prefix = ""

    tempdir = tempdir(CLEANUP => 1);

    # Process all files in list
    for file in file_list:
        # Process file
        if intermediate:
            process_intermediate(Path(file), prefix, tempdir)
        elif args.initial:
            process_graphfile(Path(file), prefix)
        else:
            process_dafile(Path(file), prefix)

    Path(tempdir).unlink()

    # Report whether files were excluded.
    if excluded_files:
        info("Excluded data for %d files due to include/exclude options",
             len(excluded_files))

# NOK
def derive_data($contentdata, $funcdata, $bbdata) -> List[]:
    # Calculate function coverage data by combining line coverage data and the
    # list of lines belonging to a function.
    #
    # contentdata: [ instr1, count1, source1, instr2, count2, source2, ... ]
    # instr<n>: Instrumentation flag for line n
    # count<n>: Execution count for line n
    # source<n>: Source code for line n
    #
    # funcdata: [ count1, func1, count2, func2, ... ]
    # count<n>: Execution count for function number n
    # func<n>: Function name for function number n
    #
    # bbdata: function_name -> [ line1, line2, ... ]
    # line<n>: Line number belonging to the corresponding function

    my @gcov_content   = @{$contentdata};
    my @gcov_functions = @{$funcdata};

    my %fn_count;
    my %ln_fn;
    my $line;
    my $maxline;
    my %fn_name;
    my $count;

    if $bbdata is None:
        return @gcov_functions

    # First add existing function data
    while (@gcov_functions):
        $count = shift(@gcov_functions)
        fn    = shift(@gcov_functions)
        $fn_count{$fn} = $count;

    # Convert line coverage data to function data
    for fn, $line_data in %{$bbdata}).items():
        if fn == "": continue
        # Find the lowest line count for this function
        fninstr = False
        count = 0
        for line in (@$line_data):
            $linstr = $gcov_content[(line - 1) * 3 + 0]
            $lcount = $gcov_content[(line - 1) * 3 + 1]
            if not $linstr: continue
            fninstr = True
            if $lcount > 0 and (count == 0 or $lcount < count):
                count = $lcount

        if not fninstr: continue
        $fn_count{$fn} = count

    # Check if we got data for all functions
    for fn in %fn_name.keys():
        if fn == "": continue
        if defined($fn_count{$fn}):
            continue
        warn(f"WARNING: no derived data found for function {fn}")

    # Convert hash to list in @gcov_functions format
    for $fn in sorted(%fn_count.keys()):
        push(@gcov_functions, $fn_count{$fn}, $fn)

    return @gcov_functions;

# NOK
def process_dafile(da_filename: Path, $dir):
    """Create a .info file for a single data file.

    Die on error.
    """
    global options
    global args
    global cwd
    global ignore
    global graph_file_extension
    global adjust_src_pattern, adjust_src_replace
    global excluded_files

    my $da_dir;        # Directory of data file
    my $source_dir;        # Directory of source file
    my $da_basename;    # data filename without ".da/.gcda" extension
    my $bb_filename;    # Name of respective graph file
    my $bb_basename;    # Basename of the original graph file
    my $graph;        # Contents of graph file
    my $instr;        # Contents of graph file part 2
    my $object_dir;        # Directory containing all object files
    my $source_filename;    # Name of a source code file
    my $gcov_file;        # Name of a .gcov file
    my @gcov_content;    # Content of a .gcov file
    my $gcov_branches;    # Branch content of a .gcov file
    my @gcov_functions;    # Function calls of a .gcov file
    my $ln_hit;        # Number of instrumented lines hit
    my $ln_found;    # Number of instrumented lines found
    my $funcs_hit;        # Number of instrumented functions hit
    my $funcs_found;    # Number of instrumented functions found
    my $br_hit;
    my $br_found;
    my $source;        # gcov source header information
    my $object;        # gcov object header information
    my @matches;        # List of absolute paths matching filename
    my $base_dir;        # Base directory for current file
    my @tmp_links;        # Temporary links to be cleaned up
    my @result;
    my $index;

    try:
        info("Processing %s", str(da_filename.relative_to($dir)))

        # Get path to data file in absolute and normalized form (begins with /,
        # contains no more ../ or ./)
        da_filename = solve_relative_path(cwd, str(da_filename))
        # Get directory and basename of data file
        $da_dir, $da_basename, _ = split_filename(da_filename)

        $source_dir = $da_dir;
        if is_compat(COMPAT_MODE_LIBTOOL):
            # Avoid files from .libs dirs
            $source_dir =~ s/\.libs$//;

        da_renamed = (-z da_filename)

        # Construct base_dir for current file
        $base_dir = args.base_directory or $source_dir

        # Check for writable $base_dir (gcov will try to write files there)
        if not os.access($base_dir, os.W_OK):
            die("ERROR: cannot write to directory $base_dir!")

        # Construct name of graph file
        $bb_basename = $da_basename + graph_file_extension
        $bb_filename = "$da_dir/$bb_basename";

        # Find out the real location of graph file in case we're just looking at
        # a link
        while readlink($bb_filename):
            last_dir = dirname($bb_filename);
            $bb_filename = readlink($bb_filename)
            $bb_filename = solve_relative_path(Path(last_dir), $bb_filename)

        # Ignore empty graph file (e.g. source file with no statement)
        if (-z $bb_filename):
            warn("WARNING: empty $bb_filename (skipped)")
            return

        # Read contents of graph file into hash. We need it later to find out
        # the absolute path to each .gcov file created as well as for
        # information about functions and their source code positions.
        if gcov_version >= GCOV_VERSION_3_4_0:
            instr, graph = read_gcno(Path($bb_filename))
        elif is_compat($COMPAT_MODE_HAMMER):
            instr, graph = read_bbg(Path($bb_filename))
        else:
            instr, graph = read_bb(Path($bb_filename))

        # Try to find base directory automatically if requested by user
        if options.auto_base:
            $base_dir = str(find_base_from_source(Path($base_dir),
                                                  [ keys(%{$instr}), keys(%{$graph}) ]))

        adjust_source_filenames($instr, Path($base_dir))
        adjust_source_filenames($graph, Path($base_dir))

        # Set $object_dir to real location of object files. This may differ
        # from $da_dir if the graph file is just a link to the "real" object
        # file location.
        $object_dir = dirname($bb_filename);

        # Is the data file in a different directory? (this happens e.g. with
        # the gcov-kernel patch)
        if $object_dir != $da_dir:
            # Need to create link to data file in $object_dir
            system("ln", "-s", da_filename,
                   f"$object_dir/$da_basename{data_file_extension}")
                and die(f"ERROR: cannot create link $object_dir/".
                        f"$da_basename{data_file_extension}!")
            push(@tmp_links,
                 f"$object_dir/$da_basename{data_file_extension}")
            # Need to create link to graph file if basename of link
            # and file are different (CONFIG_MODVERSION compat)
            if (basename($bb_filename) != $bb_basename and
                (! -e "$object_dir/$bb_basename")):
                symlink($bb_filename, "$object_dir/$bb_basename") or
                    warn("WARNING: cannot create link $object_dir/$bb_basename")
                push(@tmp_links, "$object_dir/$bb_basename");

        # Change to directory containing data files and apply GCOV
        debug(f"chdir({base_dir})\n")
        os.chdir($base_dir)

        if da_renamed:
            # Need to rename empty data file to workaround gcov <= 3.2.x bug (Abort)
            if system_no_output(3, "mv", f"{da_filename}", f"{da_filename}.ori")[0] != NO_ERROR:
                die(f"ERROR: cannot rename {da_filename}")

        # Execute gcov command and suppress standard output
        gcov_error = system_no_output(1, options.gcov_tool, da_filename,
                                      "-o", $object_dir, @gcov_options)[0]

        if da_renamed:
            if system_no_output(3, "mv", f"{da_filename}.ori", f"{da_filename}")[0] != NO_ERROR:
                die(f"ERROR: cannot rename {da_filename}.ori", end="") # !!! chyba bex end=""

        # Clean up temporary links
        for $_ in @tmp_links:
            Path($_).unlink()

        if gcov_error:
            if ignore[ERROR_GCOV]:
                warn(f"WARNING: GCOV failed for {da_filename}!")
                return
            die(f"ERROR: GCOV failed for {da_filename}!")

        # Collect data from resulting .gcov files and create .info file
        gcov_list = get_filenames(Path("."), "\.gcov$")
        # Check for files
        if not gcov_list:
            warn(f"WARNING: gcov did not create any files for {da_filename}!")

        # Check whether we're writing to a single file
        if args.output_filename:
            if args.output_filename == "-":
                INFO_HANDLE = sys.stdout
            else:
                # Append to output file
                try:
                    INFO_HANDLE = Path(args.output_filename).open(">>")
                except:
                    die(f"ERROR: cannot write to {args.output_filename}!")
        else:
            # Open .info file for output
            try:
                INFO_HANDLE = Path(f"{da_filename}.info").open("wt")
            except:
                die(f"ERROR: cannot create {da_filename}.info!")

        # Write test name
        print("TN:%s" % $test_name, file=INFO_HANDLE)

        # Traverse the list of generated .gcov files and combine them into a
        # single .info file
        for $gcov_file in sorted(gcov_list):
        {
            my $i;
            my $num;

            # Skip gcov file for gcc built-in code
            if $gcov_file == "<built-in>.gcov": continue

            $source, $object = read_gcov_header(Path($gcov_file))

            if ! defined($source):
                # Derive source file name from gcov file name if
                # header format could not be parsed
                $source = $gcov_file;
                $source =~ s/\.gcov$//;

            # Convert to absolute canonical form
            $source = solve_relative_path(Path($base_dir), $source)
            if adjust_src_pattern is not None:
                # Apply transformation as specified by user
                $source = re.sub(adjust_src_pattern, adjust_src_replace, $source)

            # gcov will happily create output even if there's no source code
            # available - this interferes with checksum creation so we need
            # to pull the emergency brake here.
            if (! -r $source and $checksum):
                if ignore[ERROR_SOURCE]:
                    warn("WARNING: could not read source file $source")
                    continue
                die("ERROR: could not read source file $source")

            @matches = match_filename($source, keys(%{$instr}));

            # Skip files that are not mentioned in the graph file
            if ! @matches:
                warn("WARNING: cannot find an entry for ".$gcov_file.
                     f" in {graph_file_extension} file, skipping "
                     "file!")
                Path($gcov_file).unlink()
                continue

            # Read in contents of gcov file
            @result = read_gcov_file(Path($gcov_file))
            if ! defined($result[0]):
                warn("WARNING: skipping unreadable file ".$gcov_file)
                Path($gcov_file).unlink()
                continue

            @gcov_content   = @{$result[0]};
            $gcov_branches  = $result[1];
            @gcov_functions = @{$result[2]};

            # Skip empty files
            if ! @gcov_content:
                warn("WARNING: skipping empty file ".$gcov_file)
                Path($gcov_file).unlink()
                continue

            if len(matches) == 1:
                # Just one match
                $source_filename = matches[0]
            else:
                # Try to solve the ambiguity
                $source_filename = solve_ambiguous_match($gcov_file, \@matches, \@gcov_content)

            if args.include_patterns:
                keep = False
                for $pattern in args.include_patterns:
                    keep = keep or $source_filename =~ rf"^{pattern}$";

                if not keep:
                    excluded_files.add(source_filename)
                    Path($gcov_file).unlink()
                    continue

            if args.exclude_patterns:
                exclude = False
                for $pattern in args.exclude_patterns:
                    exclude = exclude or $source_filename =~ rf"^{pattern}$"

                if exclude:
                    excluded_files.add(source_filename)
                    Path($gcov_file).unlink()
                    continue

            # Skip external files if requested
            if not options.external:
                if is_external($source_filename):
                    info("  ignoring data for external file $source_filename")
                    Path($gcov_file).unlink()
                    continue

            # Write absolute path of source file
            print("SF:%s" % $source_filename, file=INFO_HANDLE)

            # If requested, derive function coverage data from
            # line coverage data of the first line of a function
            if options.derive_func_data:
                @gcov_functions = derive_data(\@gcov_content, \@gcov_functions,
                                              $graph->{$source_filename})

            # Write function-related information
            if (defined($graph->{$source_filename}))
            {
                my $fn_data = $graph->{$source_filename};
                my $fn;

                foreach $fn (sort
                    {$fn_data->{$a}->[0] <=> $fn_data->{$b}->[0]}
                    keys(%{$fn_data})) {
                    my $ln_data = $fn_data->{$fn};
                    my $line = $ln_data->[0];

                    # Skip empty function
                    if $fn == "": continue

                    # Remove excluded functions
                    if not args.no_markers:
                    {
                        my $gfn;
                        my $found = 0;
                        foreach $gfn (@gcov_functions):
                            if $gfn == $fn:
                                $found = 1;
                                break
                        if (!$found) {
                            continue
                        }
                    }

                    # Normalize function name
                    $fn = filter_fn_name($fn)

                    print("FN:$line,$fn", file=INFO_HANDLE)
                }
            }

            #--
            #-- FNDA: <call-count>, <function-name>
            #-- FNF: overall count of functions
            #-- FNH: overall count of functions with non-zero call count
            #--
            $funcs_found = 0;
            $funcs_hit   = 0;
            while (@gcov_functions):
                my $count = shift(@gcov_functions)
                my $fn    = shift(@gcov_functions)
                $fn = filter_fn_name($fn)
                printf(INFO_HANDLE "FNDA:$count,$fn\n")
                $funcs_found += 1
                if $count > 0: $funcs_hit += 1
            if $funcs_found > 0:
                printf(INFO_HANDLE "FNF:%s\n", $funcs_found)
                printf(INFO_HANDLE "FNH:%s\n", $funcs_hit)

            # Write coverage information for each instrumented branch:
            #
            #   BRDA:<line number>,<block number>,<branch number>,<taken>
            #
            # where 'taken' is the number of times the branch was taken
            # or '-' if the block to which the branch belongs was never
            # executed
            $br_found = 0
            $br_hit   = 0
            $num = br_gvec_len($gcov_branches);
            for ($i = 0; $i < $num; $i++)
                $line, $block, $branch, $taken = br_gvec_get($gcov_branches, $i)
                if $block < 0: $block = BR_VEC_MAX
                print(INFO_HANDLE "BRDA:$line,$block,$branch,$taken\n")
                $br_found += 1
                if $taken != '-' and $taken > 0:
                    $br_hit += 1
            if $br_found > 0:
                printf(INFO_HANDLE "BRF:%s\n", $br_found);
                printf(INFO_HANDLE "BRH:%s\n", $br_hit);

            # Reset line counters
            line_number = 0
            ln_found    = 0
            ln_hit      = 0
            # Write coverage information for each instrumented line
            # Note: @gcov_content contains a list of (flag, count, source)
            # tuple for each source code line
            while (@gcov_content):
                line_number += 1
                # Check for instrumented line
                if $gcov_content[0]:
                    $ln_found += 1
                    printf(INFO_HANDLE f"DA:{line_number},".
                           $gcov_content[1].($checksum ?
                           ",". md5_base64($gcov_content[2]) : "").
                           "\n");
                    # Increase $ln_hit in case of an execution
                    # count>0
                    if $gcov_content[1] > 0:
                        $ln_hit += 1
                # Remove already processed data from array
                splice(@gcov_content,0,3);
            # Write line statistics and section separator
            printf(INFO_HANDLE "LF:%s\n", $ln_found);
            printf(INFO_HANDLE "LH:%s\n", $ln_hit);
            print(INFO_HANDLE "end_of_record\n");

            # Remove .gcov file after processing
            Path($gcov_file).unlink()
        }

        if not (args.output_filename and args.output_filename == "-"):
            close(INFO_HANDLE)
    finally:
        # Change back to initial directory
        os.chdir(cwd)

# NOK
def br_gvec_len(vector: Optional):
    # Return the number of entries in the branch coverage vector.
    if vector is None: return 0
    return (len(vector) * 8 / BR_VEC_WIDTH) / BR_VEC_ENTRIES

# NOK
def br_gvec_get(vector, number):
    """Return an entry from the branch coverage vector."""
    offset = number * BR_VEC_ENTRIES

    # Retrieve data from vector
    line   = vec(vector, offset + BR_LINE,   BR_VEC_WIDTH)
    block  = vec(vector, offset + BR_BLOCK,  BR_VEC_WIDTH)
    if block == BR_VEC_MAX: block  = -1
    branch = vec(vector, offset + BR_BRANCH, BR_VEC_WIDTH)
    taken  = vec(vector, offset + BR_TAKEN,  BR_VEC_WIDTH)
    # Decode taken value from an integer
    if taken == 0:
        taken = "-"
    else:
        taken -= 1

    return (line, block, branch, taken)

# NOK
def br_gvec_push(vector: Optional, line, block, branch, taken):
    # br_gvec_push(vector, line, block, branch, taken)
    #
    # Add an entry to the branch coverage vector.

    if vector is None: vector = ""
    offset = br_gvec_len(vector) * BR_VEC_ENTRIES
    if block < 0: block = BR_VEC_MAX
    # Encode taken value into an integer
    if taken == "-":
        taken = 0
    else:
        taken += 1

    # Add to vector
    vec(vector, offset + BR_LINE,   BR_VEC_WIDTH) = line
    vec(vector, offset + BR_BLOCK,  BR_VEC_WIDTH) = block
    vec(vector, offset + BR_BRANCH, BR_VEC_WIDTH) = branch
    vec(vector, offset + BR_TAKEN,  BR_VEC_WIDTH) = taken

    return vector

# NOK
def get_filenames(dirname: Path, pattern: str) -> List[str]:
    """Return a list of filenames found in directory which match
    the specified pattern.

    Die on error.
    """
    try:
        DIR = opendir(str(dirname))
    except:
        or die(f"ERROR: cannot read directory {dirname}")
    result = []
    while (directory = readdir(DIR)):
        if re.???($pattern, directory):
            result.append(directory)
    closedir(DIR)

    return result

# NOK
def match_filename($filename, @list) -> List[???]:
    # match_filename(gcov_filename, list)
    #
    """Return a list of those entries of LIST which match the relative
    filename GCOV_FILENAME.
    """
    result: List[???] = []

    $vol, $dir, $file = splitpath(filename)

    @comp = splitdir($dir)
    $comps = len(comp)
    entry:
    for entry in @list:
        $evol, $edir, $efile = splitpath(entry)

        # Filename component must match
        if $efile != $file:
            continue

        # Check directory components last to first for match
        @ecomp = splitdir($edir)
        if len(@ecomp) < $comps:
            continue

        for idx in range($comps):
            if $comp[- idx - 1] != $ecomp[- idx - 1]:
                next entry;

        result.append(entry)

    return result

# NOK
def solve_ambiguous_match($rel_name, $matches, $content):
    # solve_ambiguous_match(rel_filename, matches_ref, gcov_content_ref)
    #
    # Try to solve ambiguous matches of mapping (gcov file) -> (source code) file
    # by comparing source code provided in the GCOV file with that of the files
    # in MATCHES. REL_FILENAME identifies the relative filename of the gcov
    # file.
    #
    # Return the one real match or die if there is none.

    my $index;

    # Check the list of matches
    for filename in @$matches:
        # Compare file contents
        try:
            SOURCE = Path(filename).open("rt")
        except:
            die(f"ERROR: cannot read {filename}!")
        $no_match = 0;
        with SOURCE:
            for ($index = 2; <SOURCE>; $index += 3):
                chomp;

                # Also remove CR from line-end
                s/\015$//;

                if $_ != @$content[$index]:
                    $no_match = 1;
                    break

        if not $no_match:
            info(f"Solved source file ambiguity for {rel_name}")
            return filename

    die(f"ERROR: could not match gcov data for {rel_name}!")

# NOK
def split_filename(filename: str) -> Tuple[str, str, str]:
    """Return (path, filename, extension) for a given FILENAME."""
    path_components = filename.split("/")
    file_components = path_components.pop().split(".")
    extension       = file_components.pop()
    return ("/".join(path_components), ".".join(file_components), extension)

# NOK
def read_gcov_header(gcov_filename: Path) -> Tuple[Optional[???], Optional[???]]:
    """Parse file GCOV_FILENAME and return a list containing the following
    information:

      (source, object)

    where:

    source: complete relative path of the source code file (gcc >= 3.3 only)
    object: name of associated graph file

    Die on error.
    """
    global ignore_errors

    try:
        fhandle = gcov_filename.open("rt")
    except:
        if $ignore_errors[ERROR_GCOV]:
            warn(f"WARNING: cannot read {gcov_filename}!")
            return (None, None)
        else:
            die(f"ERROR: cannot read {gcov_filename}!")
    source = None
    object = None
    with fhandle:
        for line in fhandle:
            line = line.rstrip("\n")
            # Also remove CR from line-end
            line = line.rstrip("\r")

            if r"^\s+-:\s+0:Source:(.*)$":
                # Source: header entry
                source = match.group(1)
                continue

            if r"^\s+-:\s+0:Object:(.*)$":
                # Object: header entry
                object = match.group(1)
                continue

            break

    return (source, object)

# NOK
def read_gcov_file(gcov_filename: Path) -> Tuple[Optional[???], Optional[???], Optional[???]]:
    """Parse file GCOV_FILENAME (.gcov file format) and return the list:
    (reference to gcov_content, reference to gcov_branch, reference to gcov_func)

    gcov_content is a list of 3 elements
    (flag, count, source) for each source code line:

    $result[(line_number-1)*3+0] = instrumentation flag for line line_number
    $result[(line_number-1)*3+1] = execution count      for line line_number
    $result[(line_number-1)*3+2] = source code text     for line line_number

    gcov_branch is a vector of 4 4-byte long elements for each branch:
    line number, block number, branch number, count + 1 or 0

    gcov_func is a list of 2 elements
    (number of calls, function name) for each function

    Die on error.
    """
    global options
    global args

    @result = ();

    my $branches  = "";
    my @functions = ();

    my $number;

    $exclude_flag              = 0
    $exclude_line              = 0
    $exclude_br_flag           = 0
    $exclude_exception_br_flag = 0
    $exclude_branch            = 0
    $exclude_exception_branch  = 0

    try:
        INPUT = gcov_filename.open("rt")
    except:
        if $ignore_errors[ERROR_GCOV]:
            warn(f"WARNING: cannot read {gcov_filename}!")
            return (None, None, None)
        else:
            die(f"ERROR: cannot read {gcov_filename}!")
    last_line  = 0
    last_block = $UNNAMED_BLOCK
    with INPUT:
        if gcov_version < GCOV_VERSION_3_3_0:
            # Expect gcov format as used in gcc < 3.3
            while (<INPUT>)
                $_ = $_.rstrip("\n")

                # Also remove CR from line-end
                s/\015$//;

                if (/^branch\s+(\d+)\s+taken\s+=\s+(\d+)/):
                    if (!$br_coverage);   continue
                    if ($exclude_line);   continue
                    if ($exclude_branch); continue
                    $branches = br_gvec_push($branches, last_line, last_block, $1, $2)
                elif (/^branch\s+(\d+)\s+never\s+executed/):
                    if (!$br_coverage);   continue
                    if ($exclude_line);   continue
                    if ($exclude_branch); continue
                    $branches = br_gvec_push($branches, last_line, last_block, $1, '-')
                elif (/^call/ or /^function/):
                    pass # Function call return data
                else:
                    last_line += 1
                    # Check for exclusion markers
                    if not args.no_markers:
                        if (/$EXCL_STOP/) {
                            $exclude_flag = 0;
                        elif (/$EXCL_START/):
                            $exclude_flag = 1;

                        if (/$options.excl_line/ or $exclude_flag):
                            $exclude_line = 1;
                        else:
                            $exclude_line = 0;

                    # Check for exclusion markers (branch exclude)
                    if not args.no_markers:
                        if (/$EXCL_BR_STOP/):
                            $exclude_br_flag = 0;
                        elif (/$EXCL_BR_START/):
                            $exclude_br_flag = 1;

                        if (/$options.excl_br_line/ or $exclude_br_flag):
                            $exclude_branch = 1;
                        else:
                            $exclude_branch = 0;

                    # Check for exclusion markers (exception branch exclude)
                    if (not args.no_markers and
                        /($EXCL_EXCEPTION_BR_STOP|$EXCL_EXCEPTION_BR_START|$options.excl_exception_br_line)/):
                        warn(f"WARNING: $1 found at {gcov_filename}:$last_line but "
                             "branch exceptions exclusion is not supported with "
                             "gcov versions older than 3.3")

                    # Source code execution data
                    if /^\t\t(.*)$/:
                        # Uninstrumented line
                        push(@result, 0);
                        push(@result, 0);
                        push(@result, $1);
                        continue
                    $number = substr($_, 0, 16).split(" ")[0]

                    # Check for zero count which is indicated
                    # by ######
                    if $number == "######": $number = 0

                    if $exclude_line:
                        # Register uninstrumented line instead
                        push(@result, 0);
                        push(@result, 0);
                    else:
                        push(@result, 1);
                        push(@result, $number);
                    push(@result, substr($_, 16));
        else:
            # Expect gcov format as used in gcc >= 3.3
            while (<INPUT>)
                $_ = $_.rstrip("\n")

                # Also remove CR from line-end
                s/\015$//;

                if (/^\s*(\d+|\$+|\%+):\s*(\d+)-block\s+(\d+)\s*$/):
                    # Block information - used to group related
                    # branches
                    last_line  = $2;
                    last_block = $3;
                elif (/^branch\s+(\d+)\s+taken\s+(\d+)(?:\s+\(([^)]*)\))?/):
                    if (!$br_coverage);   continue
                    if ($exclude_line);   continue
                    if ($exclude_branch); continue
                    if (($exclude_exception_branch or options.no_exception_br) and
                        defined($3) and $3 == "throw"): continue
                    $branches = br_gvec_push($branches, last_line, last_block, $1, $2)
                elif (/^branch\s+(\d+)\s+never\s+executed/):
                    if (!$br_coverage);   continue
                    if ($exclude_line);   continue
                    if ($exclude_branch); continue
                    $branches = br_gvec_push($branches, last_line, last_block, $1, '-')
                elif (/^function\s+(.+)\s+called\s+(\d+)\s+/):
                    if (!$fn_coverage): continue
                    if ($exclude_line): continue
                    push(@functions, $2, $1);
                elif (/^call/):
                    # Function call return data
                    pass
                elif (/^\s*([^:]+):\s*([^:]+):(.*)$/)
                    my ($count, $line, $code) = ($1, $2, $3);

                    # Skip instance-specific counts
                    if $line <= len(@result) / 3: continue

                    last_line  = $line;
                    last_block = $UNNAMED_BLOCK
                    # Check for exclusion markers
                    if not args.no_markers:
                        if (/$EXCL_STOP/):
                            $exclude_flag = 0;
                        elif (/$EXCL_START/):
                            $exclude_flag = 1;

                        if (/$options.excl_line/ or $exclude_flag):
                            $exclude_line = 1;
                        else:
                            $exclude_line = 0;

                    # Check for exclusion markers (branch exclude)
                    if not args.no_markers:
                        if (/$EXCL_BR_STOP/):
                            $exclude_br_flag = 0;
                        elif (/$EXCL_BR_START/):
                            $exclude_br_flag = 1;

                        if (/$options.excl_br_line/ or $exclude_br_flag):
                            $exclude_branch = 1;
                        else:
                            $exclude_branch = 0;

                    # Check for exclusion markers (exception branch exclude)
                    if not args.no_markers:
                        if (/$EXCL_EXCEPTION_BR_STOP/):
                            $exclude_exception_br_flag = 0;
                        elif (/$EXCL_EXCEPTION_BR_START/):
                            $exclude_exception_br_flag = 1;

                        if (/$options.excl_exception_br_line/ or $exclude_exception_br_flag):
                            $exclude_exception_branch = 1;
                        else:
                            $exclude_exception_branch = 0;

                    # Strip unexecuted basic block marker
                    $count =~ s/\*$//;

                    # <exec count>:<line number>:<source code>
                    if $line == "0":
                        # Extra data
                        pass
                    elif $count == "-":
                        # Uninstrumented line
                        push(@result, 0);
                        push(@result, 0);
                        push(@result, $code);
                    else:
                        if $exclude_line:
                            push(@result, 0);
                            push(@result, 0);
                        else:
                            # Check for zero count
                            if ($count =~ /^[#=]/):
                                $count = 0;
                            push(@result, 1);
                            push(@result, $count);
                        push(@result, $code);

    if $exclude_flag or $exclude_br_flag or $exclude_exception_br_flag:
        warn(f"WARNING: unterminated exclusion section in {gcov_filename}")

    return (\@result, $branches, \@functions)


def read_intermediate_text(gcov_filename: Path, data: Dict[str, str]):
    """Read gcov intermediate text format in gcov_filename and add
    the resulting data to 'data' in the following format:

    data:      source_filename -> file_data
    file_data: concatenated lines of intermediate text data
    """
    try:
        fhandle = gcov_filename.open("rt")
    except Exception as exc:
        die(f"ERROR: Could not read {gcov_filename}: {exc}!")
    with fhandle:
        filename = None
        for line in fhandle:
            match = re.match(r"^file:(.*)$", line)
            if match:
                filename = match.group(1).rstrip("\n")
            elif filename is not None:
                if filename not in data:
                    data[filename] = line
                else:
                    data[filename] += line


def read_intermediate_json(gcov_filename: Path, data: Dict[str, object]) -> str:
    """Read gcov intermediate JSON format in gcov_filename and add the resulting
    data to 'data' in the following format:

    data:      source_filename -> file_data
    file_data: GCOV JSON data for file

    Also return the value for current_working_directory.
    """
    try:
        with gzip.open(str(gcov_filename), "rt") as fhandle:
            text = fhandle.read()
    except Exception as exc:
        die(f"ERROR: Could not read {gcov_filename}: {exc}")

    json = json.loads(text)
    if json is None or "files" not in json or ref(json["files"] != "ARRAY"): # NOK
        die(f"ERROR: Unrecognized JSON output format in {gcov_filename}")

    json_basedir = json["current_working_directory"]
    # Workaround for bug in MSYS GCC 9.x that encodes \ as \n in gcov JSON output
    if $^O == "msys" and re.???(r"\n", json_basedir): # NOK
        json_basedir = re.sub(r"\n", r"/", json_basedir)

    for file in json["files"]:
        filename = file["file"]
        data[filename] = file

    return json_basedir

# NOK
def intermediate_text_to_info(fhandle, $data, $srcdata):
    """Write DATA in info format to file descriptor fhandle.

    data:      filename -> file_data:
    file_data: concatenated lines of intermediate text data

    srcdata:   filename -> [ excl, brexcl, checksums ]
    excl:      lineno -> 1 for all lines for which to exclude all data
    brexcl:    lineno -> 1 for all lines for which to exclude branch data
                         2 for all lines for which to exclude exception branch data
    checksums: lineno -> source code checksum

    Note: To simplify processing, gcov data is not combined here, that is counts
          that appear multiple times for the same lines/branches are not added.
          This is done by lcov/genhtml when reading the data files.
    """
    if not data: return

    print(f"TN:$test_name", file=fhandle)

    my $c;

    branch_num = 0
    for filename, file_data in data.items():

        ln_found = 0
        ln_hit   = 0
        fn_found = 0
        fn_hit   = 0
        br_found = 0
        br_hit   = 0

        my ($excl, $brexcl, $checksums);
        if defined($srcdata->{$filename}):
            $excl, $brexcl, $checksums = @{$srcdata->{$filename}}

        print(f"SF:{filename}", file=fhandle)

        for $line in split(/\n/, file_data):
            if $line =~ /^lcount:(\d+),(\d+),?/:
                # lcount:<line>,<count>
                # lcount:<line>,<count>,<has_unexecuted_blocks>
                if $checksum and exists($checksums->{$1}):
                    $c = ",".$checksums->{$1}
                else:
                    $c = ""

                if ! $excl->{$1}: print(f"DA:$1,$2$c", file=fhandle)

                # Intermediate text format does not provide
                # branch numbers, and the same branch may appear
                # multiple times on the same line (e.g. in
                # template instances). Synthesize a branch
                # number based on the assumptions:
                # a) the order of branches is fixed across
                #    instances
                # b) an instance starts with an lcount line
                branch_num = 0

                ln_found += 1
                if $2 > 0:
                    ln_hit += 1
            elif $line =~ /^function:(\d+),(\d+),([^,]+)$/:
                if (!$fn_coverage or $excl->{$1}); continue

                # function:<line>,<count>,<name>
                print(f"FN:$1,$3",   file=fhandle)
                print(f"FNDA:$2,$3", file=fhandle)

                fn_found += 1
                if $2 > 0:
                    fn_hit += 1
            elif $line =~ /^function:(\d+),\d+,(\d+),([^,]+)$/:
                if (!$fn_coverage or $excl->{$1}); continue

                # function:<start_line>,<end_line>,<count>,
                #          <name>
                print(f"FN:$1,$3",   file=fhandle)
                print(f"FNDA:$2,$3", file=fhandle)

                fn_found += 1
                if $2 > 0:
                    fn_hit += 1
            elif $line =~ /^branch:(\d+),(taken|nottaken|notexec)/:
                if (!$br_coverage or $excl->{$1} or
                    (defined($brexcl->{$1}) and ($brexcl->{$1} == 1))); continue

                # branch:<line>,taken|nottaken|notexec
                if $2 == "taken":
                    $c = 1
                elif $2 == "nottaken":
                    $c = 0
                else:
                    $c = "-"
                print(f"BRDA:$1,0,$branch_num,$c", file=fhandle)
                branch_num += 1

                br_found += 1
                if $2 == "taken":
                    br_hit += 1

        if fn_found > 0:
            print("FNF:%s" % fn_found, file=fhandle)
            print("FNH:%s" % fn_hit,   file=fhandle)
        if br_found > 0:
            print("BRF:%s", br_found, file=fhandle)
            print("BRH:%s", br_hit,   file=fhandle)
        print("LF:%s", ln_found, file=fhandle)
        print("LH:%s", ln_hit,   file=fhandle)

        print("end_of_record", file=fhandle)

# NOK
def intermediate_json_to_info(fhandle, $data, $srcdata):
    """Write DATA in info format to file descriptor fhandle.

    data:      filename -> file_data:
    file_data: GCOV JSON data for file

    srcdata:   filename -> [ excl, brexcl, checksums ]
    excl:      lineno -> 1 for all lines for which to exclude all data
    brexcl:    lineno -> 1 for all lines for which to exclude branch data
                         2 for all lines for which to exclude exception branch data
    checksums: lineno -> source code checksum

    Note: To simplify processing, gcov data is not combined here, that is counts
          that appear multiple times for the same lines/branches are not added.
          This is done by lcov/genhtml when reading the data files.
    """
    global options

    if not data: return

    print(f"TN:$test_name", file=fhandle)

    branch_num = 0
    for filename, file_data in data.items():

        ln_found = 0
        ln_hit   = 0
        fn_found = 0
        fn_hit   = 0
        br_found = 0
        br_hit   = 0

        my ($excl, $brexcl, $checksums);
        if (defined($srcdata->{$filename})):
            ($excl, $brexcl, $checksums) = @{$srcdata->{$filename}};

        print(f"SF:{filename}", file=fhandle)

        # Function data
        if $fn_coverage:
            for $d in @{$file_data["functions"]}:
                $line  = $d->{"start_line"}
                $count = $d->{"execution_count"}
                $name  = $d->{"name"}

                if (!defined($line) or !defined($count) or
                    !defined($name) or $excl->{$line}); continue

                print(f"FN:$line,$name",    file=fhandle)
                print(f"FNDA:$count,$name", file=fhandle)

                fn_found += 1
                if $count > 0:
                    fn_hit += 1

        if fn_found > 0:
            print("FNF:%s" % fn_found, file=fhandle)
            print("FNH:%s" % fn_hit,   file=fhandle)

        # Line data
        for my $d in @{$file_data->{"lines"}}:
            my $line     = $d->{"line_number"};
            my $count    = $d->{"count"};
            my $branches = $d->{"branches"};
            my $unexec   = $d->{"unexecuted_block"};

            if !defined($line) or !defined($count) or $excl->{$line}; continue

            if defined($unexec) and $unexec and $count == 0:
                $unexec = 1
            else:
                $unexec = 0

            if $checksum and exists($checksums->{$line}):
                $c = ",".$checksums->{$line}
            else:
                $c = ""

            print(f"DA:$line,$count$c", file=fhandle)

            ln_found += 1
            if $count > 0:
                ln_hit += 1

            branch_num = 0
            # Branch data
            if $br_coverage and (!defined($brexcl->{$line}) or $brexcl->{$line} != 1):
                for my $b in @$branches:
                    $brcount      = $b->{"count"}
                    $is_exception = $b->{"throw"}

                    if (not $is_exception or
                        ((!defined($brexcl->{$line}) or $brexcl->{$line} != 2) and
                         not options.no_exception_br)):
                        if !defined($brcount) or $unexec:
                            $brcount = "-";
                        print(f"BRDA:$line,0,$branch_num,$brcount", file=fhandle)

                    br_found += 1
                    if $brcount != "-" and $brcount > 0:
                        br_hit += 1
                    branch_num += 1

        if br_found > 0:
            printf("BRF:%s" % br_found, file=fhandle)
            printf("BRH:%s" % br_hit,   file=fhandle)
        print("LF:%s" % ln_found, file=fhandle)
        print("LH:%s" % ln_hit,   file=fhandle)
        print("end_of_record",    file=fhandle)

# NOK
def get_output_fd(outfile: Optional[str], $file):
    """ """
    if outfile is None:
        try:
            fhandle = Path(f"{file}.info").open("wt")
        except Exception as exc:
            die(f"ERROR: Cannot create file {file}.info: {exc}")
    elif outfile == "-":
        try:
            fhandle = sys.stdout
        except Exception as exc:
            die(f"ERROR: Cannot duplicate stdout: {exc}")
    else:
        try:
            fhandle = Path(outfile).open(">>")
        except Exception as exc:
            die(f"ERROR: Cannot write to file {outfile}: {exc}")

    return fhandle

# NOK
def print_gcov_warnings(stderr_file: Path, is_graph: bool, map: Dict[???, ???]):
    """Print GCOV warnings in file STDERR_FILE to STDERR.
    If IS_GRAPH is non-zero, suppress warnings about missing as these
    are expected. Replace keys found in MAP with their values.
    """
    try:
        fhandle = stderr_file.open("rt")
    except Exception as exc:
        warn(f"WARNING: Could not open GCOV stderr file {stderr_file}: {exc}")
        return
    with fhandle:
        for line in <fhandle>:
            if is_graph and re.???(r"cannot open data file", line):
                continue
            for key, val in map.items():
                line =~ s/\Q$key\E/$val/g
            print(line, end="", file=sys.stderr)

# NOK
def process_intermediate($file: Path, $dir, $tempdir):
    """Create output for a single file (either a data file or a graph file)
    using gcov's intermediate option.
    """
    global options
    global args
    global cwd
    global ignore
    global graph_file_extension

    my $base;
    my $srcdata;
    my ($out, $err, $rc);
    my $json_format;

    json_basedir = None

    try:
        info("Processing %s", str(file.relative_to($dir)))

        file = solve_relative_path(cwd, str(file))
        $fdir, $fbase, $fext = split_filename(file)

        is_graph = (graph_file_extension == f".{fext}")

        if is_graph:
            # Process graph file - copy to temp directory to prevent
            # accidental processing of associated data file
            data_file = f"$tempdir/$fbase{graph_file_extension}"
            if ! copy(file, data_file):
                errmsg = f"ERROR: Could not copy file {file}"
                goto err;
        else:
            # Process data file in place
            data_file = file

        # Change directory
        try
            os.chdir($tempdir)
        except Exception as exc:
            errmsg = f"Could not change to directory $tempdir: {exc}"
            goto err;

        # Run gcov on data file
        $out, $err, $rc = system_no_output(1 + 2 + 4, options.gcov_tool,
                                           data_file, @gcov_options, "-i")
        if defined($out):
            Path($out).unlink()
        if defined($err):
            print_gcov_warnings(Path($err), is_graph, { $data_file: $file, })
            Path($err).unlink()
        if $rc:
            errmsg = f"GCOV failed for {file}"
            goto err;

        if is_graph:
            # Remove graph file copy
            Path(data_file).unlink()

        %data: Dict[str, ???] = {}

        # Parse resulting file(s)
        for gcov_filename in glob("*.gcov"):
            read_intermediate_text(gcov_filename, \%data);
            Path(gcov_filename).unlink()

        for gcov_filename in glob("*.gcov.json.gz"):
            json_basedir = read_intermediate_json(gcov_filename, \%data)
            Path(gcov_filename).unlink()
            $json_format = 1;

        if not %data:
            warn(f"WARNING: GCOV did not produce any data for {file}")
            return

        # Determine base directory
        if args.base_directory is not None:
            $base = args.base_directory
        elif json_basedir is not None:
            $base = json_basedir
        else:
            $base = $fdir;

            if is_compat(COMPAT_MODE_LIBTOOL):
                # Avoid files from .libs dirs
                $base =~ s/\.libs$//;

            # Try to find base directory automatically if requested by user
            if options.auto_base:
                $base = str(find_base_from_source(Path($base), [ keys(%data) ]))

        # Apply base file name to relative source files
        adjust_source_filenames(\%data, Path($base))

        # Remove excluded source files
        filter_source_files(\%data)

        # Get data on exclusion markers and checksums if requested
        if not args.no_markers or $checksum:
            $srcdata: Dict[str, Tuple[???, ???, ???]] = get_all_source_data(%data.keys())

        # Generate output
        with get_output_fd(args.output_filename, $file) as fhandle:
            if $json_format:
                intermediate_json_to_info(fhandle, \%data, $srcdata);
            else:
                intermediate_text_to_info(fhandle, \%data, $srcdata);
    finaly:
        os.chdir(cwd)

    return

    err:
    if ignore[ERROR_GCOV]:
        warn(f"WARNING: {errmsg}!")
    else:
        die(f"ERROR: {errmsg}!")


def map_llvm_version(version: int) -> int:
    """Map LLVM versions to the version of GCC gcov which they emulate."""
    if version >= 0x030400:
        return 0x040200
    else:
        warn("WARNING: This version of LLVM's gcov is unknown.  "
             "Assuming it emulates GCC gcov version 4.2.")
        return 0x040200


def get_gcov_version() -> Tuple[int, str]:
    """Get the GCOV tool version. Return an integer number which represents
    the GCOV version. Version numbers can be compared using standard integer
    operations."""

    # Examples for gcov version output:
    #
    # gcov (GCC) 4.4.7 20120313 (Red Hat 4.4.7-3)
    #
    # gcov (crosstool-NG 1.18.0) 4.7.2
    #
    # LLVM (http://llvm.org/):
    #   LLVM version 3.4svn
    #
    # Apple LLVM version 8.0.0 (clang-800.0.38)
    #       Optimized build.
    #       Default target: x86_64-apple-darwin16.0.0
    #       Host CPU: haswell
    try:
        gcov_process = subprocess.run([options.gcov_tool, "--version"],
                                      capture_output=True, encoding="utf-8",
                                      check=True)
    except:
        die("ERROR: cannot retrieve gcov version!")
    #local $/;  # NOK
    # Remove all bracketed information
    version_string = re.sub(r"\([^\)]*\)", "", gcov_process.stdout)

    match = re.???(r"(\d+)\.(\d+)(\.(\d+))?", version_string) # NOK
    if match:
        a, b, c = match.group(1), match.group(2), match.group(4)
        if c is None: c = 0
    else:
        a, b, c = 4, 2, 0  # Fallback version
        warn(f"WARNING: cannot determine gcov version - assuming {a}.{b}.{c}")

    result = a << 16 | b << 8 | c

    if re.???(r"LLVM", version_string): # NOK
        result = map_llvm_version(result)
        info(f"Found LLVM gcov version {a}.{b}.{c}, which emulates "
             "gcov version {}".format(gcov_version_to_str(result)))
    else:
        info("Found gcov version: {}".format(gcov_version_to_str(result)))

    return (result, version_string)


def gcov_version_to_str(version: int) -> str:
    """Return a readable version of encoded gcov version."""
    a = version >> 16 & 0xFF
    b = version >>  8 & 0xFF
    c = version       & 0xFF
    return f"{a}.{b}.{c}"

# NOK
def system_no_output(mode: int, *args) -> Tuple[int, Optional[???], Optional[???]]:
    """Call an external program using args while suppressing
    depending on the value of mode:

      MODE & 1: suppress sys.stdout
      MODE & 2: suppress sys.stderr
      MODE & 4: redirect to temporary files instead of suppressing

    Return (stdout, stderr, rc):
       stdout: path to tempfile containing stdout or None
       stderr: path to tempfile containing stderr or None
       0 on success, non-zero otherwise
    """
    stdout_file = None
    stderr_file = None
    # Save old stdout and stderr handles
    if mode & 1: prev_stdout = sys.stdout
    if mode & 2: prev_stderr = sys.stderr
    if mode & 4:
        # Redirect to temporary files
        if mode & 1:
            $fd, $stdout_file = tempfile(UNLINK => 1)
            sys.stdout = Path(stdout_file).open("wt")
                or warn("$!")
            close($fd);
        if mode & 2:
            $fd, $stderr_file = tempfile(UNLINK => 1)
            sys.stderr = Path(stderr_file).open("wt")
                or warn("$!")
            close($fd);
    else:
        # Redirect to /dev/null
        if mode & 1: sys.stdout = open(os.devnull, "wb")
        if mode & 2: sys.stderr = open(os.devnull, "wb")
    try:
        debug("system({}"")\n".format(" ".join(*args)))
        result = os.system(*args)
    finally:
        # Close redirected handles
        if mode & 1: close(sys.stdout)
        if mode & 2: close(sys.stderr)
        # Restore old handles
        if mode & 1: sys.stdout = prev_stdout
        if mode & 2: sys.stderr = prev_stderr
        # Remove empty output files
        if stdout_file is not None and -z $stdout_file:
            Path(stdout_file).unlink()
            stdout_file = None
        if stderr_file is not None and -z $stderr_file:
            Path(stderr_file).unlink()
            stderr_file = None

    return (result, stdout_file, stderr_file)


def get_all_source_data(filenames: List[str]) -> Dict[str, Tuple[???, ???, ???]]: # NOK
    """Scan specified source code files for exclusion markers and return
      filename -> [ excl, brexcl, checksums ]
      excl:      lineno -> 1 for all lines for which to exclude all data
      brexcl:    lineno -> 1 for all lines for which to exclude branch data
      checksums: lineno -> source code checksum
    """
    data: Dict[str, Tuple[???, ???, ???]] = {} # NOK
    failed = False
    for filename in filenames:
        if filename in data: continue
        srcdata = get_source_data(Path(filename))
        if srcdata:
            data[filename] = srcdata
        else:
            failed = True

    if failed:
        warn("WARNING: some exclusion markers may be ignored")

    return data

# NOK
def get_source_data(filename: Path) -> Optional[Tuple[???, ???, ???]]:
    """Scan specified source code file for exclusion markers and checksums.
    Return
      ( excl, brexcl, checksums ) where
      excl:      lineno -> 1 for all lines for which to exclude all data
      brexcl:    lineno -> 1 for all lines for which to exclude branch data
      checksums: lineno -> source code checksum
    """
    global options
    global intermediate

    ln_flag           = False
    br_flag           = False
    exception_br_flag = False

    my %list;
    my %brdata;
    my %checksums;

    try:
        fhandle = filename.open("rt")
    except:
        warn(f"WARNING: could not open {filename}")
        return None
    with fhandle:
        while (<fhandle>):
            if /$EXCL_STOP/:
                ln_flag = False
            elif /$EXCL_START/:
                ln_flag = True
            if /$options.excl_line/ or ln_flag:
                $list{$.} = 1
            if /$EXCL_BR_STOP/:
                br_flag = False
            elif /$EXCL_BR_START/:
                br_flag = True
            if /$EXCL_EXCEPTION_BR_STOP/:
                exception_br_flag = False
            elif /$EXCL_EXCEPTION_BR_START/:
                exception_br_flag = True
            if /$options.excl_br_line/ or br_flag:
                $brdata{$.} = 1
            elif /$options.excl_exception_br_line/ or exception_br_flag:
                $brdata{$.} = 2
            if $checksum:
                chomp();
                $checksums{$.} = md5_base64($_)
            if (intermediate and "json-format" not in gcov_capabilities and
                /($EXCL_EXCEPTION_BR_STOP|$EXCL_EXCEPTION_BR_START|$options.excl_exception_br_line)/):
                warn(f"WARNING: $1 found at {filename}:$. but branch exceptions "
                     "exclusion is not supported when using text intermediate "
                     "format")

    if ln_flag or br_flag or exception_br_flag:
        warn(f"WARNING: unterminated exclusion section in {filename}")

    return (\%list, \%brdata, \%checksums)

# NOK
def process_graphfile(graph_filename: Path, $dir):
    """ """
    global options
    global args
    global cwd

    info("Processing %s", str(graph_filename.relative_to($dir)))

    # Get path to data file in absolute and normalized form (begins with /,
    # contains no more ../ or ./)
    graph_filename = solve_relative_path(cwd, str(graph_filename))
    # Get directory and basename of data file
    $graph_dir, $graph_basename, _ = split_filename(graph_filename)

    $source_dir = $graph_dir
    if is_compat(COMPAT_MODE_LIBTOOL):
        # Avoid files from .libs dirs
        $source_dir = re.sub(r"\.libs$", "", $source_dir)

    # Construct base_dir for current file
    $base_dir = args.base_directory or $source_dir

    # Ignore empty graph file (e.g. source file with no statement)
    if (-z graph_filename):
        warn(f"WARNING: empty {graph_filename} (skipped)")
        return

    graph_filepath = Path(graph_filename)
    if gcov_version >= GCOV_VERSION_3_4_0:
        instr, graph = read_gcno(graph_filepath)
    elif is_compat($COMPAT_MODE_HAMMER):
        instr, graph = read_bbg(graph_filepath)
    else:
        instr, graph = read_bb(graph_filepath)

    # Try to find base directory automatically if requested by user
    if options.auto_base:
        $base_dir = str(find_base_from_source(Path($base_dir),
                                              [ keys(%{$instr}), keys(%{$graph}) ]))

    adjust_source_filenames($instr, Path($base_dir))
    adjust_source_filenames($graph, Path($base_dir))

    if not args.no_markers:
        # Apply exclusion marker data to graph file data
        instr, graph = apply_exclusion_data($instr, $graph)

    # Check whether we're writing to a single file
    if args.output_filename:
        if args.output_filename == "-":
            INFO_HANDLE = sys.stdout
        else:
            # Append to output file
            try:
                INFO_HANDLE = Path(args.output_filename).open(">>")
            except:
                die(f"ERROR: cannot write to {args.output_filename}!")
    else:
        # Open .info file for output
        try:
            INFO_HANDLE = Path(f"{graph_filename}.info").open("wt")
        except:
            die(f"ERROR: cannot create {graph_filename}.info!")

    # Write test name
    print("TN:%s" % $test_name, file=INFO_HANDLE)

    for filename in sorted($instr.keys()):

        my $funcdata = $graph->{$filename};

        my $line;
        my $linedata;

        # Skip external files if requested
        if not options.external and if is_external(filename):
            info(f"  ignoring data for external file {filename}")
            continue

        print(f"SF:{filename}", file=INFO_HANDLE)

        if defined($funcdata) and $fn_coverage:
            functions = sorted({ $funcdata->{$a}->[0] <=> $funcdata->{$b}->[0] }
                               $funcdata.keys())
            # Gather list of instrumented lines and functions
            for func in functions:
                $linedata = $funcdata[func]
                # Print function name and starting line
                print("FN:".$linedata->[0].",".filter_fn_name(func), file=INFO_HANDLE)
            # Print zero function coverage data
            for func in functions:
                print("FNDA:0,".filter_fn_name(func), file=INFO_HANDLE)
            # Print function summary
            print("FNF:{}".format(len(functions)), file=INFO_HANDLE)
            print("FNH:0", file=INFO_HANDLE)

        # Print zero line coverage data
        foreach $line (@{$instr->{$filename}}):
            print("DA:$line,0", file=INFO_HANDLE)
        # Print line summary
        print("LF:{}".format(len(@{$instr->{$filename}})), file=INFO_HANDLE)
        print("LH:0", file=INFO_HANDLE)

        print("end_of_record", file=INFO_HANDLE)

    if not (args.output_filename and args.output_filename == "-"):
        close(INFO_HANDLE)

# NOK
def apply_exclusion_data($instr, $graph):
    # Remove lines from instr and graph data structures which are marked
    # for exclusion in the source code file.
    #
    # Return adjusted (instr, graph).
    #
    # graph         : file name -> function data
    # function data : function name -> line data
    # line data     : [ line1, line2, ... ]
    #
    # instr     : filename -> line data
    # line data : [ line1, line2, ... ]

    $excl_data: Dict[str, Tuple[???, ???, ???]] = get_all_source_data($graph.keys() + $instr.keys())

    # Skip if no markers were found
    if not $excl_data:
        return ($instr, $graph)

    # Apply exclusion marker data to graph
    for filename in %$excl_data.keys():

        $excl = $excl_data->{$filename}->[0];
        $function_data = $graph->{$filename};

        if ! defined($function_data): continue

        for $function, $line_data in %{$function_data}.items():
            # To be consistent with exclusion parser in non-initial
            # case we need to remove a function if the first line
            # was excluded
            if $excl->{$line_data->[0]}:
                delete ($function_data->{$function});
                continue

            my @new_data;
            # Copy only lines which are not excluded
            for $line in (@{$line_data}):
                if not $excl->{$line}:
                    push(@new_data, $line)

            # Store modified list
            if len(@new_data) > 0:
                $function_data->{$function} = \@new_data;
            else:
                # All of this function was excluded
                delete($function_data->{$function});

        # Check if all functions of this file were excluded
        if keys(%{$function_data}) == 0:
            delete ($graph->{$filename});

    # Apply exclusion marker data to instr
    for filename in %$excl_data.keys():

        $excl = $excl_data->{$filename}->[0];
        $line_data = instr[filename]

        if ! defined($line_data): continue

        my @new_data;
        # Copy only lines which are not excluded
        for $line in @{$line_data}:
            if not $excl->{$line}:
                push(@new_data, $line)

        # Store modified list
        instr[filename] = \@new_data;

    return ($instr, $graph)


def filter_fn_name(func: str):
    """Remove characters used internally as function name delimiters."""
    func = re.sub(r"[,=]", "_", func)
    return func


def graph_expect(description: Optional[str]):
    """If debug is set to a non-zero value, print the specified description
    of what is expected to be read next from the graph file.
    """
    global args
    if not args.debug or description is None: return
    print(f"DEBUG: expecting {description}", file=sys.stderr)


def graph_skip(fhandle, length: int, description: Optional[str] = None) -> bool:
    """Read and discard the specified number of bytes from fhandle.
    Return True if bytes could be read, False otherwise.
    """
    return graph_read(fhandle, length, description) is not None


def find_base_from_source(base_dir: Path, source_files: List[???]) -> Path: # NOK
    """Try to determine the base directory of the object file built from
    SOURCE_FILES. The base directory is the base for all relative filenames
    in the gcov data. It is defined by the current working directory at time
    of compiling the source file.

    This function implements a heuristic which relies on the following
    assumptions:
    - all files used for compilation are still present at their location
    - the base directory is either BASE_DIR or one of its parent directories
    - files by the same name are not present in multiple parent directories
    """
    rel_files = set()
    # Determine list of relative paths
    for filename in source_files:
        if not file_name_is_absolute(filename):
            rel_files.add(filename)
    # Early exit if there are no relative paths
    if not rel_files:
        return base_dir

    best_miss = None
    best_base = None

    while True:
        miss = 0
        for filename in rel_files:
            if not -e solve_relative_path(base_dir, filename): # NOK
                miss += 1

        debug(f"base_dir={base_dir} miss={miss}\n")

        # Exit if we find an exact match with no misses
        if miss == 0:
            return base_dir

        # No exact match, aim for the one with the least source file
        # misses
        if best_base is None or miss < best_miss:
            best_base = base_dir
            best_miss = miss

        # Repeat until there's no more parent directory
        old_base = base_dir
        base_dir = parent_dir(base_dir)
        if old_base == base_dir:
            break

    return best_base

# NOK
def parent_dir(dir: Path) -> Path:
    """Return parent directory for DIR.
    DIR must not contain relative path components."""
    $v, $d, $f = splitpath(str(dir), 1)
    dirs = splitdir($d)
    pop(@dirs)
    return Path(catpath($v, catdir(dirs), $f))


def adjust_source_filenames(data_dict: Dict[str, object], base_dir: Path):
    """ransform all keys of data_dict to absolute form and apply requested
    transformations."""
    global adjust_src_pattern, adjust_src_replace

    for filename in list(data_dict.keys()):
        old_filename = filename

        # Convert to absolute canonical form
        filename = solve_relative_path(base_dir, filename)
        # Apply adjustment
        if adjust_src_pattern is not None:
            filename = re.sub(adjust_src_pattern, adjust_src_replace, filename)

        if filename != old_filename:
            data_dict[filename] = data_dict.pop(old_filename)


def filter_source_files(data_dict: Dict[???, ???]): # NOK
    """Remove unwanted source file data from data_dict."""
    global options
    global excluded_files

    for filename in list(data_dict.keys()):

        # Skip external files if requested
        if not options.external and is_external(filename):
            # Remove file data
            del data_dict[filename]
            excluded_files.add(filename)
            continue

        # Apply include patterns
        if args.include_patterns:
            for pattern in args.include_patterns:
                match = re.match(rf"^{pattern}$", filename)
                if match:
                    break
            else:
                # Remove file data
                del data_dict[filename]
                excluded_files.add(filename)
                continue

        # Apply exclude patterns
        if args.exclude_patterns:
            for pattern in args.exclude_patterns:
                match = re.match(rf"^{pattern}$", filename)
                if match:
                    # Remove file data
                    del data_dict[filename]
                    excluded_files.add(filename)
                    break


def graph_cleanup(graph: Dict[str, Dict[???, List[???]]]): # NOK
    """Remove entries for functions with no lines.
    Remove duplicate line numbers.
    Sort list of line numbers numerically ascending.
    """
    for filename in list(graph.keys()):
        per_file: Dict[???, List[???]] = graph[filename] # NOK

        for function in list(per_file.keys()):
            lines: List[???] = per_file[function] # NOK
            if len(lines) == 0:
                # Remove empty function
                del per_file[function]
            else:
                # Normalize list
                per_file[function] = unique(lines)

        if len(per_file) == 0:
            # Remove empty file
            del graph[filename]

# NOK
def graph_from_bb($bb: Dict[???, ???], $fileorder: Dict[???, ???], bb_filename: Path, *,
                  fileorder_first: bool = False) -> Tuple[Dict[str, List[???]], Dict[str, Dict[str, List[???]]]]:
    # Convert data from bb to the graph format and list of instrumented lines.
    #
    # If FILEORDER_FIRST is set, use fileorder data to determine a functions
    # base source file.
    #
    # Returns (instr, graph).
    #
    # bb         : function name -> file data
    #            : undef -> file order
    # file data  : filename -> line data
    # line data  : [ line1, line2, ... ]
    #
    # file order : function name -> [ filename1, filename2, ... ]
    #
    # graph         : file name -> function data
    # function data : function name -> line data
    # line data     : [ line1, line2, ... ]
    #
    # instr     : filename -> line data
    # line data : [ line1, line2, ... ]

    instr: Dict[str, List[???]] = {}
    graph: Dict[str, Dict[str, List[???]]] = {}

    basefile = graph_find_base(bb)

    # Create graph structure
    for func, filedata in bb.items():

        # Account for lines in functions
        if basefile is not None and basefile in filedata and not fileorder_first:
            # If the basefile contributes to this function,
            # account this function to the basefile.
            file = basefile
        else:
            # If the basefile does not contribute to this function,
            # account this function to the first file contributing
            # lines.
            file = fileorder[func][0]
        linedata = filedata[file]
        if file not in graph: graph[file] = {}
        graph[file][func] = linedata

        for file, linedata in filedata.items():
            # Account for instrumented lines
            if file not in instr: instr[file] = []
            instr[file].append(@$linedata) # ??? a nie extend ???

    # Clean up array of instrumented lines
    for file in instr.keys():
        instr[file] = sort_unique(instr[file])

    return (instr, graph)


def graph_find_base(bb: Dict[???, Dict[???, ???]]) -> Optional[str]: # NOK
    """Try to identify the filename which is the base source file
    for the specified bb data.
    """
    file_count: Dict[???, int] = {} # NOK
    # Identify base name for this bb data.
    for filedata in bb.values():
        for file in filedata.keys():
            # Count file occurrence
            if file in file_count:
                file_count[file] += 1
            else:
                file_count[file] = 1

    basefile = None
    count    = 0
    for file, fcount in file_count.items():
        if fcount > count:
            # The file that contains code for the most functions is likely
            # the base file
            count = fcount
            basefile = file
        elif fcount == count:
            # If more than one file could be the basefile, we don't have
            # a basefile
            basefile = None

    return basefile


def graph_add_order(fileorder: Dict[str, object], function: str, filename: str):
    """Add an entry for filename to the fileorder data set for function."""
    list = fileorder[function]
    if filename not in list:
        list.append(filename)
        fileorder[function] = list

# NOK
def read_bb(bb_filename: Path):
    # Read the contents of the specified .bb file and return (instr, graph), where:
    #
    #   instr     : filename -> line data
    #   line data : [ line1, line2, ... ]
    #
    #   graph     :     filename -> file_data
    #   file_data : function name -> line_data
    #   line_data : [ line1, line2, ... ]
    #
    # See the gcov info pages of gcc 2.95 for a description of the .bb file format.

    minus_one = 0x80000001
    minus_two = 0x80000002

    my $instr;
    my $graph;

    my $bb        = {}
    my $fileorder = {}

    try:
        fhandle = bb_filename.open("rb")
    except:
        graph_error(bb_filename, "could not open file")
        return None
    filename = None
    function = None
    with fhandle:
        while ! eof(fhandle):
            word_value = read_bb_value(fhandle, "data word")
            if word_value is None:
                goto incomplete
            _, value: int = word_value
            if value == minus_one:
                # Source file name
                graph_expect("filename")
                filename = read_bb_string(fhandle, minus_one)
                if filename is None:
                    goto incomplete
            elif value == minus_two:
                # Function name
                graph_expect("function name")
                function = read_bb_string(fhandle, minus_two)
                if function is None:
                    goto incomplete
            elif value > 0:
                # Line number
                if filename is None or function is None:
                    warn(f"WARNING: unassigned line number {value}")
                    continue
                @{$bb[function]->{$filename}}.append(value)
                graph_add_order($fileorder, function, filename)

    instr, graph = graph_from_bb(bb, $fileorder, bb_filename)
    graph_cleanup(graph)

    return (instr, graph)

    incomplete:
    graph_error(bb_filename, "reached unexpected end of file")
    return None


def read_bb_string(fhandle,
                   delimiter: int) -> Optional[str]:
    """Read and return a string in .bb format from fhandle up to the
    specified delimiter value."""
    graph_expect("string")
    string = ""
    while True:
        word_value = read_bb_value(fhandle, "string or delimiter")
        if word_value is None:
            return None
        word: str, value: int = word_value
        if value == delimiter:
            break
        string += word
    string =~ s/\0//g # NOK

    return string


def read_bb_value(fhandle,
                  description: Optional[str] = None) -> Optional[Tuple[str, int]]:
    """Read a word in .bb format from fhandle and return the word and
    its integer value."""
    word = read_bb_word(fhandle, description)
    return (word, unpack("V", word)) if word is not None else None


def read_bb_word(fhandle,
                 description: Optional[str] = None) -> Optional[str]:
    """Read and return a word in .bb format from fhandle."""
    return graph_read(fhandle, 4, description)

# NOK
def read_bbg(bbg_filename: Path):
    # Read the contents of the specified .bbg file and return the following mapping:
    #   graph:     filename -> file_data
    #   file_data: function name -> line_data
    #   line_data: [ line1, line2, ... ]
    #
    # See the gcov-io.h file in the SLES 9 gcc 3.3.3 source code for a description
    # of the .bbg format.

    file_magic   = 0x67626267
    tag_function = 0x01000000
    tag_lines    = 0x01450000

    my $word;
    my $instr;
    my $graph;

    function  = None
    $bb        = {}
    $fileorder = {}

    try
        fhandle = bbg_filename.open("rb")
    except:
        graph_error(bbg_filename, "could not open file")
        return None
    filename = None
    with fhandle:
        # Read magic
        word = read_bbg_value(fhandle, "file magic")
        if word is None:
            goto incomplete
        # Check magic
        if word != file_magic:
            goto magic_error;
        # Skip version
        if not graph_skip(fhandle, 4, "version"):
            goto incomplete;
        while not eof(fhandle):
            # Read record tag
            tag = read_bbg_value(fhandle, "record tag")
            if tag is None:
                goto incomplete
            # Read record length
            rec_length = read_bbg_value(fhandle, "record length")
            if rec_length is None: # !!! tu blad - ma byc !defined($length) !!!
                goto incomplete
            if tag == tag_function:
                graph_expect("function record")
                # Read function name
                graph_expect("function name")
                function = read_bbg_string(fhandle)
                if function is None:
                    goto incomplete
                filename = None
                # Skip function checksum
                if not graph_skip(fhandle, 4, "function checksum"):
                    goto incomplete;
            elif tag == tag_lines:
                # Read lines record
                filename = read_bbg_lines_record(fhandle, bbg_filename,
                                                 $bb, $fileorder, filename,
                                                 function)
                if filename is None:
                    goto incomplete
            else:
                # Skip record contents
                if not graph_skip(fhandle, rec_length, "unhandled record"):
                    goto incomplete;

    instr, graph = graph_from_bb(bb, $fileorder, bbg_filename)
    graph_cleanup(graph)

    return (instr, graph)

    incomplete:
    graph_error(bbg_filename, "reached unexpected end of file")
    return None

    magic_error:
    graph_error(bbg_filename, "found unrecognized bbg file magic")
    return None

# NOK
def read_bbg_lines_record(fhandle, bbg_filename: Path,
                          $bb, $fileorder, $filename, $function) -> Optional[???]:
    # Read a bbg format lines record from handle and add the relevant data to
    # bb and fileorder. Return filename on success, None on error.

    my $string;
    my $lineno;

    graph_expect("lines record")
    # Skip basic block index
    if not graph_skip(fhandle, 4, "basic block index"):
        return None
    while True:
        # Read line number
        lineno = read_bbg_value(fhandle, "line number")
        if lineno is None:
            return None
        if lineno == 0:
            # Got a marker for a new filename
            graph_expect("filename")
            string = read_bbg_string(fhandle)
            if string is None:
                return None
            # Check for end of record
            if string == "":
                return filename
            filename = string
            if ! exists($bb->{$function}->{$filename}):
                $bb->{$function}->{$filename} = []
            continue

        # Got an actual line number
        if filename is None:
            warn(f"WARNING: unassigned line number in {bbg_filename}")
            continue

        @{$bb->{$function}->{$filename}}.append($lineno)
        graph_add_order($fileorder, $function, $filename)


def read_bbg_string(fhandle) -> Optional[str]:
    # !!! byl niepotrzebny parametr $desc !!!
    """Read and return a string in .bbg format."""
    graph_expect("string")
    # Read string length
    length = read_bbg_value(fhandle, "string length")
    if length is None:
        return None
    if length == 0:
        return ""
    # Read string
    string = graph_read(fhandle, length, "string")
    if string is None:
        return None
    # Skip padding
    if not graph_skip(fhandle, 4 - length % 4, "string padding"):
        return None
    return string


def read_bbg_value(fhandle,
                   description: Optional[str] = None) -> Optional[int]:
    """Read a word in .bbg format from fhandle and return its integer value."""
    word = read_bbg_word(fhandle, description)
    return unpack("N", word) if word is not None else None


def read_bbg_word(fhandle,
                  description: Optional[str] = None) -> Optional[str]:
    """Read and return a word in .bbg format."""
    return graph_read(fhandle, 4, description)

# NOK
def read_gcno(gcno_filename: Path) -> Optional[Tuple[Any, Any]]
    # Read the contents of the specified .gcno file and return the following
    # mapping:
    #   graph:    filename -> file_data
    #   file_data: function name -> line_data
    #   line_data: [ line1, line2, ... ]
    #
    # See the gcov-io.h file in the gcc 3.3 source code for a description of
    # the .gcno format.

    file_magic   = 0x67636e6f
    tag_function = 0x01000000
    tag_lines    = 0x01450000

    my $length;
    my $filename;
    my $function;
    my $bb = {};
    my $instr;
    my $graph;
    my $filelength;

    $fileorder: Dict = {}
    artificial_fns: List = []

    try:
        fhandle = gcno_filename.open("rb")
    except:
        graph_error(gcno_filename, "could not open file")
        return None

    $filelength = Path().stat(fhandle)[7]
    # Read magic
    word = read_gcno_word(fhandle, "file magic")
    if word is None:
        goto incomplete
    # Determine file endianness
    big_endian: bool
    if unpack("N", word) == file_magic:
        big_endian = True
    elif unpack("V", word) == file_magic:
        big_endian = False
    else:
        goto magic_error;
    # Read version
    version = read_gcno_value(fhandle, big_endian, "compiler version")
    version = map_gcno_version(version)
    debug("found version 0x%08x\n" % version)
    # Skip stamp
    if not graph_skip(fhandle, 4, "file timestamp"):
        goto incomplete;
    if version >= GCOV_VERSION_8_0_0:
        if not graph_skip(fhandle, 4, "support unexecuted blocks flag"):
            goto incomplete;

    with fhandle:
        while !eof(fhandle):
            # Read record tag
            tag = read_gcno_value(fhandle, big_endian, "record tag")
            if tag is None:
                goto incomplete
            # Read record length
            length = read_gcno_value(fhandle, big_endian, "record length")
            if length is None:
                goto incomplete
            # Convert length to bytes
            length *= 4
            # Calculate start of next record
            next_pos = tell(fhandle);
            if next_pos == -1:
                goto tell_error
            next_pos += length

            # Catch garbage at the end of a gcno file
            if next_pos > $filelength:
                debug(f"Overlong record: file_length={filelength} rec_length={length}\n")
                warn(f"WARNING: {gcno_filename}: Overlong record at end of file!")
                break

            # Process record
            if tag == tag_function:
                filename_function_artificial = read_gcno_function_record(fhandle, $bb,
                                                                         $fileorder,
                                                                         big_endian,
                                                                         length,
                                                                         version)
                if filename_function_artificial is None:
                     goto incomplete
                $filename, $function, artificial = filename_function_artificial
                if artificial:
                    artificial_fns.append($function)
            elif tag == tag_lines:
                # Read lines record
                $filename = read_gcno_lines_record(fhandle,
                                                   gcno_filename, $bb, $fileorder,
                                                   $filename, $function, big_endian)
                if $filename is None:
                    goto incomplete
            else:
                # Skip record contents
                if not graph_skip(fhandle, length, "unhandled record"):
                    goto incomplete;
            # Ensure that we are at the start of the next record
            curr_pos = tell(fhandle)
            if curr_pos == -1:
                goto tell_error
            if curr_pos == next_pos:
                continue
            if curr_pos > next_pos:
                goto record_error
            if not graph_skip(fhandle, next_pos - curr_pos, "unhandled record content"):
                goto incomplete;

    # Remove artificial functions from result data
    remove_items_from_dict($bb,        artificial_fns)
    remove_items_from_dict($fileorder, artificial_fns)

    instr, graph = graph_from_bb(bb, $fileorder, gcno_filename, fileorder_first=True)
    graph_cleanup(graph)

    return (instr, graph)

    incomplete:
    graph_error(gcno_filename, "reached unexpected end of file")
    return None

    magic_error:
    graph_error(gcno_filename, "found unrecognized gcno file magic")
    return None

    tell_error:
    graph_error(gcno_filename, "could not determine file position")
    return None

    record_error:
    graph_error(gcno_filename, "found unrecognized record format")
    return None

# NOK
def read_gcno_function_record(fhandle,
                              $bb, $fileorder,
                              big_endian: bool,
                              rec_length: int,
                              version: int) -> Optional[Tuple[str, str, bool]]:
    # read_gcno_function_record(handle, graph, big_endian, rec_length, version)
    #
    # Read a gcno format function record from handle and add the relevant data
    # to graph. Return (filename, function, artificial) on success, None on error.

    global gcno_split_crc

    graph_expect("function record");
    # Skip ident and checksum
    if not graph_skip(fhandle, 8, "function ident and checksum"):
        return None
    # Determine if this is a function record with split checksums
    if gcno_split_crc is None:
        gcno_split_crc = determine_gcno_split_crc(fhandle, big_endian,
                                                  rec_length, version)
        if gcno_split_crc is None:
            return None
    # Skip cfg checksum word in case of split checksums
    if gcno_split_crc:
        graph_skip(fhandle, 4, "function cfg checksum")
    # Read function name
    graph_expect("function name");
    function = read_gcno_string(fhandle, big_endian)
    if function is None:
        return None
    artificial = None
    if version >= GCOV_VERSION_8_0_0:
        artificial = read_gcno_value(fhandle, big_endian,
                                     "compiler-generated entity flag")
        if artificial is None:
            return None
    # Read filename
    graph_expect("filename");
    filename = read_gcno_string(fhandle, big_endian)
    if filename is None:
        return None
    # Read first line number
    lineno = read_gcno_value(fhandle, big_endian, "initial line number")
    if lineno is None:
        return None
    # Skip column and ending line number
    if version >= GCOV_VERSION_8_0_0:
        if not graph_skip(fhandle, 4, "column number"):
            return None
        if not graph_skip(fhandle, 4, "ending line number"):
            return None
    # Add to list
    @{$bb->{function}->{filename}}.append(lineno)
    graph_add_order($fileorder, function, filename)

    return (filename, function, bool(artificial))


def determine_gcno_split_crc(fhandle,
                             big_endian: bool,
                             rec_length: int,
                             version: int) -> Optional[bool]:
    """Determine if fhandle refers to a .gcno file with a split checksum
    function record format. Return non-zero in case of split checksum format,
    zero otherwise, None in case of read error."""

    if version >= GCOV_VERSION_4_7_0:    return True
    if is_compat(COMPAT_MODE_SPLIT_CRC): return True

    # Heuristic:
    # Decide format based on contents of next word in record:
    # - pre-gcc 4.7
    #   This is the function name length / 4 which should be
    #   less than the remaining record length
    # - gcc 4.7
    #   This is a checksum, likely with high-order bits set,
    #   resulting in a large number
    strlen = read_gcno_value(fhandle, big_endian, None, peek=True)
    if strlen is None:
        return None

    overlong_string = (strlen * 4 >= rec_length - 12)
    if overlong_string:
        if is_compat_auto(COMPAT_MODE_SPLIT_CRC):
            info("Auto-detected compatibility mode for split "
                 "checksum .gcno file format")
            return True
        else:
            # Sanity check
            warn("Found overlong string in function record: "
                 "try '--compat split_crc'")

    return False

# NOK
def read_gcno_lines_record(fhandle,
                           gcno_filename: Path, $bb, $fileorder, $filename, $function, big_endian: bool) -> Optional[???]:
    """
    Read a gcno format lines record from handle and add the relevant data to
    bb and fileorder. Return filename on success, None on error.
    """
    graph_expect("lines record")
    # Skip basic block index
    if not graph_skip(fhandle, 4, "basic block index"):
        return None
    while True:
        # Read line number
        lineno = read_gcno_value(fhandle, big_endian, "line number")
        if lineno is None:
            return None
        if lineno == 0:
            # Got a marker for a new filename
            graph_expect("filename")
            string = read_gcno_string(fhandle, big_endian)
            if string is None:
                return None
            # Check for end of record
            if string == "":
                return filename
            filename = string
            if !exists($bb->{$function}->{$filename}):
                $bb->{$function}->{$filename} = [];
            continue

        # Got an actual line number
        if filename is None:
            warn(f"WARNING: unassigned line number in {gcno_filename}")
            continue

        # Add to list
        push(@{$bb->{$function}->{$filename}}, lineno)
        graph_add_order($fileorder, $function, $filename)


def read_gcno_string(fhandle,
                     big_endian: bool) -> Optional[str]:
    """Read and return a string in .gcno format."""
    graph_expect("string")
    # Read string length
    length = read_gcno_value(fhandle, big_endian, "string length")
    if length is None:
        return None
    if length == 0:
        return ""
    # Read string
    string = graph_read(fhandle, length * 4, "string and padding")
    if string is None:
        return None
    string =~ s/\0//g # NOK

    return string


def read_gcno_value(fhandle, big_endian: bool, description=None, *,
                    peek: bool = False) -> Optional[int]:
    """Read a word in .gcno format from fhandle and return its integer value
    according to the specified endianness. If PEEK is non-zero, reset file
    position after read.
    """
    word = read_gcno_word(fhandle, description, peek=peek)
    return unpack("N" if big_endian else "V", word) if word is not None else None


def read_gcno_word(fhandle, description=None, *,
                   peek: bool = False) -> Optional[str]:
    """Read and return a word in .gcno format."""
    return graph_read(fhandle, 4, description, peek=peek)


def graph_read(fhandle, length: int, description: Optional[str] = None, *,
               peek: bool = False) -> Optional[str]:
    """Read and return the specified number of bytes from fhandle.
    Return None if the number of bytes could not be read.
    If peek is non-zero, reset file position after read.
    """
    graph_expect(description)

    if peek:
        try:
            pos = fhandle.tell()
        except Exception as exc:
            warn(f"Could not get current file position: {exc}!")
            return None

    data = fhandle.read(length)

    if args.debug:
        op = "peek" if peek else "read"
        print(f"DEBUG: {op}({length})={result}: ", end="", file=sys.stderr)
        ascii, hex = "", ""
        for ch in data:
            hex   += "%02x " % ord(ch)
            ascii += ch if 32 <= ord(ch) <= 127 else "."
        print(f"{hex} |{ascii}|", file=sys.stderr)

    if peek:
        try:
            fhandle.seek(pos, 0)
        except Exception as exc:
            warn(f"Could not set file position: {exc}!")
            return None

    if len(data) != length:
        return None

    return data


def graph_error(filename: Path, msg: str):
    """Print message about error in graph file.
    If ignore_graph_error is set, return. Otherwise abort.
    """
    global ignore
    if ignore[ERROR_GRAPH]:
        warn(f"WARNING: {filename}: {msg} - skipping")
    else:
        die(f"ERROR: {filename}: {msg}")


def map_gcno_version(version: int) ->int:
    """Map version number as found in .gcno files to the format
    used in geninfo."""

    a = version >> 24
    b = version >> 16 & 0xFF
    c = version >>  8 & 0xFF

    ord_0 = ord("0")
    ord_A = ord("A")

    if a < ord_A:
        major = (a - ord_0)
        minor = (b - ord_0) * 10 + (c - ord_0)
    else:
        major = (a - ord_A) * 10 + (b - ord_0)
        minor = (c - ord_0)

    return major << 16 | minor << 8


def get_gcov_capabilities() -> Set[str]:
    """Determine the list of available gcov options."""
    global options

    short_option_translations = {
        "a": "all-blocks",
        "b": "branch-probabilities",
        "c": "branch-counts",
        "f": "function-summaries",
        "h": "help",
        "i": "intermediate-format",
        "l": "long-file-names",
        "n": "no-output",
        "o": "object-directory",
        "p": "preserve-paths",
        "u": "unconditional-branches",
        "v": "version",
        "x": "hash-filenames",
    }

    gcov_process = subprocess.run([options.gcov_tool, "--help"],
                                  capture_output=True, encoding="utf-8",
                                  check=True)
    gcov_help = gcov_process.stdout

    capabilities: Set[str] = set()
    for line in gcov_help.splitlines():
        match = re.???(r"--(\S+)", line) # NOK
        if match:
            capability = match.group(1)
        else:
            # If the line provides a short option, translate it.
            match = re.match(r"^\s*-(\S)\s", line)
            if not match:
                continue
            capability = short_option_translations.get(match.group(1))
            if capability is None:
                continue
        if capability in ("help", "version", "object-directory"):
            continue

        capabilities.add(capability)
        debug(f"gcov has capability '{capability}'\n")

    return capabilities


def is_external(filename: str) -> bool:
    """Determine if a file is located outside of the specified
    data directories."""
    global internal_dirs
    for dir in internal_dirs:
        match = re.match(rf"^\Q{dir}/\E", filename)
        if match:
            return False
    return True


def parse_compat_modes(opt: Optional[str], compat_value: Dict[int, int]):
    """Determine compatibility mode settings."""
    global options

    # Initialize with defaults
    compat_value = COMPAT_MODE_DEFAULTS.copy()

    # Add old style specifications
    if options.compat_libtool is not None:
        compat_value[COMPAT_MODE_LIBTOOL] = (COMPAT_VALUE_ON
                                             if options.compat_libtool else
                                             COMPAT_VALUE_OFF)
    # Parse settings
    opt_list: List[str] = re.split(r"\s*,\s*", opt) if opt is not None else []

    specified = set()
    for directive in opt_list:
        # Either
        #   mode=off|on|auto or
        #   mode (implies on)
        match = re.match(r"^(\w+)=(\w+)$", directive)
        if not match:
            match = re.match(r"^(\w+)$", directive)
        if not match:
            die(f"ERROR: Unknown compatibility mode specification: {directive}!")
        mode_gr  = match.group(1)
        value_gr = match.group(2)
        # Determine mode
        mode: Optional[int] = COMPAT_NAME_TO_MODE.get(mode_gr.lower())
        if mode is None:
            die(f"ERROR: Unknown compatibility mode '{mode_gr}'!")
        specified.add(mode)
        # Determine value
        if value_gr is not None:
            value: Optional[int] = COMPAT_NAME_TO_VALUE.get(value_gr.lower())
            if value is None:
                die(f"ERROR: Unknown compatibility mode value '{value_gr}'!")
        else:
            value = COMPAT_VALUE_ON

        compat_value[mode] = value

    # Perform auto-detection
    for mode in sorted(compat_value.keys()):
        value = compat_value[mode]
        name  = compat_name(mode)
        is_autodetect = ""

        if value == COMPAT_VALUE_AUTO:
            autodetect = COMPAT_MODE_AUTO.get(mode)
            if autodetect is None:
                die(f"ERROR: No auto-detection for mode '{name}' available!")

            if callable(autodetect):
                value = autodetect()
                compat_value[mode] = value
                is_autodetect = " (auto-detected)"

        if mode in specified:
            if value == COMPAT_VALUE_ON:
                info(f"Enabling compatibility mode '{name}'{is_autodetect}")
            elif value == COMPAT_VALUE_OFF:
                info(f"Disabling compatibility mode '{name}'{is_autodetect}")
            else:
                info(f"Using delayed auto-detection for compatibility mode '{name}'")


def compat_name(mode: int) -> str:
    """Return the name of compatibility mode MODE."""
    return COMPAT_MODE_TO_NAME.get(mode, "<unknown>")


def compat_hammer_autodetect() -> int:
    """ """
    global gcov_version, gcov_version_string

    if ((re.search(r"suse",     gcov_version_string, re.I) and gcov_version == 0x30303) or
        (re.search(r"mandrake", gcov_version_string, re.I) and gcov_version == 0x30302)):
        info("Auto-detected compatibility mode for GCC 3.3 (hammer)")
        return COMPAT_VALUE_ON
    else:
        return COMPAT_VALUE_OFF


def is_compat(mode) -> bool:
    """Return non-zero if compatibility mode MODE is enabled."""
    global compat_value
    return (compat_value[mode] == COMPAT_VALUE_ON)


def is_compat_auto(mode) -> bool:
    """Return non-zero if compatibility mode MODE is set to auto-detect."""
    global compat_value
    return (compat_value[mode] == COMPAT_VALUE_AUTO)


def solve_relative_path(path: Path, dir: str) -> str:
    """Solve relative path components of dir which, if not absolute,
    resides in path."""

    # Convert from Windows path to msys path
    if $^O == "msys": # NOK
        # search for a windows drive letter at the beginning
        volume, directories, filename = File::Spec::Win32->splitpath(dir)
        if volume != "":
            # transform c/d\../e/f\g to Windows style c\d\..\e\f\g
            dir = File::Spec::Win32->canonpath(dir)
            # use Win32 module to retrieve path components
            # uppercase_volume is not used any further
            uppercase_volume, directories, filename = File::Spec::Win32->splitpath(dir)
            dirs = File::Spec::Win32->splitdir(directories)  # holds path elements

            # prepend volume, since in msys C: is always mounted to /c
            volume = re.sub(r"^([a-zA-Z]+):", r"/\L\1\E", volume)
            unshift( dirs, volume );

            # transform to Unix style '/' path
            directories = File::Spec->catdir(dirs)
            dir = File::Spec->catpath('', directories, filename)
        else:
            # eliminate '\' path separators
            dir = File::Spec->canonpath(dir)

    result = dir
    # Prepend path if not absolute
    match = re.match(r"^[^/]", result)
    if match:
        path = path.as_posix()
        result = f"{path}/{result}"

    # Remove //
    result = re.sub(r"//", r"/", result)

    # Remove .
    while True:
        result, nsub = re.subn(r"/./", r"/", result)
        if nsub == 0: break
    result = re.sub(r"/.$", r"/", result)

    # Remove trailing /
    result = re.sub(r"/$", r"", result)

    # Solve ..
    while True:
        result, nsub = re.subn(r"/[^\/]+/../", r"/", result)#, nonglobal) # NOK ???
        if nsub == 0: break

    # Remove preceding ..
    result = re.sub(r"^/../", r"/", result)

    return result

# NOK
def get_common_prefix(min_dir: int, @files):
    # get_common_prefix(min_dir, filenames)
    #
    # Return the longest path prefix shared by all filenames. MIN_DIR specifies
    # the minimum number of directories that a filename may have after removing
    # the prefix.

    my @prefix;
    my $i;

    for $file in @files:
        $v, $d, $f = splitpath($file)
        @comp = splitdir($d)

        if ! @prefix:
            @prefix = @comp;
            continue

        for ($i = 0; $i < len(comp) and $i < len(prefix); $i++):
            if $comp[$i] != $prefix[$i] or (len(comp) - ($i + 1)) <= min_dir:
                delete (@prefix[$i..len(prefix)]);
                break

    return catdir(@prefix)


def info(format, *pars, *, end="\n"):
    """Use printf to write to stdout only when the args.quiet flag
    is not set."""
    global args
    global output_filename
    if args.quiet: return
    # Print info string
    if output_filename is not None and output_filename == "-":
        # Don't interfere with the .info output to sys.stdout
        print(format % pars, end=end, file=sys.stderr)
    else:
        print(format % pars, end=end)


def main(argv=sys.argv[1:]):
    """\
    """
    global tool_name, lcov_version, lcov_url

    # NOK
    def int_handler()
        # Called when the script was interrupted by an INT signal (e.g. CTRl-C)
        global cwd
        if cwd:
            os.chdir(cwd)
        info("Aborted.")
        sys.exit(1)

    def debug(msg: str):
        global args
        if not args.debug: return
        print(f"DEBUG: {msg}", end="", file=sys.stderr)

    def warn_handler(msg: str):
        global tool_name
        import warnings
        warnings.warn(f"{tool_name}: {msg}")

    def die_handler(msg: str):
        global tool_name
        import sys
        sys.exit(f"{tool_name}: {msg}")

    # Register handler routine to be called when interrupted
    # $SIG{"INT"}    = int_handler
    # $SIG{__WARN__} = warn_handler
    # $SIG{__DIE__}  = die_handler


if __name__.rpartition(".")[-1] == "__main__":
    sys.exit(main())
