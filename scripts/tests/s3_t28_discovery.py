"""Deciding guards for the task's driver-free unittest discovery proof."""

import importlib.abc
import unittest
from importlib.machinery import ModuleSpec
from types import ModuleType
from typing import Any


class DenyStoreDrivers(importlib.abc.MetaPathFinder):
    s3_t28_tripwire = True

    def find_spec(self, fullname: str, *args: Any) -> ModuleSpec | None:
        if fullname.split(".")[0] in {"duckdb", "psycopg"}:
            raise AssertionError("INVENTED-driver-import-tripwire")
        return None


def require_cases(
    loader: unittest.TestLoader, module: ModuleType
) -> unittest.TestSuite:
    suite = loader.loadTestsFromModule(module)
    if suite.countTestCases() == 0:
        raise AssertionError("INVENTED-empty-test-module")
    return suite
