#!/usr/bin/env python3
"""
Offline test runner for environments with no PyPI/apt access (no fastapi,
no real pytest available). Runs plain `def test_*` functions found in the
given test files, providing stdlib-only versions of the two fixtures the
paper-trading tests actually use: `tmp_path` and `monkeypatch`.

Usage:
    python3 _offline_pytest_shim/run_tests.py tests/test_paper_execution.py tests/test_paper_monitor.py ...

Limitations (by design, scoped to what these test files need):
- No pytest.fixture/parametrize/mark support beyond what's already absent.
- `pytest.raises(exc, match=...)` is supported via the bundled pytest shim.
- Setup/teardown is per-test-function only (no class-based tests here).
"""
from __future__ import annotations
import sys
import os
import importlib
import importlib.util
import tempfile
import traceback
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
SHIM_DIR = Path(__file__).resolve().parent

_SENTINEL = object()


class MonkeyPatch:
    """Stdlib-only stand-in for pytest's monkeypatch fixture (the subset used
    here: setattr on an object/attribute, restored on teardown)."""

    def __init__(self):
        self._undo = []  # list of (obj, name, had_value, old_value)

    @staticmethod
    def _resolve_dotted(dotted):
        """Resolve 'pkg.mod.sub.attr' to (holder_object, 'attr'), importing
        the longest importable module prefix and walking getattr() the rest
        (this is what real monkeypatch.setattr(str, value) does)."""
        parts = dotted.split(".")
        module = None
        split_at = 0
        for i in range(len(parts), 0, -1):
            candidate = ".".join(parts[:i])
            try:
                module = importlib.import_module(candidate)
                split_at = i
                break
            except ImportError:
                continue
        if module is None:
            raise ImportError(f"Could not import any prefix of '{dotted}'")
        obj = module
        for attr in parts[split_at:-1]:
            obj = getattr(obj, attr)
        return obj, parts[-1]

    def setattr(self, target, name, value=_SENTINEL, raising=True):
        # Two call forms, like real pytest monkeypatch:
        #   setattr(obj, "attr", value)
        #   setattr("dotted.module.path.attr", value)   <- value passed as `name`
        if value is _SENTINEL:
            dotted_value = name
            obj, name = self._resolve_dotted(target)
            value = dotted_value
        else:
            obj = target
        had_value = hasattr(obj, name)
        old_value = getattr(obj, name, None)
        if raising and not had_value:
            raise AttributeError(f"{obj!r} has no attribute {name!r}")
        setattr(obj, name, value)
        self._undo.append((obj, name, had_value, old_value))

    def undo(self):
        for obj, name, had_value, old_value in reversed(self._undo):
            if had_value:
                setattr(obj, name, old_value)
            else:
                try:
                    delattr(obj, name)
                except AttributeError:
                    pass
        self._undo.clear()


def make_fixture_value(fixture_name, tmp_ctx):
    if fixture_name == "tmp_path":
        return Path(tmp_ctx.name)
    if fixture_name == "monkeypatch":
        return MonkeyPatch()
    raise KeyError(fixture_name)


def load_module(test_file: Path):
    mod_name = f"_offline_{test_file.stem}"
    spec = importlib.util.spec_from_file_location(mod_name, test_file)
    module = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = module
    spec.loader.exec_module(module)
    return module


def run_file(test_file: Path):
    results = []
    try:
        module = load_module(test_file)
    except Exception as e:
        results.append((f"<module import: {test_file.name}>", "ERROR", "".join(
            traceback.format_exception(type(e), e, e.__traceback__))))
        return results

    test_funcs = [
        (name, obj) for name, obj in vars(module).items()
        if name.startswith("test_") and callable(obj)
    ]
    for name, func in sorted(test_funcs, key=lambda x: x[0]):
        code = func.__code__
        params = code.co_varnames[: code.co_argcount]
        kwargs = {}
        monkeypatch = None
        tmp_ctx = None
        try:
            if "tmp_path" in params or "monkeypatch" in params:
                tmp_ctx = tempfile.TemporaryDirectory()
            for p in params:
                if p == "tmp_path":
                    kwargs[p] = make_fixture_value(p, tmp_ctx)
                elif p == "monkeypatch":
                    monkeypatch = make_fixture_value(p, tmp_ctx)
                    kwargs[p] = monkeypatch
                else:
                    raise KeyError(f"unsupported fixture '{p}'")
            func(**kwargs)
            results.append((f"{test_file.name}::{name}", "PASS", ""))
        except Exception as e:
            tb = "".join(traceback.format_exception(type(e), e, e.__traceback__))
            results.append((f"{test_file.name}::{name}", "FAIL", tb))
        finally:
            if monkeypatch is not None:
                monkeypatch.undo()
            if tmp_ctx is not None:
                tmp_ctx.cleanup()
    return results


def main(argv):
    # Make the bundled pytest shim importable, and the backend app importable.
    sys.path.insert(0, str(SHIM_DIR))
    sys.path.insert(0, str(BACKEND_ROOT))

    test_files = [Path(a).resolve() for a in argv]
    if not test_files:
        print("usage: run_tests.py <test_file.py> [...]")
        return 2

    all_results = []
    for tf in test_files:
        all_results.extend(run_file(tf))

    passed = [r for r in all_results if r[1] == "PASS"]
    failed = [r for r in all_results if r[1] in ("FAIL", "ERROR")]

    print("=" * 70)
    for name, status, tb in all_results:
        marker = "." if status == "PASS" else ("F" if status == "FAIL" else "E")
        print(f"{marker} {name}")
    print("=" * 70)
    for name, status, tb in failed:
        print(f"\n--- {status}: {name} ---")
        print(tb)

    print("=" * 70)
    print(f"{len(passed)} passed, {len(failed)} failed out of {len(all_results)}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
