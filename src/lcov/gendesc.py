# Copyright (c) 2020-2022, Adam Karpierz
# Licensed under the BSD license
# https://opensource.org/licenses/BSD-3-Clause

"""
gendesc

  This script creates a description file as understood by genhtml.
  Input file format:

  For each test case:
    <test name><optional whitespace>
    <at least one whitespace character (blank/tab)><test description>

  Actual description may consist of several lines. By default, output is
  written to stdout. Test names consist of alphanumeric characters
  including _ and -.

"""

# History:
#   2002-09-02: created by Peter Oberparleiter <Peter.Oberparleiter@de.ibm.com>

#use strict;
#use warnings;

from typing import List, Optional
import argparse
import sys
import re
from pathlib import Path

# Constants
tool_name    = Path(__file__).stem
lcov_version = "LCOV version " #+ `${abs_path(dirname($0))}/get_version.sh --full`
lcov_url     = "http://ltp.sourceforge.net/coverage/lcov.php"


def gen_description(input_filename: Path, output_filename: Optional[Path]):
    """Read text file INPUT_FILENAME and convert the contained description
    to a format as understood by genhtml, i.e.

       TN:<test name>
       TD:<test description>

    If defined, write output to OUTPUT_FILENAME, otherwise to stdout.

    Die on error.
    """
    try:
        finput = input_filename.open("rt")
    except:
        raise OSError(f"ERROR: cannot open {input_filename}!\n")
    with finput:
        # Open output file for writing
        try:
            foutput = output_filename.open("wt") if output_filename else sys.stdout
        except:
            raise OSError(f"ERROR: cannot create {output_filename}!\n")

        # Process all lines in input file
        empty_line = "ignore"
        for line in finput:
            line = line.rstrip("\n")

            match = re.match(r"^(\w[\w-]*)(\s*)$", line)
            if match:
                # Matched test name
                # Name starts with alphanum or _, continues with
                # alphanum, _ or -
                print("TN: {}".format(match.group(1)), file=foutput)
                empty_line = "ignore"
                continue

            match = re.match(r"^(\s+)(\S.*?)\s*$", line)
            if match:
                # Matched test description
                if empty_line == "insert":
                    # Write preserved empty line
                    print("TD: ", file=foutput)
                print("TD: {}".format(match.group(2)), file=foutput)
                empty_line = "observe"
                continue

            match = re.match(r"^\s*$", line)
            if match:
                # Matched empty line to preserve paragraph separation
                # inside description text
                if empty_line == "observe":
                    empty_line = "insert"
                continue

        # Close output file if defined
        if output_filename:
            foutput.close()


def main(argv=sys.argv[1:]):
    """\
    Convert a test case description file into a format as understood
    by genhtml.
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

    # Parse command line options
    parser = argparse.ArgumentParser(prog=tool_name, description=main.__doc__,
                                     epilog=f"For more information see: {lcov_url}",
                                     add_help=False)
    parser.add_argument("input_filename", type=str,
        metavar="INPUTFILE", help="INPUTFILE")
    parser.add_argument("-h", "-?", "--help", action="help",
        help="Print this help, then exit")
    parser.add_argument("-v", "--version", action="version",
        version=f"%(prog)s: {lcov_version}",
        help="Print version number, then exit")
    parser.add_argument("-o", "--output-filename", type=str,
        metavar="FILENAME", help="Write description to FILENAME")

    args = parser.parse_args(argv)

    try:
        gen_description(Path(args.input_filename),
                        Path(args.output_filename)
                        if args.output_filename else None)
    except BaseException as exc:
        return str(exc)


if __name__.rpartition(".")[-1] == "__main__":
    sys.exit(main())
