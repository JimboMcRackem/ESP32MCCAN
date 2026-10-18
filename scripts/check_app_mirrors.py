#!/usr/bin/env python3
"""Check data/app.js's mirrors of two firmware constants.

    python scripts/check_app_mirrors.py

The app and the LittleFS image are separate flashes, so the app hardcodes a
copy of PROTOCOL_VERSION and a copy of the output list. Nothing in the build
holds either in step, and PROTOCOL_VERSION already went stale at 2 on this
branch, which would have tripped the app's version-mismatch banner on every
connect with no firmware fault to find.

Deliberately NOT an extra_scripts pre-build hook: a bug in this checker must
not be able to block a flash. Run it by hand, or from CI.

Exits 0 when the mirrors agree, 1 on a mismatch, 2 if a value could not be
read at all (a moved file or a reworded declaration -- also a failure, since
it means the check is no longer checking anything).
"""

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

WEB_PROTOCOL_H = os.path.join(ROOT, "src", "domain", "web_protocol.h")
OUTPUTS_H = os.path.join(ROOT, "src", "domain", "outputs.h")
APP_JS = os.path.join(ROOT, "data", "app.js")


def read(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except OSError as e:
        sys.exit("%s: cannot read: %s" % (path, e))


def one(pattern, text, path, what, flags=0):
    found = re.findall(pattern, text, flags)
    if len(found) != 1:
        sys.exit(
            "%s: expected exactly one %s, found %d. The declaration moved or\n"
            "was reworded, so this check is no longer checking anything.\n"
            "Pattern: %s" % (path, what, len(found), pattern)
        )
    return found[0]


def main():
    # Firmware side.
    fw_version = int(one(
        r"constexpr\s+int\s+kProtocolVersion\s*=\s*(\d+)\s*;",
        read(WEB_PROTOCOL_H), WEB_PROTOCOL_H, "kProtocolVersion"))

    # OUT_COUNT is the last enumerator of OutputIndex and has no initialiser,
    # so count the named outputs that precede it instead of parsing a literal.
    outputs_h = read(OUTPUTS_H)
    body = one(r"enum\s+OutputIndex\s*:\s*uint8_t\s*\{(.*?)\}",
               outputs_h, OUTPUTS_H, "OutputIndex enum", re.S)
    body = re.sub(r"//[^\n]*", "", body)
    names = [n for n in re.findall(r"\b(OUT_[A-Z0-9_]+)\b", body)
             if n != "OUT_COUNT"]
    if "OUT_COUNT" not in body:
        sys.exit("%s: OutputIndex has no OUT_COUNT terminator" % OUTPUTS_H)
    fw_out_count = len(names)

    # App side.
    app_js = read(APP_JS)
    app_version = int(one(
        r"const\s+PROTOCOL_VERSION\s*=\s*(\d+)\s*;",
        app_js, APP_JS, "PROTOCOL_VERSION"))
    app_outputs = one(r"const\s+OUTPUT_NAMES\s*=\s*\[(.*?)\]\s*;",
                      app_js, APP_JS, "OUTPUT_NAMES", re.S)
    app_out_count = len(re.findall(r'"[^"]*"', app_outputs))

    problems = []
    if fw_version != app_version:
        problems.append(
            "PROTOCOL_VERSION: data/app.js has %d, "
            "src/domain/web_protocol.h kProtocolVersion is %d"
            % (app_version, fw_version))
    if fw_out_count != app_out_count:
        problems.append(
            "OUTPUT_NAMES length: data/app.js has %d entries, "
            "src/domain/outputs.h OUT_COUNT is %d"
            % (app_out_count, fw_out_count))

    if problems:
        print("data/app.js is out of step with the firmware:", file=sys.stderr)
        for p in problems:
            print("  - " + p, file=sys.stderr)
        print("\nThe firmware is authoritative. Update data/app.js.",
              file=sys.stderr)
        return 1

    print("app.js mirrors OK: PROTOCOL_VERSION=%d, %d outputs"
          % (fw_version, fw_out_count))
    # Order is NOT checked -- only the count. A reordered OutputIndex still
    # passes here and is caught only by the on-device output walk.
    return 0


if __name__ == "__main__":
    sys.exit(main())
