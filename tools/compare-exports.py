#!/usr/bin/env python3
"""Atalho: mastertool-bridge compare <export-a> <export-b>."""
import sys

from mastertool_bridge.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["compare", *sys.argv[1:]]))
