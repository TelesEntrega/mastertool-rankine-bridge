# -*- coding: utf-8 -*-
"""Logger simples e auto-contido para os scripts internos (IronPython 2.7).

Gera log texto e JSON Lines em workspace/logs/. Nunca registra credenciais.
Campos JSON: timestamp, level, script, operation, project, object, result,
error, duration_ms, read_only.
"""
from __future__ import print_function

import json
import os

from common import file_io


class ScriptLogger(object):

    def __init__(self, script_name, log_dir=None):
        self.script_name = script_name
        self.log_dir = log_dir
        self._text_path = None
        self._json_path = None
        if log_dir:
            try:
                file_io.ensure_dir(log_dir)
                stamp = file_io.timestamp()
                base = "%s_%s" % (stamp, file_io.safe_filename(script_name))
                self._text_path = os.path.join(log_dir, base + ".log")
                self._json_path = os.path.join(log_dir, base + ".jsonl")
            except Exception as exc:
                print("[WARN] Nao foi possivel criar diretorio de log: %s" % exc)
                self.log_dir = None

    def _emit(self, level, message, **fields):
        line = "[%s] %s" % (level, message)
        print(line)
        if self._text_path:
            try:
                file_io.append_text(self._text_path, line + "\n")
            except Exception:
                pass
        if self._json_path:
            try:
                record = {
                    "timestamp": file_io.iso_now(),
                    "level": level,
                    "script": self.script_name,
                    "message": message,
                    "read_only": True,
                }
                record.update(fields)
                file_io.append_text(
                    self._json_path,
                    json.dumps(record, ensure_ascii=False, default=str) + "\n")
            except Exception:
                pass

    def info(self, message, **fields):
        self._emit("INFO", message, **fields)

    def ok(self, message, **fields):
        self._emit("OK", message, **fields)

    def warn(self, message, **fields):
        self._emit("WARN", message, **fields)

    def error(self, message, **fields):
        self._emit("ERROR", message, **fields)

    def paths(self):
        return {"text": self._text_path, "json": self._json_path}
