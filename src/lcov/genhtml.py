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
use File::Basename;
use File::Temp qw(tempfile);
use Getopt::Long;
use Digest::MD5 qw(md5_base64);
use Cwd qw/abs_path cwd/;

from typing import List
import argparse
import sys
import re
from pathlib import Path

from .util import reverse_dict

# Global constants
tool_name    = Path(__file__).stem
our $title   = "LCOV - code coverage report"
our $tool_dir        = abs_path(dirname($0));
lcov_version = "LCOV version " #+ `${abs_path(dirname($0))}/get_version.sh --full`
lcov_url     = "http://ltp.sourceforge.net/coverage/lcov.php"

# Specify coverage rate default precision
our $default_precision = 1;

# Specify coverage rate limits (in %) for classifying file entries
# HI:   $hi_limit <= rate <= 100          graph color: green
# MED: $med_limit <= rate <  $hi_limit    graph color: orange
# LO:          0  <= rate <  $med_limit   graph color: red

# For line coverage/all coverage types if not specified
our $hi_limit = 90;
our $med_limit = 75;

# For function coverage
our $fn_hi_limit;
our $fn_med_limit;

# For branch coverage
our $br_hi_limit;
our $br_med_limit;

# Width of overview image
our $overview_width = 80;

# Resolution of overview navigation: this number specifies the maximum
# difference in lines between the position a user selected from the overview
# and the position the source code window is scrolled to.
our $nav_resolution = 4;

# Clicking a line in the overview image should show the source code view at
# a position a bit further up so that the requested line is not the first
# line in the window. This number specifies that offset in lines.
our $nav_offset = 10;

# Clicking on a function name should show the source code at a position a
# few lines before the first line of code of that function. This number
# specifies that offset in lines.
our $func_offset = 2;

our $overview_title = "top level";

# Width for line coverage information in the source code view
options.line_field_width = 12
# Width for branch coverage information in the source code view
options.br_field_width = 16

# Internal Constants

# Header types
our $HDR_DIR        = 0;
our $HDR_FILE        = 1;
our $HDR_SOURCE        = 2;
our $HDR_TESTDESC    = 3;
our $HDR_FUNC        = 4;

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
our $ERROR_SOURCE    = 0;
ERROR_ID = {
    "source" => $ERROR_SOURCE,
}

# Data related prototypes
from .util import strip_spaces_in_options
sub print_usage(*);
sub process_dir($);
sub info(@);
sub read_info_file($);
sub get_prefix($@);
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
sub apply_prefix($@);
sub write_dir_page($$$$$$$$$$$$$$$$$);
sub parse_ignore_errors(@);
from .lcov import rate
from .util import apply_config
from .util import system_no_output
from .util import get_date_string

# HTML related prototypes
sub escape_html($);
sub get_bar_graph_code($$$);

sub write_css_file();

sub write_html_prolog(*$$);
sub write_html_epilog(*$;$);

sub write_header_prolog(*$);
sub write_header_line(*@);
sub write_header_epilog(*$);

sub write_file_table(*$$$$$$$);

sub write_test_table_prolog(*$);
sub write_test_table_entry(*$$);
sub write_test_table_epilog(*);

sub write_frameset(*$$$);
sub write_overview_line(*$$$);
sub write_overview(*$$$$);

# External prototype (defined in genpng)
sub gen_png($$$$@);


# Global variables & initialization
our %info_data;        # Hash containing all data from .info file
our @opt_dir_prefix;    # Array of prefixes to remove from all sub directories
our @dir_prefix;
test_description: Dict[str, str] = {}  # Hash containing test descriptions if available
our $date = get_date_string()

our @info_filenames;    # List of .info files to use as data source
our $test_title;    # Title for output as written to each page header
our $output_directory;    # Name of directory in which to store output
our $base_filename;    # Optional name of file containing baseline data
our $desc_filename;    # Name of file containing test descriptions
our $css_filename;    # Optional name of external stylesheet file to use
our $quiet;        # If set, suppress information messages
our $help;        # Help option flag
our $version;        # Version option flag
our $show_details;    # If set, generate detailed directory view
our $no_prefix;        # If set, do not remove filename prefix
our $fn_coverage;    # If set, generate function coverage statistics
our $no_fn_coverage;    # Disable fn_coverage
our $br_coverage;    # If set, generate branch coverage statistics
our $no_br_coverage;    # Disable br_coverage
our $sort = 1;        # If set, provide directory listings with sorted entries
our $no_sort;        # Disable sort
our $frames;        # If set, use frames for source code view
our $keep_descriptions;    # If set, do not remove unused test case descriptions
our $no_sourceview;    # If set, do not create a source code view for each file
options.highlight: Optional[bool] = None  # If set, highlight lines covered by converted data only
our $legend;        # If set, include legend in output
our $tab_size = 8;    # Number of spaces to use in place of tab
our $config;        # Configuration file contents
our $html_prolog_file;    # Custom HTML prolog file (up to and including <body>)
our $html_epilog_file;    # Custom HTML epilog file (from </body> onwards)
our $html_prolog;    # Actual HTML prolog
our $html_epilog;    # Actual HTML epilog
args.html_ext = "html"  # Extension for generated HTML files
our $html_gzip = 0;    # Compress with gzip
args.demangle_cpp = False  # Demangle C++ function names
options.demangle_cpp_tool   = "c++filt"  # Default demangler for C++ function names
options.demangle_cpp_params = ""         # Extra parameters for demangling
our @opt_ignore_errors;    # Ignore certain error classes during processing
our @ignore;
our $opt_config_file;    # User-specified configuration file location
our %opt_rc;
our $opt_missed;    # List/sort lines by missed counts
our $dark_mode;         # Use dark mode palette or normal
our $charset = "UTF-8";    # Default charset for HTML pages
our @fileview_sortlist;
our @fileview_sortname = ("", "-sort-l", "-sort-f", "-sort-b");
our @funcview_sortlist;
our @rate_name = ("Lo", "Med", "Hi");
our @rate_png = ("ruby.png", "amber.png", "emerald.png");
options.lcov_function_coverage: bool = True
options.lcov_branch_coverage:   bool = False
options.rc_desc_html:           bool = False  # lcovrc: genhtml_desc_html

$cwd = Path.cwd()  # Current working directory

#
# Code entry point
#

# Check command line for a configuration file name
Getopt::Long::Configure("pass_through", "no_auto_abbrev")
GetOptions("config-file=s" => \$opt_config_file,
           "rc=s%"         => \%opt_rc)
Getopt::Long::Configure("default")

# Remove spaces around rc options
%opt_rc = strip_spaces_in_options(%opt_rc)
# Read configuration file if available
$config = read_lcov_config_file($opt_config_file)

if $config or %opt_rc:
{
    # Copy configuration file and --rc values to variables
    apply_config({
        "genhtml_css_file"        => \$css_filename,
        "genhtml_hi_limit"        => \$hi_limit,
        "genhtml_med_limit"        => \$med_limit,
        "genhtml_line_field_width"  => \options.line_field_width,
        "genhtml_overview_width"    => \$overview_width,
        "genhtml_nav_resolution"    => \$nav_resolution,
        "genhtml_nav_offset"        => \$nav_offset,
        "genhtml_keep_descriptions"    => \$keep_descriptions,
        "genhtml_no_prefix"        => \$no_prefix,
        "genhtml_no_source"        => \$no_sourceview,
        "genhtml_num_spaces"        => \$tab_size,
        "genhtml_highlight"        => \options.highlight,
        "genhtml_legend"        => \$legend,
        "genhtml_html_prolog"        => \$html_prolog_file,
        "genhtml_html_epilog"        => \$html_epilog_file,
        "genhtml_html_extension"    => \args.html_ext,
        "genhtml_html_gzip"        => \$html_gzip,
        "genhtml_precision"        => \$default_precision,
        "genhtml_function_hi_limit"    => \$fn_hi_limit,
        "genhtml_function_med_limit"    => \$fn_med_limit,
        "genhtml_function_coverage"    => \$fn_coverage,
        "genhtml_branch_hi_limit"    => \$br_hi_limit,
        "genhtml_branch_med_limit"    => \$br_med_limit,
        "genhtml_branch_coverage"    => \$br_coverage,
        "genhtml_branch_field_width"    => \options.br_field_width,
        "genhtml_sort"            => \$sort,
        "genhtml_charset"        => \$charset,
        "genhtml_desc_html"        => \options.rc_desc_html,
        "genhtml_demangle_cpp"        => \args.demangle_cpp,
        "genhtml_demangle_cpp_tool"    => \options.demangle_cpp_tool,
        "genhtml_demangle_cpp_params"  => \options.demangle_cpp_params,
        "genhtml_dark_mode"             => \$dark_mode,
        "genhtml_missed"              => \$opt_missed,
        "lcov_function_coverage"      => \options.lcov_function_coverage,
        "lcov_branch_coverage"        => \options.lcov_branch_coverage,
        });
}

# Copy related values if not specified
if ! defined($fn_hi_limit):  $fn_hi_limit  = $hi_limit              
if ! defined($fn_med_limit): $fn_med_limit = $med_limit             
if ! defined($br_hi_limit):  $br_hi_limit  = $hi_limit              
if ! defined($br_med_limit): $br_med_limit = $med_limit             
if ! defined($fn_coverage):  $fn_coverage  = options.lcov_function_coverage
if ! defined($br_coverage):  $br_coverage  = options.lcov_branch_coverage  

# Parse command line options
if (!GetOptions("output-directory|o=s"    => \$output_directory,
        "title|t=s"        => \$test_title,
        "description-file|d=s"    => \$desc_filename,
        "keep-descriptions|k"    => \$keep_descriptions,
        "css-file|c=s"        => \$css_filename,
        "baseline-file|b=s"    => \$base_filename,
        "prefix|p=s"        => \@opt_dir_prefix,
        "num-spaces=i"        => \$tab_size,
        "no-prefix"        => \$no_prefix,
        "no-sourceview"        => \$no_sourceview,
        "show-details|s"    => \$show_details,
        "frames|f"        => \$frames,
        "highlight"        => \options.highlight,
        "legend"        => \$legend,
        "quiet|q"        => \$quiet,
        "help|h|?"        => \$help,
        "version|v"        => \$version,
        "html-prolog=s"        => \$html_prolog_file,
        "html-epilog=s"        => \$html_epilog_file,
        "html-extension=s"    => \args.html_ext,
        "html-gzip"        => \$html_gzip,
        "function-coverage"    => \$fn_coverage,
        "no-function-coverage"    => \$no_fn_coverage,
        "branch-coverage"    => \$br_coverage,
        "no-branch-coverage"    => \$no_br_coverage,
        "sort"            => \$sort,
        "no-sort"        => \$no_sort,
        "demangle-cpp"        => \args.demangle_cpp,
        "ignore-errors=s"    => \@opt_ignore_errors,
        "config-file=s"        => \$opt_config_file,
        "rc=s%"            => \%opt_rc,
        "precision=i"        => \$default_precision,
        "missed"        => \$opt_missed,
        "dark-mode"        => \$dark_mode,
        ))
{
    print("Use $tool_name --help to get usage information", file=sys.stderr)
    sys.exit(1)
}

# Merge options
if $no_fn_coverage:
    $fn_coverage = 0;

if $no_br_coverage:
    $br_coverage = 0;

if $no_sort:
    $sort = 0;

@info_filenames = @ARGV;

# Check for help option
if $help:
    print_usage(sys.stdout)
    sys.exit(0)

# Check for version option
if $version:
    print("$tool_name: $lcov_version\n")
    sys.exit(0)

# Determine which errors the user wants us to ignore
parse_ignore_errors(@opt_ignore_errors)

# Split the list of prefixes if needed
parse_dir_prefix(@opt_dir_prefix)

# Check for info filename
if ! @info_filenames:
    die("No filename specified\n"
        "Use $tool_name --help to get usage information\n")

# Generate a title if none is specified
if ! $test_title:
    if len(@info_filenames) == 1:
        # Only one filename specified, use it as title
        $test_title = basename($info_filenames[0]);
    else:
        # More than one filename specified, used default title
        $test_title = "unnamed"

# Make sure css_filename is an absolute path (in case we're changing
# directories)
if $css_filename:
    if ! ($css_filename =~ /^\/(.*)$/):
        $css_filename = $cwd."/".$css_filename;

# Make sure tab_size is within valid range
if $tab_size < 1:
    print("ERROR: invalid number of spaces specified: $tab_size!", file=sys.stderr)
    sys.exit(1)

# Get HTML prolog and epilog
$html_prolog = get_html_prolog(Path($html_prolog_file) if $html_prolog_file else None)
$html_epilog = get_html_epilog(Path($html_epilog_file) if $html_epilog_file else None)

# Issue a warning if --no-sourceview is enabled together with --frames
if $no_sourceview and defined($frames):
    warn("WARNING: option --frames disabled because --no-sourceview "
         "was specified!\n");
    $frames = None

# Issue a warning if --no-prefix is enabled together with --prefix
if $no_prefix and @dir_prefix:
    warn("WARNING: option --prefix disabled because --no-prefix was "
         "specified!\n");
    @dir_prefix = None

@fileview_sortlist = [SORT_FILE]
@funcview_sortlist = [SORT_FILE]
if $sort:
    @fileview_sortlist.append(SORT_LINE)
    if $fn_coverage:
        @fileview_sortlist.append(SORT_FUNC)  
    if $br_coverage:
        @fileview_sortlist.append(SORT_BRANCH)
    @funcview_sortlist.append(SORT_LINE)

if $frames:
    # Include genpng code needed for overview image generation
    do("$tool_dir/genpng")

