#!/usr/bin/env python3
"""Atalho: mastertool-bridge inspect <diretorio>."""
import sys

from mastertool_bridge.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["inspect", *sys.argv[1:]]))
