#!/usr/bin/env python3
"""
apply-chrome.py
Sinclair Dynamics website: single-source the nav and footer across every page.

WHAT THIS IS
------------
The nav and footer are the same on every page of this site, apart from which
nav entry is marked active. Until now they were duplicated into each page file
by hand, so changing either meant editing thirteen files and hoping none of
them drifted. This script makes three fragment files authoritative and writes
them into every page:

    _nav_canonical.html      the nav block, with no active entry set
    _footer_canonical.html   the footer block, complete
    _consent_canonical.html  the consent banner, complete

Each page file carries a pair of marker comments per block. Everything
between and including each pair is replaced. Nothing else in any file is
touched.

    <!-- NAV:START ...        ... NAV:END -->
    <!-- FOOTER:START ...     ... FOOTER:END -->
    <!-- CONSENT:START ...    ... CONSENT:END -->

NAV and FOOTER markers must already exist in every page; their absence stops
the run, because both are structural furniture every page has carried since
it was written; a page missing either has a real problem worth surfacing
loudly rather than a guess worth making quietly.

CONSENT is different, once. Added 19 August 2026, to a page set that has
never carried it. The first time this script finds a page with no CONSENT
markers at all, it inserts the fragment fresh, immediately before </body>,
writing the marker pair as it does. Every run after that finds the markers
this run just wrote and takes the same replace path nav and footer already
do. A page carrying one marker but not the other, or more than one of
either, is not bootstrapped: that shape means the page is already damaged
rather than simply new, and the run stops rather than guessing.

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
    python apply-chrome.py            apply, verify, and report
    python apply-chrome.py --check    verify only, change nothing

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
#
# What that reasoning missed, found 23 August 2026. The list fails loudly for
# a name that is in it and has no file. It cannot fail at all for a page that
# exists on the site and is not in it, because such a page is invisible to
# every check below: it is never opened, never hashed and never compared.
# machine-was-never-the-ceiling.html shipped on 22 August, was added to
# sitemap.xml and to the site record, and was not added here. It therefore
# received no single-sourced chrome for a day, and nothing could have said so.
# Its markup happened to be correct, having been copied by hand from
# spotting-ai-writing.html, which is the part that makes this hard to see: a
# copy that is documented as single-sourced is indistinguishable from a page
# that actually is one. Only this list decides which it is.
#
# The reconciliation against sitemap.xml in verify() is the fix. The sitemap
# is the register that was complete, it is maintained for its own reasons, and
# a page missing from either list is now reported rather than remembered.
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
    "machine-was-never-the-ceiling.html",
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
CONSENT_FRAGMENT = "_consent_canonical.html"

# The fifth field is where a block may be bootstrapped from if its markers
# are wholly absent. None means the markers must already exist, and their
# absence stops the run. A string names the text to insert immediately
# before, the first time only.
BLOCKS = [
    ("nav", NAV_FRAGMENT, "<!-- NAV:START", "<!-- NAV:END -->", None),
    ("footer", FOOTER_FRAGMENT, "<!-- FOOTER:START", "<!-- FOOTER:END -->", None),
    (
        "consent",
        CONSENT_FRAGMENT,
        "<!-- CONSENT:START",
        "<!-- CONSENT:END -->",
        "</body>",
    ),
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


def locate(text, start_marker, end_marker, filename, label, bootstrap_before=None):
    """Return (start_index, end_index) of one block, or raise.

    Both markers must appear exactly once. Two pairs in one file would make
    the replacement ambiguous and is far more likely to be damage than intent.

    The one exception: if neither marker appears at all, and bootstrap_before
    is given, this returns a zero-length span immediately before the first
    occurrence of bootstrap_before, rather than raising. The caller then
    inserts the block there instead of replacing anything, which is the path
    a block takes the one time it is new to a page. bootstrap_before must
    itself appear exactly once; if it does not, there is no safe place to
    insert and the run stops rather than guessing one.

    A count of one for one marker and zero for the other, or more than one of
    either, is never bootstrapped regardless of bootstrap_before. That shape
    means the page is already damaged rather than simply new.
    """
    start_count = text.count(start_marker)
    end_count = text.count(end_marker)

    if start_count == 0 and end_count == 0 and bootstrap_before is not None:
        anchor_count = text.count(bootstrap_before)
        if anchor_count != 1:
            raise Stop(
                f"{filename}: {label} has no markers to bootstrap from, and "
                f"'{bootstrap_before}' appears {anchor_count} times in the "
                f"file, expected exactly 1. No safe place to insert it."
            )
        anchor = text.index(bootstrap_before)
        return anchor, anchor

    if start_count != 1:
        raise Stop(
            f"{filename}: expected exactly one '{start_marker}', "
            f"found {start_count}"
        )
    if end_count != 1:
        raise Stop(
            f"{filename}: expected exactly one '{end_marker}', " f"found {end_count}"
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


SITEMAP = "sitemap.xml"


def reconcile_with_sitemap(folder):
    """Compare PAGES against sitemap.xml and report either list being short.

    This exists because of the failure recorded above PAGES: nothing in this
    script could see a page that had shipped and not been enrolled. The
    sitemap is the register that was complete on the day that happened, it is
    maintained for search reasons rather than for this one, and two lists
    maintained for different reasons are unlikely to be forgotten in the same
    sitting.

    What it would look like if it failed: a page present on the site and in
    the sitemap, absent from PAGES, is named here. So is the reverse, a page
    in PAGES with no sitemap entry, which is a page search engines are not
    being told about.

    The homepage is the one mapping that is not literal: the sitemap declares
    the site root, which is served by index.html.
    """
    path = os.path.join(folder, SITEMAP)
    if not os.path.exists(path):
        return [f"{SITEMAP} not found, so the page list could not be reconciled"]

    text = read(path)
    locs = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", text)
    if not locs:
        return [f"{SITEMAP}: no <loc> entries found, expected one per page"]

    listed = set()
    for loc in locs:
        tail = re.sub(r"^https?://[^/]+", "", loc)
        tail = tail.lstrip("/")
        listed.add(tail if tail else "index.html")

    known = set(PAGES)
    problems = []
    for page in sorted(listed - known):
        problems.append(
            f"{page}: in {SITEMAP} but not in PAGES, so it receives no "
            f"single-sourced chrome and no check in this script can see it"
        )
    for page in sorted(known - listed):
        problems.append(
            f"{page}: in PAGES but not in {SITEMAP}, so search engines are "
            f"not being told it exists"
        )
    return problems


# --------------------------------------------------------------------------
# Verification. Every check below states what it would look like if the thing
# it watches had failed, because a check incapable of failing confirms nothing.
# --------------------------------------------------------------------------


def verify(folder):
    problems = reconcile_with_sitemap(folder)
    nav_hashes = {}
    footer_hashes = {}
    consent_hashes = {}
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
            consent = extract(
                text, "<!-- CONSENT:START", "<!-- CONSENT:END -->", page, "consent"
            )
        except Stop as exc:
            problems.append(str(exc))
            continue

        nav_hashes[page] = digest(strip_active(nav))
        footer_hashes[page] = digest(footer)
        consent_hashes[page] = digest(consent)

        # Which entry, if any, is marked active in this page's nav.
        marks = re.findall(r'<a href="([^"]+)" class="active">([^<]+)</a>', nav)
        if len(marks) > 1:
            problems.append(
                f"{page}: {len(marks)} active nav entries, expected at most 1"
            )
        active_found[page] = marks[0][1] if marks else None

        expected = NAV_ACTIVE.get(page)
        if active_found[page] != expected:
            problems.append(
                f"{page}: active entry is {active_found[page]!r}, expected {expected!r}"
            )

        # Every internal link inside the three blocks must resolve to a real file.
        for href in re.findall(r'href="([^"]+)"', nav + footer + consent):
            if href.startswith(("http", "mailto:", "#")):
                continue
            if href not in known_files:
                problems.append(f"{page}: link target {href!r} does not exist")

        # The consent script must be present exactly once per page: it wires
        # itself up by element id, and a second copy would attach a second
        # set of listeners and record a choice twice per click.
        script_count = consent.count("(function () {")
        if script_count != 1:
            problems.append(
                f"{page}: consent block contains {script_count} copies of "
                f"its own script, expected exactly 1"
            )

    # One nav shape, one footer shape, one consent shape across the whole site.
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
    if len(set(consent_hashes.values())) != 1:
        problems.append(
            "consent differs between pages: "
            + ", ".join(f"{p}={h}" for p, h in sorted(consent_hashes.items()))
        )

    return problems, nav_hashes, footer_hashes, consent_hashes, active_found


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------


def main():
    check_only = "--check" in sys.argv
    folder = os.getcwd()

    print(f"Sinclair Dynamics chrome application")
    print(f"Folder: {folder}")
    print(
        f"Mode:   {'verify only, nothing will be written' if check_only else 'apply then verify'}"
    )
    print()

    if not check_only:
        # Read both fragments before touching anything, so a missing or
        # malformed fragment stops the run before any file is modified.
        sources = {}
        for label, fragment, start_marker, end_marker, bootstrap_before in BLOCKS:
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
            for label, fragment, start_marker, end_marker, bootstrap_before in BLOCKS:
                block = sources[label]
                if label == "nav":
                    block = render_nav(block, page)
                start, end = locate(
                    text, start_marker, end_marker, page, label, bootstrap_before
                )
                # A zero-length span is the bootstrap case: nothing is being
                # replaced, so the block needs its own trailing newline to
                # land as a clean line rather than run into whatever follows.
                piece = block if start != end else block + "\n"
                text = text[:start] + piece + text[end:]

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

    problems, nav_hashes, footer_hashes, consent_hashes, active_found = verify(folder)

    print("VERIFICATION")
    print(f"  Pages checked:        {len(nav_hashes)} of {len(PAGES)}")
    if nav_hashes:
        print(
            f"  Nav shapes found:     {len(set(nav_hashes.values()))} "
            f"(expected 1) -> {sorted(set(nav_hashes.values()))}"
        )
    if footer_hashes:
        print(
            f"  Footer shapes found:  {len(set(footer_hashes.values()))} "
            f"(expected 1) -> {sorted(set(footer_hashes.values()))}"
        )
    if consent_hashes:
        print(
            f"  Consent shapes found: {len(set(consent_hashes.values()))} "
            f"(expected 1) -> {sorted(set(consent_hashes.values()))}"
        )
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

    print("PASSED. Every page carries the same nav, the same footer, and the")
    print("same consent banner, and every active entry is the one its")
    print("filename calls for.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Stop as exc:
        print(f"STOPPED: {exc}", file=sys.stderr)
        sys.exit(2)