# Ensure that the c++filt tool is available when using --demangle-cpp
if args.demangle_cpp:
    if system_no_output(3, options.demangle_cpp_tool, "--version") != NO_ERROR:
        die(f"ERROR: could not find {options.demangle_cpp_tool} tool needed for "
            "--demangle-cpp\n")

# Make sure precision is within valid range
if $default_precision < 1 or $default_precision > 4:
    die("ERROR: specified precision is out of range (1 to 4)\n")

# Make sure output_directory exists, create it if necessary
if $output_directory:
    if not Path($output_directory).exists():
        create_sub_dir(Path($output_directory))

# Do something
gen_html()

sys.exit(0)


#
# print_usage(handle)
#
# Print usage information.
#

# NOK
def print_usage(*)
{
    local *HANDLE = $_[0];

    print(HANDLE <<END_OF_USAGE);
Usage: $tool_name [OPTIONS] INFOFILE(S)

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

For more information see: $lcov_url
END_OF_USAGE
    ;
}

# NOK
def get_fn_list($)
{
    my ($info) = @_;
    my %fns;
    my @result;

    foreach my $filename (keys(%{$info})) {
        my $data = $info->{$filename};
        my $funcdata = $data->{"func"};
        my $sumfnccount = $data->{"sumfnc"};

        if (defined($funcdata)) {
            foreach my $func_name (keys(%{$funcdata})) {
                $fns{$func_name} = 1;
            }
        }

        if (defined($sumfnccount)) {
            foreach my $func_name (keys(%{$sumfnccount})) {
                $fns{$func_name} = 1;
            }
        }
    }

    @result = keys(%fns);

    return \@result;
}

#
# rename_functions(info, conv)
#
# Rename all function names in INFO according to CONV: OLD_NAME -> NEW_NAME.
# In case two functions demangle to the same name, assume that they are
# different object code implementations for the same source function.
#

# NOK
def rename_functions($$)
{
    my ($info, $conv) = @_;

    foreach my $filename (keys(%{$info})) {
        my $data = $info->{$filename};
        my $funcdata;
        my $testfncdata;
        my $sumfnccount;
        my %newfuncdata;
        my %newsumfnccount;
        my $f_found;
        my $f_hit;

        # funcdata: function name -> line number
        $funcdata = $data->{"func"};
        foreach my $fn (keys(%{$funcdata})) {
            my $cn = $conv->{$fn};

            # Abort if two functions on different lines map to the
            # same demangled name.
            if (defined($newfuncdata{$cn}) and
                $newfuncdata{$cn} != $funcdata->{$fn}):
            {
                die("ERROR: Demangled function name $cn ".
                    "maps to different lines (".
                    $newfuncdata{$cn}." vs ".
                    $funcdata->{$fn}.") in $filename\n");
            }
            $newfuncdata{$cn} = $funcdata->{$fn};
        }
        $data->{"func"} = \%newfuncdata;

        # testfncdata: test name -> testfnccount
        # testfnccount: function name -> execution count
        $testfncdata = $data->{"testfnc"};
        foreach my $tn (keys(%{$testfncdata})) {
            my $testfnccount = $testfncdata->{$tn};
            my %newtestfnccount;

            foreach my $fn (keys(%{$testfnccount})) {
                my $cn = $conv->{$fn};

                # Add counts for different functions that map
                # to the same name.
                $newtestfnccount{$cn} +=
                    $testfnccount->{$fn};
            }
            $testfncdata->{$tn} = \%newtestfnccount;
        }

        # sumfnccount: function name -> execution count
        $sumfnccount = $data->{"sumfnc"};
        foreach my $fn (keys(%{$sumfnccount})) {
            my $cn = $conv->{$fn};

            # Add counts for different functions that map
            # to the same name.
            $newsumfnccount{$cn} += $sumfnccount->{$fn};
        }
        $data->{"sumfnc"} = \%newsumfnccount;

        # Update function found and hit counts since they may have
        # changed
        $f_found = 0;
        $f_hit = 0;
        foreach my $fn (keys(%newsumfnccount)) {
            $f_found += 1
            $f_hit++ if ($newsumfnccount{$fn} > 0);
        }
        $data["f_found"] = $f_found;
        $data["f_hit"] = $f_hit;
    }
}

