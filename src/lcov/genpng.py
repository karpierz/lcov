# Copyright (c) 2020-2022, Adam Karpierz
# Licensed under the BSD license
# https://opensource.org/licenses/BSD-3-Clause

"""
genpng

  This script creates an overview PNG image of a source code file by
  representing each source code character by a single pixel.

"""

#   Note that the Perl module GD.pm is required for this script to work.
#   It may be obtained from http://www.cpan.org
#
# History:
#   2002-08-26: created by Peter Oberparleiter <Peter.Oberparleiter@de.ibm.com>

#use strict;
#use warnings;

from typing import List
import argparse
import sys
import re
from pathlib import Path

# Constants
tool_name    = Path(__file__).stem
lcov_version = "LCOV version " #+ `${abs_path(dirname($0))}/get_version.sh --full`
lcov_url     = "http://ltp.sourceforge.net/coverage/lcov.php"


def genpng_process_file(filename: Path, out_filename: Path,
                        width: int, tab_size: int):
    try:
        file = filename.open("rt")
    except:
        raise OSError(f"ERROR: cannot open {filename}!\n")
    source = []
    with file:
        # Check for .gcov filename extension
        if filename.suffix == ".gcov":
            # Assume gcov text format
            for line in file:
                match = re.match(r"^\t\t(.*)$", line)

                if match:
                    # Uninstrumented line
                    source.append(":{}".format(match.group(1)))
                    continue

                match = re.match(r"^      ######    (.*)$", line)
                if match:
                    # Line with zero execution count
                    source.append("0:{}".format(match.group(1)))
                    continue

                match = re.match(r"^( *)(\d*)    (.*)$", line)
                if match:
                    # Line with positive execution count
                    source.append("{}:{}".format(match.group(2), match.group(3)))
                    continue
        else:
            # Plain text file
            for line in file:
                source.append(f":{line}")

    gen_png(out_filename, False, width, tab_size, source)


def gen_png(filename: Path,   # Filename for PNG file
            dark_mode: bool,  # dark-on-light, if set
            width: int,       # Imagewidth for image
            tab_size: int,    # Replacement string for tab signs
            source: List):    # Source code as passed via argument 2
    # Write an overview PNG file to FILENAME.
    # Source code is defined by SOURCE which is a list of lines
    # <count>:<source code> per source code line.
    # The output image will be made up of one pixel per character of source,
    # coloring will be done according to execution counts.
    # WIDTH defines the image width.
    # TAB_SIZE specifies the number of spaces to use as replacement string
    # for tabulator signs in source code text.
    #
    # Die on error.

    # Handle empty source files
    if not source: source = [""]

    height = len(source)  # Height as define by source size
    # Create image - source code overview image data
    try:
        overview = GD.Image(width, height)
    except:
        raise OSError("ERROR: cannot allocate overview image!\n")

    # Define colors   # overview.colorAllocate(red, green, blue)
    # col_plain_text  # Color for uninstrumented text
    # col_plain_back  # Color for overview background
    # col_cov_text    # Color for text of covered lines
    # col_cov_back    # Color for background of covered lines
    # col_nocov_text  # Color for test of lines which were not
                      # covered (count == 0)
    # col_nocov_back  # Color for background of lines which
                      # were not covered (count == 0)
    # col_hi_text     # Color for text of highlighted lines
    # col_hi_back     # Color for background of highlighted lines
    if dark_mode:
        # just reverse foregrond and background
        # there is probably a better color scheme than this.
        col_plain_text = overview.colorAllocate(0xaa, 0xaa, 0xaa) # light grey
        col_plain_back = overview.colorAllocate(0x00, 0x00, 0x00)
        col_cov_text   = overview.colorAllocate(0xaa, 0xa7, 0xef)
        col_cov_back   = overview.colorAllocate(0x5d, 0x5d, 0xea)
        col_nocov_text = overview.colorAllocate(0xff, 0x00, 0x00)
        col_nocov_back = overview.colorAllocate(0xaa, 0x00, 0x00)
        col_hi_text    = overview.colorAllocate(0x00, 0xff, 0x00)
        col_hi_back    = overview.colorAllocate(0x00, 0xaa, 0x00)
    else:
        col_plain_back = overview.colorAllocate(0xff, 0xff, 0xff)
        col_plain_text = overview.colorAllocate(0xaa, 0xaa, 0xaa)
        col_cov_back   = overview.colorAllocate(0xaa, 0xa7, 0xef)
        col_cov_text   = overview.colorAllocate(0x5d, 0x5d, 0xea)
        col_nocov_back = overview.colorAllocate(0xff, 0x00, 0x00)
        col_nocov_text = overview.colorAllocate(0xaa, 0x00, 0x00)
        col_hi_back    = overview.colorAllocate(0x00, 0xff, 0x00)
        col_hi_text    = overview.colorAllocate(0x00, 0xaa, 0x00)

    tab_rexp = re.compile(r"^([^\t]*)(\t)")

    # Visualize each line
    last_count = ""  # Count of last processed line
    row = 0          # Current row number
    for line in source:
        # Replace tabs with spaces to keep consistent with source code view
        match = tab_rexp.match(line)
        while match:
            spaces_count = tab_size - ((len(match.group(1)) - 1) % tab_size)
            line = tab_rexp.sub(match.group(1) + (" " * spaces_count), line)
            match = tab_rexp.match(line)

        # Process only a lines which follow the <count>:<line> specification
        match = re.match(r"(\*?)(\d*):(.*)$", line)
        if not match:
            continue

        highlighted = match.group(1)
        count       = match.group(2)  # Count of current line
        source_code = match.group(3)

        # Decide which color pair to use

        # If this line was not instrumented but the one before was,
        # take the color of that line to widen color areas in
        # resulting image
        if count == "" and last_count != "":
            count = last_count

        if count == "":
            # Line was not instrumented
            color_text = col_plain_text
            color_back = col_plain_back
        elif count == "0":
            # Line was instrumented but not executed
            color_text = col_nocov_text
            color_back = col_nocov_back
        elif highlighted == "*":
            # Line was highlighted
            color_text = col_hi_text
            color_back = col_hi_back
        else:
            # Line was instrumented and executed
            color_text = col_cov_text
            color_back = col_cov_back

        # Write one pixel for each source character
        column = 0  # Current column number
        for ch in source_code:
            # Check for width
            if column >= width:
                break
            overview.setPixel(column, row,
                              color_back if ch == " " else color_text)
            column += 1
        # Fill rest of line
        while column < width:
            overview.setPixel(column, row, color_back)
            column += 1

        last_count = match.group(2)
        row += 1

    # Write PNG file
    with filename.open("wb") as file:
        #or raise OSError(f"ERROR: cannot write png file {filename}!\n");
        file.write(overview.png())


def main(argv=sys.argv[1:]):
    """\
    Create an overview image for a given source code file of either
    plain text or .gcov file format.
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
        genpng_process_file(Path(args.filename), Path(args.output_filename),
                            args.width, args.tab_size)
    except BaseException as exc:
        return str(exc)


if __name__.rpartition(".")[-1] == "__main__":
    sys.exit(main())
