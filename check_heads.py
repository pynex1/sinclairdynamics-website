# check_heads.py
# Repository: sinclairdynamics-website
#
# Reads the <head> block of every page on the site and checks it against what
# the site record says a head block must carry.
#
#   python check_heads.py                 # checks the repository it sits in
#   python check_heads.py --dir scratch   # checks a copy, for fault injection
#
# What it is for, and what it is not for.
#
#   It does not ask whether a title or a description is any good. That is the
#   positioning reference's business and Ainsley's. It asks whether the tags
#   are present, whether the pairs that must agree do agree, and whether the
#   values that have a stated limit sit inside it.
#
#   That is a real question because nothing else on this site reads a head
#   block. On 5 September 2026 a page shipped with no head metadata at all and
#   nothing reported it, because the page renders correctly without one.
#
# Every check reports; none raises. One failure never hides the ones after it.
#
# ONE CHECK IN SITE RECORD ITEM 26 IS NOT IMPLEMENTED HERE, DELIBERATELY.
#
#   Item 26 asks for "title at or under 600 rendered pixels". That is a font
#   metric and not a character count: it needs Barlow Condensed measured per
#   glyph at the size Google renders. Building it means carrying a font file
#   and an imaging library into this repository, which is more machinery than
#   the other seven checks put together.
#
#   It is declared in the report as NOT CHECKED rather than left out, so the
#   report cannot say eight checks and mean seven. Site record item 26 stays
#   open on that one point.
#
# Revisions:
#   Session 66, 7 September 2026: created. Seven of item 26's eight checks.

import argparse
import os
import re
import sys


# ---------------------------------------------------------------------------
# WHAT A HEAD BLOCK MUST CARRY
# ---------------------------------------------------------------------------

# The eighteen tags, enumerated rather than counted.
#
# The site record at Session 64 records the count as eighteen and separately
# enumerates the Open Graph set as five tags plus og:site_name, which is six.
# The files carry eight: og:image:width and og:image:height are absent from
# that prose. The count of eighteen is right and the enumeration was not, so
# this list is built from the files rather than from the sentence.
REQUIRED_META = [
    "charset",
    "viewport",
    "description",
    "author",
    "robots",
    "og:type",
    "og:url",
    "og:title",
    "og:description",
    "og:image",
    "og:image:width",
    "og:image:height",
    "og:site_name",
    "twitter:card",
    "twitter:title",
    "twitter:description",
    "twitter:image",
]
# Plus <title>, which is the eighteenth. Canonical is the nineteenth element
# and item 26 asserts it on its own terms, so it is checked separately below.

HOST = "https://www.sinclairdynamics.co"

# The homepage canonical is the bare root, not index.html. Every other page
# canonicalises to its own filename.
ROOT_PAGE = "index.html"

# The search description ceiling. Google truncates the snippet on rendered
# width, which is roughly 155 to 160 characters desktop. The site record sets
# the ceiling at 158 and calls it hard.
DESCRIPTION_MAX = 158

# Files that are chrome fragments rather than pages. apply-chrome.py writes
# these into the pages; they carry no head of their own.
FRAGMENT_PREFIX = "_"

EM_DASH = "\u2014"


# ---------------------------------------------------------------------------
# READING A HEAD BLOCK
# ---------------------------------------------------------------------------

HEAD = re.compile(r"<head[ >].*?</head>|<head>.*?</head>", re.S | re.I)
COMMENT = re.compile(r"<!--(.*?)-->", re.S)

# A meta tag's identity is whichever of these attributes it carries.
META_TAG = re.compile(r"<meta\b([^>]*)>", re.S | re.I)
ATTR = re.compile(r'(\w[\w:-]*)\s*=\s*"([^"]*)"', re.S)

TITLE = re.compile(r"<title>(.*?)</title>", re.S | re.I)
CANONICAL = re.compile(
    r'<link\b[^>]*rel="canonical"[^>]*>', re.S | re.I)
CANONICAL_HREF = re.compile(r'href="([^"]*)"', re.S | re.I)


def head_of(path):
    """
    The head block as raw text, or None if the file has no <head> element.

    Read as text rather than parsed, because what is being checked includes
    comments and the shape of the block, and a parser discards both.
    """
    with open(path, encoding="utf-8") as f:
        source = f.read()
    m = HEAD.search(source)
    return m.group(0) if m else None


def metas_in(head):
    """
    Every meta tag in the block, as {identity: content}.

    Identity is the value of name, property, or the literal string "charset"
    for the charset declaration, which carries neither. Order is preserved so
    that a duplicate is visible as a repeat rather than silently collapsed.
    """
    found = []
    for m in META_TAG.finditer(head):
        attrs = dict(ATTR.findall(m.group(1)))
        if "charset" in attrs:
            found.append(("charset", attrs["charset"]))
        elif "name" in attrs:
            found.append((attrs["name"], attrs.get("content", "")))
        elif "property" in attrs:
            found.append((attrs["property"], attrs.get("content", "")))
    return found