# NOK
def gen_html():
    # Generate a set of HTML pages from contents of .info file INFO_FILENAME.
    # Files will be written to the current directory. If provided, test case
    # descriptions will be read from .tests file TEST_FILENAME and included
    # in ouput.
    #
    # Die on error.

    global args
    global %info_data
    global $base_filename
    global test_description

    my %base_data;

    try:
        # Read in all specified .info files
        for $_ in @info_filenames:
            current = read_info_file($_)
            # Combine current with %info_data
            %info_data = combine_info_files(%info_data, current)

        info("Found %d entries.\n", len(%info_data))

        # Read and apply baseline data if specified
        if $base_filename:
            # Read baseline file
            info("Reading baseline file $base_filename\n")
            %base_data = read_info_file($base_filename)
            info("Found %d entries.\n", len(%base_data))
            # Apply baseline
            info("Subtracting baseline data.\n")
            %info_data = apply_baseline(%info_data, %base_data)

        dir_list: List[str] = get_dir_list(%info_data.keys())

        if $no_prefix:
            # User requested that we leave filenames alone
            info("User asked not to remove filename prefix\n")
        elif not @dir_prefix:
            # Get prefix common to most directories in list
            prefix = get_prefix(1, keys(%info_data))
            if prefix:
                info(f"Found common filename prefix \"{prefix}\"\n")
                $dir_prefix[0] = prefix
            else:
                info("No common filename prefix found!\n")
                $no_prefix = 1
        else:
            my $msg = "Using user-specified filename prefix ";
            for $i in (0 .. $#dir_prefix):
                $dir_prefix[$i] =~ s/\/+$//;
                $msg += ", " unless 0 == $i;
                $msg += "\"" . $dir_prefix[$i] . "\"";
            info($msg . "\n");

        # Read in test description file if specified
        if $desc_filename:
            info("Reading test description file $desc_filename\n")
            test_description = read_testfile(Path($desc_filename))
            # Remove test descriptions which are not referenced
            # from %info_data if user didn't tell us otherwise
            if not $keep_descriptions:
                remove_unused_descriptions()

        # Change to output directory if specified
        if $output_directory:
            try:
                os.chdir($output_directory)
            except:
                die("ERROR: cannot change to directory $output_directory!\n")

        info("Writing .css and .png files.\n")
        write_css_file()
        write_png_files()

        if $html_gzip:
            info("Writing .htaccess file.\n")
            write_htaccess_file()

        info("Generating output.\n")

        # Process each subdirectory and collect overview information
        overview: Dict[???, ???] = {}
        overall_found  = 0
        overall_hit    = 0
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
            if not $no_prefix and @dir_prefix:
                # Match directory names beginning with one of @dir_prefix
                dir_name = apply_prefix(dir_name, @dir_prefix)

            # Generate name for directory overview HTML page
            if (dir_name =~ /^\/(.*)$/):
                link_name = dir_name[1:] + f"/index.{args.html_ext}"
            else:
                link_name = dir_name + f"/index.{args.html_ext}"

            overview[dir_name] = [ln_found, ln_hit,
                                  fn_found, fn_hit,
                                  br_found, br_hit,
                                  link_name,
                                  get_rate(ln_found, ln_hit),
                                  get_rate(fn_found, fn_hit),
                                  get_rate(br_found, br_hit)]
            overall_found  += ln_found
            overall_hit    += ln_hit
            total_fn_found += fn_found
            total_fn_hit   += fn_hit
            total_br_found += br_found
            total_br_hit   += br_hit

        # Generate overview page
        info("Writing directory view page.\n")

        # Create sorted pages
        for $_ in @fileview_sortlist:
            write_dir_page($fileview_sortname[$_], ".", "", $test_title,
                           _, $overall_found, $overall_hit,
                           $total_fn_found, $total_fn_hit, $total_br_found,
                           $total_br_hit, \%overview, {}, {}, {}, 0, $_)

        # Check if there are any test case descriptions to write out
        if test_description:
            info("Writing test case description file.\n")
            write_description_file(test_description,
                                   $overall_found,  $overall_hit,
                                   $total_fn_found, $total_fn_hit,
                                   $total_br_found, $total_br_hit);

        print_overall_rate(1,           overall_found,  overall_hit,
                           fn_coverage, total_fn_found, total_fn_hit,
                           br_coverage, total_br_found, total_br_hit,
                           title="Overall coverage rate:")
    finally:
        os.chdir(cwd)

# NOK
def html_create($filename):
    if $html_gzip:
        handle = open("|-", "gzip -c >'$filename'")
            or die("ERROR: cannot open $filename for writing (gzip)!\n");
    else:
        handle = open(">", $filename)
            or die("ERROR: cannot open $filename for writing!\n");
    return handle

# NOK
def write_dir_page($name,
                   $rel_dir, $base_dir, title: str, $trunc_dir,
                   $overall_found,  $overall_hit,
                   $total_fn_found, $total_fn_hit,
                   $total_br_found, $total_br_hit,
                   $overview,
                   $testhash, $testfnchash, $testbrhash,
                   $view_type, sort_type: int):
    """ """
    global args

    # Generate directory overview page including details
    with html_create(f"$rel_dir/index$name.{args.html_ext}") as html_handle:

        if ! defined($trunc_dir):
            trunc_dir = ""
        if trunc_dir != "":
            title += " - "

        write_html_prolog(html_handle, $base_dir, f"LCOV - {title}{trunc_dir}")

        write_header(html_handle, $view_type,
                     trunc_dir, $rel_dir,
                     $overall_found,  $overall_hit,
                     $total_fn_found, $total_fn_hit,
                     $total_br_found, $total_br_hit,
                     sort_type)

        write_file_table(html_handle, $base_dir, $overview,
                         $testhash, $testfnchash, $testbrhash,
                         $view_type, sort_type);

        write_html_epilog(html_handle, $base_dir)

# NOK
def process_dir(abs_dir):
    # process_dir(dir_name)

    global args
    global %info_data

    my $rel_dir = $abs_dir;
    my $trunc_dir;
    my $filename;
    my %overview;
    my $ln_found;
    my $ln_hit;
    my $fn_found;
    my $fn_hit;
    my $br_found;
    my $br_hit;
    my $base_name;
    my $extension;
    my $testdata;
    my %testhash;
    my $testfncdata;
    my %testfnchash;
    my $testbrdata;
    my %testbrhash;
    my @sort_list;

    # Remove prefix if applicable
    if ! $no_prefix:
        # Match directory name beginning with one of @dir_prefix
        $rel_dir = apply_prefix($rel_dir, @dir_prefix)

    trunc_dir = $rel_dir;
    # Remove leading /
    if ($rel_dir =~ /^\/(.*)$/):
        $rel_dir = substr($rel_dir, 1)

    # Handle files in root directory gracefully
    if $rel_dir   == "": $rel_dir   = "root"
    if trunc_dir == "": trunc_dir = "root"

    base_dir: str = get_relative_base_path($rel_dir)

    create_sub_dir(Path($rel_dir))

    # Match filenames which specify files in this directory, not including
    # sub-directories
    overall_found  = 0
    overall_hit    = 0
    total_fn_found = 0
    total_fn_hit   = 0
    total_br_found = 0
    total_br_hit   = 0

    foreach $filename (grep(/^\Q$abs_dir\E\/[^\/]*$/,keys(%info_data))):
        my $page_link;
        my $func_link;

        (ln_found, ln_hit,
         fn_found, fn_hit,
         br_found, br_hit,
         $testdata, $testfncdata, $testbrdata) = process_file(trunc_dir, $rel_dir, $filename)

        $base_name = basename($filename);

        if ($no_sourceview) {
            $page_link = "";
        } elsif ($frames) {
            # Link to frameset page
            $page_link = f"$base_name.gcov.frameset.{args.html_ext}"
        else:
            # Link directory to source code view page
            $page_link = f"$base_name.gcov.{args.html_ext}"
        }
        $overview{$base_name} = [ln_found, ln_hit,
                                 fn_found, fn_hit,
                                 br_found, br_hit,
                                 $page_link,
                                 get_rate(ln_found, ln_hit),
                                 get_rate(fn_found, fn_hit),
                                 get_rate(br_found, br_hit)]

        $testhash{$base_name}    = $testdata;
        $testfnchash{$base_name} = $testfncdata;
        $testbrhash{$base_name}  = $testbrdata;

        overall_found  += ln_found
        overall_hit    += ln_hit
        total_fn_found += fn_found
        total_fn_hit   += fn_hit
        total_br_found += br_found
        total_br_hit   += br_hit

    # Create sorted pages
    for $_ in @fileview_sortlist:
        # Generate directory overview page (without details)    
        write_dir_page($fileview_sortname[$_],
                   $rel_dir, base_dir, $test_title, trunc_dir,
                   $overall_found,  $overall_hit,
                   $total_fn_found, $total_fn_hit,
                   $total_br_found, $total_br_hit,
                   \%overview, {}, {}, {}, 1, $_)
        if not $show_details: continue
        # Generate directory overview page including details
        write_dir_page("-detail".$fileview_sortname[$_],
                   $rel_dir, $base_dir, $test_title, trunc_dir,
                   $overall_found,  $overall_hit,
                   $total_fn_found, $total_fn_hit,
                   $total_br_found, $total_br_hit,
                   \%overview,
                   \%testhash, \%testfnchash, \%testbrhash, 1, $_)

    # Calculate resulting line counts
    return (overall_found,  overall_hit,
            total_fn_found, total_fn_hit,
            total_br_found, total_br_hit)

# NOK
def write_function_page($base_dir, $rel_dir, trunc_dir,
                        $base_name, title: str,
                        $ln_found, $ln_hit,
                        $fn_found, $fn_hit,
                        $br_found, $br_hit,
                        $sumcount,    $funcdata,
                        $sumfnccount, $testfncdata,
                        $sumbrcount,  $testbrdata,
                        sort_type: int):
    """ """
    global args

    # Generate function table for this file
    if sort_type == 0:
        $filename = f"$rel_dir/$base_name.func.{args.html_ext}"
    else:
        $filename = f"$rel_dir/$base_name.func-sort-c.{args.html_ext}"

    with html_create($filename) as html_handle:

        write_html_prolog(html_handle, $base_dir,
                          f"LCOV - {title} - {trunc_dir}/$base_name - functions")

        write_header(html_handle, 4,
                     f"{trunc_dir}/$base_name", "$rel_dir/$base_name",
                     $ln_found, $ln_hit,
                     $fn_found, $fn_hit,
                     $br_found, $br_hit,
                     sort_type)

        write_function_table(html_handle,
                             f"$base_name.gcov.{args.html_ext}",
                             $sumcount,    $funcdata,
                             $sumfnccount, $testfncdata,
                             $sumbrcount,  $testbrdata,
                             $base_name, $base_dir,
                             sort_type)

        write_html_epilog(html_handle, $base_dir, 1)

# NOK
def write_function_table(html_handle,
                         $source,
                         $sumcount,   $funcdata,
                         $sumfncdata, $testfncdata,
                         $sumbrcount, $testbrdata,
                         $name, $base, $type):
    # write_function_table(html_handle, source_file, sumcount, funcdata,
    #               sumfnccount, testfncdata, sumbrcount, testbrdata,
    #               base_name, base_dir, sort_type)
    #
    # Write an HTML table listing all functions in a source file, including
    # also function call counts and line coverages inside of each function.
    #
    # Die on error.

    my $func;
    my $demangle;

    # Get HTML code for headings
    $func_code  = funcview_get_func_code($name,  $base, $type)
    $count_code = funcview_get_count_code($name, $base, $type)
    write_html(html_handle, <<END_OF_HTML)
      <center>
      <table width="60%" cellpadding=1 cellspacing=1 border=0>
        <tr><td><br></td></tr>
        <tr>
          <td width="80%" class="tableHead">$func_code</td>
          <td width="20%" class="tableHead">$count_code</td>
        </tr>
END_OF_HTML

    # Get demangle translation hash
    if args.demangle_cpp:
        $demangle = demangle_list(sorted($funcdata.keys()))

    # Get a sorted table
    for $func in funcview_get_sorted($funcdata, $sumfncdata, $type):
        if ! defined($funcdata->{$func}): continue

        my $startline = $funcdata->{$func} - $func_offset;
        my $name      = $func;
        my $count     = $sumfncdata->{$name};

        my $countstyle;

        # Replace function name with demangled version if available
        if (exists($demangle->{$name})):
            $name = $demangle->{$name}

        # Escape special characters
        $name = escape_html($name);

        if $startline < 1:
            $startline = 1
        $countstyle = "coverFnLo" if $count == 0 else "coverFnHi"

        write_html(html_handle, <<END_OF_HTML)
        <tr>
              <td class="coverFn"><a href="$source#$startline">$name</a></td>
              <td class="$countstyle">$count</td>
            </tr>
END_OF_HTML

    write_html(html_handle, <<END_OF_HTML)
      </table>
      <br>
      </center>
END_OF_HTML

# NOK
def process_file($trunc_dir, $rel_dir, $filename) -> Tuple ???:

    global args
    global %info_data

    info("Processing file {}\n".format(apply_prefix(filename, @dir_prefix)))

    base_name: str = basename($filename);
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
    if $no_sourceview:
        return (ln_found, ln_hit,
                fn_found, fn_hit,
                br_found, br_hit,
                testdata, testfncdata, testbrdata)

    converted: Set[int] = get_converted_lines(testdata)

    page_title = f"LCOV - $test_title - {trunc_dir}/$base_name"

    # Generate source code view for this file
    with html_create(f"$rel_dir/$base_name.gcov.{args.html_ext}") as html_handle: 

        write_html_prolog(html_handle, base_dir, page_title)

        write_header(html_handle, 2,
                     f"{trunc_dir}/$base_name", "$rel_dir/$base_name"
                     ln_found, ln_hit,
                     fn_found, fn_hit,
                     br_found, br_hit,
                     0)

        @source = write_source(html_handle, $filename,
                               sumcount, checkdata, converted,
                               funcdata, sumbrcount)

        write_html_epilog(html_handle, base_dir, 1)

    if $fn_coverage:
        # Create function tables
        for line in @funcview_sortlist:
            write_function_page($base_dir, $rel_dir, trunc_dir,
                                base_name, $test_title,
                                ln_found, ln_hit,
                                fn_found, fn_hit,
                                br_found, br_hit,
                                $sumcount,    $funcdata,
                                $sumfnccount, testfncdata,
                                $sumbrcount,  testbrdata,
                                line)

    # Additional files are needed in case of frame output
    if ! $frames:
        return (ln_found, ln_hit,
                fn_found, fn_hit,
                br_found, br_hit,
                testdata, testfncdata, testbrdata)

    # Create overview png file
    gen_png("$rel_dir/$base_name.gcov.png",
            $dark_mode, $overview_width, $tab_size, @source)

    # Create frameset page
    with html_create(f"$rel_dir/$base_name.gcov.frameset.{args.html_ext}") as html_handle:
        write_frameset(html_handle, $base_dir, base_name, page_title)

    # Write overview frame
    with html_create(f"$rel_dir/$base_name.gcov.overview.{args.html_ext}") as html_handle:
        write_overview(html_handle, $base_dir, base_name, page_title, len(@source))

    return (ln_found, ln_hit,
            fn_found, fn_hit,
            br_found, br_hit,
            testdata, testfncdata, testbrdata)

# NOK
def get_converted_lines(testdata: Dict[str, Dict[???, ???]]) -> Set[int]:
    """Return set of line numbers of those lines which were only covered
    in converted data sets.
    """
    converted    = set()
    nonconverted = set()

    # Get a set containing line numbers with positive counts
    # both for converted and original data sets
    for testcase, testcount in testdata.items():
        # Check to see if this is a converted data set
        convset = converted if (testcase =~ /,diff$/) else nonconverted
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

#
# read_info_file(info_filename)
#
# Read in the contents of the .info file specified by INFO_FILENAME. Data will
# be returned as a reference to a hash containing the following mappings:
#
# %result: for each filename found in file -> \%data
#
# %data: "test"    -> \%testdata
#        "sum"     -> \%sumcount
#        "func"    -> \%funcdata
#        "found"   -> $ln_found (number of instrumented lines found in file)
#        "hit"     -> $ln_hit (number of executed lines in file)
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
# $brdata      : vector of items: block, branch, taken
# 
# Note that .info file sections referring to the same file and test name
# will automatically be combined by adding all execution counts.
#
# Note that if INFO_FILENAME ends with ".gz", it is assumed that the file
# is compressed using GZIP. If available, GUNZIP will be used to decompress
# this file.
#
# Die on error.
#

# NOK
def read_info_file($tracefile):

    my %result;            # Resulting hash: file -> data
    my $data;            # Data handle for current entry
    my $testdata;            #       "             "
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
    my $testname;            # Current test name
    my $filename;            # Current filename
    my $hitcount;            # Count for lines hit
    my $count;            # Execution count of current line
    my $negative;            # If set, warn about negative counts
    my $changed_testname;        # If set, warn about changed testname
    my $line_checksum;        # Checksum of current line
    my $notified_about_relative_paths;

    info("Reading data file $tracefile\n")

    # Check if file exists and is readable
    if not os.access($_[0], os.R_OK):
        die(f"ERROR: cannot read file $_[0]!\n")
    # Check if this is really a plain file
    fstatus = Path($_[0]).stat()
    if ! (-f _):
        die(f"ERROR: not a plain file: $_[0]!\n")

    # Check for .gz extension
    if $_[0] =~ /\.gz$/:
        # Check for availability of GZIP tool
        if system_no_output(1, "gunzip" ,"-h") != NO_ERROR:
            die("ERROR: gunzip command not available!\n")

        # Check integrity of compressed file
        if system_no_output(1, "gunzip", "-t", $_[0]) != NO_ERROR:
            die("ERROR: integrity check failed for compressed file $_[0]!\n")

        # Open compressed file
        INFO_HANDLE = open("-|", "gunzip -c '$_[0]'")
            or die("ERROR: cannot start gunzip to decompress file $_[0]!\n")
    else:
        # Open decompressed file
        INFO_HANDLE = open("<", $_[0])
            or die("ERROR: cannot read file $_[0]!\n")

    $testname = "";
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
                    $testname = defined($1) ? $1 : "";
                    if ($testname =~ s/\W/_/g)
                    {
                        $changed_testname = 1;
                    }
                    if (defined($2)):
                        $testname += $2

                    last;
                };

                /^[SK]F:(.*)/ && do
                {
                    # Filename information found
                    # Retrieve data for new entry
                    $filename = File::Spec->rel2abs($1, $cwd);

                    if (!File::Spec->file_name_is_absolute($1) and
                        !$notified_about_relative_paths):
                    {
                        info("Resolved relative source file ".
                             "path \"$1\" with CWD to ".
                             "\"$filename\".\n");
                        $notified_about_relative_paths = 1;
                    }

                    $data = $result[filename]

                    ($testdata, $sumcount, $funcdata, $checkdata,
                     $testfncdata, $sumfnccount, 
                     $testbrdata,  $sumbrcount,
                     _, _, _, _, _, _) = get_info_entry($data)

                    if defined($testname):
                        $testcount    = $testdata[$testname]
                        $testfnccount = $testfncdata[$testname]
                        $testbrcount  = $testbrdata[$testname]
                    else:
                        $testcount    = {}
                        $testfnccount = {}
                        $testbrcount  = {}

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
                            ($checkdata->{$1} ne $line_checksum)):
                        {
                            die("ERROR: checksum mismatch ".
                                "at $filename:$1\n");
                        }

                        $checkdata->{$1} = $line_checksum;
                    }

                    last;
                };

                /^FN:(\d+),([^,]+)/ && do
                {
                    last if (!$fn_coverage);

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
                    last if (!$fn_coverage);
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

                    if $br_coverage:
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
                    if ($filename)
                    {
                        # Store current section data
                        if (defined($testname))
                        {
                            $testdata->{$testname}    = $testcount;
                            $testfncdata->{$testname} = $testfnccount;
                            $testbrdata->{$testname}  = $testbrcount;
                        }    

                        set_info_entry($data,
                                       $testdata, $sumcount, $funcdata, $checkdata,
                                       $testfncdata, $sumfnccount,
                                       $testbrdata,  $sumbrcount)
                        $result[filename] = $data;

                        last;
                    }
                };

                # default
                last;
            }
        }

    close(INFO_HANDLE);

    # Calculate hit and found values for lines and functions of each file
    for $filename in keys(%result):
        $data = $result{$filename};

        ($testdata, $sumcount, _, _,
         $testfncdata, $sumfnccount,
         $testbrdata,  $sumbrcount,
         _, _, _, _, _, _) = get_info_entry($data)

        # Filter out empty files
        if len(%{$sumcount}) == 0:
            delete($result{$filename});
            continue

        # Filter out empty test cases
        for $testname in keys(%{$testdata}):
            if (!defined($testdata->{$testname}) or
                len(%{$testdata->{$testname}}) == 0):
                delete($testdata->{$testname});
                delete($testfncdata->{$testname});

        $data["found"] = len(%{$sumcount});
        $hitcount = 0;

        foreach (keys(%{$sumcount})):
            if ($sumcount->{$_} > 0):
                $hitcount += 1
        $data["hit"] = $hitcount;

        # Get found/hit values for function call data
        $data["f_found"] = len($sumfnccount)
        $hitcount = 0;

        foreach (keys(%{$sumfnccount})):
            if ($sumfnccount->{$_} > 0):
                $hitcount += 1
        $data["f_hit"] = $hitcount;

        # Combine branch data for the same branches
        _, $data["b_found"], $data->{"b_hit"} = compress_brcount($sumbrcount)
        for $testname in keys(%{$testbrdata}):
            compress_brcount($testbrdata->{$testname})

    if len(keys(%result)) == 0:
        die("ERROR: no valid records found in tracefile $tracefile\n")
    if $negative:
        warn("WARNING: negative counts found in tracefile "
             "$tracefile\n");
    if $changed_testname:
        warn("WARNING: invalid characters removed from testname in "
             "tracefile $tracefile\n")

    return (\%result)

#
# brcount_to_db(brcount)
#
# Convert brcount data to the following format:
#
# db:          line number    -> block hash
# block hash:  block number   -> branch hash
# branch hash: branch number  -> taken value
#

# NOK
def brcount_to_db($)
{
    my ($brcount) = @_;
    my $line;
    my $db;

    # Add branches to database
    foreach $line (keys(%{$brcount})) {
        my $brdata = $brcount->{$line};

        foreach my $entry (split(/:/, $brdata)) {
            my ($block, $branch, $taken) = split(/,/, $entry);
            my $old = $db->{$line}->{$block}->{$branch};

            if (!defined($old) or $old == "-") {
                $old = $taken;
            } elsif ($taken != "-") {
                $old += $taken;
            }

            $db->{$line}->{$block}->{$branch} = $old;
        }
    }

    return $db;
}

#
# get_prefix(min_dir, filename_list)
#
# Search FILENAME_LIST for a directory prefix which is common to as many
# list entries as possible, so that removing this prefix will minimize the
# sum of the lengths of all resulting shortened filenames while observing
# that no filename has less than MIN_DIR parent directories.
#

