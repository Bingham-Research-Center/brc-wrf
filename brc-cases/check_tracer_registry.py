#!/usr/bin/env python3
"""Check the exact research tracer package, optionally its generated allocation code.

Metadata only: this neither opens NetCDF nor executes WRF.
"""
import argparse
import re
from pathlib import Path


def check(root, generated=False, count=12):
    lines = (root / "Registry/Registry.EM").read_text().splitlines()
    assert count > 0, "positive scalar count required"
    expected = [f"tr17_{n}" for n in range(1, count + 1)]
    states = [line.split() for line in lines
              if re.match(r"^state\s+real\s+tr17_\d+\s", line)]
    assert [row[2] for row in states] == expected, f"expected exactly tr17_1..{count}, once each"
    for row in states:
        assert row[3:8] == ["ikjftb", "tracer", "1", "-", "irhusdf=(bdy_interp:dt)"], row
    packages = [line.split() for line in lines
                if re.match(r"^package\s+tracer_test1\s", line)]
    assert packages == [["package", "tracer_test1", "tracer_opt==2", "-",
                         "tracer:" + ",".join(expected)]], "package membership differs"
    if generated:
        text = (root / "inc/scalar_indices.inc").read_text()
        active = re.findall(r"^\s*F_(tr17_\d+)\s*=\s*\.TRUE\.", text, re.M | re.I)
        assert active == expected, f"generated active tracers differ: {active}"
        for name in expected:
            assert re.search(rf"tracer_dname_table\([^\n]+\)\s*=\s*'{name}'", text), name
    print(f"PASS: {root}: {count} tracer declarations and exact tracer_opt=2 membership"
          + ("; generated allocation metadata agrees" if generated else ""))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--generated", action="store_true")
    parser.add_argument("--count", type=int, default=12,
                        help="expected package size (use 24 to audit the October 6 release)")
    args = parser.parse_args()
    check(args.root, args.generated, args.count)
