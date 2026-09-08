# remove_font_links.py
# Repository: sinclairdynamics-website
#
# Removes the two Google Fonts elements from the <head> of every page, now that
# Barlow and Barlow Condensed are served from fonts/ in this repository. The
# preconnect and the stylesheet link are the site's only render-blocking
# third-party requests and sit on the critical path ahead of first paint.
#
#   python remove_font_links.py --dry-run    # report only, writes nothing
#   python remove_font_links.py              # apply
#
# Nothing is added in their place. A preconnect to our own origin would be
# meaningless: the connection carrying the HTML is already open.
#
# THIS IS AN EDIT SCRIPT AND NOT A CHECK. It does not count toward the check
# runner's deferral condition, which asks for a third check script.
#
# The verification instrument is VERIFICATION.md in the assistant repository.
#
# Revisions:
#   Session 69, 8 September 2026: created.

import argparse
import glob
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

# Two patterns rather than one. They are separated by a newline and the
# formatter wraps the second across three lines on every page seen so far, but
# "so far" is four of sixteen, so nothing here assumes they are adjacent or
# that either is on a single line.
#
# [^>]* crosses newlines without needing DOTALL, because a newline is not '>'.
# The trailing \r?\n takes the line ending with the element, so removal does
# not leave a blank line behind. CRLF is preserved everywhere else because the
# file is read and written with newline='' and never re-joined.
PRECONNECT = re.compile(
    r'[ \t]*<link\b[^>]*rel="preconnect"[^>]*fonts\.googleapis\.com[^>]*>\r?\n')
STYLESHEET = re.compile(
    r'[ \t]*<link\b[^>]*fonts\.googleapis\.com/css2[^>]*>\r?\n')

# Anything left matching this after the edit means something was missed.
RESIDUE = re.compile(r'fonts\.googleapis\.com|fonts\.gstatic\.com')


def pages():
    """
    Every page in the repository, found by pattern rather than by a list.

    A hardcoded list is the failure this project has already paid for: a page
    absent from a list is never opened, never checked and never reported. A
    glob cannot develop that gap.

    Files beginning with an underscore are the single-sourced chrome fragments.
    They carry no <head> and would match nothing, which would stop the run for
    a reason that is not a fault.
    """
    found = sorted(glob.glob(os.path.join(HERE, "*.html")))
    return [p for p in found if not os.path.basename(p).startswith("_")]


def read(path):
    # newline='' keeps CRLF exactly as it sits on disk. Without it Python
    # translates line endings on the way in and writes back LF, which would
    # rewrite every line of every file and bury the real change in the diff.
    with open(path, "r", encoding="utf-8", newline="") as f:
        return f.read()


def write(path, text):
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(text)


def plan(text):
    """
    Return (new_text, removed_spans, fault) for one page.

    Each pattern must match exactly once. Zero means the page does not carry
    it, which on a second run is the whole file set and is how re-running
    refuses rather than doing nothing quietly. More than one means the page is
    already wrong and is not somewhere to guess.
    """
    pre = PRECONNECT.findall(text)
    css = STYLESHEET.findall(text)

    if len(pre) != 1 or len(css) != 1:
        return None, [], ("expected exactly one preconnect and one stylesheet "
                          "link, found %d and %d" % (len(pre), len(css)))

    new = STYLESHEET.sub("", PRECONNECT.sub("", text), count=1)

    # Removal is subtraction and nothing else. If the lengths do not account
    # for each other, something matched that was not intended.
    expected = len(text) - len(pre[0]) - len(css[0])
    if len(new) != expected:
        return None, [], ("length after removal is %d, expected %d"
                          % (len(new), expected))

    residue = RESIDUE.search(new)
    if residue:
        return None, [], ("a Google Fonts reference survives at offset %d"
                          % residue.start())

    return new, [pre[0], css[0]], None


def main():
    ap = argparse.ArgumentParser(
        description="Remove the Google Fonts links from every page head.")
    ap.add_argument("--dry-run", action="store_true",
                    help="report what would change and write nothing")
    args = ap.parse_args()

    files = pages()
    if not files:
        print("No pages found in %s. Nothing done." % HERE)
        return 1

    print("%d page(s) found:\n" % len(files))
    for p in files:
        print("  %s" % os.path.basename(p))
    print("")

    # Every page is planned before any page is written. A run that would fail
    # halfway leaves the site in two states, and the second half looks exactly
    # like the first from the outside.
    planned, faults = [], []
    for path in files:
        text = read(path)
        new, removed, fault = plan(text)
        if fault:
            faults.append((os.path.basename(path), fault))
        else:
            planned.append((path, text, new, removed))

    if faults:
        print("STOPPED. %d page(s) are not in the expected shape and NOTHING "
              "has been written:\n" % len(faults))
        for name, fault in faults:
            print("  %s: %s" % (name, fault))
        print("\nNo page was edited, including the ones that were fine.")
        return 1

    for path, text, new, removed in planned:
        name = os.path.basename(path)
        print("%s  -%d bytes" % (name, len(text) - len(new)))
        for chunk in removed:
            for line in chunk.splitlines():
                if line.strip():
                    print("       - %s" % line.strip())
        if not args.dry_run:
            write(path, new)
            back = read(path)
            if back != new:
                print("       FAILED: the file on disk does not match what "
                      "was written. Stop and inspect %s." % name)
                return 1

    print("")
    if args.dry_run:
        print("Dry run. %d page(s) would change. Nothing was written."
              % len(planned))
    else:
        print("%d page(s) written and read back." % len(planned))
        print("Now run: python check_heads.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