# NOK
def get_prefix($@)
{
    my ($min_dir, @filename_list) = @_;
    my %prefix;            # mapping: prefix -> sum of lengths
    my $current;            # Temporary iteration variable

    # Find list of prefixes
    for $current in @filename_list:
        while ($current = shorten_prefix($current)):
            $current += "/"

            # Skip rest if the remaining prefix has already been
            # added to hash
            if (exists($prefix{$current})) { last; }

            # Initialize with 0
            $prefix{$current} = "0"

    # Remove all prefixes that would cause filenames to have less than
    # the minimum number of parent directories
    foreach my $filename (@filename_list) {
        my $dir = dirname($filename);

        for (my $i = 0; $i < $min_dir; $i++) {
            delete($prefix{$dir."/"});
            $dir = shorten_prefix($dir);
        }
    }

    # Check if any prefix remains
    if (!%prefix):
        return _

    # Calculate sum of lengths for all prefixes
    for $current in %prefix.keys():
        foreach (@filename_list):
            # Add original length
            $prefix{$current} += length($_)

            # Check whether prefix matches
            if substr($_, 0, length($current)) == $current:
                # Subtract prefix length for this filename
                $prefix{$current} -= length($current)

    # Find and return prefix with minimal sum
    $current = %prefix.keys()[0]
    for pkey in %prefix.keys():
        if $prefix{pkey} < $prefix{$current}:
            $current = pkey

    $current =~ s/\/$//;

    return($current);
}


def shorten_prefix(prefix: str, sep: str = "/") -> str:
    """Return PREFIX shortened by last directory component."""
    list = prefix.split(sep)
    if list: list.pop()
    return sep.join(list)


def get_dir_list(filename_list: List[str]) -> List[str]:
    """Return sorted list of directories for each entry in given FILENAME_LIST."""
    result = set()
    for fname in filename_list:
        result.add(shorten_prefix(fname))
    return sorted(result)

