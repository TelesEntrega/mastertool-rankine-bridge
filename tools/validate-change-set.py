#!/usr/bin/env python3
"""Atalho: mastertool-bridge validate-change-set <arquivo>."""
import sys

from mastertool_bridge.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["validate-change-set", *sys.argv[1:]]))
