# Copyright (c) 2020-2022, Adam Karpierz
# Licensed under the BSD license
# https://opensource.org/licenses/BSD-3-Clause

"""
genhtml

  This script generates HTML output from .info files as created by the
  geninfo script. Call it with --help and refer to the genhtml man page
  to get information on usage and available options.

"""

# History:
#   2002-08-23 created by Peter Oberparleiter <Peter.Oberparleiter@de.ibm.com>
#                         IBM Lab Boeblingen
#        based on code by Manoj Iyer <manjo@mail.utexas.edu> and
#                         Megan Bock <mbock@us.ibm.com>
#                         IBM Austin
#   2002-08-27 / Peter Oberparleiter: implemented frame view
#   2002-08-29 / Peter Oberparleiter: implemented test description filtering
#                so that by default only descriptions for test cases which
#                actually hit some source lines are kept
#   2002-09-05 / Peter Oberparleiter: implemented --no-sourceview
#   2002-09-05 / Mike Kobler: One of my source file paths includes a "+" in
#                the directory name.  I found that genhtml.pl died when it
#                encountered it. I was able to fix the problem by modifying
#                the string with the escape character before parsing it.
#   2002-10-26 / Peter Oberparleiter: implemented --num-spaces
#   2003-04-07 / Peter Oberparleiter: fixed bug which resulted in an error
#                when trying to combine .info files containing data without
#                a test name
#   2003-04-10 / Peter Oberparleiter: extended fix by Mike to also cover
#                other special characters
#   2003-04-30 / Peter Oberparleiter: made info write to STDERR, not STDOUT
#   2003-07-10 / Peter Oberparleiter: added line checksum support
#   2004-08-09 / Peter Oberparleiter: added configuration file support
#   2005-03-04 / Cal Pierog: added legend to HTML output, fixed coloring of
#                "good coverage" background
#   2006-03-18 / Marcus Boerger: added --custom-intro, --custom-outro and
#                overwrite --no-prefix if --prefix is present
#   2006-03-20 / Peter Oberparleiter: changes to custom_* function (rename
#                to html_prolog/_epilog, minor modifications to implementation),
#                changed prefix/noprefix handling to be consistent with current
#                logic
#   2006-03-20 / Peter Oberparleiter: added --html-extension option
#   2008-07-14 / Tom Zoerner: added --function-coverage command line option;
#                added function table to source file page
#   2008-08-13 / Peter Oberparleiter: modified function coverage
#                implementation (now enabled per default),
#                introduced sorting option (enabled per default)

#use strict;
#use warnings;
#use File::Basename;
#use Getopt::Long;
#use Digest::MD5 qw(md5_base64);

from typing import List, Dict, Optional
import argparse
import sys
import re
from pathlib import Path
import gzip

from .lcov import add_counts
from .lcov import add_fnccount
from .lcov import combine_info_files
from .lcov import brcount_db_get_found_and_hit
from .lcov import combine_info_entries
from .lcov import add_testbrdata
from .lcov import combine_brcount
from .lcov import brcount_db_combine
from .lcov import get_info_entry
from .lcov import set_info_entry
from .lcov import print_overall_rate
from .lcov import get_line_found_and_hit
from .lcov import get_func_found_and_hit
from .lcov import get_branch_found_and_hit
from .lcov import merge_checksums
from .lcov import db_to_brcount
from .lcov import compress_brcount
from .lcov import rate
from .genpng import gen_png
from .util import reverse_dict
from .util import apply_config
from .util import system_no_output, NO_ERROR
from .util import get_date_string
from .util import strip_spaces_in_options
from .util import parse_ignore_errors
from .util import warn, die

# Global constants
tool_name    = Path(__file__).stem
our $title   = "LCOV - code coverage report"
lcov_version = "LCOV version " #+ `${abs_path(dirname($0))}/get_version.sh --full`
lcov_url     = "http://ltp.sourceforge.net/coverage/lcov.php"

# Specify coverage rate default precision
options.default_precision = 1
# Specify coverage rate limits (in %) for classifying file entries
# HI:   options.hi_limit <= rate <= 100             graph color: green
# MED: options.med_limit <= rate < options.hi_limit graph color: orange
# LO:         0  <= rate < options.med_limit        graph color: red
# For line coverage/all coverage types if not specified
options.hi_limit:  int = 90
options.med_limit: int = 75
# For function coverage
options.fn_hi_limit:  Optional[int] = None
options.fn_med_limit: Optional[int] = None
# For branch coverage
options.br_hi_limit:  Optional[int] = None
options.br_med_limit: Optional[int] = None
# Width of overview image
options.overview_width = 80
# Resolution of overview navigation: this number specifies the maximum
# difference in lines between the position a user selected from the overview
# and the position the source code window is scrolled to.
options.nav_resolution = 4
# Clicking a line in the overview image should show the source code view
# at a position a bit further up so that the requested line is not the first
# line in the window. This number specifies that offset in lines.
options.nav_offset = 10
# Width for line coverage information in the source code view
options.line_field_width = 12
# Width for branch coverage information in the source code view
options.br_field_width = 16

# Clicking on a function name should show the source code at a position
# a few lines before the first line of code of that function. This number
# specifies that offset in lines.
func_offset = 2

overview_title = "top level"

# Internal Constants

# Header types
HDR_DIR      = 0
HDR_FILE     = 1
HDR_SOURCE   = 2
HDR_TESTDESC = 3
HDR_FUNC     = 4

# Sort types
SORT_FILE   = 0
SORT_LINE   = 1
SORT_FUNC   = 2
SORT_BRANCH = 3

# Fileview heading types
HEAD_NO_DETAIL     = 1
HEAD_DETAIL_HIDDEN = 2
HEAD_DETAIL_SHOWN  = 3

# Additional offsets used when converting branch coverage data to HTML
BR_LEN   = 3
BR_OPEN  = 4
BR_CLOSE = 5

# Branch data combination types
from .lcov import BR_SUB
from .lcov import BR_ADD

# Block value used for unnamed blocks
UNNAMED_BLOCK_MARKER = vec(pack('b*', 1 x 32), 0, 32)

# Error classes which users may specify to ignore during processing
ERROR_SOURCE = 0
ERROR_ID = {
    "source": ERROR_SOURCE,
}

# Global variables & initialization
info_data: Dict[str, ???] = {}  # Hash containing all data from .info file
our @opt_dir_prefix;    # Array of prefixes to remove from all sub directories
our @dir_prefix;
test_description: Dict[str, str] = {}  # Hash containing test descriptions if available
our $date = get_date_string()

args.info_filenames: List[Path] = [] # List of .info files to use as data source
args.test_title: Optional[str] = None  # Title for output as written to each page header
our $output_directory;    # Name of directory in which to store output
args.base_filename: Optional[Path] = None  # Optional name of file containing baseline data
our $desc_filename;    # Name of file containing test descriptions
options.css_filename: Optional[Path] = None  # Optional name of external stylesheet file to use
args.quiet: bool = False  # If set, suppress information messages
args.help:  bool = False  # Help option flag
args.version: bool = False  # Version option flag
options.show_details: bool = False  # If set, generate detailed directory view
options.no_prefix:    bool = False  # If set, do not remove filename prefix
options.fn_coverage:     Optionsl[bool] = None  # If set, generate function coverage statistics
options.no_fn_coverage:  Optionsl[bool] = None  # Disable fn_coverage
options.br_coverage:     Optionsl[bool] = None  # If set, generate branch coverage statistics
options.no_br_coverage:  Optionsl[bool] = None  # Disable br_coverage
options.sort:    bool = True   # If set, provide directory listings with sorted entries
options.no_sort: bool = False  # Disable sort
args.frames: Optional[bool] = None  # If set, use frames for source code view
options.keep_descriptions: bool = False  # If set, do not remove unused test case descriptions
options.no_sourceview: bool = False  # If set, do not create a source code view for each file
options.highlight: Optional[bool] = None  # If set, highlight lines covered by converted data only
options.legend: bool = False  # If set, include legend in output
options.tab_size: int = 8  # Number of spaces to use in place of tab
our $config;        # Configuration file contents
options.html_prolog_file: Optional[Path] = None  # Custom HTML prolog file (up to and including <body>)
options.html_epilog_file: Optional[Path] = None  # Custom HTML epilog file (from </body> onwards)
html_prolog: Optional[str] = None  # Actual HTML prolog
html_epilog: Optional[str] = None  # Actual HTML epilog
options.html_ext:  str  = "html"   # Extension for generated HTML files
options.html_gzip: bool = False    # Compress with gzip
options.demangle_cpp = False  # Demangle C++ function names
options.demangle_cpp_tool:   str = "c++filt"  # Default demangler for C++ function names
options.demangle_cpp_params: str = ""         # Extra parameters for demangling
args.ignore_errors:     List[str] = []    # Ignore certain error classes during processing
ignore: Dict[int, bool] = {}  # List of errors to ignore (array)
args.config_file: Optional[Path] = None  # User-specified configuration file location
args.rc:          Dict[str, str] = {}
options.missed;    # List/sort lines by missed counts
options.dark_mode: bool = False  # Use dark mode palette or normal
options.charset: str = "UTF-8"    # Default charset for HTML pages
options.lcov_function_coverage: bool = True
options.lcov_branch_coverage:   bool = False
options.desc_html:              bool = False  # lcovrc: genhtml_desc_html

fileview_sortnames = ("", "-sort-l", "-sort-f", "-sort-b")
our @rate_name = ("Lo", "Med", "Hi")
our @rate_png  = ("ruby.png", "amber.png", "emerald.png")

html_templates_dir: Path = Path(__file__)/"html"

cwd = Path.cwd()  # Current working directory

#
# Code entry point
#

# Check command line for a configuration file name
Getopt::Long::Configure("pass_through", "no_auto_abbrev")
GetOptions("config-file=s" => \Path(args.config_file),
           "rc=s%"         => \args.rc)
Getopt::Long::Configure("default")

# Remove spaces around rc options
args.rc = strip_spaces_in_options(args.rc)
# Read configuration file if available
$config = read_lcov_config_file(args.config_file)

if $config or args.rc:
{
    # Copy configuration file and --rc values to variables
    apply_config({
        "genhtml_css_file"            => \Path(options.css_filename),
        "genhtml_hi_limit"            => \options.hi_limit,
        "genhtml_med_limit"           => \options.med_limit,
        "genhtml_line_field_width"    => \options.line_field_width,
        "genhtml_overview_width"      => \options.overview_width,
        "genhtml_nav_resolution"      => \options.nav_resolution,
        "genhtml_nav_offset"          => \options.nav_offset,
        "genhtml_keep_descriptions"   => \options.keep_descriptions,
        "genhtml_no_prefix"           => \options.no_prefix,
        "genhtml_no_source"           => \options.no_sourceview,
        "genhtml_num_spaces"          => \options.tab_size,
        "genhtml_highlight"           => \options.highlight,
        "genhtml_legend"              => \options.legend,
        "genhtml_html_prolog"         => \Path(options.html_prolog_file),
        "genhtml_html_epilog"         => \Path(options.html_epilog_file),
        "genhtml_html_extension"      => \options.html_ext,
        "genhtml_html_gzip"           => \options.html_gzip,
        "genhtml_precision"           => \options.default_precision,
        "genhtml_function_hi_limit"   => \options.fn_hi_limit,
        "genhtml_function_med_limit"  => \options.fn_med_limit,
        "genhtml_branch_hi_limit"     => \options.br_hi_limit,
        "genhtml_branch_med_limit"    => \options.br_med_limit,
        "genhtml_branch_field_width"  => \options.br_field_width,
        "genhtml_sort"                => \options.sort,
        "genhtml_charset"             => \options.charset,
        "genhtml_desc_html"           => \options.desc_html,
        "genhtml_demangle_cpp"        => \options.demangle_cpp,
        "genhtml_demangle_cpp_tool"   => \options.demangle_cpp_tool,
        "genhtml_demangle_cpp_params" => \options.demangle_cpp_params,
        "genhtml_dark_mode"           => \options.dark_mode,
        "genhtml_missed"              => \options.missed,
        "genhtml_function_coverage"   => \options.fn_coverage,
        "genhtml_branch_coverage"     => \options.br_coverage,
        "lcov_function_coverage"      => \options.lcov_function_coverage,
        "lcov_branch_coverage"        => \options.lcov_branch_coverage,
        });
}

# Copy related values if not specified
if options.fn_hi_limit  is None: options.fn_hi_limit  = options.hi_limit
if options.fn_med_limit is None: options.fn_med_limit = options.med_limit
if options.br_hi_limit  is None: options.br_hi_limit  = options.hi_limit
if options.br_med_limit is None: options.br_med_limit = options.med_limit
if options.fn_coverage  is None: options.fn_coverage  = options.lcov_function_coverage
if options.br_coverage  is None: options.br_coverage  = options.lcov_branch_coverage

# Parse command line options
if (!GetOptions(
        "output-directory|o=s" => \$output_directory,
        "title|t=s"            => \args.test_title,
        "description-file|d=s" => \$desc_filename,
        "keep-descriptions|k"  => \options.keep_descriptions,
        "css-file|c=s"         => \Path(options.css_filename),
        "baseline-file|b=s"    => \Path(args.base_filename),
        "prefix|p=s"           => \@opt_dir_prefix,
        "num-spaces=i"         => \options.tab_size,
        "no-prefix"            => \options.no_prefix,
        "no-sourceview"        => \options.no_sourceview,
        "show-details|s"       => \options.show_details,
        "frames|f"             => \args.frames,
        "highlight"            => \options.highlight,
        "legend"               => \options.legend,
        "quiet|q"              => \args.quiet,
        "help|h|?"             => \args.help,
        "version|v"            => \args.version,
        "html-prolog=s"        => \Path(options.html_prolog_file),
        "html-epilog=s"        => \Path(options.html_epilog_file),
        "html-extension=s"     => \options.html_ext,
        "html-gzip"            => \options.html_gzip,
        "function-coverage"    => \options.fn_coverage,
        "no-function-coverage" => \options.no_fn_coverage,
        "branch-coverage"      => \options.br_coverage,
        "no-branch-coverage"   => \options.no_br_coverage,
        "sort"                 => \options.sort,
        "no-sort"              => \options.no_sort,
        "demangle-cpp"         => \options.demangle_cpp,
        "ignore-errors=s"      => \args.ignore_errors,
        "config-file=s"        => \Path(args.config_file),
        "rc=s%"                => \args.rc,
        "precision=i"          => \options.default_precision,
        "missed"               => \options.missed,
        "dark-mode"            => \options.dark_mode,
        )):
    print(f"Use {tool_name} --help to get usage information", file=sys.stderr)
    sys.exit(1)

# Merge options
if options.no_fn_coverage:
    options.fn_coverage = False
if options.no_br_coverage:
    options.br_coverage = False
if options.no_sort:
    options.sort = False

args.info_filenames = [Path(fname) for fname in @ARGV]

# Check for help option
if args.help:
    print_usage(sys.stdout)
    sys.exit(0)

# Check for version option
if args.version:
    print(f"{tool_name}: {lcov_version}")
    sys.exit(0)