# NOK
def get_relative_base_path(subdir: str):
    """Return a relative path string which references the base path when
    applied in SUBDIRECTORY.
    
    Example: get_relative_base_path("fs/mm") -> "../../"
    """
    my $result = ""

    # Make an empty directory path a special case
    if subdir:
        # Count number of /s in path
        index = (subdir =~ s/\//\//g)
        # Add a ../ to $result for each / in the directory path + 1
        for (; index >= 0; index--):
            result += "../"

    return result

# NOK
def read_testfile(test_filename: Path) -> Dict[str, str]:
    # Read in file TEST_FILENAME which contains test descriptions in the format:
    #
    #   TN:<whitespace><test name>
    #   TD:<whitespace><test description>
    #
    # for each test case. Return a reference to a hash containing a mapping
    #
    #   test name -> test description.
    #
    # Die on error.

    result: Dict[str, str] = {}

    try:
        fhandle = test_filename.open("rt")
    except:
        die(f"ERROR: cannot open {test_filename}!\n")

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
                if (test_name =~ s/\W/_/g):
                    changed_testname = True
                continue

            # Match lines beginning with TD:<whitespace(s)>
            match = re.match(r"^TD:\s+(.*?)\s*$", line)
            if match:
                if test_name is None:
                    die(f"ERROR: Found test description without prior test name in {test_filename}:$.\n")

                if test_name not in result: result[test_name] = ""
                # Check for empty line
                if match.group(1):
                    # Add description to hash
                    result[test_name] += " " + match.group(1)
                else:
                    # Add empty line
                    result[test_name] += "\n\n"
                continue

    if changed_testname:
        warn("WARNING: invalid characters removed from testname in "
             f"descriptions file {test_filename}\n")

    return result


#
# escape_html(STRING)
#
# Return a copy of STRING in which all occurrences of HTML special characters
# are escaped.
#

# NOK
def escape_html($string: str):

    if ! $string:
        return ""

    $string =~ s/&/&amp;/g;        # & -> &amp;
    $string =~ s/</&lt;/g;        # < -> &lt;
    $string =~ s/>/&gt;/g;        # > -> &gt;
    $string =~ s/\"/&quot;/g;    # " -> &quot;

    while ($string =~ /^([^\t]*)(\t)/):
        my $replacement = " "x($tab_size - (length($1) % $tab_size));
        $string =~ s/^([^\t]*)(\t)/$1$replacement/;

    $string =~ s/\n/<br>/g;        # \n -> <br>

    return $string;

# NOK
def write_description_file(description: Dict[???, ???],
                           ln_found: int, ln_hit: int,
                           fn_found: int, fn_hit: int,
                           br_found: int, br_hit: int):
    # write_description_file(descriptions, overall_found, overall_hit,
    #                        total_fn_found, total_fn_hit, total_br_found,
    #                        total_br_hit)
    #
    # Write HTML file containing all test case descriptions. DESCRIPTIONS is a
    # reference to a hash containing a mapping
    #
    #   test case name -> test case description
    #
    # Die on error.

    global options
    global args

    with html_create(f"descriptions.{args.html_ext}") as html_handle:
        write_html_prolog(html_handle, "", "LCOV - test case descriptions")
        write_header(html_handle, 3,
                     "", "",
                     ln_found, ln_hit,
                     fn_found, fn_hit,
                     br_found, br_hit, 0)
        write_test_table_prolog(html_handle,
                                "Test case descriptions - alphabetical list")

        for test_name in sorted(description.keys()):
            desc = description[test_name]
            if not options.rc_desc_html:
                desc = escape_html(desc)
            write_test_table_entry(html_handle, test_name, desc)

        write_test_table_epilog(html_handle)
        write_html_epilog(html_handle, "")

# NOK
def write_png_files():
    """Create all necessary .png files for the HTML-output
    in the current directory. .png-files are used as bar graphs.

    Die on error.
    """
    global dark_mode
    global $sort

    data: Dict[str, object] = {}

    if dark_mode:
        data["ruby.png"] =
            [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, 0x00,
             0x00, 0x00, 0x0d, 0x49, 0x48, 0x44, 0x52, 0x00, 0x00,
             0x00, 0x01, 0x00, 0x00, 0x00, 0x01, 0x01, 0x03, 0x00,
             0x00, 0x00, 0x25, 0xdb, 0x56, 0xca, 0x00, 0x00, 0x00,
             0x06, 0x50, 0x4c, 0x54, 0x45, 0x80, 0x1b, 0x18, 0x00,
             0x00, 0x00, 0x39, 0x4a, 0x74, 0xf4, 0x00, 0x00, 0x00,
             0x0a, 0x49, 0x44, 0x41, 0x54, 0x08, 0xd7, 0x63, 0x60,
             0x00, 0x00, 0x00, 0x02, 0x00, 0x01, 0xe2, 0x21, 0xbc,
             0x33, 0x00, 0x00, 0x00, 0x00, 0x49, 0x45, 0x4e, 0x44,
             0xae, 0x42, 0x60, 0x82]
    else:
        data["ruby.png"] =
            [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, 0x00,
             0x00, 0x00, 0x0d, 0x49, 0x48, 0x44, 0x52, 0x00, 0x00,
             0x00, 0x01, 0x00, 0x00, 0x00, 0x01, 0x01, 0x03, 0x00,
             0x00, 0x00, 0x25, 0xdb, 0x56, 0xca, 0x00, 0x00, 0x00,
             0x07, 0x74, 0x49, 0x4d, 0x45, 0x07, 0xd2, 0x07, 0x11,
             0x0f, 0x18, 0x10, 0x5d, 0x57, 0x34, 0x6e, 0x00, 0x00,
             0x00, 0x09, 0x70, 0x48, 0x59, 0x73, 0x00, 0x00, 0x0b,
             0x12, 0x00, 0x00, 0x0b, 0x12, 0x01, 0xd2, 0xdd, 0x7e,
             0xfc, 0x00, 0x00, 0x00, 0x04, 0x67, 0x41, 0x4d, 0x41,
             0x00, 0x00, 0xb1, 0x8f, 0x0b, 0xfc, 0x61, 0x05, 0x00,
             0x00, 0x00, 0x06, 0x50, 0x4c, 0x54, 0x45, 0xff, 0x35,
             0x2f, 0x00, 0x00, 0x00, 0xd0, 0x33, 0x9a, 0x9d, 0x00,
             0x00, 0x00, 0x0a, 0x49, 0x44, 0x41, 0x54, 0x78, 0xda,
             0x63, 0x60, 0x00, 0x00, 0x00, 0x02, 0x00, 0x01, 0xe5,
             0x27, 0xde, 0xfc, 0x00, 0x00, 0x00, 0x00, 0x49, 0x45,
             0x4e, 0x44, 0xae, 0x42, 0x60, 0x82]

    if dark_mode:
        data["amber.png"] =
            [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, 0x00,
             0x00, 0x00, 0x0d, 0x49, 0x48, 0x44, 0x52, 0x00, 0x00,
             0x00, 0x01, 0x00, 0x00, 0x00, 0x01, 0x01, 0x03, 0x00,
             0x00, 0x00, 0x25, 0xdb, 0x56, 0xca, 0x00, 0x00, 0x00,
             0x06, 0x50, 0x4c, 0x54, 0x45, 0x99, 0x86, 0x30, 0x00,
             0x00, 0x00, 0x51, 0x83, 0x43, 0xd7, 0x00, 0x00, 0x00,
             0x0a, 0x49, 0x44, 0x41, 0x54, 0x08, 0xd7, 0x63, 0x60,
             0x00, 0x00, 0x00, 0x02, 0x00, 0x01, 0xe2, 0x21, 0xbc,
             0x33, 0x00, 0x00, 0x00, 0x00, 0x49, 0x45, 0x4e, 0x44,
             0xae, 0x42, 0x60, 0x82]
    else:
        data["amber.png"] =
            [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, 0x00,
             0x00, 0x00, 0x0d, 0x49, 0x48, 0x44, 0x52, 0x00, 0x00,
             0x00, 0x01, 0x00, 0x00, 0x00, 0x01, 0x01, 0x03, 0x00,
             0x00, 0x00, 0x25, 0xdb, 0x56, 0xca, 0x00, 0x00, 0x00,
             0x07, 0x74, 0x49, 0x4d, 0x45, 0x07, 0xd2, 0x07, 0x11,
             0x0f, 0x28, 0x04, 0x98, 0xcb, 0xd6, 0xe0, 0x00, 0x00,
             0x00, 0x09, 0x70, 0x48, 0x59, 0x73, 0x00, 0x00, 0x0b,
             0x12, 0x00, 0x00, 0x0b, 0x12, 0x01, 0xd2, 0xdd, 0x7e,
             0xfc, 0x00, 0x00, 0x00, 0x04, 0x67, 0x41, 0x4d, 0x41,
             0x00, 0x00, 0xb1, 0x8f, 0x0b, 0xfc, 0x61, 0x05, 0x00,
             0x00, 0x00, 0x06, 0x50, 0x4c, 0x54, 0x45, 0xff, 0xe0,
             0x50, 0x00, 0x00, 0x00, 0xa2, 0x7a, 0xda, 0x7e, 0x00,
             0x00, 0x00, 0x0a, 0x49, 0x44, 0x41, 0x54, 0x78, 0xda,
             0x63, 0x60, 0x00, 0x00, 0x00, 0x02, 0x00, 0x01, 0xe5,
             0x27, 0xde, 0xfc, 0x00, 0x00, 0x00, 0x00, 0x49, 0x45,
             0x4e, 0x44, 0xae, 0x42, 0x60, 0x82]

    if dark_mode:
        data["emerald.png"] =
            [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, 0x00,
             0x00, 0x00, 0x0d, 0x49, 0x48, 0x44, 0x52, 0x00, 0x00,
             0x00, 0x01, 0x00, 0x00, 0x00, 0x01, 0x01, 0x03, 0x00,
             0x00, 0x00, 0x25, 0xdb, 0x56, 0xca, 0x00, 0x00, 0x00,
             0x06, 0x50, 0x4c, 0x54, 0x45, 0x00, 0x66, 0x00, 0x0a,
             0x0a, 0x0a, 0xa4, 0xb8, 0xbf, 0x60, 0x00, 0x00, 0x00,
             0x0a, 0x49, 0x44, 0x41, 0x54, 0x08, 0xd7, 0x63, 0x60,
             0x00, 0x00, 0x00, 0x02, 0x00, 0x01, 0xe2, 0x21, 0xbc,
             0x33, 0x00, 0x00, 0x00, 0x00, 0x49, 0x45, 0x4e, 0x44,
             0xae, 0x42, 0x60, 0x82]
    else:
        data["emerald.png"] =
            [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, 0x00,
             0x00, 0x00, 0x0d, 0x49, 0x48, 0x44, 0x52, 0x00, 0x00,
             0x00, 0x01, 0x00, 0x00, 0x00, 0x01, 0x01, 0x03, 0x00,
             0x00, 0x00, 0x25, 0xdb, 0x56, 0xca, 0x00, 0x00, 0x00,
             0x07, 0x74, 0x49, 0x4d, 0x45, 0x07, 0xd2, 0x07, 0x11,
             0x0f, 0x22, 0x2b, 0xc9, 0xf5, 0x03, 0x33, 0x00, 0x00,
             0x00, 0x09, 0x70, 0x48, 0x59, 0x73, 0x00, 0x00, 0x0b,
             0x12, 0x00, 0x00, 0x0b, 0x12, 0x01, 0xd2, 0xdd, 0x7e,
             0xfc, 0x00, 0x00, 0x00, 0x04, 0x67, 0x41, 0x4d, 0x41,
             0x00, 0x00, 0xb1, 0x8f, 0x0b, 0xfc, 0x61, 0x05, 0x00,
             0x00, 0x00, 0x06, 0x50, 0x4c, 0x54, 0x45, 0x1b, 0xea,
             0x59, 0x0a, 0x0a, 0x0a, 0x0f, 0xba, 0x50, 0x83, 0x00,
             0x00, 0x00, 0x0a, 0x49, 0x44, 0x41, 0x54, 0x78, 0xda,
             0x63, 0x60, 0x00, 0x00, 0x00, 0x02, 0x00, 0x01, 0xe5,
             0x27, 0xde, 0xfc, 0x00, 0x00, 0x00, 0x00, 0x49, 0x45,
             0x4e, 0x44, 0xae, 0x42, 0x60, 0x82]

    if dark_mode:
        data["snow.png"] =
            [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, 0x00,
             0x00, 0x00, 0x0d, 0x49, 0x48, 0x44, 0x52, 0x00, 0x00,
             0x00, 0x01, 0x00, 0x00, 0x00, 0x01, 0x01, 0x03, 0x00,
             0x00, 0x00, 0x25, 0xdb, 0x56, 0xca, 0x00, 0x00, 0x00,
             0x06, 0x50, 0x4c, 0x54, 0x45, 0xdd, 0xdd, 0xdd, 0x00,
             0x00, 0x00, 0xae, 0x9c, 0x6c, 0x92, 0x00, 0x00, 0x00,
             0x0a, 0x49, 0x44, 0x41, 0x54, 0x08, 0xd7, 0x63, 0x60,
             0x00, 0x00, 0x00, 0x02, 0x00, 0x01, 0xe2, 0x21, 0xbc,
             0x33, 0x00, 0x00, 0x00, 0x00, 0x49, 0x45, 0x4e, 0x44,
             0xae, 0x42, 0x60, 0x82]
    else:
        data["snow.png"] =
            [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, 0x00,
             0x00, 0x00, 0x0d, 0x49, 0x48, 0x44, 0x52, 0x00, 0x00,
             0x00, 0x01, 0x00, 0x00, 0x00, 0x01, 0x01, 0x03, 0x00,
             0x00, 0x00, 0x25, 0xdb, 0x56, 0xca, 0x00, 0x00, 0x00,
             0x07, 0x74, 0x49, 0x4d, 0x45, 0x07, 0xd2, 0x07, 0x11,
             0x0f, 0x1e, 0x1d, 0x75, 0xbc, 0xef, 0x55, 0x00, 0x00,
             0x00, 0x09, 0x70, 0x48, 0x59, 0x73, 0x00, 0x00, 0x0b,
             0x12, 0x00, 0x00, 0x0b, 0x12, 0x01, 0xd2, 0xdd, 0x7e,
             0xfc, 0x00, 0x00, 0x00, 0x04, 0x67, 0x41, 0x4d, 0x41,
             0x00, 0x00, 0xb1, 0x8f, 0x0b, 0xfc, 0x61, 0x05, 0x00,
             0x00, 0x00, 0x06, 0x50, 0x4c, 0x54, 0x45, 0xff, 0xff,
             0xff, 0x00, 0x00, 0x00, 0x55, 0xc2, 0xd3, 0x7e, 0x00,
             0x00, 0x00, 0x0a, 0x49, 0x44, 0x41, 0x54, 0x78, 0xda,
             0x63, 0x60, 0x00, 0x00, 0x00, 0x02, 0x00, 0x01, 0xe5,
             0x27, 0xde, 0xfc, 0x00, 0x00, 0x00, 0x00, 0x49, 0x45,
             0x4e, 0x44, 0xae, 0x42, 0x60, 0x82]

    data["glass.png"] =
        [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, 0x00, 0x00, 
         0x00, 0x0d, 0x49, 0x48, 0x44, 0x52, 0x00, 0x00, 0x00, 0x01, 
         0x00, 0x00, 0x00, 0x01, 0x01, 0x03, 0x00, 0x00, 0x00, 0x25, 
         0xdb, 0x56, 0xca, 0x00, 0x00, 0x00, 0x04, 0x67, 0x41, 0x4d, 
         0x41, 0x00, 0x00, 0xb1, 0x8f, 0x0b, 0xfc, 0x61, 0x05, 0x00, 
         0x00, 0x00, 0x06, 0x50, 0x4c, 0x54, 0x45, 0xff, 0xff, 0xff, 
         0x00, 0x00, 0x00, 0x55, 0xc2, 0xd3, 0x7e, 0x00, 0x00, 0x00, 
         0x01, 0x74, 0x52, 0x4e, 0x53, 0x00, 0x40, 0xe6, 0xd8, 0x66, 
         0x00, 0x00, 0x00, 0x01, 0x62, 0x4b, 0x47, 0x44, 0x00, 0x88, 
         0x05, 0x1d, 0x48, 0x00, 0x00, 0x00, 0x09, 0x70, 0x48, 0x59, 
         0x73, 0x00, 0x00, 0x0b, 0x12, 0x00, 0x00, 0x0b, 0x12, 0x01, 
         0xd2, 0xdd, 0x7e, 0xfc, 0x00, 0x00, 0x00, 0x07, 0x74, 0x49, 
         0x4d, 0x45, 0x07, 0xd2, 0x07, 0x13, 0x0f, 0x08, 0x19, 0xc4, 
         0x40, 0x56, 0x10, 0x00, 0x00, 0x00, 0x0a, 0x49, 0x44, 0x41, 
         0x54, 0x78, 0x9c, 0x63, 0x60, 0x00, 0x00, 0x00, 0x02, 0x00, 
         0x01, 0x48, 0xaf, 0xa4, 0x71, 0x00, 0x00, 0x00, 0x00, 0x49, 
         0x45, 0x4e, 0x44, 0xae, 0x42, 0x60, 0x82]

    if $sort;
        if dark_mode:
            data["updown.png"] =
                [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, 0x00,
                 0x00, 0x00, 0x0d, 0x49, 0x48, 0x44, 0x52, 0x00, 0x00,
                 0x00, 0x0a, 0x00, 0x00, 0x00, 0x0e, 0x08, 0x06, 0x00,
                 0x00, 0x00, 0x16, 0xa3, 0x8d, 0xab, 0x00, 0x00, 0x00,
                 0x43, 0x49, 0x44, 0x41, 0x54, 0x28, 0xcf, 0x63, 0x60,
                 0x40, 0x03, 0x77, 0xef, 0xde, 0xfd, 0x7f, 0xf7, 0xee,
                 0xdd, 0xff, 0xe8, 0xe2, 0x8c, 0xe8, 0x8a, 0x90, 0xf9,
                 0xca, 0xca, 0xca, 0x8c, 0x18, 0x0a, 0xb1, 0x99, 0x82,
                 0xac, 0x98, 0x11, 0x9f, 0x22, 0x64, 0xc5, 0x8c, 0x84,
                 0x14, 0xc1, 0x00, 0x13, 0xc3, 0x80, 0x01, 0xea, 0xbb,
                 0x91, 0xf8, 0xe0, 0x21, 0x29, 0xc0, 0x89, 0x89, 0x42,
                 0x06, 0x62, 0x13, 0x05, 0x00, 0xe1, 0xd3, 0x2d, 0x91,
                 0x93, 0x15, 0xa4, 0xb2, 0x00, 0x00, 0x00, 0x00, 0x49,
                 0x45, 0x4e, 0x44, 0xae, 0x42, 0x60, 0x82]
        else:
            data["updown.png"] =
                [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, 0x00,
                 0x00, 0x00, 0x0d, 0x49, 0x48, 0x44, 0x52, 0x00, 0x00,
                 0x00, 0x0a, 0x00, 0x00, 0x00, 0x0e, 0x08, 0x06, 0x00,
                 0x00, 0x00, 0x16, 0xa3, 0x8d, 0xab, 0x00, 0x00, 0x00,
                 0x3c, 0x49, 0x44, 0x41, 0x54, 0x28, 0xcf, 0x63, 0x60,
                 0x40, 0x03, 0xff, 0xa1, 0x00, 0x5d, 0x9c, 0x11, 0x5d,
                 0x11, 0x8a, 0x24, 0x23, 0x23, 0x23, 0x86, 0x42, 0x6c,
                 0xa6, 0x20, 0x2b, 0x66, 0xc4, 0xa7, 0x08, 0x59, 0x31,
                 0x23, 0x21, 0x45, 0x30, 0xc0, 0xc4, 0x30, 0x60, 0x80,
                 0xfa, 0x6e, 0x24, 0x3e, 0x78, 0x48, 0x0a, 0x70, 0x62,
                 0xa2, 0x90, 0x81, 0xd8, 0x44, 0x01, 0x00, 0xe9, 0x5c,
                 0x2f, 0xf5, 0xe2, 0x9d, 0x0f, 0xf9, 0x00, 0x00, 0x00,
                 0x00, 0x49, 0x45, 0x4e, 0x44, 0xae, 0x42, 0x60, 0x82]

    for fname, content in data.items():
        try:
            fhandle = Path(fname).open("wb")
        except:
            die("ERROR: cannot create {fname}!\n")
        with fhandle:
            fhandle.write(map(chr, content))

# NOK
def write_htaccess_file():

    local *HTACCESS_HANDLE;
    my $htaccess_data;

    open(*HTACCESS_HANDLE, ">", ".htaccess")
        or die("ERROR: cannot open .htaccess for writing!\n");

    $htaccess_data = (<<"END_OF_HTACCESS")
AddEncoding x-gzip .html
END_OF_HTACCESS
    ;

    print(HTACCESS_HANDLE $htaccess_data);
    close(*HTACCESS_HANDLE);

# NOK
def write_css_file():
    # Write the cascading style sheet file gcov.css to the current directory.
    # This file defines basic layout attributes of all generated HTML pages.

    local *CSS_HANDLE;

    # Check for a specified external style sheet file
    if ($css_filename)
    {
        # Simply copy that file
        system("cp", $css_filename, "gcov.css")
            and die("ERROR: cannot copy file $css_filename!\n");
        return;
    }

    open(CSS_HANDLE, ">", "gcov.css")
        or die ("ERROR: cannot open gcov.css for writing!\n");


    # *************************************************************

    my $css_data = ($_=<<"END_OF_CSS")
    # !!! read from html/genhtml.css
END_OF_CSS
    ;

    # *************************************************************


    # Remove leading tab from all lines
    $css_data =~ s/^\t//gm;
    my %palette = ( 'COLOR_00' => "000000",
            'COLOR_01' => "00cb40",
            'COLOR_02' => "284fa8",
            'COLOR_03' => "6688d4",
            'COLOR_04' => "a7fc9d",
            'COLOR_05' => "b5f7af",
            'COLOR_06' => "b8d0ff",
            'COLOR_07' => "cad7fe",
            'COLOR_08' => "dae7fe",
            'COLOR_09' => "efe383",
            'COLOR_10' => "ff0000",
            'COLOR_11' => "ff0040",
            'COLOR_12' => "ff6230",
            'COLOR_13' => "ffea20",
            'COLOR_14' => "ffffff",
            'COLOR_15' => "284fa8",
            'COLOR_16' => "ffffff");

    if dark_mode:
        %palette =  (   'COLOR_00' => "e4e4e4",
                'COLOR_01' => "58a6ff",
                'COLOR_02' => "8b949e",
                'COLOR_03' => "3b4c71",
                'COLOR_04' => "006600",
                'COLOR_05' => "4b6648",
                'COLOR_06' => "495366",
                'COLOR_07' => "143e4f",
                'COLOR_08' => "1c1e23",
                'COLOR_09' => "202020",
                'COLOR_10' => "801b18",
                'COLOR_11' => "66001a",
                'COLOR_12' => "772d16",
                'COLOR_13' => "796a25",
                'COLOR_14' => "000000",
                'COLOR_15' => "58a6ff",
                'COLOR_16' => "eeeeee");

    # Apply palette
    for (keys %palette) {
            $css_data =~ s/$_/$palette{$_}/gm;
    }

    print(CSS_HANDLE $css_data);

    close(CSS_HANDLE);

# NOK
def get_bar_graph_code($base_dir, $found, $hit):
    # get_bar_graph_code(base_dir, cover_found, cover_hit)
    #
    # Return a string containing HTML code which implements a bar graph display
    # for a coverage rate of cover_hit * 100 / cover_found.
    my $rate;
    my $alt;
    my $width;
    my $remainder;
    my $png_name;
    my $graph_code;

    # Check number of instrumented lines
    if ($_[1] == 0) { return ""; }

    $alt       = rate($hit, $found, "%")
    $width     = rate($hit, $found, None, 0)
    $remainder = 100 - $width

    # Decide which .png file to use
    $png_name = $rate_png[classify_rate($found, $hit, $med_limit, $hi_limit)]

    if ($width == 0)
    {
        # Zero coverage
        $graph_code = (<<END_OF_HTML)
            <table border=0 cellspacing=0 cellpadding=1><tr><td class="coverBarOutline"><img src="$_[0]snow.png" width=100 height=10 alt="$alt"></td></tr></table>
END_OF_HTML
        ;
    }
    elsif ($width == 100)
    {
        # Full coverage
        $graph_code = (<<END_OF_HTML)
        <table border=0 cellspacing=0 cellpadding=1><tr><td class="coverBarOutline"><img src="$_[0]$png_name" width=100 height=10 alt="$alt"></td></tr></table>
END_OF_HTML
        ;
    }
    else
    {
        # Positive coverage
        $graph_code = (<<END_OF_HTML)
        <table border=0 cellspacing=0 cellpadding=1><tr><td class="coverBarOutline"><img src="$_[0]$png_name" width=$width height=10 alt="$alt"><img src="$_[0]snow.png" width=$remainder height=10 alt="$alt"></td></tr></table>
END_OF_HTML
        ;
    }

    # Remove leading tabs from all lines
    $graph_code =~ s/^\t+//gm;
    $graph_code = $graph_code.rstrip("\n")

    return $graph_code


def classify_rate(found: int, hit: int, med_limit: int, high_limit: int) -> int:
    # classify_rate(found, hit, med_limit, high_limit)
    #
    # Return 0 for low rate, 1 for medium rate and 2 for high rate.
    #
    if found == 0:
        return 2
    rate = rate(hit, found)
    if rate < med_limit:
        return 0
    elif rate < high_limit:
        return 1
    return 2

# NOK
def write_html(html_handle, $html_code):
    """Write out HTML_CODE to FILEHANDLE while removing a leading tabulator mark
    in each line of HTML_CODE.
    
    Remove leading tab from all lines
    """
    $html_code =~ s/^\t//gm;
    try:
        print($html_code, end="", file=html_handle)
    except Exception as exc:
        or die(f"ERROR: cannot write HTML data ({exc})\n")

# NOK
def write_html_prolog(html_handle, basedir, pagetitle):
    # Write an HTML prolog common to all HTML files to FILEHANDLE. PAGETITLE will
    # be used as HTML page title. BASE_DIR contains a relative path which points
    # to the base directory.
    #
    global html_prolog

    prolog = html_prolog
    prolog =~ rf"s\@pagetitle\@", rf"$pagetitle"g
    prolog =~ rf"s\@basedir\@",   rf"$basedir"g

    write_html(html_handle, prolog)

# NOK
def write_header_prolog(html_handle, base_dir):
    """Write beginning of page header HTML code."""

    # !!! read from html/header_prolog.html
    write_html(html_handle, <<END_OF_HTML)
END_OF_HTML


#
# write_header_line(handle, content)
#
# Write a header line with the specified table contents.
#

# NOK
def write_header_line($handle, @content):

    write_html($handle, "          <tr>\n");
    foreach $entry (@content) {
        my ($width, $class, $text, $colspan) = @{$entry};

        if (defined($width)) {
            $width = " width=\"$width\"";
        else:
            $width = "";
        }
        if (defined($class)) {
            $class = " class=\"$class\"";
        else:
            $class = "";
        }
        if (defined($colspan)) {
            $colspan = " colspan=\"$colspan\"";
        else:
            $colspan = "";
        }
        $text = "" if (!defined($text));
        write_html($handle,
               "            <td$width$class$colspan>$text</td>\n");
    }
    write_html($handle, "          </tr>\n");


# NOK
def write_header_epilog(html_handle, base_dir)
    # Write end of page header HTML code.
    #
    # !!! read from html/header_epilog.html
    write_html(html_handle, <<END_OF_HTML)
END_OF_HTML

# NOK
def write_test_table_prolog(html_handle, table_heading)
    # Write heading for test case description table.
    #
    # !!! read from html/test_table_prolog.html
    write_html(html_handle, <<END_OF_HTML)
END_OF_HTML

# NOK
def write_test_table_epilog(html_handle):
    # Write end of test description table HTML code.
    #
    # !!! read from html/test_table_epilog.html
    write_html(html_handle, <<END_OF_HTML)
END_OF_HTML

# NOK
def write_test_table_entry(html_handle, test_name, test_description):
    """Write entry for the test table."""

    # *************************************************************

    write_html(html_handle, <<END_OF_HTML)
          <dt>$_[1]<a name="$_[1]">&nbsp;</a></dt>
          <dd>$_[2]<br><br></dd>
END_OF_HTML


# NOK
def fmt_centered($$):
    my ($width, $text) = @_;

    my $w0 = length($text);
    my $w1 = $width > $w0 ? int(($width - $w0) / 2) : 0;
    my $w2 = $width > $w0 ? $width - $w0 - $w1 : 0;

    return (" "x$w1).$text.(" "x$w2);

# NOK
def get_block_len(block: List[???]) -> int:
    """Calculate total text length of all branches in a block of branches."""
    return sum((branch[BR_LEN] for branch in block), 0)

# NOK
def write_html_epilog(html_handle, base_dir[, break_frames]):
    # write_html_epilog(html_handle, base_dir[, break_frames])
    #
    # Write HTML page footer to FILEHANDLE. BREAK_FRAMES should be set when
    # this page is embedded in a frameset, clicking the URL link will then
    # break this frameset.

    my $basedir = $_[1];

    break_code = ' target="_parent"' if defined($_[2]) else ""

    # *************************************************************

    write_html(html_handle, <<END_OF_HTML)
      <table width="100%" border=0 cellspacing=0 cellpadding=0>
        <tr><td class="ruler"><img src="$_[1]glass.png" width=3 height=3 alt=""></td></tr>
        <tr><td class="versionInfo">Generated by: <a href="$lcov_url"$break_code>$lcov_version</a></td></tr>
      </table>
      <br>
END_OF_HTML

    epilog = html_epilog
    epilog =~ s/\@basedir\@/$basedir/g
    write_html(html_handle, epilog)

# NOK
def write_frameset(html_handle, basedir, basename, pagetitle):

    global args

    $frame_width = $overview_width + 40

    # *************************************************************

    write_html(html_handle, <<END_OF_HTML)
    <!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Frameset//EN">

    <html lang="en">

    <head>
      <meta http-equiv="Content-Type" content="text/html; charset=$charset">
      <title>$_[3]</title>
      <link rel="stylesheet" type="text/css" href="$_[1]gcov.css">
    </head>

    <frameset cols="$frame_width,*">
      <frame src=f"$_[2].gcov.overview.{args.html_ext}" name="overview">
      <frame src=f"$_[2].gcov.{args.html_ext}" name="source">
      <noframes>
        <center>Frames not supported by your browser!<br></center>
      </noframes>
    </frameset>

    </html>
END_OF_HTML

# NOK
def write_overview_line(html_handle, basename, line, link   *$$$):

    y1 = $_[2] - 1;
    y2 = $y1 + $nav_resolution - 1;
    x2 = $overview_width - 1;

    # *************************************************************

    write_html(html_handle, <<END_OF_HTML)
        <area shape="rect" coords="0,$y1,$x2,$y2" href="$_[1].gcov.$html_ext#$_[3]" target="source" alt="overview">
END_OF_HTML

# NOK
def write_overview(html_handle, basedir, basename, pagetitle, lines   *$$$$):

    max_line = $_[4] - 1

    # *************************************************************

    write_html(html_handle, <<END_OF_HTML)
    <!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN">

    <html lang="en">

    <head>
      <title>$_[3]</title>
      <meta http-equiv="Content-Type" content="text/html; charset=$charset">
      <link rel="stylesheet" type="text/css" href="$_[1]gcov.css">
    </head>

    <body>
      <map name="overview">
END_OF_HTML

    # Make offset the next higher multiple of $nav_resolution
    offset = ($nav_offset + $nav_resolution - 1) / $nav_resolution;
    offset = sprintf("%d", offset ) * $nav_resolution;

    # Create image map for overview image
    for (index = 1; index <= $_[4]; index += $nav_resolution):
        # Enforce nav_offset
        if index < offset + 1:
            write_overview_line(html_handle, $_[2], index, 1)
        else:
            write_overview_line(html_handle, $_[2], index, index - offset)

    # *************************************************************

    write_html(html_handle, <<END_OF_HTML)
      </map>

      <center>
      <a href="$_[2].gcov.$html_ext#top" target="source">Top</a><br><br>
      <img src="$_[2].gcov.png" width=$overview_width height={max_line} alt="Overview" border=0 usemap="#overview">
      </center>
    </body>
    </html>
END_OF_HTML

# NOK
def write_header(html_handle, $type,        
                 $trunc_name,  $rel_filename,
                 $ln_found, $ln_hit,      
                 $fn_found, $fn_hit,      
                 $br_found, $br_hit,      
                 sort_type: int):

    global args
    global test_description

    # write_header(html_handle, type, trunc_file_name, rel_file_name, ln_found,
    # ln_hit, funcs_found, funcs_hit, sort_type)
    #
    # Write a complete standard page header. TYPE may be (0, 1, 2, 3, 4)
    # corresponding to (directory view header, file view header, source view
    # header, test case description header, function view header)

    my $base_dir;
    my $view;
    my $test;
    my $base_name;
    my $style;
    my $rate;
    my $num_rows;
    my $i;
    my $esc_trunc_name = escape_html($trunc_name);

    $base_name = basename($rel_filename);

    # Prepare text for "current view" field
    if ($type == $HDR_DIR):
        # Main overview
        $base_dir = ""
        $view = $overview_title;
    elif $type == $HDR_FILE:
        # Directory overview
        $base_dir = get_relative_base_path($rel_filename);
        $view = "<a href=\"$base_dir" + f"index.{args.html_ext}\">".
                "$overview_title</a> - $esc_trunc_name"
    elif $type == $HDR_SOURCE or $type == $HDR_FUNC:
    {
        # File view
        dir_name      = dirname($rel_filename)
        esc_base_name = escape_html($base_name)
        esc_dir_name  = escape_html($dir_name)

        $base_dir = get_relative_base_path($dir_name);
        if $frames:
            # Need to break frameset when clicking any of these
            # links
            $view = "<a href=\"$base_dir" + f"index.{args.html_ext}\" ".
                    "target=\"_parent\">$overview_title</a> - ".
                    f"<a href=\"index.{args.html_ext}\" target=\"_parent\">".
                    "$esc_dir_name</a> - $esc_base_name"
        else:
            $view = "<a href=\"$base_dir" + f"index.{args.html_ext}\">".
                    "$overview_title</a> - ".
                    f"<a href=\"index.{args.html_ext}\">".
                    "$esc_dir_name</a> - $esc_base_name"

        # Add function suffix
        if $fn_coverage:
            $view += "<span style=\"font-size: 80%;\">"
            if ($type == $HDR_SOURCE) {
                if ($sort) {
                    $view += " (source / <a href=\"$base_name.func-sort-c.$html_ext\">functions</a>)";
                else:
                    $view += " (source / <a href=\"$base_name.func.$html_ext\">functions</a>)";
                }
            } elsif ($type == $HDR_FUNC) {
                $view += " (<a href=\"$base_name.gcov.$html_ext\">source</a> / functions)";
            }
            $view += "</span>";
    }
    elif $type == $HDR_TESTDESC:
        # Test description header
        $base_dir = "";
        $view = "<a href=\"$base_dir" + f"index.{args.html_ext}\">".
                "$overview_title</a> - test case descriptions"

    # Prepare text for "test" field
    $test = escape_html($test_title);

    # Append link to test description page if available
    if test_description and ($type != $HDR_TESTDESC):
        if $frames and ($type == $HDR_SOURCE or $type == $HDR_FUNC):
            # Need to break frameset when clicking this link
            $test += " ( <span style=\"font-size:80%;\">".
                 "<a href=\"$base_dir".
                 f"descriptions.{args.html_ext}\" target=\"_parent\">".
                 "view descriptions</a></span> )";
        else:
            $test += " ( <span style=\"font-size:80%;\">".
                 "<a href=\"$base_dir".
                 f"descriptions.{args.html_ext}\">".
                 "view descriptions</a></span> )";

    # Write header
    write_header_prolog(html_handle, $base_dir)

    row_left = []
    row_right = []

    # Left row
    row_left.append([[ "10%", "headerItem", "Current view:" ],
                     [ "35%", "headerValue", $view ]]);
    row_left.append([[_, "headerItem", "Test:"],
                     [_, "headerValue", $test]]);
    row_left.append([[_, "headerItem", "Date:"],
                     [_, "headerValue", $date]]);

    # Right row
    if $legend and ($type == $HDR_SOURCE or $type == $HDR_FUNC):
        my $text = <<END_OF_HTML;
            Lines:
            <span class="coverLegendCov">hit</span>
            <span class="coverLegendNoCov">not hit</span>
END_OF_HTML
        if $br_coverage:
            $text += <<END_OF_HTML;
            | Branches:
            <span class="coverLegendCov">+</span> taken
            <span class="coverLegendNoCov">-</span> not taken
            <span class="coverLegendNoCov">#</span> not executed
END_OF_HTML
        row_left.append([[_, "headerItem", "Legend:"],
                         [_, "headerValueLeg", $text]])
    elif $legend and ($type != $HDR_TESTDESC):
        my $text = <<END_OF_HTML;
        Rating:
            <span class="coverLegendCovLo" title="Coverage rates below $med_limit % are classified as low">low: &lt; $med_limit %</span>
            <span class="coverLegendCovMed" title="Coverage rates between $med_limit % and $hi_limit % are classified as medium">medium: &gt;= $med_limit %</span>
            <span class="coverLegendCovHi" title="Coverage rates of $hi_limit % and more are classified as high">high: &gt;= $hi_limit %</span>
END_OF_HTML
        row_left.append([[_, "headerItem", "Legend:"],
                         [_, "headerValueLeg", $text]])
    if ($type == $HDR_TESTDESC):
        row_right.append([[ "55%" ]]);
    else:
        row_right.append([["15%", _, _ ],
                          ["10%", "headerCovTableHead", "Hit" ],
                          ["10%", "headerCovTableHead", "Total" ],
                          ["15%", "headerCovTableHead", "Coverage"]])
    # Line coverage
    $style = $rate_name[classify_rate($ln_found, $ln_hit,
                                      $med_limit, $hi_limit)];
    $rate = rate($ln_hit, $ln_found, " %");
    row_right.append([[_, "headerItem", "Lines:"],
                      [_, "headerCovTableEntry", $ln_hit],
                      [_, "headerCovTableEntry", $ln_found],
                      [_, "headerCovTableEntry$style", $rate]])
            if ($type != $HDR_TESTDESC);
    # Function coverage
    if ($fn_coverage) {
        $style = $rate_name[classify_rate($fn_found, $fn_hit,
                          $fn_med_limit, $fn_hi_limit)];
        $rate = rate($fn_hit, $fn_found, " %");
        row_right.append([[_, "headerItem", "Functions:"],
                          [_, "headerCovTableEntry", $fn_hit],
                          [_, "headerCovTableEntry", $fn_found],
                          [_, "headerCovTableEntry$style", $rate]])
            if ($type != $HDR_TESTDESC);
    }
    # Branch coverage
    if ($br_coverage) {
        $style = $rate_name[classify_rate($br_found, $br_hit,
                          $br_med_limit, $br_hi_limit)];
        $rate = rate($br_hit, $br_found, " %");
        row_right.append([[_, "headerItem", "Branches:"],
                          [_, "headerCovTableEntry", $br_hit],
                          [_, "headerCovTableEntry", $br_found],
                          [_, "headerCovTableEntry$style", $rate]])
            if ($type != $HDR_TESTDESC);
    }

    # Print rows
    $num_rows = max(len(row_left), len(row_right))
    for ($i = 0; $i < $num_rows; $i++)
    {
        my $left = $row_left[$i];
        my $right = $row_right[$i];

        if (!defined($left)) {
            $left = [[_, _, _],
                     [_, _, _]]
        }
        if (!defined($right)) {
            $right = [];
        }
        write_header_line(html_handle,
                          @{$left},
                          [ $i == 0 ? "5%" : _, _, _],
                          @{$right})
    }

    # Fourth line
    write_header_epilog(html_handle, $base_dir)

# NOK
def get_sort_code(link: Optional[str], $alt, $base):

    if link is not None:
        png        = "updown.png"
        link_start = f'<a href="{link}">'
        link_end   = "</a>"
    else:
        png        = "glass.png"
        link_start = ""
        link_end   = ""

    return (' '
            f'<span class="tableHeadSort">'.$link_start
            f'<img src="'.$base.$png.'" width=10 height=14'
            f' alt="'.$alt.'" title="'.$alt.'" border=0>'.$link_end
            f'</span>')

# NOK
def write_file_table(html_handle,
                     base_dir,    
                     overview,    
                     testhash,    
                     testfnchash, 
                     testbrhash,  
                     fileview,    
                     sort_type: int):

    # write_file_table(html_handle, base_dir, overview, testhash, testfnchash,
    #                  testbrhash, fileview, sort_type)
    #
    # Write a complete file table. OVERVIEW is a reference to a hash containing
    # the following mapping:
    #
    #   filename -> "ln_found,ln_hit,funcs_found,funcs_hit,page_link,
    #         func_link"
    #
    # TESTHASH is a reference to the following hash:
    #
    #   filename -> \%testdata
    #   %testdata: name of test affecting this file -> \%testcount
    #   %testcount: line number -> execution count for a single test
    #
    # Heading of first column is "Filename" if FILEVIEW is true, "Directory name"
    # otherwise.

    global test_description

    my $bar_graph;
    my $testname;
    my $testfncdata;
    my $testbrdata;
    my %affecting_tests;

    # Determine HTML code for column headings
    if $base_dir != "" and $show_details:
        my $detailed = keys(%{$testhash});
        view_type = HEAD_DETAIL_HIDDEN if $detailed else HEAD_NO_DETAIL

        file_code = get_file_code(view_type,
                                   "Filename" if $fileview else "Directory",
                                   $sort and sort_type != SORT_FILE,
                                   $base_dir);
        line_code = get_line_code(HEAD_DETAIL_SHOWN if $detailed else HEAD_DETAIL_HIDDEN,
                                   sort_type, "Line Coverage",
                                   $sort and sort_type != SORT_LINE,
                                   $base_dir);
    else:
        view_type = HEAD_NO_DETAIL
        file_code = get_file_code(view_type, "Filename" if $fileview else "Directory",
                                   $sort and sort_type != SORT_FILE,
                                   $base_dir);
        line_code = get_line_code(view_type, sort_type, "Line Coverage",
                                   $sort and sort_type != SORT_LINE,
                                   $base_dir);
    func_code = get_func_code(view_type,
                               "Functions",
                               $sort and sort_type != SORT_FUNC,
                               $base_dir);
    bran_code = get_bran_code(view_type,
                               "Branches",
                               $sort and sort_type != SORT_BRANCH,
                               $base_dir);

    head_columns = []
    push(head_columns, [ line_code, 3])
    if $fn_coverage:
        push(head_columns, [ func_code, 2])
    if $br_coverage:
        push(head_columns, [ bran_code, 2])

    write_file_table_prolog(html_handle, file_code, head_columns)

    for filename in get_sorted_keys($overview, sort_type):

        $testdata    = $testhash[filename]
        $testfncdata = $testfnchash[filename]
        $testbrdata  = $testbrhash[filename]

        ($found,    $hit,
         fn_found, fn_hit,
         br_found, br_hit,
         page_link) = overview[filename]

        columns = []
        # Line coverage
        push(columns, [$found, $hit, $med_limit, $hi_limit, 1]);
        # Function coverage
        if $fn_coverage:
            push(columns, [$fn_found, $fn_hit, $fn_med_limit, $fn_hi_limit, 0])
        # Branch coverage
        if $br_coverage:
            push(columns, [$br_found, $br_hit, $br_med_limit, $br_hi_limit, 0])

        write_file_table_entry(html_handle, $base_dir, filename, page_link, columns)

        # Check whether we should write test specific coverage
        # as well
        if !($show_details and $testdata): continue

        # Filter out those tests that actually affect this file
        %affecting_tests = get_affecting_tests($testdata, $testfncdata, $testbrdata)

        # Does any of the tests affect this file at all?
        if ! %affecting_tests: continue

        foreach $testname (keys(%affecting_tests))
            my @results = []
            ($found, $hit, $fn_found, $fn_hit, $br_found, $br_hit) =
                split(",", $affecting_tests{$testname});

            # Insert link to description of available
            if $test_description{$testname}:
                $testname = ('<a href=\"$base_dir"
                             "descriptions.$html_ext#$testname\">'
                             '$testname</a>')

            push(@results, [$found, $hit]);
            push(@results, [$fn_found, $fn_hit]) if ($fn_coverage);
            push(@results, [$br_found, $br_hit]) if ($br_coverage);
            write_file_table_detail_entry(html_handle, $testname, @results)

    write_file_table_epilog(html_handle)

# NOK
def get_file_code($type, $text, sort_button: bool, $base):

    global args

    result = $text
    link = None
    if sort_button:
        if $type == HEAD_NO_DETAIL:
            link = f"index.{args.html_ext}"
        else:
            link = f"index-detail.{args.html_ext}"
    result += get_sort_code($link, "Sort by name", $base);

    return result

# NOK
def get_line_code($type, $sort_type: int, $text, sort_button: bool, $base):

    global args

    result = $text
    my $sort_link;
    if $type == HEAD_NO_DETAIL:
        # Just text
        if sort_button:
            $sort_link = f"index-sort-l.{args.html_ext}"
    elif $type == HEAD_DETAIL_HIDDEN:
        # Text + link to detail view
        $result += ' ( <a class="detail" href="index-detail'.
                   $fileview_sortname[$sort_type].'.'.$html_ext.'">show details</a> )'
        if sort_button:
            $sort_link = f"index-sort-l.{args.html_ext}"
    else:
        # Text + link to standard view
        $result += ' ( <a class="detail" href="index'.
                   $fileview_sortname[$sort_type].'.'.$html_ext.'">hide details</a> )'
        if sort_button:
            $sort_link = f"index-detail-sort-l.{args.html_ext}"
    # Add sort button
    result += get_sort_code($sort_link, "Sort by line coverage", $base);

    return result

# NOK
def get_func_code($type, $text, sort_button: bool, $base):

    global args

    result = $text
    link = None
    if sort_button:
        if $type == HEAD_NO_DETAIL:
            link = f"index-sort-f.{args.html_ext}"
        else:
            link = f"index-detail-sort-f.{args.html_ext}"
    result += get_sort_code($link, "Sort by function coverage", $base);

    return result

# NOK
def get_bran_code($type, $text, sort_button: bool, $base):

    global args

    result = $text
    link = None
    if sort_button:
        if $type == HEAD_NO_DETAIL:
            link = f"index-sort-b.{args.html_ext}"
        else:
            link = f"index-detail-sort-b.{args.html_ext}"
    result += get_sort_code(link, "Sort by branch coverage", $base)

    return result

# NOK
def write_file_table_prolog(html_handle, file_heading: str, columns: List[Tuple[str, int]]):
    """Write heading for file table."""
    # write_file_table_prolog(handle, file_heading, [heading, num_cols, ...])

    if   len(columns) == 1: width = 20
    elif len(columns) == 2: width = 10
    elif len(columns) >  2: width = 8
    else:                   width = 0

    num_columns = 0
    for heading, cols in columns:
        num_columns += cols

    file_width = 100 - num_columns * width

    # Table definition
    write_html(html_handle, <<END_OF_HTML)
      <center>
      <table width="80%" cellpadding=1 cellspacing=1 border=0>

        <tr>
          <td width="{file_width}%"><br></td>
END_OF_HTML
    # Empty first row
    for heading, cols in columns:
        for _ in range(cols):
            write_html(html_handle, <<END_OF_HTML)
          <td width="{width}%"></td>
END_OF_HTML
    # Next row
    write_html(html_handle, <<END_OF_HTML)
        </tr>

        <tr>
          <td class="tableHead">{file_heading}</td>
END_OF_HTML
    # Heading row
    for heading, cols in columns:
        colspan = f" colspan={cols}" if cols > 1 else ""
        write_html(html_handle, <<END_OF_HTML);
          <td class="tableHead"{colspan}>$heading</td>
END_OF_HTML
    write_html(html_handle, <<END_OF_HTML);
        </tr>
END_OF_HTML

# NOK
def write_file_table_epilog(html_handle):
    """Write end of file table HTML code."""
    # !!! read from html/file_table_epilog.html
    write_html(html_handle, <<END_OF_HTML)
END_OF_HTML

# NOK
def write_file_table_entry(html_handle, $base_dir, filename: str, page_link: Optional[str], @entries):
    # write_file_table_entry(handle, base_dir, filename, page_link,
    #             ([ found, hit, med_limit, hi_limit, graph ], ..)
    #
    # Write an entry of the file table.
    #

    esc_filename = escape_html(filename)
    # Add link to source if provided
    if page_link isn not None and page_link != "":
        file_code = f'<a href="$page_link">{esc_filename}</a>'
    else:
        file_code = esc_filename

    # First column: filename
    write_html(html_handle, <<END_OF_HTML);
        <tr>
          <td class="coverFile">{file_code}</td>
END_OF_HTML
    # Columns as defined
    for $entry in @entries:
    {
        my ($found, $hit, $med, $hi, $graph) = @{$entry};
        my $bar_graph;
        my $class;
        my $rate;

        # Generate bar graph if requested
        if ($graph) {
            $bar_graph = get_bar_graph_code($base_dir, $found, $hit)
            write_html(html_handle, <<END_OF_HTML);
          <td class="coverBar" align="center">
            $bar_graph
          </td>
END_OF_HTML
        }

        # Get rate color and text
        if $found == 0:
            $rate = "-";
            $class = "Hi";
        else:
            $rate = rate($hit, $found, "&nbsp;%")
            $class = $rate_name[classify_rate($found, $hit, $med, $hi)];

        if $opt_missed:
            # Show negative number of items without coverage
            $hit = -($found - $hit);

        write_html(html_handle, <<END_OF_HTML)
          <td class="coverPer$class">$rate</td>
          <td class="coverNum$class">$hit / $found</td>
END_OF_HTML
    }
    # End of row
    write_html(html_handle, <<END_OF_HTML)
        </tr>
END_OF_HTML

# NOK
def write_file_table_detail_entry(html_handle, $test, entries: List[]):
    #
    # write_file_table_detail_entry(html_handle, test_name, ([found, hit], ...))
    #
    # Write entry for detail section in file table.
    #

    if $test == "":
        $test = "<span style=\"font-style:italic\">&lt;unnamed&gt;</span>"
    elif ($test =~ /^(.*),diff$/):
        $test = $1." (converted)"

    # Testname
    write_html(html_handle, <<END_OF_HTML)
        <tr>
          <td class="testName" colspan=2>$test</td>
END_OF_HTML
    # Test data
    for $found, $hit in entries:
        $rate = rate($hit, $found, "&nbsp;%")

        write_html(html_handle, <<END_OF_HTML);
          <td class="testPer">$rate</td>
          <td class="testNum">$hit&nbsp;/&nbsp;$found</td>
END_OF_HTML

    write_html(html_handle, <<END_OF_HTML)
        </tr>

END_OF_HTML

# NOK
def get_sorted_keys($hash, sort_type: int) -> List[???]:
    """
    hash:  filename -> stats
    stats: [ ln_found, ln_hit, fn_found, fn_hit, br_found, br_hit,
             link_name, line_rate, fn_rate, br_rate ]
    """
    if sort_type == SORT_FILE:
        # Sort by name
        return sorted($hash.keys())
    elif $opt_missed:
        return get_sorted_by_missed(hash, sort_type)
    else:
        return get_sorted_by_rate(hash, sort_type)

# NOK
def get_sorted_by_missed($hash, sort_type: int) -> List[???]:

    if sort_type == SORT_LINE:
        # Sort by number of instrumented lines without coverage
        return sorted(
            { ($hash->{$b}[0] - $hash->{$b}[1]) <=> ($hash->{$a}[0] - $hash->{$a}[1]) } $hash.keys()) # NOK
    elif sort_type == SORT_FUNC:
        # Sort by number of instrumented functions without coverage
        return sorted(
            { ($hash->{$b}[2] - $hash->{$b}[3]) <=> ($hash->{$a}[2] - $hash->{$a}[3]) } $hash.keys()) # NOK
    elif sort_type == SORT_BRANCH:
        # Sort by number of instrumented branches without coverage
        return sorted(
            { ($hash->{$b}[4] - $hash->{$b}[5]) <=> ($hash->{$a}[4] - $hash->{$a}[5]) } $hash.keys()) # NOK

# NOK
def get_sorted_by_rate($hash, sort_type: int) -> List[???]:

    if sort_type == SORT_LINE:
        # Sort by line coverage
        return sorted({$hash->{$a}[7] <=> $hash->{$b}[7]} $hash.keys()) # NOK
    elif sort_type == SORT_FUNC:
        # Sort by function coverage;
        return sorted({$hash->{$a}[8] <=> $hash->{$b}[8]} $hash.keys()) # NOK
    elif sort_type == SORT_BRANCH:
        # Sort by br coverage;
        return sorted({$hash->{$a}[9] <=> $hash->{$b}[9]} $hash.keys()) # NOK


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
                 $source_filename,
                 $, 
                 $checkdata,
                 converted: Set[int],
                 $funcdata,
                 $sumbrcount) -> List:
    # write_source(html_handle, source_filename, count_data, checksum_data,
    #              converted_data, func_data, sumbrcount)
    #
    # Write an HTML view of a source code file. Returns a list containing
    # data as needed by gen_png().
    #
    # Die on error.

    my $datafunc = reverse_dict(funcdata)
    my @file;

    %count_data: Dict = %{$_[2]} if $_[2] else {}

    SOURCE_HANDLE = open("<", $source_filename)
    if SOURCE_HANDLE:
        @file = <SOURCE_HANDLE>
    else:
        if not $ignore[$ERROR_SOURCE]:
            die(f"ERROR: cannot read {source_filename}\n")

        # Continue without source file
        warn(f"WARNING: cannot read {source_filename}!\n")

        last_line = 0
        lines = sorted({ $a <=> $b } %count_data.keys())
        if lines:
            last_line = lines[-1]

        if last_line < 1:
            return [":"]

        # Simulate gcov behavior
        for (my line_number = 1; line_number <= last_line; line_number++):
            @file.append("/* EOF */")

    write_source_prolog(html_handle)

    result = []
    line_number = 0
    for $_ in @file:
        line_number += 1
        line = $_.rstrip("\n")

        # Also remove CR from line-end
        s/\015$//;

        # Source code matches coverage data?
        if (line_number in $checkdata and
            $checkdata->{line_number} != md5_base64($_)):
            die(f"ERROR: checksum mismatch  at {source_filename}:{line_number}\n")

        result.push(write_source_line(html_handle, line_number,
                                      $_, $count_data{line_number},
                                      line_number in converted,
                                      $sumbrcount->{line_number}))

    if SOURCE_HANDLE:
        SOURCE_HANDLE.close()

    write_source_epilog(html_handle)

    return result