def title_of(head):
    m = TITLE.search(head)
    return m.group(1).strip() if m else None


def canonical_of(head):
    m = CANONICAL.search(head)
    if not m:
        return None
    href = CANONICAL_HREF.search(m.group(0))
    return href.group(1) if href else None


def analytics_comments_in(head):
    """
    Comments in the head that concern analytics.

    The site record records six variants replaced by one on 6 September 2026,
    the previous ones having described a consent gate that had been live since
    19 August. A stale comment in source is read by nothing and says something
    untrue for as long as nobody opens the file.
    """
    return [c.strip() for c in COMMENT.findall(head)
            if "analytics" in c.lower()]


def pages_in(directory):
    """Every page file, excluding the chrome fragments."""
    names = [n for n in sorted(os.listdir(directory))
             if n.endswith(".html") and not n.startswith(FRAGMENT_PREFIX)]
    return [(n, os.path.join(directory, n)) for n in names]


# ---------------------------------------------------------------------------
# REPORTING
# ---------------------------------------------------------------------------

class Report:
    def __init__(self):
        self.rows = []
        self.skipped = []

    def add(self, name, passed, detail=""):
        self.rows.append((name, passed, detail))

    def skip(self, name, reason):
        self.skipped.append((name, reason))

    def show(self):
        for name, passed, detail in self.rows:
            print("  %-6s %s" % ("PASS" if passed else "FAIL", name))
            for line in (detail or "").splitlines():
                print("         %s" % line)
        for name, reason in self.skipped:
            print("  %-6s %s" % ("SKIP", name))
            for line in reason.splitlines():
                print("         %s" % line)
        failed = sum(1 for _, p, _ in self.rows if not p)
        print("")
        print("  %d checks, %d failed, %d not implemented"
              % (len(self.rows), failed, len(self.skipped)))
        return failed


# ---------------------------------------------------------------------------
# THE CHECKS
# ---------------------------------------------------------------------------