# Determine which errors the user wants us to ignore
parse_ignore_errors(args.ignore_errors, ignore)
# Split the list of prefixes if needed
parse_dir_prefix(@opt_dir_prefix)

# Check for info filename
if not args.info_filenames:
    die("No filename specified\n"
        f"Use {tool_name} --help to get usage information")

# Generate a title if none is specified
if not args.test_title:
    if len(args.info_filenames) == 1:
        # Only one filename specified, use it as title
        args.test_title = basename(args.info_filenames[0])
    else:
        # More than one filename specified, used default title
        args.test_title = "unnamed"

# Make sure css_filename is an absolute path (in case we're changing
# directories)
if options.css_filename is not None:
    if not (str(options.css_filename) =~ /^\/(.*)$/):
        options.css_filename = cwd/options.css_filename

# Make sure tab_size is within valid range
if options.tab_size < 1:
    print(f"ERROR: invalid number of spaces specified: {options.tab_size}!",
          file=sys.stderr)
    sys.exit(1)

# Get HTML prolog and epilog
html_prolog = get_html_prolog(options.html_prolog_file or None)
html_epilog = get_html_epilog(options.html_epilog_file or None)

# Issue a warning if --no-sourceview is enabled together with --frames
if options.no_sourceview and args.frames is not None:
    warn("WARNING: option --frames disabled because --no-sourceview "
         "was specified!")
    args.frames = None

# Issue a warning if --no-prefix is enabled together with --prefix
if options.no_prefix and @dir_prefix:
    warn("WARNING: option --prefix disabled because --no-prefix was "
         "specified!")
    @dir_prefix = None

fileview_sortlist: List[int] = [SORT_FILE]
funcview_sortlist: List[int] = [SORT_FILE]
if options.sort:
    fileview_sortlist.append(SORT_LINE)
    if options.fn_coverage:
        fileview_sortlist.append(SORT_FUNC)
    if options.br_coverage:
        fileview_sortlist.append(SORT_BRANCH)
    funcview_sortlist.append(SORT_LINE)

# Ensure that the c++filt tool is available when using --demangle-cpp
if options.demangle_cpp:
    if system_no_output(3, options.demangle_cpp_tool, "--version")[0] != NO_ERROR:
        die(f"ERROR: could not find {options.demangle_cpp_tool} tool needed for "
            "--demangle-cpp")

# Make sure precision is within valid range
if not (1 <= options.default_precision <= 4):
    die("ERROR: specified precision is out of range (1 to 4)")

# Make sure output_directory exists, create it if necessary
if $output_directory:
    create_sub_dir(Path($output_directory), exist_ok=True)

# Do something
gen_html()

sys.exit(0)


def print_usage(fhandle):
    """Print usage information."""
    global tool_name, lcov_url
    print(f"""\
Usage: {tool_name} [OPTIONS] INFOFILE(S)

Create HTML output for coverage data found in INFOFILE. Note that INFOFILE
may also be a list of filenames.

Misc:
  -h, --help                        Print this help, then exit
  -v, --version                     Print version number, then exit
  -q, --quiet                       Do not print progress messages
      --config-file FILENAME        Specify configuration file location
      --rc SETTING=VALUE            Override configuration file setting
      --ignore-errors ERRORS        Continue after ERRORS (source)

Operation:
  -o, --output-directory OUTDIR     Write HTML output to OUTDIR
  -s, --show-details                Generate detailed directory view
  -d, --description-file DESCFILE   Read test case descriptions from DESCFILE
  -k, --keep-descriptions           Do not remove unused test descriptions
  -b, --baseline-file BASEFILE      Use BASEFILE as baseline file
  -p, --prefix PREFIX               Remove PREFIX from all directory names
      --no-prefix                   Do not remove prefix from directory names
      --(no-)function-coverage      Enable (disable) function coverage display
      --(no-)branch-coverage        Enable (disable) branch coverage display

HTML output:
  -f, --frames                      Use HTML frames for source code view
  -t, --title TITLE                 Display TITLE in header of all pages
  -c, --css-file CSSFILE            Use external style sheet file CSSFILE
      --no-source                   Do not create source code view
      --num-spaces NUM              Replace tabs with NUM spaces in source view
      --highlight                   Highlight lines with converted-only data
      --legend                      Include color legend in HTML output
      --html-prolog FILE            Use FILE as HTML prolog for generated pages
      --html-epilog FILE            Use FILE as HTML epilog for generated pages
      --html-extension EXT          Use EXT as filename extension for pages
      --html-gzip                   Use gzip to compress HTML
      --(no-)sort                   Enable (disable) sorted coverage views
      --demangle-cpp                Demangle C++ function names
      --precision NUM               Set precision of coverage rate
      --missed                      Show miss counts as negative numbers
      --dark-mode                   Use the dark-mode CSS

For more information see: {lcov_url}""", file=fhandle)