# NOK
def write_source_prolog(html_handle):
    """Write start of source code table."""
    global options

    lineno_heading = "         "
    branch_heading = ((fmt_centered(options.br_field_width, "Branch data") + " ")
                       if $br_coverage else "")
    line_heading   = fmt_centered(options.line_field_width, "Line data") + " "
    source_heading = " Source code"

    # *************************************************************

    # !!! read from html/source_prolog.html
    write_html(html_handle, <<END_OF_HTML)
END_OF_HTML

# NOK
def write_source_epilog(html_handle):
    # Write end of source code table.
    #
    # !!! read from html/source_epilog.html
    write_html(html_handle, <<END_OF_HTML)
END_OF_HTML

# NOK
def write_source_line(html_handle, line_num: int, $source, hit_count: Optional[float],
                      converted: bool, $brdata) -> str:
    """Write formatted source code line.
    Return a line in a format as needed by gen_png()
    """
    global options

    count_field_width = options.line_field_width - 1

    # Get branch HTML data for this line
    if $br_coverage:
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

    # Write out a line number navigation anchor every $nav_resolution
    # lines if necessary
    anchor_start = f'<a name="{line_num}">'
    anchor_end   = '</a>'

    # *************************************************************

    html = anchor_start
    html += '<span class="lineNum">{} </span>'.format("%8d" % line_num)
    if $br_coverage:
        html += shift(@br_html)
        html += ":"
    html += f"{source_format}{count_format} : "
    html += escape_html($source)
    if source_format:
        html += '</span>'
    html += anchor_end
    html += "\n"

    write_html(html_handle, html)
    if $br_coverage:
        # Add lines for overlong branch information
        for br_row in @br_html:
            write_html(html_handle,
                       f'<span class="lineNum">         </span>{br_row}\n')

    # *************************************************************

    return result

