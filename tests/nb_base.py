# -*- coding: utf-8 -*-
"""共享测试基座:把 scripts/ 挂进 sys.path,每个用例用独立临时状态目录(离线、合成数据)。"""
import os
import sys
import shutil
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
SCRIPTS = os.path.join(REPO, "scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

import notebook as nb  # noqa: E402  (path 挂载后再导入)


class NotebookTestBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="nb-test-")
        self._old_state = os.environ.get("BOSS_ZHIPIN_STATE_DIR")
        self._old_now = os.environ.pop("BOSS_ZHIPIN_NOTEBOOK_NOW", None)
        os.environ["BOSS_ZHIPIN_STATE_DIR"] = self.tmp

    def tearDown(self):
        if self._old_state is None:
            os.environ.pop("BOSS_ZHIPIN_STATE_DIR", None)
        else:
            os.environ["BOSS_ZHIPIN_STATE_DIR"] = self._old_state
        if self._old_now is not None:
            os.environ["BOSS_ZHIPIN_NOTEBOOK_NOW"] = self._old_now
        shutil.rmtree(self.tmp, ignore_errors=True)

    # 便捷断言:某次 record 应被拒,且带指定 reason_code,且未落盘
    def assertRejected(self, payload, reason_code=None, account_id=None):
        path = os.path.join(self.tmp, nb.notebook_filename(account_id))
        existed = os.path.exists(path)
        before = _read(path) if existed else None
        with self.assertRaises(nb.NotebookError) as ctx:
            nb.record(payload, account_id=account_id)
        if reason_code is not None:
            self.assertEqual(ctx.exception.reason_code, reason_code,
                             "expected %s got %s" % (reason_code, ctx.exception.reason_code))
        # 不落盘:文件要么仍不存在,要么内容未变
        after = _read(path) if os.path.exists(path) else None
        self.assertEqual(before, after, "拒绝的条目不应落盘/改动文件")
        return ctx.exception


def _read(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()