def run_checks(directory):
    report = Report()
    pages = pages_in(directory)

    if not pages:
        report.add("pages found in %s" % directory, False,
                   "no .html files that are not chrome fragments")
        return report

    # Read every head once. A page with no <head> at all is the failure the
    # third article shipped with, so it is reported here and then excluded
    # from the checks that would all fail for the same single reason.
    heads = {}
    headless = []
    for name, path in pages:
        h = head_of(path)
        if h is None:
            headless.append(name)
        else:
            heads[name] = h

    report.add("every page has a head block (%d pages)" % len(pages),
               not headless,
               "\n".join("%s: no <head> element" % n for n in headless))

    # 1. The eighteen tags are present on every page.
    faults = []
    for name, head in heads.items():
        present = {ident for ident, _ in metas_in(head)}
        missing = [t for t in REQUIRED_META if t not in present]
        if title_of(head) is None:
            missing.append("<title>")
        if missing:
            faults.append("%s: missing %s" % (name, ", ".join(missing)))
    report.add("all eighteen tags present on every page",
               not faults, "\n".join(faults))

    # 2. The og and twitter pairs agree.
    #
    #    Three pairs carry the same string by design. A page edited on one side
    #    only is the fault this catches, and it is invisible on the rendered
    #    page because neither tag is displayed anywhere.
    PAIRS = [("og:title", "twitter:title"),
             ("og:description", "twitter:description"),
             ("og:image", "twitter:image")]
    faults = []
    for name, head in heads.items():
        values = dict(metas_in(head))
        for a, b in PAIRS:
            if a in values and b in values and values[a] != values[b]:
                faults.append("%s: %s and %s differ" % (name, a, b))
                faults.append("    %s = %s" % (a, values[a][:90]))
                faults.append("    %s = %s" % (b, values[b][:90]))
    report.add("og and twitter pairs agree on every page",
               not faults, "\n".join(faults))

    # 3. Canonical matches host and filename, and og:url agrees with it.
    #
    #    index.html canonicalises to the bare root. Every other page
    #    canonicalises to its own filename on the same host.
    faults = []
    for name, head in heads.items():
        want = HOST + "/" if name == ROOT_PAGE else "%s/%s" % (HOST, name)
        got = canonical_of(head)
        if got is None:
            faults.append("%s: no canonical link" % name)
            continue
        if got != want:
            faults.append("%s: canonical is %s, expected %s"
                          % (name, got, want))
        og_url = dict(metas_in(head)).get("og:url")
        if og_url is not None and og_url != got:
            faults.append("%s: og:url is %s, canonical is %s"
                          % (name, og_url, got))
    report.add("canonical matches host and filename, and og:url agrees",
               not faults, "\n".join(faults))

    # 4. The search description sits at or under the snippet ceiling.
    faults = []
    for name, head in heads.items():
        d = dict(metas_in(head)).get("description")
        if d is not None and len(d) > DESCRIPTION_MAX:
            faults.append("%s: %d characters, ceiling is %d"
                          % (name, len(d), DESCRIPTION_MAX))
    report.add("search description at or under %d characters"
               % DESCRIPTION_MAX,
               not faults, "\n".join(faults))

    # 5. No keywords tag anywhere.
    #
    #    Removed site-wide on 6 September 2026. No engine uses it as a positive
    #    signal and on Bing it is understood to feed spam detection, which the
    #    four discipline pages were exactly the shape to trigger.
    faults = [name for name, head in heads.items()
              if "keywords" in {ident for ident, _ in metas_in(head)}]
    report.add("no keywords tag on any page",
               not faults,
               "\n".join("%s: carries a keywords tag" % n for n in faults))

    # 6. Exactly one analytics comment per page, every one opening the same way.
    #
    #    What this is guarding against is the state before 6 September 2026,
    #    when six different analytics comments were in use and five of them
    #    described a consent gate that had gone live on 19 August. A comment in
    #    source is read by nothing and stays untrue until somebody opens the
    #    file.
    #
    #    THIS CHECK ASSERTED EXACT IDENTITY UNTIL SESSION 66 AND WAS WRONG TO.
    #    privacy.html carries the site-wide comment plus two sentences that
    #    belong only to that page: that it is the disclosure half of the gate,
    #    and that anything the banner starts collecting has to be described
    #    there first. That is deliberate and correct, and item 26 asks for one
    #    comment rather than for one wording. Identity was stricter than the
    #    spec and it failed on intentional content.
    #
    #    So the test is a shared opening rather than identity: every comment on
    #    the site must be the shortest one, or the shortest one plus an
    #    addendum. A variant from the six would diverge mid-sentence and would
    #    not carry the shortest as a prefix, so it still fails. A page-specific
    #    extension passes. There is no literal here to go stale, because the
    #    baseline is measured from the pages themselves each run.
    counts = {name: analytics_comments_in(head)
              for name, head in heads.items()}
    faults = ["%s: %d analytics comments, expected 1" % (n, len(c))
              for n, c in sorted(counts.items()) if len(c) != 1]
    singles = {n: re.sub(r"\s+", " ", c[0])
               for n, c in counts.items() if len(c) == 1}
    extended = []
    if singles:
        base = min(singles.values(), key=len)
        for n, text in sorted(singles.items()):
            if not text.startswith(base):
                faults.append("%s: analytics comment diverges from the "
                              "site-wide one" % n)
                faults.append("    reads:    %s" % text[:110])
                faults.append("    expected: %s" % base[:110])
            elif text != base:
                extended.append("%s extends it by %d characters"
                                % (n, len(text) - len(base)))
    report.add("exactly one analytics comment per page, all opening the same",
               not faults,
               "\n".join(faults) if faults else "\n".join(extended))

    # 7. No em dash in any head block.
    #
    #    House rule. In a head it matters more than elsewhere, because these
    #    strings are what a search result and a shared card display, and
    #    nobody proofreads a tag they cannot see on the page.
    faults = []
    for name, head in sorted(heads.items()):
        if EM_DASH in head:
            for ident, content in metas_in(head):
                if EM_DASH in content:
                    faults.append("%s: em dash in %s" % (name, ident))
            t = title_of(head)
            if t and EM_DASH in t:
                faults.append("%s: em dash in <title>" % name)
            if not any(f.startswith(name + ":") for f in faults):
                faults.append("%s: em dash in the head block, outside any "
                              "tag value" % name)
    report.add("no em dash in any head block",
               not faults, "\n".join(faults))

    # 8. NOT IMPLEMENTED. See the note at the head of this file.
    report.skip("title at or under 600 rendered pixels",
                "not implemented: needs font metrics rather than a character\n"
                "count. Site record item 26 stays open on this point.\n"
                "Named exception when it is built: "
                "the-document-was-always-the-substitute.html")

    return report


def main():
    ap = argparse.ArgumentParser(
        description="Check every page's head block against the site record.")
    ap.add_argument("--dir", default=None,
                    help="directory to check. Defaults to the directory this "
                         "script sits in.")
    args = ap.parse_args()

    directory = args.dir or os.path.dirname(os.path.abspath(__file__))
    if not os.path.isdir(directory):
        print("Not a directory: %s" % directory)
        return 1

    print("Checking head blocks in %s" % directory)
    print("")
    failed = run_checks(directory).show()
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