# NOK
def get_branch_html(brdata: Optional[str]) -> List[str]:
    # Return a list of HTML lines which represent the specified branch coverage
    # data in source code view.

    global options

    blocks: List[List[List]] = get_branch_blocks(brdata)

    my $branch;
    my $line_len = 0;
    my $line = [];    # [branch2|" ", branch|" ", ...]

    lines: List = []  # [line1, line2, ...]
    # Distribute blocks to lines
    for block in blocks:
    {
        block_len: int = get_block_len(block)

        # Does this block fit into the current line?
        if $line_len + block_len <= options.br_field_width:
            # Add it
            $line_len += block_len
            push(@{$line}, @{$block});
            continue
        elif block_len <= options.br_field_width:
            # It would fit if the line was empty - add it to new line
            lines.append($line)
            $line_len = block_len
            $line = [ @{$block} ];
            continue
        # Split the block into several lines
        foreach $branch (@{$block})
        {
            if ($line_len + $branch[BR_LEN] >= options.br_field_width)
            {
                # Start a new line
                if (($line_len + 1 <= options.br_field_width) and
                    len(@{$line}) > 0 and !$line->[len(@$line) - 1][BR_CLOSE]):
                    # Try to align branch symbols to be in one # row
                    push(@{$line}, " ");
                lines.append($line)
                $line_len = 0;
                $line = [];
            }
            push(@{$line}, $branch);
            $line_len += $branch[BR_LEN]
        }
    }
    lines.append($line)

    result: List[str] = []

    # Convert to HTML
    for $line in @lines:

        current     = ""
        current_len = 0

        for $branch in @$line:
            # Skip alignment space
            if $branch == " ":
                current     += " "
                current_len += 1
                continue

            block_num, branch_num, taken, text_len, open, close =  @{$branch}

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
            current = (" " * (options.br_field_width - current_len)) + current

        result.append(current)

    return result

