#!/usr/bin/env python3
"""
apply-chrome.py
Sinclair Dynamics website: single-source the nav and footer across every page.

WHAT THIS IS
------------
The nav and footer are the same on every page of this site, apart from which
nav entry is marked active. Until now they were duplicated into each page file
by hand, so changing either meant editing thirteen files and hoping none of
them drifted. This script makes two fragment files authoritative and writes
them into every page:

    _nav_canonical.html      the nav block, with no active entry set
    _footer_canonical.html   the footer block, complete

Each page file carries a pair of marker comments. Everything between and
including each pair is replaced. Nothing else in any file is touched.

    <!-- NAV:START ...        ... NAV:END -->
    <!-- FOOTER:START ...     ... FOOTER:END -->

WHY THIS RUNS HERE AND NOT IN THE BROWSER
-----------------------------------------
The obvious alternative is to fetch and inject the footer at page load. That
was considered and rejected on 19 August 2026, for four reasons:

  1. Almost every internal link on this site lives in the nav and the footer.
     Links present in served HTML are crawled more reliably than links that
     appear only after script execution, and this site exists to be found.
  2. The privacy notice link must not depend on JavaScript running. A notice a
     visitor can only reach conditionally is a weaker notice.
  3. Pages are previewed locally over file://, where fetch() is blocked as a
     cross-origin request. Injection would remove the ability to check a page
     before deploying it, which has caught real faults more than once.
  4. The site record's guarantee that no page is an orphan is verifiable by
     reading files only while the links are actually in the files.

The site's own convention is that a script enhances markup that already works.
The two hero figures both carry real geometry in the page and are replaced by
script on load. Injection would invert that for the site's entire link graph.

The cost of this choice, stated plainly: it is a step somebody has to run. The
compensation is that forgetting it fails loudly here, at the verification pass
below, rather than silently in a visitor's browser.

USAGE
-----
    python3 apply-chrome.py            apply, verify, and report
    python3 apply-chrome.py --check    verify only, change nothing

Run it from the folder holding the page files and the two fragments.
Exit code 0 means every page agrees. Any other exit code means stop.
"""

import sys
import re
import os
import shutil
import hashlib
from datetime import datetime

# --------------------------------------------------------------------------
# The page set. Adding a page to the site means adding it here, and that is
# deliberate: an explicit list fails loudly when a file is missing, where a
# directory glob would silently skip a page nobody noticed had been renamed.
# --------------------------------------------------------------------------
PAGES = [
    "index.html",
    "about.html",
    "work.html",
    "engagement.html",
    "contact.html",
    "platform.html",
    "monitoring-calibration.html",
    "interval-question.html",
    "spotting-ai-writing.html",
    "project-management.html",
    "technical-consulting.html",
    "ai-digital.html",
    "energy-systems.html",
    "privacy.html",
]

# The five pages with a nav slot, mapped to the exact anchor text of their
# entry. A page absent from this map correctly receives no active entry.
NAV_ACTIVE = {
    "index.html": "Home",
    "about.html": "About",
    "work.html": "The Work",
    "engagement.html": "The Engagement",
    "contact.html": "Contact",
}

NAV_FRAGMENT = "_nav_canonical.html"
FOOTER_FRAGMENT = "_footer_canonical.html"

BLOCKS = [
    ("nav", NAV_FRAGMENT, "<!-- NAV:START", "<!-- NAV:END -->"),
    ("footer", FOOTER_FRAGMENT, "<!-- FOOTER:START", "<!-- FOOTER:END -->"),
]


class Stop(Exception):
    """Raised for any condition that should halt the run without writing."""


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def write(path, text):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def normalise(text):
    """Collapse all runs of whitespace to a single space.

    VS Code's HTML formatter reflows markup to its own print width, so a file
    can be opened, changed, changed back, saved, and come out semantically
    identical and byte different. A byte comparison would report that as a
    fault, and a check that cries wolf gets ignored. Comparing normalised text
    is the guarantee actually worth having.
    """
    return re.sub(r"\s+", " ", text).strip()


def digest(text):
    return hashlib.sha256(normalise(text).encode("utf-8")).hexdigest()[:12]


