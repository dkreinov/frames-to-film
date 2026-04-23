"""Prove each script's run() helper is thread-safe.

Without a lock, two concurrent calls would race on the module globals
(SRC_DIR/OUT_DIR/etc). With threading.Lock, the second call must wait
until the first releases.

We patch each script's main() to block on a threading.Event so we can
deterministically observe the second thread waiting. The module-level
lock is read via the expected attribute name `_RUN_LOCK`.
"""
from __future__ import annotations

import threading
import time
from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "module_name",
    ["outpaint_images", "outpaint_16_9", "generate_all_videos", "concat_videos"],
)
def test_run_is_serialised(module_name: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import importlib
    mod = importlib.import_module(module_name)

    # The lock must be a public attribute of the module.
    assert hasattr(mod, "_RUN_LOCK"), f"{module_name}._RUN_LOCK not defined"
    assert isinstance(mod._RUN_LOCK, type(threading.Lock())), type(mod._RUN_LOCK)

    entered = threading.Event()
    release = threading.Event()
    order: list[str] = []

    def blocking_main(_tag):
        order.append(f"enter-{_tag}")
        entered.set()
        assert release.wait(timeout=2.0), "release never signalled"
        order.append(f"exit-{_tag}")

    monkeypatch.setattr(mod, "main", lambda: blocking_main(threading.current_thread().name))

    # dir kwargs vary per script; all accept src_dir/out_dir-style pairs
    kwargs_variants = {
        "outpaint_images": dict(src_dir=str(tmp_path / "src"), out_dir=str(tmp_path / "out")),
        "outpaint_16_9":   dict(src_dir=str(tmp_path / "src"), out_dir=str(tmp_path / "out")),
        "generate_all_videos": dict(img_dir=str(tmp_path / "img"), video_dir=str(tmp_path / "vid")),
        "concat_videos":       dict(img_dir=str(tmp_path / "img"), video_dir=str(tmp_path / "vid")),
    }
    kwargs = kwargs_variants[module_name]

    t1 = threading.Thread(target=mod.run, name="T1", kwargs=kwargs)
    t2 = threading.Thread(target=mod.run, name="T2", kwargs=kwargs)
    t1.start()
    assert entered.wait(timeout=2.0), "T1 never entered patched main"
    # T1 is now inside main holding the lock. Start T2 — it should block on acquire.
    t2.start()
    # Give T2 a moment to try acquiring (and fail / wait).
    time.sleep(0.1)
    assert order == ["enter-T1"], f"T2 ran concurrently: {order!r}"
    # Release T1; T2 then proceeds.
    release.set()
    t1.join(timeout=2.0)
    # T2 enters immediately after T1 releases — blocking_main rechecks `release` which is now set.
    t2.join(timeout=2.0)
    assert order == ["enter-T1", "exit-T1", "enter-T2", "exit-T2"], order
