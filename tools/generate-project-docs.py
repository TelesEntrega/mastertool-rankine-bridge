#!/usr/bin/env python3
"""Atalho: mastertool-bridge document <diretorio>."""
import sys

from mastertool_bridge.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["document", *sys.argv[1:]]))