def locate(text, start_marker, end_marker, filename, label):
    """Return (start_index, end_index) of one block, or raise.

    Both markers must appear exactly once. Two pairs in one file would make
    the replacement ambiguous and is far more likely to be damage than intent.
    """
    if text.count(start_marker) != 1:
        raise Stop(
            f"{filename}: expected exactly one '{start_marker}', "
            f"found {text.count(start_marker)}"
        )
    if text.count(end_marker) != 1:
        raise Stop(
            f"{filename}: expected exactly one '{end_marker}', "
            f"found {text.count(end_marker)}"
        )
    start = text.index(start_marker)
    end = text.index(end_marker) + len(end_marker)
    if end <= start:
        raise Stop(f"{filename}: {label} end marker precedes its start marker")

    # Snap the start back to the beginning of its line, so that the leading
    # indentation already in the page file is consumed by the replacement
    # rather than left in front of the fragment's own indentation. Without
    # this every block lands two spaces further right on each run, which is
    # invisible in a browser, silent in a byte comparison after whitespace
    # normalisation, and cumulative. It was caught by comparing the pages
    # outside the blocks against their originals, not by looking at output.
    line_start = text.rfind("\n", 0, start) + 1
    if text[line_start:start].strip() == "":
        start = line_start

    return start, end


def extract(text, start_marker, end_marker, filename, label):
    start, end = locate(text, start_marker, end_marker, filename, label)
    return text[start:end]


def render_nav(nav_source, page):
    """Return the nav with the active class set for this page, if it has one.

    The anchor is matched on its exact full tag rather than on the href alone.
    The logo anchor also points at index.html and carries class="nav-logo", so
    an href-only match would hit two elements on the homepage and set the
    active state on the logo. The match count is asserted rather than assumed,
    because a replacement whose anchor matches nothing changes the file not at
    all and still reports success.
    """
    label = NAV_ACTIVE.get(page)
    if label is None:
        return nav_source

    href = page
    old = f'<a href="{href}">{label}</a>'
    new = f'<a href="{href}" class="active">{label}</a>'

    if nav_source.count(old) != 1:
        raise Stop(
            f"{page}: the nav fragment contains {nav_source.count(old)} "
            f"instances of {old!r}, expected exactly 1. The fragment and "
            f"NAV_ACTIVE have gone out of step."
        )
    return nav_source.replace(old, new)


def strip_active(nav_text):
    """Remove the active class so navs from different pages can be compared."""
    return nav_text.replace(' class="active"', "")


# --------------------------------------------------------------------------
# Verification. Every check below states what it would look like if the thing
# it watches had failed, because a check incapable of failing confirms nothing.
# --------------------------------------------------------------------------