# NOK
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
    for entry in (split(/:/, brdata)):
        block_num, branch_num, taken = split(/,/, entry)
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

# NOK
def cmp_blocks($a, $b):
    $fa, $fb = $a->[0], $b->[0]
    if $fa->[0] != $fb->[0]:
        return $fa->[0] <=> $fb->[0]
    else:
        return $fa->[1] <=> $fb->[1]


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

# NOK
def funcview_get_func_code(name: str, $base, sort_type: int) -> str:

    global args

    link = None
    if $sort and sort_type == 1:
        link = f"{name}.func.{args.html_ext}"

    result = "Function Name"
    result += get_sort_code(link, "Sort by function name", $base)

    return result

# NOK
def funcview_get_count_code(name: str, $base, sort_type: int) -> str:

    global args

    link = None
    if $sort and sort_type == 0:
        link = f"{name}.func-sort-c.{args.html_ext}"

    result = "Hit count"
    result += get_sort_code(link, "Sort by hit count", $base)

    return result

# NOK
def funcview_get_sorted($funcdata, $sumfncdata, sort_type: int):
    # Depending on the value of sort_type, return a list of functions sorted
    # by name (sort_type 0) or by the associated call count (sort_type 1).
    if sort_type == 0:
        return sorted(keys(%{$funcdata}))
    else:
        return sorted({ $sumfncdata->{$b} == $sumfncdata->{$a}
                        ? $a cmp $b : $sumfncdata->{$a} <=> $sumfncdata->{$b}
                      } keys(%{$sumfncdata}))

# NOK
def info(printf_parameter):
    # Use printf to write PRINTF_PARAMETER to stdout only when
    # the $quiet flag is not set.
    global quiet
    if not quiet:
        # Print info string
        printf(printf_parameter)


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

# NOK
def remove_unused_descriptions():
    # Removes all test descriptions from the global hash test_description
    # which are not present in %info_data.
    #
    global %info_data
    global test_description

    my $test_data;  # Reference to hash test_name -> count_data
    
    my %test_list = {}  # Hash containing found test names
    for filename in (keys(%info_data)):
        ($test_data) = get_info_entry($info_data[filename])
        for $_ in (keys(%{$test_data})):
            $test_list{$_} = "";

    before: int = len(test_description)  # Initial number of descriptions
    # Remove descriptions for tests which are not in our list
    for $_ in list(test_description.keys()):
        if $_ not in $test_list:
            del $test_description[$_]
    after: int = len(test_description)  # Remaining number of descriptions

    if after < before:
        info("Removed {} unused descriptions, {} remaining.\n".format(
             (before - after), after))

# NOK
def apply_prefix(filename, prefixes: List):
    # If FILENAME begins with PREFIX from PREFIXES,
    # remove PREFIX from FILENAME and return resulting string,
    # otherwise return FILENAME.
    if prefixes:
        for prefix in prefixes:
            if prefix == filename:
                return "root"
            if prefix != "" and filename =~ /^\Q$prefix\E\/(.*)$/:
                return substr(filename, len(prefix) + 1)
    return filename


def get_html_prolog(filename: Optional[Path] = None):
    """If FILENAME is defined, return contents of file.
    Otherwise return default HTML prolog.
    Die on error."""
    if filename is None:
        filename = Path("html/html_prolog.html")
    try:
        return filename.read_text()
    exept:
        die("ERROR: cannot open html prolog {filename}!\n")


def get_html_epilog(filename: Optional[Path] = None):
    """If FILENAME is defined, return contents of file.
    Otherwise return default HTML epilog.
    Die on error."""
    if filename is None:
        filename = Path("html/html_epilog.html")
    try:
        return filename.read_text()
    exept:
        die(f"ERROR: cannot open html epilog {filename}!\n")

# NOK
def parse_ignore_errors(ignore_errors: Optional[List]):
    """Parse user input about which errors to ignore."""
    global ignore

    if not ignore_errors:
        return

    items = []
    for item in ignore_errors:
        item =~ s/\s//g;
        if "," in item:
            # Split and add comma-separated parameters
            items.append(item.split(","))
        else:
            # Add single parameter
            items.append(item)

    for item in items:
        lc_item = lc(item)
        if lc_item not in ERROR_ID:
            die("ERROR: unknown argument for --ignore-errors: {item}\n")
        item_id = ERROR_ID[lc_item]
        $ignore[item_id] = 1


def parse_dir_prefix(prefixes: Optional[List]):
    """Parse user input about the prefix list"""
    global dir_prefix

    if not prefixes:
        return

    for item in prefixes:
        if "," in item:
            # Split and add comma-separated parameters
            dir_prefix.append(item.split(","))
        else:
            # Add single parameter
            dir_prefix.append(item)

# NOK
def demangle_list(func_list: List[str]) -> Dict[str, str]:

    global options

    # Write function names to file
    try:
        fhandle, tmpfile = tempfile()
    except Exception as exc:
        die("ERROR: could not create temporary file")
    with fhandle:
        print("\n".join(func_list), end="", file=fhandle)

    # Extra flag necessary on OS X so that symbols listed by gcov
    # get demangled properly.
    demangle_args = options.demangle_cpp_params
    if demangle_args == "" and $^O == "darwin":
        demangle_args = "--no-strip-underscores"
    # Build translation hash from c++filt output
    try:
        fhandle = open("-|", f"{options.demangle_cpp_tool} {demangle_args} < {tmpfile}")
    except Exception as exc:
        die(f"ERROR: could not run c++filt: {exc}!\n")
    with fhandle:
        flines = fhandle.readlines()
    if len(flines) != len(func_list):
        die("ERROR: c++filt output not as expected ({} vs {}) lines\n".format(
            len(flines), len(func_list)))

    demangle: Dict[str, str] = {}

    versions: Dict[str, int] = {}
    for func, translated in zip(func_list, flines):
        translated = translated.rstrip("\n")
        if translated not in versions:
            versions[translated] = 1
        else:
            versions[translated] += 1
        version = versions[translated]
        if version > 1: translated += f".{version}"

        demangle[func] = translated

    try:
        Path(tmpfile).unlink()
    except Exception as exc:
        warn(f"WARNING: could not remove temporary file {tmpfile}: {exc}!\n")

    return demangle


def get_rate(found: int, hit: int) -> int:
    """Return a relative value for the specified found&hit values
    which is used for sorting the corresponding entries in a
    file list."""
    if found == 0:
        return 10000
    else:
        return int(hit * 1000 / found) * 10 + 2 - (1 / found)

# NOK
def create_sub_dir($dir: Path):
    # Create subdirectory DIR if it does not already exist,
    # including all its parent directories.
    #
    # Die on error.
    #
    system("mkdir", "-p", str($dir))
        and die(f"ERROR: cannot create directory {dir}!\n")

def main(argv=sys.argv[1:]):
    """\
    """
    global tool_name
    global lcov_version
    global lcov_url

    def warn_handler(msg: str):
        global tool_name
        warn(f"{tool_name}: {msg}")

    def die_handler(msg: str):
        global tool_name
        die(f"{tool_name}: {msg}")

    # $SIG{__WARN__} = warn_handler
    # $SIG{__DIE__}  = die_handler


if __name__.rpartition(".")[-1] == "__main__":
    sys.exit(main())