# NOK
def gen_html():
    """Generate a set of HTML pages from contents of .info file INFO_FILENAME.
    Files will be written to the current directory. If provided, test case
    descriptions will be read from .tests file TEST_FILENAME and included
    in ouput.

    Die on error.
    """
    global options
    global args
    global info_data
    global test_description
    global fileview_sortnames
    global fileview_sortlist

    try:
        # Read in all specified .info files
        for fname in args.info_filenames:
            current = read_info_file(fname)
            # Combine current with info_data
            info_data = combine_info_files(info_data, current)

        info("Found %d entries.", len(info_data))

        # Read and apply baseline data if specified
        if args.base_filename:
            # Read baseline file
            info(f"Reading baseline file {base_filename}")
            base_data = read_info_file(args.base_filename)
            info("Found %d entries.", len(base_data))
            # Apply baseline
            info("Subtracting baseline data.")
            info_data = apply_baseline(info_data, base_data)

        dir_list: List[str] = get_dir_list(info_data.keys())

        if options.no_prefix:
            # User requested that we leave filenames alone
            info("User asked not to remove filename prefix")
        elif not @dir_prefix:
            # Get prefix common to most directories in list
            prefix = get_prefix(1, info_data.keys())
            if prefix:
                info(f"Found common filename prefix \"{prefix}\"")
                $dir_prefix[0] = prefix
            else:
                info("No common filename prefix found!")
                options.no_prefix = True
        else:
            msg = "Using user-specified filename prefix "
            for $i in (0 .. $#dir_prefix):
                $dir_prefix[$i] =~ s/\/+$//;
                unless 0 == $i: msg += ", "
                msg += "\"" . $dir_prefix[$i] . "\"";
            info(msg)

        # Read in test description file if specified
        if $desc_filename:
            info(f"Reading test description file $desc_filename")
            test_description = read_testfile(Path($desc_filename))
            # Remove test descriptions which are not referenced
            # from info_data if user didn't tell us otherwise
            if not options.keep_descriptions:
                remove_unused_descriptions()

        # Change to output directory if specified
        if $output_directory:
            try:
                os.chdir($output_directory)
            except:
                die("ERROR: cannot change to directory $output_directory!")

        info("Writing .css and .png files.")
        write_css_file()
        write_png_files()

        if options.html_gzip:
            info("Writing .htaccess file.")
            write_htaccess_file()

        info("Generating output.")

        # Process each subdirectory and collect overview information
        overview: Dict[???, ???] = {}
        total_ln_found = 0
        total_ln_hit   = 0
        total_fn_found = 0
        total_fn_hit   = 0
        total_br_found = 0
        total_br_hit   = 0
        for dir_name in dir_list:

            (ln_found, ln_hit,
             fn_found, fn_hit,
             br_found, br_hit) = process_dir(dir_name)

            # Handle files in root directory gracefully
            if dir_name == "": dir_name = "root"
            # Remove prefix if applicable
            if not options.no_prefix and @dir_prefix:
                # Match directory names beginning with one of @dir_prefix
                dir_name = apply_prefix(dir_name, @dir_prefix)

            # Generate name for directory overview HTML page
            link_name = dir_name[1:] if re.match(r"^/(.*)$", dir_name) else dir_name
            link_name += f"/index.{options.html_ext}"

            overview[dir_name] = [ln_found, ln_hit,
                                  fn_found, fn_hit,
                                  br_found, br_hit,
                                  link_name,
                                  get_rate(ln_found, ln_hit),
                                  get_rate(fn_found, fn_hit),
                                  get_rate(br_found, br_hit)]
            total_ln_found += ln_found
            total_ln_hit   += ln_hit
            total_fn_found += fn_found
            total_fn_hit   += fn_hit
            total_br_found += br_found
            total_br_hit   += br_hit

        # Generate overview page
        info("Writing directory view page.")

        # Create sorted pages
        for sort_type in fileview_sortlist:
            write_dir_page(fileview_sortnames[sort_type],
                           Path("."), Path(""), args.test_title, None,
                           total_ln_found, total_ln_hit,
                           total_fn_found, total_fn_hit,
                           total_br_found, total_br_hit,
                           \%overview,
                           {}, {}, {},
                           0, sort_type)

        # Check if there are any test case descriptions to write out
        if test_description:
            info("Writing test case description file.")
            write_description_file(test_description,
                                   total_ln_found, total_ln_hit,
                                   total_fn_found, total_fn_hit,
                                   total_br_found, total_br_hit);

        print_overall_rate(1,           total_ln_found, total_ln_hit,
                           fn_coverage, total_fn_found, total_fn_hit,
                           br_coverage, total_br_found, total_br_hit,
                           title="Overall coverage rate:")
    finally:
        os.chdir(cwd)


def html_create(filename: Path) -> object:
    """ """
    global options
    if options.html_gzip:
        try:
            html_handle = gzip.open(str(filename), "wt") as:
        except:
            die(f"ERROR: cannot open {filename} for writing (gzip)!")
    else:
        try:
            html_handle = filename.open("wt")
        except:
            die(f"ERROR: cannot open {filename} for writing!")
    return html_handle

# NOK
def write_dir_page($name,
                   rel_dir: Path, $base_dir, title: str, trunc_dir: Optionl[Path],
                   total_ln_found: int, total_ln_hit: int,
                   total_fn_found: int, total_fn_hit: int,
                   total_br_found: int, total_br_hit: int,
                   overview: Dict[str, List],
                   $testhash, $testfnchash, $testbrhash,
                   header_type: int, sort_type: int):
    """ """
    global options

    if trunc_dir is None:
        trunc_dir = Path("")
    if trunc_dir != Path(""):
        title += " - "

    # Generate directory overview page including details
    with html_create(rel_dir/f"index{name}.{options.html_ext}") as html_handle:

        write_html_prolog(html_handle, Path($base_dir),
                          f"LCOV - {title}{trunc_dir}")

        write_header(html_handle, header_type,
                     trunc_dir, rel_dir,
                     total_ln_found, total_ln_hit,
                     total_fn_found, total_fn_hit,
                     total_br_found, total_br_hit,
                     sort_type)

        write_file_table(html_handle, Path($base_dir), overview,
                         $testhash, $testfnchash, $testbrhash,
                         header_type != HDR_DIR, sort_type);

        write_html_epilog(html_handle, Path($base_dir))

# NOK
def process_dir(abs_dir):
    # process_dir(dir_name)
    """ """
    global options
    global args
    global info_data
    global fileview_sortlist

    my %overview;
    my $ln_found;
    my $ln_hit;
    my $fn_found;
    my $fn_hit;
    my $br_found;
    my $br_hit;
    my $base_name;
    my $extension;
    my @sort_list;

    rel_dir = $abs_dir
    # Remove prefix if applicable
    if not options.no_prefix:
        # Match directory name beginning with one of @dir_prefix
        rel_dir = apply_prefix(rel_dir, @dir_prefix)

    trunc_dir = rel_dir
    # Remove leading /
    if rel_dir =~ /^\/(.*)$/:
        rel_dir = rel_dir[1:]

    # Handle files in root directory gracefully
    if rel_dir   == "": rel_dir   = "root"
    if trunc_dir == "": trunc_dir = "root"

    base_dir: str = get_relative_base_path(rel_dir)

    create_sub_dir(Path(rel_dir))

    # Match filenames which specify files in this directory, not including
    # sub-directories

    %testhash    = {}
    %testfnchash = {}
    %testbrhash  = {}

    total_ln_found = 0
    total_ln_hit   = 0
    total_fn_found = 0
    total_fn_hit   = 0
    total_br_found = 0
    total_br_hit   = 0

    for filename in (grep(/^\Q$abs_dir\E\/[^\/]*$/,keys(%info_data))):
        my $page_link;
        my $func_link;

        (ln_found, ln_hit,
         fn_found, fn_hit,
         br_found, br_hit,
         testdata, testfncdata, testbrdata) = process_file(trunc_dir, $rel_dir, filename)

        $base_name = basename($filename)

        if options.no_sourceview:
            $page_link = "";
        elif args.frames:
            # Link to frameset page
            $page_link = f"$base_name.gcov.frameset.{options.html_ext}"
        else:
            # Link directory to source code view page
            $page_link = f"$base_name.gcov.{options.html_ext}"
        $overview[base_name] = [ln_found, ln_hit,
                                fn_found, fn_hit,
                                br_found, br_hit,
                                $page_link,
                                get_rate(ln_found, ln_hit),
                                get_rate(fn_found, fn_hit),
                                get_rate(br_found, br_hit)]

        $testhash[base_name]    = testdata
        $testfnchash[base_name] = testfncdata
        $testbrhash[base_name]  = testbrdata

        total_ln_found += ln_found
        total_ln_hit   += ln_hit
        total_fn_found += fn_found
        total_fn_hit   += fn_hit
        total_br_found += br_found
        total_br_hit   += br_hit

    # Create sorted pages
    for sort_type in fileview_sortlist:
        # Generate directory overview page (without details)
        write_dir_page(fileview_sortnames[sort_type],
                       Path($rel_dir), Path($base_dir), args.test_title, Path(trunc_dir),
                       total_ln_found, total_ln_hit,
                       total_fn_found, total_fn_hit,
                       total_br_found, total_br_hit,
                       \%overview,
                       {}, {}, {},
                       1, sort_type)
        if not options.show_details: continue
        # Generate directory overview page including details
        write_dir_page("-detail" + fileview_sortnames[sort_type],
                       Path($rel_dir), Path($base_dir), args.test_title, Path(trunc_dir),
                       total_ln_found, total_ln_hit,
                       total_fn_found, total_fn_hit,
                       total_br_found, total_br_hit,
                       \%overview,
                       \%testhash, \%testfnchash, \%testbrhash,
                       1, sort_type)

    # Calculate resulting line counts
    return (total_ln_found, total_ln_hit,
            total_fn_found, total_fn_hit,
            total_br_found, total_br_hit)

# NOK
def process_file($trunc_dir, $rel_dir, $filename) -> Tuple ???:

    global options
    global args
    global info_data
    global funcview_sortlist

    info("Processing file {}".format(apply_prefix(filename, @dir_prefix)))

    base_name: str = basename($filename)
    base_dir:  str = get_relative_base_path($rel_dir)

    my $testcount;
    my @source;

    (testdata, sumcount, funcdata, checkdata,
     testfncdata, sumfnccount,
     testbrdata,  sumbrcount,
     ln_found, ln_hit,
     fn_found, fn_hit,
     br_found, br_hit) = get_info_entry(info_data[filename])

    # Return after this point in case user asked us not to generate
    # source code view
    if options.no_sourceview:
        return (ln_found, ln_hit,
                fn_found, fn_hit,
                br_found, br_hit,
                testdata, testfncdata, testbrdata)

    converted: Set[int] = get_converted_lines(testdata)

    page_title = f"LCOV - args.test_title - {trunc_dir}/$base_name"

    # Generate source code view for this file
    with html_create(Path(f"$rel_dir/$base_name.gcov.{options.html_ext}")) as html_handle:

        write_html_prolog(html_handle, Path(base_dir), page_title)

        write_header(html_handle, 2,
                     Path(f"{trunc_dir}/$base_name"), Path(f"$rel_dir/$base_name"),
                     ln_found, ln_hit,
                     fn_found, fn_hit,
                     br_found, br_hit,
                     SORT_FILE)

        @source = write_source(html_handle, Path($filename),
                               sumcount, checkdata, converted,
                               funcdata, sumbrcount)

        write_html_epilog(html_handle, Path(base_dir), True)

    if options.fn_coverage:
        # Create function tables
        for sort_type in funcview_sortlist:
            write_function_page(Path($base_dir), Path($rel_dir), Path(trunc_dir),
                                base_name, args.test_title,
                                ln_found, ln_hit,
                                fn_found, fn_hit,
                                br_found, br_hit,
                                $funcdata,   $sumcount,
                                testfncdata, sumfnccount,
                                testbrdata,  sumbrcount,
                                sort_type)

    # Additional files are needed in case of frame output
    if not args.frames:
        return (ln_found, ln_hit,
                fn_found, fn_hit,
                br_found, br_hit,
                testdata, testfncdata, testbrdata)

    # Create overview png file
    gen_png("$rel_dir/$base_name.gcov.png",
            options.dark_mode, options.overview_width, options.tab_size, @source)

    # Create frameset page
    with html_create(Path(f"$rel_dir/$base_name.gcov.frameset.{options.html_ext}")) as html_handle:
        write_frameset(html_handle, Path($base_dir), base_name, page_title)

    # Write overview frame
    with html_create(Path(f"$rel_dir/$base_name.gcov.overview.{options.html_ext}")) as html_handle:
        write_overview(html_handle, Path($base_dir), base_name, page_title, len(@source))

    return (ln_found, ln_hit,
            fn_found, fn_hit,
            br_found, br_hit,
            testdata, testfncdata, testbrdata)

# NOK
def write_function_page(base_dir: Path, rel_dir: Path, trunc_dir: Path,
                        $base_name, title: str,
                        $ln_found, $ln_hit,
                        $fn_found, $fn_hit,
                        $br_found, $br_hit,
                        funcdata:    Dict[str, ???], sumcount:    Dict[???, ???],
                        testfncdata: Dict[???, ???], sumfnccount: Dict[str, int],
                        testbrdata:  Dict[???, ???], sumbrcount:  Dict[???, ???],
                        sort_type: int):
    """ """
    global options

    # Generate function table for this file
    if sort_type == SORT_FILE:
        filename = rel_dir/f"$base_name.func.{options.html_ext}"
    else:
        filename = rel_dir/f"$base_name.func-sort-c.{options.html_ext}"

    with html_create(filename) as html_handle:

        write_html_prolog(html_handle, base_dir,
                          f"LCOV - {title} - {trunc_dir/base_name} - functions")

        write_header(html_handle, 4,
                     trunc_dir/base_name, rel_dir/base_name,
                     ln_found, ln_hit,
                     fn_found, fn_hit,
                     br_found, br_hit,
                     sort_type)

        write_function_table(html_handle,
                             f"$base_name.gcov.{options.html_ext}",
                             funcdata,    sumcount,
                             testfncdata, sumfnccount,
                             testbrdata,  sumbrcount,
                             $base_name, base_dir, sort_type)

        write_html_epilog(html_handle, base_dir, True)

# NOK
def write_function_table(html_handle,
                         $source,
                         funcdata:    Dict[str, ???], sumcount:    Dict[???, ???],
                         testfncdata: Dict[???, ???], sumfnccount: Dict[str, int],
                         testbrdata:  Dict[???, ???], sumbrcount:  Dict[???, ???],
                         $name, base_dir: Path, sort_type: int):
    # (..., source_file, base_name, ...)
    """Write an HTML table listing all functions in a source file, including
    also function call counts and line coverages inside of each function.

    Die on error.
    """
    global options
    global html_templates_dir
    global func_offset

    # Get HTML code for headings
    func_code  = funcview_get_func_code($name,  base_dir, sort_type)
    count_code = funcview_get_count_code($name, base_dir, sort_type)

    html = (html_templates_dir/"").read_text()
    write_html(html_handle, <<END_OF_HTML) # NOK
      <center>
      <table width="60%" cellpadding=1 cellspacing=1 border=0>
        <tr><td><br></td></tr>
        <tr>
          <td width="80%" class="tableHead">{func_code}</td>
          <td width="20%" class="tableHead">{count_code}</td>
        </tr>
END_OF_HTML

    # Get demangle translation hash
    demangle: Dict[str, str] = {}
    if options.demangle_cpp:
        demangle = demangle_list(sorted(funcdata.keys()))

    # Get a sorted table
    for func in funcview_get_sorted($funcdata, sumfnccount, sort_type):
        if ! defined($funcdata[func]): continue

        startline = $funcdata[func] - func_offset
        count     = sumfnccount[func]

        # Replace function name with demangled version if available
        name = func
        if name in demangle:
            name = demangle[name]

        # Escape special characters
        name = escape_html(name)

        if startline < 1: startline = 1
        countstyle = "coverFnLo" if count == 0 else "coverFnHi"

        html = (html_templates_dir/"").read_text()
        write_html(html_handle, <<END_OF_HTML) # NOK
        <tr>
              <td class="coverFn"><a href="$source#{startline}">{name}</a></td>
              <td class="{countstyle}">{count}</td>
            </tr>
END_OF_HTML

    html = (html_templates_dir/"").read_text()
    write_html(html_handle, <<END_OF_HTML) # NOK
      </table>
      <br>
      </center>
END_OF_HTML


def get_converted_lines(testdata: Dict[str, Dict[???, ???]]) -> Set[int]: # NOK
    """Return set of line numbers of those lines which were only covered
    in converted data sets.
    """
    converted    = set()
    nonconverted = set()

    # Get a set containing line numbers with positive counts
    # both for converted and original data sets
    for testcase, testcount in testdata.items():
        # Check to see if this is a converted data set
        convset = converted if re.???(r",diff$", testcase) else nonconverted # NOK
        # Add lines with a positive count to set
        for line, count in testcount.items():
            if count > 0:
                convset.add(line)

    result = set()
    # Combine both sets to resulting list
    for line in converted:
        if line not in nonconverted:
            result.add(line)

    return result

# NOK
def read_info_file($tracefile: Path) -> Dict[str, Dict[str, object]]:
    """
    read_info_file(info_filename)

    Read in the contents of the .info file specified by INFO_FILENAME. Data will
    be returned as a reference to a hash containing the following mappings:

    %result: for each filename found in file -> \%data

    %data: "test"    -> \%testdata
           "sum"     -> \%sumcount
           "func"    -> \%funcdata
           "found"   -> $ln_found (number of instrumented lines found in file)
           "hit"     -> $ln_hit (number of executed lines in file)
           "f_found" -> $fn_found (number of instrumented functions found in file)
           "f_hit"   -> $fn_hit (number of executed functions in file)
           "b_found" -> $br_found (number of instrumented branches found in file)
           "b_hit"   -> $br_hit (number of executed branches in file)
           "check"   -> \%checkdata
           "testfnc" -> \%testfncdata
           "sumfnc"  -> \%sumfnccount
           "testbr"  -> \%testbrdata
           "sumbr"   -> \%sumbrcount

    %testdata   : name of test affecting this file -> \%testcount
    %testfncdata: name of test affecting this file -> \%testfnccount
    %testbrdata:  name of test affecting this file -> \%testbrcount

    %testcount   : line number   -> execution count for a single test
    %testfnccount: function name -> execution count for a single test
    %testbrcount : line number   -> branch coverage data for a single test
    %sumcount    : line number   -> execution count for all tests
    %sumfnccount : function name -> execution count for all tests
    %sumbrcount  : line number   -> branch coverage data for all tests
    %funcdata    : function name -> line number
    %checkdata   : line number   -> checksum of source code line
    $brdata      : vector of items: block, branch, taken

    Note that .info file sections referring to the same file and test name
    will automatically be combined by adding all execution counts.

    Note that if INFO_FILENAME ends with ".gz", it is assumed that the file
    is compressed using GZIP. If available, GUNZIP will be used to decompress
    this file.

    Die on error.
    """
    global options

    my %result;            # Resulting hash: file -> data

    my $data;            # Data handle for current entry
    my $testcount;            #       "             "
    my $sumcount;            #       "             "
    my $funcdata;            #       "             "
    my $checkdata;            #       "             "
    my $testfncdata;
    my $testfnccount;
    my $sumfnccount;
    my $testbrdata;
    my $testbrcount;
    my $sumbrcount;
    my $line;            # Current line read from .info file
    my $filename;            # Current filename
    my $count;            # Execution count of current line
    my $negative;            # If set, warn about negative counts
    my $changed_testname;        # If set, warn about changed testname
    my $line_checksum;        # Checksum of current line

    notified_about_relative_paths = False

    info(f"Reading data file {tracefile}")

    # Check if file exists and is readable
    if not os.access(tracefile, os.R_OK):
        die(f"ERROR: cannot read file {tracefile}!")
    # Check if this is really a plain file
    fstatus = Path(tracefile).stat()
    if ! (-f _):
        die(f"ERROR: not a plain file: {tracefile}!")

    # Check for .gz extension
    if $tracefile =~ /\.gz$/:
        # Check for availability of GZIP tool
        if system_no_output(1, "gunzip" ,"-h")[0] != NO_ERROR:
            die("ERROR: gunzip command not available!")

        # Check integrity of compressed file
        if system_no_output(1, "gunzip", "-t", str(tracefile))[0] != NO_ERROR:
            die(f"ERROR: integrity check failed for compressed file {tracefile}!")

        # Open compressed file
        INFO_HANDLE = open("-|", f"gunzip -c '{tracefile}'")
            or die(f"ERROR: cannot start gunzip to decompress file {tracefile}!")
    else:
        # Open decompressed file
        try:
            INFO_HANDLE = Path(tracefile).open("rt")
        except:
            or die(f"ERROR: cannot read file {tracefile}!")

    testname = ""  # Current test name
    with INFO_HANDLE:
        while (<INFO_HANDLE>)
        {
            line = $_.rstrip("\n")

            # Switch statement
            foreach ($line)
            {
                /^TN:([^,]*)(,diff)?/ && do
                {
                    # Test name information found
                    testname = defined($1) ? $1 : "";
                    if testname =~ s/\W/_/g:
                    {
                        $changed_testname = 1;
                    }
                    if (defined($2)):
                        testname += $2

                    last;
                };

                /^[SK]F:(.*)/ && do
                {
                    # Filename information found
                    # Retrieve data for new entry
                    $filename = File::Spec->rel2abs($1, str(cwd))

                    if (!File::Spec->file_name_is_absolute($1) and
                        not notified_about_relative_paths):
                        info(f"Resolved relative source file path \"$1\" with CWD to \"$filename\".")
                        notified_about_relative_paths = True

                    $data = $result[filename]

                    (testdata, $sumcount, $funcdata, $checkdata,
                     testfncdata, $sumfnccount,
                     $testbrdata, $sumbrcount,
                     _, _, _, _, _, _) = get_info_entry($data)

                    if defined($testname):
                        testcount    = testdata[testname]
                        testfnccount = testfncdata[testname]
                        testbrcount  = $testbrdata[testname]
                    else:
                        testcount    = {}
                        testfnccount = {}
                        testbrcount  = {}

                    last;
                };

                /^DA:(\d+),(-?\d+)(,[^,\s]+)?/ && do
                {
                    # Fix negative counts
                    $count = $2 < 0 ? 0 : $2;
                    if ($2 < 0)
                    {
                        $negative = 1;
                    }
                    # Execution count found, add to structure
                    # Add summary counts
                    $sumcount->{$1} += $count;

                    # Add test-specific counts
                    if (defined($testname))
                    {
                        $testcount->{$1} += $count;
                    }

                    # Store line checksum if available
                    if (defined($3))
                    {
                        $line_checksum = substr($3, 1);

                        # Does it match a previous definition
                        if (defined($checkdata->{$1}) and
                            ($checkdata->{$1} != $line_checksum)):
                            die(f"ERROR: checksum mismatch at $filename:$1")

                        $checkdata->{$1} = $line_checksum;
                    }

                    last;
                };

                /^FN:(\d+),([^,]+)/ && do
                {
                    if not options.fn_coverage: last

                    # Function data found, add to structure
                    $funcdata->{$2} = $1;

                    # Also initialize function call data
                    if (!defined($sumfnccount->{$2})) {
                        $sumfnccount->{$2} = 0;
                    }
                    if (defined($testname))
                    {
                        if (!defined($testfnccount->{$2})) {
                            $testfnccount->{$2} = 0;
                        }
                    }

                    last;
                };

                /^FNDA:(\d+),([^,]+)/ && do
                {
                    if not options.fn_coverage: last
                    # Function call count found, add to structure
                    # Add summary counts
                    $sumfnccount->{$2} += $1;

                    # Add test-specific counts
                    if (defined($testname))
                    {
                        $testfnccount->{$2} += $1;
                    }

                    last;
                };

                /^BRDA:(\d+),(\d+),(\d+),(\d+|-)/ && do {
                    # Branch coverage data found
                    my ($line, $block, $branch, $taken) = ($1, $2, $3, $4)

                    if options.br_coverage:
                        if $block == UNNAMED_BLOCK_MARKER: $block = -1
                        $sumbrcount->{$line} .= "$block,$branch,$taken:"

                        # Add test-specific counts
                        if defined($testname):
                            $testbrcount->{$line} .= "$block,$branch,$taken:"

                    last;
                };

                /^end_of_record/ && do
                {
                    # Found end of section marker
                    if $filename:
                        # Store current section data
                        if defined($testname):
                            testdata[testname]    = $testcount;
                            testfncdata[testname] = $testfnccount;
                            testbrdata[testname]  = $testbrcount;

                        set_info_entry($data,
                                       $testdata, $sumcount, $funcdata, $checkdata,
                                       testfncdata, $sumfnccount,
                                       $testbrdata, $sumbrcount)
                        $result[filename] = $data

                        last;
                };

                # default
                last;
            }
        }

    # Calculate hit and found values for lines and functions of each file
    for filename in list(result.keys()):
        data = result[filename]

        (testdata,   sumcount, _, _,
         testfncdata, sumfnccount,
         $testbrdata, sumbrcount,
         _, _, _, _, _, _) = get_info_entry(data)

        # Filter out empty files
        if len(sumcount) == 0:
            del result[filename]
            continue

        # Filter out empty test cases
        for testname in list(keys(%{testdata})):
            if (!defined(testdata[testname]) or
                len(%{testdata[testname]}) == 0):
                delete (testdata[testname])
                delete (testfncdata[testname])

        data["found"] = len(sumcount)
        hitcount = 0
        for $_ in (keys(%{sumcount})):
            if sumcount->{$_} > 0:
                hitcount += 1
        data["hit"] = hitcount

        # Get found/hit values for function call data
        data["f_found"] = len(sumfnccount)
        hitcount = 0
        for $_ in (keys(%{sumfnccount})):
            if sumfnccount->{$_} > 0:
                hitcount += 1
        data["f_hit"] = hitcount

        # Combine branch data for the same branches
        _, data["b_found"], data["b_hit"] = compress_brcount(sumbrcount)
        for brcount in $testbrdata.values():
            compress_brcount(brcount)

    if no result:
        die(f"ERROR: no valid records found in tracefile {tracefile}")
    if $negative:
        warn(f"WARNING: negative counts found in tracefile {tracefile}")
    if $changed_testname:
        warn("WARNING: invalid characters removed from testname in "
             f"tracefile {tracefile}")

    return %result


def get_prefix(min_dir: int, filename_list: List[str]) -> Optional[str]:
    """Search filename_list for a directory prefix which is common to as many
    list entries as possible, so that removing this prefix will minimize the
    sum of the lengths of all resulting shortened filenames while observing
    that no filename has less than min_dir parent directories.
    """
    prefix = {}  # mapping: prefix -> sum of lengths

    # Find list of prefixes
    for current in filename_list:
        while True:
            current = shorten_prefix(current)
            if not current: break
            current += "/"
            # Skip rest if the remaining prefix has already been
            # added to hash
            if current in prefix: break
            # Initialize with 0
            prefix[current] = "0"

    # Remove all prefixes that would cause filenames to have less than
    # the minimum number of parent directories
    for filename in filename_list:
        dir = dirname($filename) # NOK
        for _ in range(min_dir):
            del ($prefix{f"{dir}/"}) # NOK
            dir = shorten_prefix(dir)

    # Check if any prefix remains
    if not prefix:
        return None

    # Calculate sum of lengths for all prefixes
    for current in prefix.keys():
        for filename in filename_list:
            # Add original length
            prefix[current] += len(filename)
            # Check whether prefix matches
            if filename[:len(current) == current:
                # Subtract prefix length for this filename
                prefix[current] -= len(current)

    # Find and return prefix with minimal sum
    current = prefix.keys()[0]
    for pkey, pval in prefix.items():
        if pval < prefix[current]:
            current = pkey

    $current =~ s/\/$// # NOK

    return current


def shorten_prefix(prefix: str, sep: str = "/") -> str:
    """Return PREFIX shortened by last directory component."""
    list = prefix.split(sep)
    if list: list.pop()
    return sep.join(list)


def get_dir_list(filename_list: List[str]) -> List[str]:
    """Return sorted list of directories for each entry in given
    filename_list."""
    result = set()
    for fname in filename_list:
        result.add(shorten_prefix(fname))
    return sorted(result)


def get_relative_base_path(subdir: str) -> str:
    """Return a relative path string which references the base path
    when applied in subdir.

    Example: get_relative_base_path("fs/mm") -> "../../"
    """
    result = ""
    # Make an empty directory path a special case
    if subdir:
        # Add a ../ to result for each / in the directory path + 1
        for _ in range(subdir.count("/") + 1):
            result += "../"
    return result


def read_testfile(test_filename: Path) -> Dict[str, str]:
    """Read in file test_filename which contains test descriptions in the
    format:

      TN:<whitespace><test name>
      TD:<whitespace><test description>

    for each test case. Return a reference to a hash containing a mapping

      test name -> test description.

    Die on error.
    """
    result: Dict[str, str] = {}

    try:
        fhandle = test_filename.open("rt")
    except:
        die(f"ERROR: cannot open {test_filename}!")

    changed_testname = False
    test_name = None
    with fhandle:
        for line in fhandle:
            line = line.rstrip("\n")

            # Match lines beginning with TN:<whitespace(s)>
            match = re.match(r"^TN:\s+(.*?)\s*$", line)
            if match:
                # Store test name for later use
                test_name = match.group(1)
                if (test_name =~ s/\W/_/g): # NOK
                    changed_testname = True
                continue

            # Match lines beginning with TD:<whitespace(s)>
            match = re.match(r"^TD:\s+(.*?)\s*$", line)
            if match:
                if test_name is None:
                    die("ERROR: Found test description without prior "
                        f"test name in {test_filename}:$.")
                if test_name not in result:
                    result[test_name] = ""
                # Check for empty line
                if match.group(1):
                    # Add description to hash
                    result[test_name] += " " + match.group(1)
                else:
                    # Add empty line
                    result[test_name] += "\n\n"
                continue

    if changed_testname:
        warn("WARNING: invalid characters removed from testname "
             f"in descriptions file {test_filename}")

    return result


def escape_html(string: str):
    """Return a copy of STRING in which all occurrences of HTML
    special characters are escaped.
    """
    global options

    if not string:
        return ""

    string = string.replace("&",  "&amp")   # & -> &amp;
    string = string.replace("<",  "&lt")    # < -> &lt;
    string = string.replace(">",  "&gt")    # > -> &gt;
    string = string.replace("\"", "&quot")  # " -> &quot;

    while ($string =~ /^([^\t]*)(\t)/): # NOK
        $replacement = " " * (options.tab_size - (len($1) % options.tab_size)) # NOK
        $string =~ s/^([^\t]*)(\t)/$1$replacement/ # NOK

    string = string.replace("\n",  "<br>")  # \n -> <br>

    return string


def write_description_file(descriptions: Dict[???, ???],
                           ln_found: int, ln_hit: int,
                           fn_found: int, fn_hit: int,
                           br_found: int, br_hit: int):
    #                      total_ln_found, total_ln_hit,
    #                      total_fn_found, total_fn_hit,
    #                      total_br_found, total_br_hit)
    #
    """Write HTML file containing all test case descriptions.
    descriptions is a reference to a dict containing a mapping

      test case name -> test case description

    Die on error.
    """
    global options

    with html_create(Path(f"descriptions.{options.html_ext}")) as html_handle:
        write_html_prolog(html_handle, Path(""),
                          "LCOV - test case descriptions")
        write_header(html_handle, 3,
                     Path(""), Path(""),
                     ln_found, ln_hit,
                     fn_found, fn_hit,
                     br_found, br_hit,
                     SORT_FILE)
        write_test_table_prolog(html_handle,
                                "Test case descriptions - alphabetical list")

        for test_name in sorted(descriptions.keys()):
            desc = descriptions[test_name]
            if not options.desc_html:
                desc = escape_html(desc)
            write_test_table_entry(html_handle, test_name, desc)

        write_test_table_epilog(html_handle)
        write_html_epilog(html_handle, Path(""))


def write_png_files():
    """Create all necessary .png files for the HTML-output
    in the current directory. .png-files are used as bar graphs.

    Die on error.
    """
    global options

    data: Dict[str, object] = {}

    if options.dark_mode:
        data["ruby.png"] = bytearray(
            b"\x89\x50\x4e\x47\x0d\x0a\x1a\x0a\x00"
            b"\x00\x00\x0d\x49\x48\x44\x52\x00\x00"
            b"\x00\x01\x00\x00\x00\x01\x01\x03\x00"
            b"\x00\x00\x25\xdb\x56\xca\x00\x00\x00"
            b"\x06\x50\x4c\x54\x45\x80\x1b\x18\x00"
            b"\x00\x00\x39\x4a\x74\xf4\x00\x00\x00"
            b"\x0a\x49\x44\x41\x54\x08\xd7\x63\x60"
            b"\x00\x00\x00\x02\x00\x01\xe2\x21\xbc"
            b"\x33\x00\x00\x00\x00\x49\x45\x4e\x44"
            b"\xae\x42\x60\x82"
        )
    else:
        data["ruby.png"] = bytearray(
            b"\x89\x50\x4e\x47\x0d\x0a\x1a\x0a\x00"
            b"\x00\x00\x0d\x49\x48\x44\x52\x00\x00"
            b"\x00\x01\x00\x00\x00\x01\x01\x03\x00"
            b"\x00\x00\x25\xdb\x56\xca\x00\x00\x00"
            b"\x07\x74\x49\x4d\x45\x07\xd2\x07\x11"
            b"\x0f\x18\x10\x5d\x57\x34\x6e\x00\x00"
            b"\x00\x09\x70\x48\x59\x73\x00\x00\x0b"
            b"\x12\x00\x00\x0b\x12\x01\xd2\xdd\x7e"
            b"\xfc\x00\x00\x00\x04\x67\x41\x4d\x41"
            b"\x00\x00\xb1\x8f\x0b\xfc\x61\x05\x00"
            b"\x00\x00\x06\x50\x4c\x54\x45\xff\x35"
            b"\x2f\x00\x00\x00\xd0\x33\x9a\x9d\x00"
            b"\x00\x00\x0a\x49\x44\x41\x54\x78\xda"
            b"\x63\x60\x00\x00\x00\x02\x00\x01\xe5"
            b"\x27\xde\xfc\x00\x00\x00\x00\x49\x45"
            b"\x4e\x44\xae\x42\x60\x82"
        )

    if options.dark_mode:
        data["amber.png"] = bytearray(
            b"\x89\x50\x4e\x47\x0d\x0a\x1a\x0a\x00"
            b"\x00\x00\x0d\x49\x48\x44\x52\x00\x00"
            b"\x00\x01\x00\x00\x00\x01\x01\x03\x00"
            b"\x00\x00\x25\xdb\x56\xca\x00\x00\x00"
            b"\x06\x50\x4c\x54\x45\x99\x86\x30\x00"
            b"\x00\x00\x51\x83\x43\xd7\x00\x00\x00"
            b"\x0a\x49\x44\x41\x54\x08\xd7\x63\x60"
            b"\x00\x00\x00\x02\x00\x01\xe2\x21\xbc"
            b"\x33\x00\x00\x00\x00\x49\x45\x4e\x44"
            b"\xae\x42\x60\x82"
        )
    else:
        data["amber.png"] = bytearray(
            b"\x89\x50\x4e\x47\x0d\x0a\x1a\x0a\x00"
            b"\x00\x00\x0d\x49\x48\x44\x52\x00\x00"
            b"\x00\x01\x00\x00\x00\x01\x01\x03\x00"
            b"\x00\x00\x25\xdb\x56\xca\x00\x00\x00"
            b"\x07\x74\x49\x4d\x45\x07\xd2\x07\x11"
            b"\x0f\x28\x04\x98\xcb\xd6\xe0\x00\x00"
            b"\x00\x09\x70\x48\x59\x73\x00\x00\x0b"
            b"\x12\x00\x00\x0b\x12\x01\xd2\xdd\x7e"
            b"\xfc\x00\x00\x00\x04\x67\x41\x4d\x41"
            b"\x00\x00\xb1\x8f\x0b\xfc\x61\x05\x00"
            b"\x00\x00\x06\x50\x4c\x54\x45\xff\xe0"
            b"\x50\x00\x00\x00\xa2\x7a\xda\x7e\x00"
            b"\x00\x00\x0a\x49\x44\x41\x54\x78\xda"
            b"\x63\x60\x00\x00\x00\x02\x00\x01\xe5"
            b"\x27\xde\xfc\x00\x00\x00\x00\x49\x45"
            b"\x4e\x44\xae\x42\x60\x82"
        )

    if options.dark_mode:
        data["emerald.png"] = bytearray(
            b"\x89\x50\x4e\x47\x0d\x0a\x1a\x0a\x00"
            b"\x00\x00\x0d\x49\x48\x44\x52\x00\x00"
            b"\x00\x01\x00\x00\x00\x01\x01\x03\x00"
            b"\x00\x00\x25\xdb\x56\xca\x00\x00\x00"
            b"\x06\x50\x4c\x54\x45\x00\x66\x00\x0a"
            b"\x0a\x0a\xa4\xb8\xbf\x60\x00\x00\x00"
            b"\x0a\x49\x44\x41\x54\x08\xd7\x63\x60"
            b"\x00\x00\x00\x02\x00\x01\xe2\x21\xbc"
            b"\x33\x00\x00\x00\x00\x49\x45\x4e\x44"
            b"\xae\x42\x60\x82"
        )
    else:
        data["emerald.png"] = bytearray(
            b"\x89\x50\x4e\x47\x0d\x0a\x1a\x0a\x00"
            b"\x00\x00\x0d\x49\x48\x44\x52\x00\x00"
            b"\x00\x01\x00\x00\x00\x01\x01\x03\x00"
            b"\x00\x00\x25\xdb\x56\xca\x00\x00\x00"
            b"\x07\x74\x49\x4d\x45\x07\xd2\x07\x11"
            b"\x0f\x22\x2b\xc9\xf5\x03\x33\x00\x00"
            b"\x00\x09\x70\x48\x59\x73\x00\x00\x0b"
            b"\x12\x00\x00\x0b\x12\x01\xd2\xdd\x7e"
            b"\xfc\x00\x00\x00\x04\x67\x41\x4d\x41"
            b"\x00\x00\xb1\x8f\x0b\xfc\x61\x05\x00"
            b"\x00\x00\x06\x50\x4c\x54\x45\x1b\xea"
            b"\x59\x0a\x0a\x0a\x0f\xba\x50\x83\x00"
            b"\x00\x00\x0a\x49\x44\x41\x54\x78\xda"
            b"\x63\x60\x00\x00\x00\x02\x00\x01\xe5"
            b"\x27\xde\xfc\x00\x00\x00\x00\x49\x45"
            b"\x4e\x44\xae\x42\x60\x82"
        )

    if options.dark_mode:
        data["snow.png"] = bytearray(
            b"\x89\x50\x4e\x47\x0d\x0a\x1a\x0a\x00"
            b"\x00\x00\x0d\x49\x48\x44\x52\x00\x00"
            b"\x00\x01\x00\x00\x00\x01\x01\x03\x00"
            b"\x00\x00\x25\xdb\x56\xca\x00\x00\x00"
            b"\x06\x50\x4c\x54\x45\xdd\xdd\xdd\x00"
            b"\x00\x00\xae\x9c\x6c\x92\x00\x00\x00"
            b"\x0a\x49\x44\x41\x54\x08\xd7\x63\x60"
            b"\x00\x00\x00\x02\x00\x01\xe2\x21\xbc"
            b"\x33\x00\x00\x00\x00\x49\x45\x4e\x44"
            b"\xae\x42\x60\x82"
        )
    else:
        data["snow.png"] = bytearray(
            b"\x89\x50\x4e\x47\x0d\x0a\x1a\x0a\x00"
            b"\x00\x00\x0d\x49\x48\x44\x52\x00\x00"
            b"\x00\x01\x00\x00\x00\x01\x01\x03\x00"
            b"\x00\x00\x25\xdb\x56\xca\x00\x00\x00"
            b"\x07\x74\x49\x4d\x45\x07\xd2\x07\x11"
            b"\x0f\x1e\x1d\x75\xbc\xef\x55\x00\x00"
            b"\x00\x09\x70\x48\x59\x73\x00\x00\x0b"
            b"\x12\x00\x00\x0b\x12\x01\xd2\xdd\x7e"
            b"\xfc\x00\x00\x00\x04\x67\x41\x4d\x41"
            b"\x00\x00\xb1\x8f\x0b\xfc\x61\x05\x00"
            b"\x00\x00\x06\x50\x4c\x54\x45\xff\xff"
            b"\xff\x00\x00\x00\x55\xc2\xd3\x7e\x00"
            b"\x00\x00\x0a\x49\x44\x41\x54\x78\xda"
            b"\x63\x60\x00\x00\x00\x02\x00\x01\xe5"
            b"\x27\xde\xfc\x00\x00\x00\x00\x49\x45"
            b"\x4e\x44\xae\x42\x60\x82"
        )

    data["glass.png"] = bytearray(
        b"\x89\x50\x4e\x47\x0d\x0a\x1a\x0a\x00\x00"
        b"\x00\x0d\x49\x48\x44\x52\x00\x00\x00\x01"
        b"\x00\x00\x00\x01\x01\x03\x00\x00\x00\x25"
        b"\xdb\x56\xca\x00\x00\x00\x04\x67\x41\x4d"
        b"\x41\x00\x00\xb1\x8f\x0b\xfc\x61\x05\x00"
        b"\x00\x00\x06\x50\x4c\x54\x45\xff\xff\xff"
        b"\x00\x00\x00\x55\xc2\xd3\x7e\x00\x00\x00"
        b"\x01\x74\x52\x4e\x53\x00\x40\xe6\xd8\x66"
        b"\x00\x00\x00\x01\x62\x4b\x47\x44\x00\x88"
        b"\x05\x1d\x48\x00\x00\x00\x09\x70\x48\x59"
        b"\x73\x00\x00\x0b\x12\x00\x00\x0b\x12\x01"
        b"\xd2\xdd\x7e\xfc\x00\x00\x00\x07\x74\x49"
        b"\x4d\x45\x07\xd2\x07\x13\x0f\x08\x19\xc4"
        b"\x40\x56\x10\x00\x00\x00\x0a\x49\x44\x41"
        b"\x54\x78\x9c\x63\x60\x00\x00\x00\x02\x00"
        b"\x01\x48\xaf\xa4\x71\x00\x00\x00\x00\x49"
        b"\x45\x4e\x44\xae\x42\x60\x82"
    )

    if options.sort;
        if options.dark_mode:
            data["updown.png"] = bytearray(
                b"\x89\x50\x4e\x47\x0d\x0a\x1a\x0a\x00"
                b"\x00\x00\x0d\x49\x48\x44\x52\x00\x00"
                b"\x00\x0a\x00\x00\x00\x0e\x08\x06\x00"
                b"\x00\x00\x16\xa3\x8d\xab\x00\x00\x00"
                b"\x43\x49\x44\x41\x54\x28\xcf\x63\x60"
                b"\x40\x03\x77\xef\xde\xfd\x7f\xf7\xee"
                b"\xdd\xff\xe8\xe2\x8c\xe8\x8a\x90\xf9"
                b"\xca\xca\xca\x8c\x18\x0a\xb1\x99\x82"
                b"\xac\x98\x11\x9f\x22\x64\xc5\x8c\x84"
                b"\x14\xc1\x00\x13\xc3\x80\x01\xea\xbb"
                b"\x91\xf8\xe0\x21\x29\xc0\x89\x89\x42"
                b"\x06\x62\x13\x05\x00\xe1\xd3\x2d\x91"
                b"\x93\x15\xa4\xb2\x00\x00\x00\x00\x49"
                b"\x45\x4e\x44\xae\x42\x60\x82"
            )
        else:
            data["updown.png"] = bytearray(
                b"\x89\x50\x4e\x47\x0d\x0a\x1a\x0a\x00"
                b"\x00\x00\x0d\x49\x48\x44\x52\x00\x00"
                b"\x00\x0a\x00\x00\x00\x0e\x08\x06\x00"
                b"\x00\x00\x16\xa3\x8d\xab\x00\x00\x00"
                b"\x3c\x49\x44\x41\x54\x28\xcf\x63\x60"
                b"\x40\x03\xff\xa1\x00\x5d\x9c\x11\x5d"
                b"\x11\x8a\x24\x23\x23\x23\x86\x42\x6c"
                b"\xa6\x20\x2b\x66\xc4\xa7\x08\x59\x31"
                b"\x23\x21\x45\x30\xc0\xc4\x30\x60\x80"
                b"\xfa\x6e\x24\x3e\x78\x48\x0a\x70\x62"
                b"\xa2\x90\x81\xd8\x44\x01\x00\xe9\x5c"
                b"\x2f\xf5\xe2\x9d\x0f\xf9\x00\x00\x00"
                b"\x00\x49\x45\x4e\x44\xae\x42\x60\x82"
            )

    for fname, content in data.items():
        try:
            fhandle = Path(fname).open("wb")
        except:
            die(f"ERROR: cannot create {fname}!")
        with fhandle:
            fhandle.write(content)


def write_htaccess_file():
    """ """
    global html_templates_dir
    try:
        fhandle = Path(".htaccess").open("wt")
    except:
        die("ERROR: cannot open .htaccess for writing!")
    htaccess = (html_templates_dir/".htaccess").read_text()
    with fhandle
        print(htaccess, end="", file=fhandle)


def write_css_file():
    """Write the cascading style sheet file gcov.css to the current directory.
    This file defines basic layout attributes of all generated HTML pages.
    """
    global options
    global html_templates_dir

    # Check for a specified external style sheet file
    if options.css_filename is not None:
        # Simply copy that file
        try:
            shutil.copy2(str(options.css_filename), "gcov.css")
        except:
            die(f"ERROR: cannot copy file {css_filename}!")
        return

    css_data = (html_templates_dir/"genhtml.css").read_text(encoding="utf-8")
    # Remove leading tab from all lines
    css_data =~ s/^\t//gm;, css_data) # NOK

    if options.dark_mode:
        palette = {
            "COLOR_00": "e4e4e4",
            "COLOR_01": "58a6ff",
            "COLOR_02": "8b949e",
            "COLOR_03": "3b4c71",
            "COLOR_04": "006600",
            "COLOR_05": "4b6648",
            "COLOR_06": "495366",
            "COLOR_07": "143e4f",
            "COLOR_08": "1c1e23",
            "COLOR_09": "202020",
            "COLOR_10": "801b18",
            "COLOR_11": "66001a",
            "COLOR_12": "772d16",
            "COLOR_13": "796a25",
            "COLOR_14": "000000",
            "COLOR_15": "58a6ff",
            "COLOR_16": "eeeeee",
        }
    else:
        palette = {
            "COLOR_00": "000000",
            "COLOR_01": "00cb40",
            "COLOR_02": "284fa8",
            "COLOR_03": "6688d4",
            "COLOR_04": "a7fc9d",
            "COLOR_05": "b5f7af",
            "COLOR_06": "b8d0ff",
            "COLOR_07": "cad7fe",
            "COLOR_08": "dae7fe",
            "COLOR_09": "efe383",
            "COLOR_10": "ff0000",
            "COLOR_11": "ff0040",
            "COLOR_12": "ff6230",
            "COLOR_13": "ffea20",
            "COLOR_14": "ffffff",
            "COLOR_15": "284fa8",
            "COLOR_16": "ffffff",
        }
    # Apply palette
    for key, val in palette.items():
        css_data = re.sub(rf"{key}", rf"{val}"gm, css_data) # NOK

    try:
        fhandle = Path("gcov.css").open("wt")
    except:
        die("ERROR: cannot open gcov.css for writing!")
    with fhandle:
        print(css_data, end="", file=fhandle)


def classify_rate(found: int, hit: int, med_limit: int, hi_limit: int) -> int:
    """Return 0 for low rate, 1 for medium rate and 2 for high rate."""
    if found == 0:
        return 2
    rate = rate(hit, found)
    if rate < med_limit:
        return 0
    elif rate < hi_limit:
        return 1
    return 2


def write_html(html_handle, html: str):
    """Write out HTML_CODE to html_handle while removing a leading tabulator mark
    in each line of HTML_CODE.

    Remove leading tab from all lines
    """
    html = re.sub(s/^\t//gm;, "", html) # NOK
    try:
        print(html, end="", file=html_handle)
    except Exception as exc:
        die(f"ERROR: cannot write HTML data ({exc})")


def write_html_prolog(html_handle, base_dir: Path, pagetitle: str):
    """Write an HTML prolog common to all HTML files to FILEHANDLE. PAGETITLE
    will be used as HTML page title. BASE_DIR contains a relative path which
    points to the base directory.
    """
    global html_prolog

    basedir = base_dir.as_posix()

    prolog = html_prolog
    prolog = re.sub(rf"\@pagetitle\@", rf"{pagetitle}", prolog)
    prolog = re.sub(rf"\@basedir\@",   rf"{basedir}",   prolog)

    write_html(html_handle, prolog)


def write_html_epilog(html_handle, base_dir: Path, break_frames: bool = False):
    """Write HTML page footer to html_handle. break_frames should be set
    when this page is embedded in a frameset, clicking the url link will
    then break this frameset.
    """
    global lcov_version, lcov_url
    global html_templates_dir

    basedir    = base_dir.as_posix()
    break_code = ' target="_parent"' if break_frames is not None else ""

    html = (html_templates_dir/"").read_text()
    write_html(html_handle, <<END_OF_HTML) # NOK
      <table width="100%" border=0 cellspacing=0 cellpadding=0>
        <tr><td class="ruler"><img src="{basedir}/glass.png" width=3 height=3 alt=""></td></tr>
        <tr><td class="versionInfo">Generated by: <a href="{lcov_url}"{break_code}>{lcov_version}</a></td></tr>
      </table>
      <br>
END_OF_HTML

    epilog = html_epilog
    epilog = re.sub(rf"\@basedir\@", rf"{basedir}", epilog)

    write_html(html_handle, epilog)


def write_header_prolog(html_handle, base_dir):
    """Write beginning of page header HTML code."""
    global html_templates_dir
    html = (html_templates_dir/"header_prolog.html").read_text()
    write_html(html_handle, html)


def write_header_epilog(html_handle, base_dir)
    """Write end of page header HTML code."""
    global html_templates_dir
    html = (html_templates_dir/"header_epilog.html").read_text()
    write_html(html_handle, html)


def write_header_line(handle, content: List[???]): # NOK
    """Write a header line with the specified table contents."""
    write_html(handle, '          <tr>\n')

    for entry in content:
        width, klass, text, colspan = entry
        width   = f' width="{width}"'     if width   is not None else ""
        klass   = f' class="{klass}"'     if klass   is not None else ""
        colspan = f' colspan="{colspan}"' if colspan is not None else ""
        if text is None: text = ""
        write_html(handle, f'            <td{width}{klass}{colspan}>{text}</td>\n')

    write_html(handle, '          </tr>\n')


def write_test_table_prolog(html_handle, table_heading)
    """Write heading for test case description table."""
    global html_templates_dir
    html = (html_templates_dir/"test_table_prolog.html").read_text()
    write_html(html_handle, html)


def write_test_table_epilog(html_handle):
    """Write end of test description table HTML code."""
    global html_templates_dir
    html = (html_templates_dir/"test_table_epilog.html").read_text()
    write_html(html_handle, html)


def write_test_table_entry(html_handle, test_name: str, test_description: str):
    """Write entry for the test table."""
    global html_templates_dir
    html = (html_templates_dir/"").read_text()
    write_html(html_handle, <<END_OF_HTML) # NOK
          <dt>{test_name}<a name="{test_name}">&nbsp;</a></dt>
          <dd>test_description<br><br></dd>
END_OF_HTML


def fmt_centered(width: int, text: str) -> str:
    """ """
    w0 = len(text)
    w1 = int((width - w0) / 2) if width > w0 else 0
    w2 = width - w0 - w1       if width > w0 else 0

    return " " * w1 + text + " " * w2


def get_block_len(block: List[???]) -> int: # NOK
    """Calculate total text length of all branches in a block of branches."""
    return sum((branch[BR_LEN] for branch in block), 0)

# NOK
def write_frameset(html_handle, base_dir: Path, basename: str, pagetitle: str):
    """ """
    global options
    global html_templates_dir

    basedir     = base_dir.as_posix()
    frame_width = options.overview_width + 40

    html = (html_templates_dir/"").read_text()
    write_html(html_handle, <<END_OF_HTML) # NOK
    <!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Frameset//EN">

    <html lang="en">

    <head>
      <meta http-equiv="Content-Type" content=f"text/html; charset={options.charset}">
      <title>{pagetitle}</title>
      <link rel="stylesheet" type="text/css" href="{basedir}/gcov.css">
    </head>

    <frameset cols="{frame_width},*">
      <frame src=f"{basename}.gcov.overview.{options.html_ext}" name="overview">
      <frame src=f"{basename}.gcov.{options.html_ext}" name="source">
      <noframes>
        <center>Frames not supported by your browser!<br></center>
      </noframes>
    </frameset>

    </html>
END_OF_HTML

# NOK
def write_overview(html_handle, base_dir: Path, basename, pagetitle: str, lines: int   *$$$$):
    """ """
    global options
    global html_templates_dir

    basedir  = base_dir.as_posix()
    max_line = lines - 1

    html = (html_templates_dir/"").read_text()
    write_html(html_handle, <<END_OF_HTML) # NOK
    <!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN">

    <html lang="en">

    <head>
      <title>{pagetitle}</title>
      <meta http-equiv="Content-Type" content=f"text/html; charset={options.charset}">
      <link rel="stylesheet" type="text/css" href="{basedir}/gcov.css">
    </head>

    <body>
      <map name="overview">
END_OF_HTML

    # Make offset the next higher multiple of options.nav_resolution
    offset = (options.nav_offset + options.nav_resolution - 1) / options.nav_resolution
    offset = sprintf("%d", offset ) * options.nav_resolution

    # Create image map for overview image
    for index in range(1, lines + 1, options.nav_resolution):
        # Enforce nav_offset
        write_overview_line(html_handle, basename, index, max(1, index - offset))

    html = (html_templates_dir/"").read_text()
    write_html(html_handle, <<END_OF_HTML) # NOK
      </map>

      <center>
      <a href="{basename}.gcov.{options.html_ext}#top" target="source">Top</a><br><br>
      <img src="{basename}.gcov.png" width={options.overview_width} height={max_line} alt="Overview" border=0 usemap="#overview">
      </center>
    </body>
    </html>
END_OF_HTML


def write_overview_line(html_handle, base_name: str, line: int, link_no: int):
    """ """
    global options
    global html_templates_dir

    x1 = 0
    y1 = line - 1
    x2 = options.overview_width - 1
    y2 = y1 + options.nav_resolution - 1
    basename = base_name
    link = str(link_no)

    html = (html_templates_dir/"").read_text()
    write_html(html_handle, <<END_OF_HTML) # NOK
        <area shape="rect" coords="{x1},{y1},{x2},{y2}" href="{basename}.gcov.{options.html_ext}#{link}" target="source" alt="overview">
END_OF_HTML

# NOK
def write_header(html_handle, header_type: int,
                 $trunc_name,  $rel_filename,
                 $ln_found, $ln_hit,
                 $fn_found, $fn_hit,
                 $br_found, $br_hit,
                 sort_type: int):
    """
    write_header(html_handle, type, trunc_file_name, rel_file_name, ln_found,
                 ln_hit, funcs_found, funcs_hit, sort_type)

    Write a complete standard page header. TYPE may be (0, 1, 2, 3, 4)
    corresponding to (directory view header, file view header, source view
    header, test case description header, function view header)
    """
    global options
    global args
    global test_description
    global overview_title

    my $base_dir;
    my $view;
    my $base_name;
    my $style;
    my $rate;
    my $num_rows;
    my $i;

    esc_trunc_name = escape_html($trunc_name)

    $base_name = basename($rel_filename);

    # Prepare text for "current view" field
    if header_type == HDR_DIR:
        # Main overview
        $base_dir = ""
        $view = overview_title
    elif header_type == HDR_FILE:
        # Directory overview
        $base_dir = get_relative_base_path($rel_filename);
        $view = ("<a href=\"$base_dir" + f"index.{options.html_ext}\">"
                 f"{overview_title}</a> - {esc_trunc_name}")
    elif header_type == HDR_SOURCE or header_type == HDR_FUNC:
        # File view
        dir_name      = dirname($rel_filename)
        esc_base_name = escape_html($base_name)
        esc_dir_name  = escape_html($dir_name)

        $base_dir = get_relative_base_path($dir_name);
        if args.frames:
            # Need to break frameset when clicking any of these
            # links
            $view = ("<a href=\"$base_dir" + f"index.{options.html_ext}\" ".
                     f"target=\"_parent\">{overview_title}</a> - ".
                     f"<a href=\"index.{options.html_ext}\" target=\"_parent\">".
                     "$esc_dir_name</a> - $esc_base_name")
        else:
            $view = ("<a href=\"$base_dir" + f"index.{options.html_ext}\">".
                     f"{overview_title}</a> - ".
                     f"<a href=\"index.{options.html_ext}\">".
                     "$esc_dir_name</a> - $esc_base_name")

        # Add function suffix
        if options.fn_coverage:
            $view += "<span style=\"font-size: 80%;\">"
            if header_type == HDR_SOURCE:
                if options.sort:
                    $view += f" (source / <a href=\"$base_name.func-sort-c.{options.html_ext}\">functions</a>)"
                else:
                    $view += f" (source / <a href=\"$base_name.func.{options.html_ext}\">functions</a>)"
            elif header_type == HDR_FUNC:
                $view += f" (<a href=\"$base_name.gcov.{options.html_ext}\">source</a> / functions)"
            $view += "</span>"

    elif header_type == HDR_TESTDESC:
        # Test description header
        $base_dir = ""
        $view = ("<a href=\"$base_dir" + f"index.{options.html_ext}\">"
                 f"{overview_title}</a> - test case descriptions")

    # Prepare text for "test" field
    test = escape_html(args.test_title)

    # Append link to test description page if available
    if test_description and header_type != HDR_TESTDESC:
        if args.frames and (header_type == HDR_SOURCE or header_type == HDR_FUNC):
            # Need to break frameset when clicking this link
            test += (" ( <span style=\"font-size:80%;\">".
                      "<a href=\"$base_dir".
                      f"descriptions.{options.html_ext}\" target=\"_parent\">".
                      "view descriptions</a></span> )")
        else:
            test += (" ( <span style=\"font-size:80%;\">".
                      "<a href=\"$base_dir".
                      f"descriptions.{options.html_ext}\">".
                      "view descriptions</a></span> )")

    # Write header
    write_header_prolog(html_handle, $base_dir)

    row_left  = []
    row_right = []

    # Left row
    row_left.append([[ "10%", "headerItem", "Current view:" ],
                     [ "35%", "headerValue", $view ]]);
    row_left.append([[_, "headerItem", "Test:"],
                     [_, "headerValue", test]]);
    row_left.append([[_, "headerItem", "Date:"],
                     [_, "headerValue", $date]]);

    # Right row
    if options.legend and (header_type == HDR_SOURCE or header_type == HDR_FUNC):
        $text = <<END_OF_HTML;
            Lines:
            <span class="coverLegendCov">hit</span>
            <span class="coverLegendNoCov">not hit</span>
END_OF_HTML
        if options.br_coverage:
            $text += <<END_OF_HTML;
            | Branches:
            <span class="coverLegendCov">+</span> taken
            <span class="coverLegendNoCov">-</span> not taken
            <span class="coverLegendNoCov">#</span> not executed
END_OF_HTML
        row_left.append([[_, "headerItem", "Legend:"],
                         [_, "headerValueLeg", $text]])
    elif options.legend and header_type != HDR_TESTDESC:
        $text = <<END_OF_HTML;
        Rating:
            <span class="coverLegendCovLo" title="Coverage rates below {options.med_limit} % are classified as low">low: &lt; {options.med_limit} %</span>
            <span class="coverLegendCovMed" title="Coverage rates between {options.med_limit} % and {options.hi_limit} % are classified as medium">medium: &gt;= {options.med_limit} %</span>
            <span class="coverLegendCovHi" title="Coverage rates of {options.hi_limit} % and more are classified as high">high: &gt;= {options.hi_limit} %</span>
END_OF_HTML
        row_left.append([[_, "headerItem", "Legend:"],
                         [_, "headerValueLeg", $text]])
    if header_type == HDR_TESTDESC:
        row_right.append([[ "55%" ]]);
    else:
        row_right.append([["15%", _, _ ],
                          ["10%", "headerCovTableHead", "Hit" ],
                          ["10%", "headerCovTableHead", "Total" ],
                          ["15%", "headerCovTableHead", "Coverage"]])
    # Line coverage
    $style = $rate_name[classify_rate($ln_found, $ln_hit,
                                      options.med_limit, options.hi_limit)]
    $rate = rate($ln_hit, $ln_found, " %")
    if header_type != HDR_TESTDESC;
        row_right.append([[_, "headerItem", "Lines:"],
                          [_, "headerCovTableEntry", $ln_hit],
                          [_, "headerCovTableEntry", $ln_found],
                          [_, "headerCovTableEntry$style", $rate]])
    # Function coverage
    if options.fn_coverage:
        $style = $rate_name[classify_rate($fn_found, $fn_hit,
                                          options.fn_med_limit, options.fn_hi_limit)];
        $rate = rate($fn_hit, $fn_found, " %")
        if header_type != HDR_TESTDESC;
            row_right.append([[_, "headerItem", "Functions:"],
                              [_, "headerCovTableEntry", $fn_hit],
                              [_, "headerCovTableEntry", $fn_found],
                              [_, "headerCovTableEntry$style", $rate]])
    # Branch coverage
    if options.br_coverage:
        $style = $rate_name[classify_rate($br_found, $br_hit,
                                          options.br_med_limit, options.br_hi_limit)];
        $rate = rate($br_hit, $br_found, " %")
        if header_type != HDR_TESTDESC:
            row_right.append([[_, "headerItem", "Branches:"],
                              [_, "headerCovTableEntry", $br_hit],
                              [_, "headerCovTableEntry", $br_found],
                              [_, "headerCovTableEntry$style", $rate]])

    # Print rows
    $num_rows = max(len(row_left), len(row_right))
    for ($i = 0; $i < $num_rows; $i++):
        my $left  = $row_left[$i];
        my $right = $row_right[$i];
        if ! defined($left):
            $left = [[_, _, _],
                     [_, _, _]]
        if (!defined($right)):
            $right = [];
        write_header_line(html_handle,
                          @{$left},
                          [ $i == 0 ? "5%" : _, _, _],
                          @{$right})

    # Fourth line
    write_header_epilog(html_handle, $base_dir)


def get_sort_code(sort_link: Optional[str], alt: str, base_dir: Path):
    """ """
    basedir = base_dir.as_posix()
    if sort_link is not None:
        png        = "updown.png"
        link_start = f'<a href="{sort_link}">'
        link_end   = "</a>"
    else:
        png        = "glass.png"
        link_start = ""
        link_end   = ""

    return (' '
            f'<span class="tableHeadSort">{link_start}'
            f'<img src="{basedir}/{png}" width=10 height=14'
            f' alt="{alt}" title="{alt}" border=0>{link_end}'
            f'</span>')

# NOK
def write_file_table(html_handle,
                     base_dir: Path,
                     overview: Dict[str, List],
                     testhash,
                     testfnchash,
                     testbrhash,
                     fileview: bool, sort_type: int):
    """Write a complete file table. OVERVIEW is a reference to a hash
    containing the following mapping:

      filename -> "ln_found,ln_hit,funcs_found,funcs_hit,page_link,
                   func_link"

    TESTHASH is a reference to the following hash:

      filename -> \%testdata
      %testdata: name of test affecting this file -> \%testcount
      %testcount: line number -> execution count for a single test

    Heading of first column is "Filename" if FILEVIEW is true,
    "Directory name" otherwise.
    """
    global options
    global test_description

    my %affecting_tests;

    # Determine HTML code for column headings
    if $base_dir != "" and options.show_details:
        detailed = bool($testhash)
        view_type      = HEAD_DETAIL_HIDDEN if detailed else HEAD_NO_DETAIL
        line_view_type = HEAD_DETAIL_SHOWN  if detailed else HEAD_DETAIL_HIDDEN
    else:
        view_type = line_view_type = HEAD_NO_DETAIL

    file_code = get_file_code(view_type,
                              "Filename" if fileview else "Directory",
                              options.sort and sort_type != SORT_FILE,
                              base_dir)
    line_code = get_line_code(line_view_type, sort_type,
                              "Line Coverage",
                              options.sort and sort_type != SORT_LINE,
                              base_dir)
    func_code = get_func_code(view_type,
                              "Functions",
                              options.sort and sort_type != SORT_FUNC,
                              base_dir)
    bran_code = get_bran_code(view_type,
                              "Branches",
                              options.sort and sort_type != SORT_BRANCH,
                              base_dir)

    head_columns = []
    push(head_columns, [ line_code, 3])
    if options.fn_coverage:
        push(head_columns, [func_code, 2])
    if options.br_coverage:
        push(head_columns, [bran_code, 2])

    write_file_table_prolog(html_handle, file_code, head_columns)

    for filename in get_sorted_keys(overview, sort_type):

        testdata    = $testhash[filename]
        testfncdata = $testfnchash[filename]
        testbrdata  = $testbrhash[filename]

        (ln_found, ln_hit,
         fn_found, fn_hit,
         br_found, br_hit,
         page_link,
         _, _, _) = overview[filename]

        columns = []
        # Line coverage
        columns.append((ln_found, ln_hit, options.med_limit, options.hi_limit, True))
        # Function coverage
        if options.fn_coverage:
            columns.append((fn_found, fn_hit, options.fn_med_limit, options.fn_hi_limit, False))
        # Branch coverage
        if options.br_coverage:
            columns.append((br_found, br_hit, options.br_med_limit, options.br_hi_limit, False))
        write_file_table_entry(html_handle, base_dir, filename, page_link, columns)

        # Check whether we should write test specific coverage
        # as well
        if not testdata or not options.show_details: continue

        # Filter out those tests that actually affect this file
        %affecting_tests = get_affecting_tests(testdata, testfncdata, testbrdata)

        # Does any of the tests affect this file at all?
        if not %affecting_tests: continue

        for testname in keys(%affecting_tests):
            ln_found, ln_hit, fn_found, fn_hit, br_found, br_hit = $affecting_tests[testname].split(",")

            # Insert link to description of available
            if $test_description[testname]:
                testname = (f'<a href=\"${base_dir}descriptions.{options.html_ext}#{testname}\">'
                            f'{testname}</a>')

            results = []
            results.append((ln_found, ln_hit))
            if options.fn_coverage: results.append((fn_found, fn_hit))
            if options.br_coverage: results.append((br_found, br_hit))
            write_file_table_detail_entry(html_handle, testname, results)

    write_file_table_epilog(html_handle)


def get_file_code(view_type: int, text: str, sort_button: bool, base_dir: Path):
    """ """
    global options

    result = text
    sort_link = None
    if sort_button:
        if view_type == HEAD_NO_DETAIL:
            sort_link = f"index.{options.html_ext}"
        else:
            sort_link = f"index-detail.{options.html_ext}"
    result += get_sort_code(sort_link, "Sort by name", base_dir)

    return result


def get_line_code(view_type: int, sort_type: int, text: str, sort_button: bool, base_dir: Path):
    """ """
    global options
    global fileview_sortnames

    result = text
    sort_link = None
    if view_type == HEAD_NO_DETAIL:
        # Just text
        if sort_button:
            sort_link = f"index-sort-l.{options.html_ext}"
    elif view_type == HEAD_DETAIL_HIDDEN:
        # Text + link to detail view
        sort_name = fileview_sortnames[sort_type]
        result += (' ( <a class="detail"'
                   f' href="index-detail{sort_name}.{options.html_ext}">'
                   'show details</a> )')
        if sort_button:
            sort_link = f"index-sort-l.{options.html_ext}"
    else:
        # Text + link to standard view
        sort_name = fileview_sortnames[sort_type]
        result += (' ( <a class="detail"'
                   f' href="index{sort_name}.{options.html_ext}">'
                   'hide details</a> )')
        if sort_button:
            sort_link = f"index-detail-sort-l.{options.html_ext}"
    # Add sort button
    result += get_sort_code(sort_link, "Sort by line coverage", base_dir)

    return result


def get_func_code(view_type: int, text: str, sort_button: bool, base_dir: Path):
    """ """
    global options

    result = text
    sort_link = None
    if sort_button:
        if view_type == HEAD_NO_DETAIL:
            sort_link = f"index-sort-f.{options.html_ext}"
        else:
            sort_link = f"index-detail-sort-f.{options.html_ext}"
    result += get_sort_code(sort_link, "Sort by function coverage", base_dir)

    return result


def get_bran_code(view_type: int, text: str, sort_button: bool, base_dir: Path):
    """ """
    global options

    result = text
    sort_link = None
    if sort_button:
        if view_type == HEAD_NO_DETAIL:
            sort_link = f"index-sort-b.{options.html_ext}"
        else:
            sort_link = f"index-detail-sort-b.{options.html_ext}"
    result += get_sort_code(sort_link, "Sort by branch coverage", base_dir)

    return result


def write_file_table_prolog(html_handle, file_heading: str, columns: List[Tuple[str, int]]):
    """Write heading for file table."""
    global html_templates_dir

    if   len(columns) == 1: width = 20
    elif len(columns) == 2: width = 10
    elif len(columns) >  2: width = 8
    else:                   width = 0

    num_columns = 0
    for _, cols in columns:
        num_columns += cols

    file_width = 100 - num_columns * width

    # Table definition
    html = (html_templates_dir/"").read_text()
    write_html(html_handle, <<END_OF_HTML) # NOK
      <center>
      <table width="80%" cellpadding=1 cellspacing=1 border=0>

        <tr>
          <td width="{file_width}%"><br></td>
END_OF_HTML

    # Empty first row
    for _, cols in columns:
        for _ in range(cols):
            html = (html_templates_dir/"").read_text()
            write_html(html_handle, <<END_OF_HTML) # NOK
          <td width="{width}%"></td>
END_OF_HTML

    # Next row
    html = (html_templates_dir/"").read_text()
    write_html(html_handle, <<END_OF_HTML) # NOK
        </tr>

        <tr>
          <td class="tableHead">{file_heading}</td>
END_OF_HTML

    # Heading row
    for heading, cols in columns:
        colspan = f" colspan={cols}" if cols > 1 else ""

        html = (html_templates_dir/"").read_text()
        write_html(html_handle, <<END_OF_HTML) # NOK
          <td class="tableHead"{colspan}>{heading}</td>
END_OF_HTML

    html = (html_templates_dir/"").read_text()
    write_html(html_handle, <<END_OF_HTML) # NOK
        </tr>
END_OF_HTML


def write_file_table_epilog(html_handle):
    """Write end of file table HTML code."""
    global html_templates_dir
    html = (html_templates_dir/"file_table_epilog.html").read_text()
    write_html(html_handle, html)

# NOK
def write_file_table_entry(html_handle, base_dir: Path, filename: str,
                           page_link: Optional[str],
                           entries: List[Tuple[???, int, int, int, bool]]):
    """Write an entry of the file table."""
    global options
    global html_templates_dir

    esc_filename = escape_html(filename)
    # Add link to source if provided
    if page_link isn not None and page_link != "":
        file_code = f'<a href="{page_link}">{esc_filename}</a>'
    else:
        file_code = esc_filename

    # First column: filename
    html = (html_templates_dir/"").read_text()
    write_html(html_handle, <<END_OF_HTML) # NOK
        <tr>
          <td class="coverFile">{file_code}</td>
END_OF_HTML

    # Columns as defined
    for found, hit, med_limit, hi_limit, graph in entries:

        # Generate bar graph if requested
        if graph:
            bar_graph = get_bar_graph_code(base_dir, found, hit)

            html = (html_templates_dir/"").read_text()
            write_html(html_handle, <<END_OF_HTML) # NOK
          <td class="coverBar" align="center">
            {bar_graph}
          </td>
END_OF_HTML

        # Get rate color and text
        if found == 0:
            rate  = "-"
            klass = "Hi"
        else:
            rate  = rate(hit, $found, "&nbsp;%")
            klass = $rate_name[classify_rate($found, hit, med_limit, hi_limit)]

        if options.missed:
            # Show negative number of items without coverage
            hit = -(found - hit)

        html = (html_templates_dir/"").read_text()
        write_html(html_handle, <<END_OF_HTML) # NOK
          <td class="coverPer{klass}">{rate}</td>
          <td class="coverNum{klass}">{hit} / {found}</td>
END_OF_HTML

    # End of row
    html = (html_templates_dir/"").read_text()
    write_html(html_handle, <<END_OF_HTML) # NOK
        </tr>
END_OF_HTML


def write_file_table_detail_entry(html_handle, test_name: str,
                                  entries: List[Tuple[int, int]]):
    """Write entry for detail section in file table."""
    global html_templates_dir

    if test_name == "":
        test_name = '<span style="font-style:italic">&lt;unnamed&gt;</span>'
    else:
        match = re.match(r"^(.*),diff$")
        if match:
            test_name = match.group(1) + " (converted)"

    # Testname
    html = (html_templates_dir/"").read_text()
    write_html(html_handle, <<END_OF_HTML) # NOK
        <tr>
          <td class="testName" colspan=2>{test_name}</td>
END_OF_HTML
    # Test data
    for found, hit in entries:
        rate_val = rate(hit, found, "&nbsp;%")
        html = (html_templates_dir/"").read_text()
        write_html(html_handle, <<END_OF_HTML) # NOK
          <td class="testPer">{rate_val}</td>
          <td class="testNum">{hit}&nbsp;/&nbsp;{found}</td>
END_OF_HTML

    html = (html_templates_dir/"").read_text()
    write_html(html_handle, <<END_OF_HTML) # NOK
        </tr>

END_OF_HTML

# NOK
def get_bar_graph_code(base_dir: Path, found, hit: int) -> str:
    """Return a string containing HTML code which implements a bar graph
    display for a coverage rate of cover_hit * 100 / cover_found.
    """
    global options

    # Check number of instrumented lines
    if found == 0:
        return ""

    basedir   = base_dir.as_posix()
    alt       = rate(hit, found, "%")
    width     = rate(hit, found, None, 0)
    remainder = 100 - width
    # Decide which .png file to use
    png_name  = $rate_png[classify_rate(found, hit,
                                        options.med_limit, options.hi_limit)] # NOK
    if width == 0:
        # Zero coverage
        graph_code = (<<END_OF_HTML) # NOK
            <table border=0 cellspacing=0 cellpadding=1>
              <tr><td class="coverBarOutline">
                <img src="{basedir}/snow.png" width=100 height=10 alt="{alt}">
              </td></tr>
            </table>
END_OF_HTML
    elif width == 100:
        # Full coverage
        graph_code = (<<END_OF_HTML) # NOK
        <table border=0 cellspacing=0 cellpadding=1>
          <tr><td class="coverBarOutline">
            <img src="{basedir}/{png_name}" width=100 height=10 alt="{alt}">
          </td></tr>
        </table>
END_OF_HTML
    else:
        # Positive coverage
        graph_code = (<<END_OF_HTML) # NOK
        <table border=0 cellspacing=0 cellpadding=1>
          <tr><td class="coverBarOutline">
            <img src="{basedir}/{png_name}" width={width} height=10 alt="{alt}">
            <img src="{basedir}/snow.png" width={remainder} height=10 alt="{alt}">
          </td></tr>
        </table>
END_OF_HTML

    # Remove leading tabs from all lines
    graph_code =~ s/^\t+//gm;, graph_code) # NOK
    graph_code = graph_code.rstrip("\n")

    return graph_code


def get_sorted_keys(dict: Dict[str, List], sort_type: int) -> List[str]:
    """
    dict:  filename -> stats
    stats: [ ln_found, ln_hit, fn_found, fn_hit, br_found, br_hit,
             link_name, line_rate, fn_rate, br_rate ]
    """
    global options
    if sort_type == SORT_FILE:
        # Sort by name
        return sorted(dict.keys())
    elif options.missed:
        return get_sorted_by_missed(dict, sort_type)
    else:
        return get_sorted_by_rate(dict, sort_type)


def get_sorted_by_missed(dict: Dict[str, List], sort_type: int) -> List[str]:
    """
    dict:  filename -> stats
    stats: [ ln_found, ln_hit, fn_found, fn_hit, br_found, br_hit,
             link_name, line_rate, fn_rate, br_rate ]
    """
    if sort_type == SORT_LINE:
        # Sort by number of instrumented lines without coverage
        return sorted(
            { (dict[$b][0] - dict[$b][1]) <=> (dict[$a][0] - dict[$a][1]) } dict.keys()) # NOK
    elif sort_type == SORT_FUNC:
        # Sort by number of instrumented functions without coverage
        return sorted(
            { (dict[$b][2] - dict[$b][3]) <=> (dict[$a][2] - dict[$a][3]) } dict.keys()) # NOK
    elif sort_type == SORT_BRANCH:
        # Sort by number of instrumented branches without coverage
        return sorted(
            { (dict[$b][4] - dict[$b][5]) <=> (dict[$a][4] - dict[$a][5]) } dict.keys()) # NOK


def get_sorted_by_rate(dict: Dict[str, List], sort_type: int) -> List[str]:
    """
    dict:  filename -> stats
    stats: [ ln_found, ln_hit, fn_found, fn_hit, br_found, br_hit,
             link_name, line_rate, fn_rate, br_rate ]
    """
    if sort_type == SORT_LINE:
        # Sort by line coverage
        return sorted({dict[$a][7] <=> dict[$b][7]} dict.keys()) # NOK
    elif sort_type == SORT_FUNC:
        # Sort by function coverage;
        return sorted({dict[$a][8] <=> dict[$b][8]} dict.keys()) # NOK
    elif sort_type == SORT_BRANCH:
        # Sort by br coverage;
        return sorted({dict[$a][9] <=> dict[$b][9]} dict.keys()) # NOK


def get_affecting_tests(test_line_data:  Dict[str, Dict[int,    int]],
                        test_func_data: Dict[str, Dict[object, int]],
                        testbrdata:  Dict[str, Dict[int,    str]]) -> Dict[str, str]:
    """test_line_data contains a mapping filename -> (linenumber -> exec count).
    Return a hash containing mapping filename -> "lines found, lines hit, ..."
    for each filename which has a nonzero hit count.
    """
    result = {}
    for testname in test_line_data.keys():
        # Get (line number -> count) hash for this test case
        testlncount:  Dict[int,    int] = test_line_data[testname]
        testfnccount: Dict[object, int] = test_func_data[testname]
        testbrcount:  Dict[int,    str] = testbrdata[testname]

        # Calculate sum
        ln_found, ln_hit = get_line_found_and_hit(testlncount)
        fn_found, fn_hit = get_func_found_and_hit(testfnccount)
        br_found, br_hit = get_branch_found_and_hit(testbrcount)

        if ln_hit > 0:
            result[testname] = f"{ln_found},{ln_hit},{fn_found},{fn_hit},{br_found},{br_hit}"

    return result

# NOK
def write_source(html_handle,
                 source_filename: Path,
                 count_data: Dict[???, ???],
                 checkdata: Dict[int, ???],
                 converted: Set[int],
                 $funcdata,
                 $sumbrcount) -> List:
    # (..., checksum_data, converted_data, func_data, ...)
    """Write an HTML view of a source code file.
    Returns a list containing data as needed by gen_png().

    Die on error.
    """
    global ignore

    count_data = count_data or {}

    #datafunc = reverse_dict(funcdata)  # unused

    try:
        SOURCE_HANDLE = source_filename.open("rt")
    except:
        if not ignore[ERROR_SOURCE]:
            die(f"ERROR: cannot read {source_filename}")

        # Continue without source file
        warn(f"WARNING: cannot read {source_filename}!")

        last_line = 0
        lines = sorted({ $a <=> $b } count_data.keys()) # NOK
        if lines:
            last_line = lines[-1]

        if last_line < 1:
            return [":"]

        file = []
        # Simulate gcov behavior
        for _ in range(last_line):
            file.append("/* EOF */")
    else:
        with SOURCE_HANDLE:
            @file = <SOURCE_HANDLE>

    write_source_prolog(html_handle)

    result = []
    line_number = 0
    for $_ in file:
        line_number += 1
        line = $_.rstrip("\n")

        # Also remove CR from line-end
        s/\015$//;

        # Source code matches coverage data?
        if (line_number in checkdata and
            checkdata[line_number] != md5_base64($_)):
            die(f"ERROR: checksum mismatch  at {source_filename}:{line_number}")

        result.append(write_source_line(html_handle, line_number,
                                      $_, count_data[line_number],
                                      line_number in converted,
                                      $sumbrcount->{line_number}))

    write_source_epilog(html_handle)

    return result


def write_source_prolog(html_handle):
    """Write start of source code table."""
    global options
    global html_templates_dir

    lineno_heading = "         "
    branch_heading = ((fmt_centered(options.br_field_width, "Branch data") + " ")
                       if options.br_coverage else "")
    line_heading   = fmt_centered(options.line_field_width, "Line data") + " "
    source_heading = " Source code"

    html = (html_templates_dir/"source_prolog.html").read_text()
    write_html(html_handle, html)


def write_source_epilog(html_handle):
    """Write end of source code table."""
    global html_templates_dir
    html = (html_templates_dir/"source_epilog.html").read_text()
    write_html(html_handle, html)

# NOK
def write_source_line(html_handle, line_num: int, $source, hit_count: Optional[float],
                      converted: bool, $brdata) -> str:
    """Write formatted source code line.
    Return a line in a format as needed by gen_png()
    """
    global options

    count_field_width = options.line_field_width - 1

    # Get branch HTML data for this line
    if options.br_coverage:
         @br_html = get_branch_html($brdata)

    if hit_count is None:
        result        = ""
        source_format = ""
        count_format  = " " * count_field_width
    elif hit_count == 0:
        result        = str(hit_count)
        source_format = '<span class="lineNoCov">'
        count_format  = format_count(hit_count, count_field_width)
    elif converted and options.highlight is not None:
        result        = f"*{hit_count}"
        source_format = '<span class="lineDiffCov">'
        count_format  = format_count(hit_count, count_field_width)
    else:
        result        = str(hit_count)
        source_format = '<span class="lineCov">'
        count_format  = format_count(hit_count, count_field_width)
    result += ":"
    result += $source

    # Write out a line number navigation anchor every options.nav_resolution
    # lines if necessary
    anchor_start = f'<a name="{line_num}">'
    anchor_end   = '</a>'

    # *************************************************************

    html = anchor_start
    html += '<span class="lineNum">{} </span>'.format("%8d" % line_num)
    if options.br_coverage:
        html += shift(@br_html)
        html += ":"
    html += f"{source_format}{count_format} : "
    html += escape_html($source)
    if source_format:
        html += '</span>'
    html += anchor_end
    html += "\n"

    write_html(html_handle, html)
    if options.br_coverage:
        # Add lines for overlong branch information
        for br_row in @br_html:
            write_html(html_handle,
                       f'<span class="lineNum">         </span>{br_row}\n')

    # *************************************************************

    return result


def get_branch_html(brdata: Optional[str]) -> List[str]:
    """Return a list of HTML lines which represent the specified
    branch coverage data in source code view.
    """
    global options

    blocks: List[List[List]] = get_branch_blocks(brdata)

    line     = []  # [branch2|" ", branch|" ", ...]
    line_len = 0

    lines: List = []  # [line1, line2, ...]
    # Distribute blocks to lines
    for block in blocks:
        block_len: int = get_block_len(block)
        # Does this block fit into the current line?
        if line_len + block_len <= options.br_field_width:
            # Add it
            line_len += block_len
            line.append(block)
        elif block_len <= options.br_field_width:
            # It would fit if the line was empty - add it to new line
            lines.append(line)
            line     = [block]
            line_len = block_len
        else:
            # Split the block into several lines
            for branch in block:
                if line_len + branch[BR_LEN] >= options.br_field_width:
                    # Start a new line
                    if (line_len + 1 <= options.br_field_width and
                        len(line) > 0 and not line[-1][BR_CLOSE]):
                        # Try to align branch symbols to be in one row
                        line.append(" ")
                    lines.append(line)
                    line     = []
                    line_len = 0
                line.append(branch)
                line_len += branch[BR_LEN]
    lines.append(line)

    result: List[str] = []

    # Convert to HTML
    for line in lines:

        current     = ""
        current_len = 0

        for branch in line:
            # Skip alignment space
            if branch == " ":
                current     += " "
                current_len += 1
                continue

            block_num, branch_num, taken, text_len, open, close =  branch

            if taken == "-":
                klass = "branchNoExec"
                text  = " # "
                title = f"Branch {branch_num} was not executed"
            elif int(taken) == 0:
                klass = "branchNoCov"
                text  = " - "
                title = f"Branch {branch_num} was not taken"
            else:
                klass = "branchCov"
                text  = " + "
                title = f"Branch {branch_num} was taken {taken} time"
                if int(taken) > 1: title += "s"

            if open: current += "["
            current += f'<span class="{klass}" title="{title}">'
            current += text
            current += '</span>'
            if close: current += "]"
            current_len += text_len

        # Right-align result text
        if current_len < options.br_field_width:
            current = " " * (options.br_field_width - current_len) + current

        result.append(current)

    return result


def get_branch_blocks(brdata: Optional[str]) -> List[List[List]]:
    """Group branches that belong to the same basic block.

    Returns: [block1, block2, ...]
    block:   [branch1, branch2, ...]
    branch:  [block_num, branch_num, taken_count, text_length, open, close]
    """
    if brdata is None:
        return []

    # Group branches
    blocks: List[List[List]] = []
    block:  List[List] = []
    last_block_num = None
    for entry in brdata.split(":"):
        block_num, branch_num, taken = entry.split(",")
        if last_block_num is not None and block_num != last_block_num:
            blocks.append(block)
            block = []
        block.append([block_num, branch_num, taken, 3, 0, 0])
        last_block_num = block_num
    if len(block) > 0:
        blocks.append(block)

    # Add braces to first and last branch in group
    for block in blocks:
        br_first = block[0]
        br_last  = block[-1]
        br_first[BR_LEN] += 1
        br_first[BR_OPEN] = 1
        br_last[BR_LEN]  += 1
        br_last[BR_CLOSE] = 1

    return sorted(cmp_blocks blocks)


def cmp_blocks(a, b):
    fa, fb = a[0], b[0]
    if fa[0] != fb[0]:
        return fa[0] <=> fb[0] # NOK
    else:
        return fa[1] <=> fb[1] # NOK


def format_count(count: float, width: int):
    """Return a right-aligned representation of count
    that fits in width characters.
    """
    result = "%*.0f" % (width, count)
    exp = 0
    while len(result) > width:
        if count < 10: break
        exp += 1
        count = int(count / 10)
        result = "%*s" % (width, f">{count}*10^{exp}")

    return result


def funcview_get_func_code(name: str, base_dir: Path, sort_type: int) -> str:
    """ """
    global options

    sort_link = None
    if options.sort and sort_type == SORT_LINE:
        sort_link = f"{name}.func.{options.html_ext}"

    result = "Function Name"
    result += get_sort_code(sort_link, "Sort by function name", base_dir)

    return result


def funcview_get_count_code(name: str, base_dir: Path, sort_type: int) -> str:
    """ """
    global options

    sort_link = None
    if options.sort and sort_type == SORT_FILE:
        sort_link = f"{name}.func-sort-c.{options.html_ext}"

    result = "Hit count"
    result += get_sort_code(sort_link, "Sort by hit count", base_dir)

    return result


def funcview_get_sorted(funcdata:   Dict[str, ???], # NOK
                        sumfnccount: Dict[str, int],
                        sort_type: int) -> List[str]:
    """Depending on the value of sort_type, return a list of functions sorted
    by name (sort_type 0) or by the associated call count (sort_type 1)."""
    if sort_type == SORT_FILE:
        return sorted(funcdata.keys())
    else:
        return sorted({ a cmp b if sumfnccount[b] == sumfnccount[a]
                        else sumfnccount[a] <=> sumfnccount[b]
                      } sumfnccount.keys()) # NOK


def subtract_counts(data: Dict[object, int],
                    base: Dict[object, int]) -> Tuple[Dict[object, int], int, int]:
    """Subtract line counts found in base from those in data.
    Return (data, ln_found, ln_hit).
    """
    ln_found = 0
    ln_hit   = 0
    for line, data_count in data.items():
        ln_found += 1

        if line in base:
            base_count = base[line]
            data_count -= base_count
            # Make sure we don't get negative numbers
            data_count = max(0, data_count)

        data[line] = data_count
        if data_count > 0:
            ln_hit += 1

    return (data, ln_found, ln_hit)


def subtract_fnccounts(data: Optional[Dict[object, int]],
                       base: Optional[Dict[object, int]]) -> Tuple[Dict[object, int], int, int]:
    """Subtract function call counts found in base from those in data.
    Return (data, fn_found, fn_hit).
    """
    if data is None: data = {}
    if base is None: base = {}

    fn_found = 0
    fn_hit   = 0
    for func, data_count in data.items():
        fn_found += 1

        if func in base:
            base_count = base[func]
            data_count -= base_count
            # Make sure we don't get negative numbers
            data_count = max(0, data_count)

        data[func] = data_count
        if data_count > 0:
            fn_hit += 1

    return (data, fn_found, fn_hit)


def apply_baseline(info_data: Dict[str, Dict[str, object]],
                   base_data: Dict[str, Dict[str, object]]) -> Dict[str, Dict[str, object]]:
    """Subtract the execution counts found in the baseline dict
    referenced by base_data from actual data in info_data.
    """
    for filename, data in info_data.items()):
        # Skip data entries for which no base entry exists
        if filename not in base_data: continue
        # Get data set for baseline
        base = base_data[filename]

        # Get set entries for data and baseline
        (data_testdata, _, data_funcdata, data_checkdata,
         data_testfncdata, _,
         data_testbrdata,  _,
         _, _, _, _, _, _) = get_info_entry(data)
        (_, base_count, _, base_checkdata,
         _, base_sumfnccount,
         _, base_sumbrcount,
         _, _, _, _, _, _) = get_info_entry(base)

        # Check for compatible checksums
        merge_checksums(data_checkdata, base_checkdata, filename)

        # sumlncount has to be calculated anew
        sumlncount:  Dict[int,    int] = {}
        sumfnccount: Dict[object, int] = {}
        sumbrcount:  Dict[int,    str] = {}
        #
        ln_found: Optional[int] = None
        ln_hit:   Optional[int] = None
        fn_found: Optional[int] = None
        fn_hit:   Optional[int] = None
        br_found: Optional[int] = None
        br_hit:   Optional[int] = None
        # For each test case, subtract test specific counts
        for testname in list(data_testdata.keys()):
            # Get counts of both data and baseline
            data_count        = data_testdata[testname]
            data_testfnccount = data_testfncdata[testname]
            data_testbrcount  = data_testbrdata[testname]

            data_count, _, ln_hit   = subtract_counts(data_count, base_count)
            data_testfnccount, _, _ = subtract_fnccounts(data_testfnccount, base_sumfnccount)
            data_testbrcount,  _, _ = combine_brcount(data_testbrcount, base_sumbrcount, BR_SUB)

            # Check whether this test case did hit any line at all
            if ln_hit > 0:
                # Write back resulting hash
                data_testdata[testname]    = data_count
                data_testfncdata[testname] = data_testfnccount
                data_testbrdata[testname]  = data_testbrcount
            else:
                # Delete test case which did not impact this file
                del data_testdata[testname]
                del data_testfncdata[testname]
                del data_testbrdata[testname]

            # Add counts to sum of counts
            sumlncount,  ln_found, ln_hit = add_counts(sumlncount, data_count)
            sumfnccount, fn_found, fn_hit = add_fnccount(sumfnccount, data_testfnccount)
            sumbrcount,  br_found, br_hit = combine_brcount(sumbrcount, data_testbrcount, BR_ADD)

        # Write back resulting entry
        set_info_entry(data,
                       data_testdata, sumlncount, data_funcdata, data_checkdata,
                       data_testfncdata, sumfnccount,
                       data_testbrdata,  sumbrcount,
                       ln_found, ln_hit,
                       fn_found, fn_hit,
                       br_found, br_hit)

        info_data[filename] = data

    return info_data


def remove_unused_descriptions():
    """"Removes all test descriptions from the global hash test_description
    which are not present in info_data.
    """
    global info_data
    global test_description

    test_list = set()  # Set containing found test names
    for filename, entry in info_data.items():
        # Reference to dict test_name -> count_data
        test_data = get_info_entry(entry)[0]
        for test_name in test_data.keys():
            test_list.add(test_name)

    before = len(test_description)  # Initial number of descriptions
    # Remove descriptions for tests which are not in our list
    for test_name in list(test_description.keys()):
        if test_name not in test_list:
            del test_description[test_name]
    after = len(test_description)  # Remaining number of descriptions

    if after < before:
        info("Removed {} unused descriptions, {} remaining.".format(
             (before - after), after))


def apply_prefix(filename, prefixes: List[str]):
    # If FILENAME begins with PREFIX from PREFIXES,
    # remove PREFIX from FILENAME and return resulting string,
    # otherwise return FILENAME.
    if prefixes:
        for prefix in prefixes:
            if filename == prefix:
                return "root"
            if prefix != "" and re.match(rf"^\Q{prefix}\E/(.*)$", filename):
                return filename[len(prefix) + 1:]
    return filename


def get_html_prolog(filename: Optional[Path] = None):
    """If filename is defined, return contents of file.
    Otherwise return default HTML prolog.
    Die on error."""
    global html_templates_dir
    if filename is None:
        filename = html_templates_dir/"html_prolog.html"
    try:
        return filename.read_text()
    exept:
        die(f"ERROR: cannot open html prolog {filename}!")


def get_html_epilog(filename: Optional[Path] = None):
    """If filename is defined, return contents of file.
    Otherwise return default HTML epilog.
    Die on error."""
    global html_templates_dir
    if filename is None:
        filename = html_templates_dir/"html_epilog.html"
    try:
        return filename.read_text()
    exept:
        die(f"ERROR: cannot open html epilog {filename}!")


def rename_functions(info: Dict[???, ???], conv: Dict[???, ???]): # NOK
    """Rename all function names in INFO according to CONV: OLD_NAME -> NEW_NAME.
    In case two functions demangle to the same name, assume that they are
    different object code implementations for the same source function.
    """
    for filename, data in info.items():

        # funcdata: function name -> line number
        funcdata = data["func"]
        newfuncdata = {}
        for fn, fnccount in funcdata.items():
            cn = conv[fn]
            # Abort if two functions on different lines map to the same
            # demangled name.
            if cn in newfuncdata and newfuncdata[cn] != fnccount:
                die(f"ERROR: Demangled function name {cn} maps to different "
                    f"lines ({newfuncdata[cn]} vs {fnccount}) in {filename}")
            newfuncdata[cn] = fnccount
        data["func"] = newfuncdata

        # testfncdata: test name -> testfnccount
        # testfnccount: function name -> execution count
        testfncdata = data["testfnc"]
        for tn, testfnccount in testfncdata.items():
            newtestfnccount = {}
            for fn, fnccount in testfnccount.items():
                cn = conv[fn]
                # Add counts for different functions that map to the same name.
                if cn not in newtestfnccount
                    newtestfnccount[cn] = fnccount
                else:
                    newtestfnccount[cn] += fnccount
            testfncdata[tn] = newtestfnccount

        # sumfnccount: function name -> execution count
        sumfnccount = data["sumfnc"]
        newsumfnccount = {}
        for fn, fnccount in sumfnccount.items():
            cn = conv[fn]
            # Add counts for different functions that map to the same name.
            if cn not in newsumfnccount:
                newsumfnccount[cn] = fnccount
            else:
                newsumfnccount[cn] += fnccount
        data["sumfnc"] = newsumfnccount

        # Update function found and hit counts since they may have changed
        f_found = 0
        f_hit   = 0
        for ccount in newsumfnccount.values():
            f_found += 1
            if ccount > 0:
                f_hit += 1
        data["f_found"] = f_found
        data["f_hit"]   = f_hit


def get_fn_list(info: Dict[???, ???]) -> List[???]: # NOK
    """ """
    fns = set()
    for data in info.values():
        if "func" in data and data["func"] is not None):
            for func_name in data["func"].keys():
                fns.add(func_name)
        if "sumfnc" in data and data["sumfnc"] is not None:
            for func_name in data["sumfnc"].keys():
                fns.add(func_name)

    return list(fns)


def parse_dir_prefix(prefixes: Optional[List]):
    """Parse user input about the prefix list"""
    if not prefixes: return
    global dir_prefix

    for item in prefixes:
        if "," in item:
            # Split and add comma-separated parameters
            dir_prefix += item.split(",")
        else:
            # Add single parameter
            dir_prefix.append(item)


def demangle_list(func_list: List[str]) -> Dict[str, str]:
    """ """
    global options

    # Extra flag necessary on OS X so that symbols listed by gcov
    # get demangled properly.
    demangle_args = options.demangle_cpp_params
    if demangle_args == "" and $^O == "darwin": # NOK
        demangle_args = "--no-strip-underscore"
    # Build translation hash from c++filt output
    try:
        process = subprocess.run([options.demangle_cpp_tool, demangle_args],
                                 input="\n".join(func_list), capture_output=True,
                                 encoding="utf-8", check=True)
    except Exception as exc:
        die(f"ERROR: could not run c++filt: {exc}!")
    flines = process.stdout.splitlines()
    if len(flines) != len(func_list):
        die("ERROR: c++filt output not as expected ({} vs {}) lines".format(
            len(flines), len(func_list)))

    demangle: Dict[str, str] = {}
    versions: Dict[str, int] = {}
    for func, translated in zip(func_list, flines):
        if translated not in versions:
            versions[translated] = 1
        else:
            versions[translated] += 1
        version = versions[translated]
        if version > 1: translated += f".{version}"
        demangle[func] = translated

    return demangle


def get_rate(found: int, hit: int) -> int:
    """Return a relative value for the specified found&hit values
    which is used for sorting the corresponding entries in a
    file list."""
    if found == 0:
        return 10000
    else:
        return int(hit * 1000 / found) * 10 + 2 - (1 / found)


def create_sub_dir(dir: Path, *, exist_ok=False):
    """Create subdirectory dir if it does not already exist,
    including all its parent directories.

    Die on error.
    """
    try:
        dir.mkdir(parents=True, exist_ok=exist_ok)
    except:
        and die(f"ERROR: cannot create directory {dir}!")


def info(format, *pars, *, end="\n"):
    """Use printf to write to stdout only when the args.quiet flag
    is not set."""
    global args
    if args.quiet: return
    # Print info string
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
        import sys
        sys.exit(f"{tool_name}: {msg}")

    # $SIG{__WARN__} = warn_handler
    # $SIG{__DIE__}  = die_handler


if __name__.rpartition(".")[-1] == "__main__":
    sys.exit(main())