def verify(folder):
    problems = []
    nav_hashes = {}
    footer_hashes = {}
    active_found = {}

    known_files = {p for p in PAGES}
    known_files.add("shared.css")

    for page in PAGES:
        path = os.path.join(folder, page)
        if not os.path.exists(path):
            problems.append(f"{page}: file not found")
            continue
        text = read(path)

        try:
            nav = extract(text, "<!-- NAV:START", "<!-- NAV:END -->", page, "nav")
            footer = extract(
                text, "<!-- FOOTER:START", "<!-- FOOTER:END -->", page, "footer"
            )
        except Stop as exc:
            problems.append(str(exc))
            continue

        nav_hashes[page] = digest(strip_active(nav))
        footer_hashes[page] = digest(footer)

        # Which entry, if any, is marked active in this page's nav.
        marks = re.findall(r'<a href="([^"]+)" class="active">([^<]+)</a>', nav)
        if len(marks) > 1:
            problems.append(f"{page}: {len(marks)} active nav entries, expected at most 1")
        active_found[page] = marks[0][1] if marks else None

        expected = NAV_ACTIVE.get(page)
        if active_found[page] != expected:
            problems.append(
                f"{page}: active entry is {active_found[page]!r}, expected {expected!r}"
            )

        # Every internal link inside the two blocks must resolve to a real file.
        for href in re.findall(r'href="([^"]+)"', nav + footer):
            if href.startswith(("http", "mailto:", "#")):
                continue
            if href not in known_files:
                problems.append(f"{page}: link target {href!r} does not exist")

    # One nav shape and one footer shape across the whole site.
    if len(set(nav_hashes.values())) != 1:
        problems.append(
            "nav differs between pages: "
            + ", ".join(f"{p}={h}" for p, h in sorted(nav_hashes.items()))
        )
    if len(set(footer_hashes.values())) != 1:
        problems.append(
            "footer differs between pages: "
            + ", ".join(f"{p}={h}" for p, h in sorted(footer_hashes.items()))
        )

    return problems, nav_hashes, footer_hashes, active_found


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def main():
    check_only = "--check" in sys.argv
    folder = os.getcwd()

    print(f"Sinclair Dynamics chrome application")
    print(f"Folder: {folder}")
    print(f"Mode:   {'verify only, nothing will be written' if check_only else 'apply then verify'}")
    print()

    if not check_only:
        # Read both fragments before touching anything, so a missing or
        # malformed fragment stops the run before any file is modified.
        sources = {}
        for label, fragment, start_marker, end_marker in BLOCKS:
            path = os.path.join(folder, fragment)
            if not os.path.exists(path):
                raise Stop(f"fragment not found: {fragment}")
            body = read(path).rstrip("\n")
            # The fragment must itself be a complete, well-formed block.
            if body.count(start_marker) != 1 or body.count(end_marker) != 1:
                raise Stop(f"{fragment}: does not contain exactly one marker pair")
            if not body.lstrip().startswith(start_marker):
                raise Stop(f"{fragment}: does not begin with {start_marker}")
            if not body.rstrip().endswith(end_marker):
                raise Stop(f"{fragment}: does not end with {end_marker}")
            sources[label] = body

        missing = [p for p in PAGES if not os.path.exists(os.path.join(folder, p))]
        if missing:
            raise Stop("pages missing from folder: " + ", ".join(missing))

        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = os.path.join(folder, f"_backup-chrome-{stamp}")
        os.makedirs(backup, exist_ok=True)

        changed, unchanged = [], []

        for page in PAGES:
            path = os.path.join(folder, page)
            original = read(path)
            shutil.copy2(path, os.path.join(backup, page))

            text = original
            for label, fragment, start_marker, end_marker in BLOCKS:
                block = sources[label]
                if label == "nav":
                    block = render_nav(block, page)
                start, end = locate(text, start_marker, end_marker, page, label)
                text = text[:start] + block + text[end:]

            if text != original:
                write(path, text)
                changed.append(page)
            else:
                unchanged.append(page)

        print(f"Backup written to {os.path.basename(backup)}")
        print(f"Changed:   {len(changed)} page(s)")
        for p in changed:
            print(f"           {p}")
        if unchanged:
            print(f"Unchanged: {len(unchanged)} page(s) already matched the fragments")
        print()

    problems, nav_hashes, footer_hashes, active_found = verify(folder)

    print("VERIFICATION")
    print(f"  Pages checked:        {len(nav_hashes)} of {len(PAGES)}")
    if nav_hashes:
        print(f"  Nav shapes found:     {len(set(nav_hashes.values()))} "
              f"(expected 1) -> {sorted(set(nav_hashes.values()))}")
    if footer_hashes:
        print(f"  Footer shapes found:  {len(set(footer_hashes.values()))} "
              f"(expected 1) -> {sorted(set(footer_hashes.values()))}")
    marked = {p: a for p, a in active_found.items() if a}
    print(f"  Active nav entries:   {len(marked)} (expected {len(NAV_ACTIVE)})")
    for p, a in sorted(marked.items()):
        print(f"                        {p} -> {a}")
    print()

    if problems:
        print(f"FAILED. {len(problems)} problem(s):")
        for prob in problems:
            print(f"  - {prob}")
        if not check_only:
            print()
            print("The backup folder holds every file as it was before this run.")
        return 1

    print("PASSED. Every page carries the same nav and the same footer,")
    print("and every active entry is the one its filename calls for.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Stop as exc:
        print(f"STOPPED: {exc}", file=sys.stderr)
        sys.exit(2)
