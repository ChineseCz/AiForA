"""任务运行封装：把一段工作包成 job_runs 记录 + stdout 捕获到日志 + 完成后失效缓存。

取代旧 web.py 的 _TeeWriter + *_state 内存字典 + finally 收尾那套模式。
"""
import sys
import time
from contextlib import contextmanager

from app.core.cache import bump_dataver_sync
from app.repositories import jobs

_FLUSH_EVERY = 5      # 每累积 N 行刷一次 DB，兼顾进度可见与写放大
_FLUSH_INTERVAL = 2.0  # 或每 N 秒刷一次


class _JobLogWriter:
    """把 print 同时写回原终端和 job_runs.log（分批刷库）。"""

    def __init__(self, orig, job_id: int):
        self.orig = orig
        self.job_id = job_id
        self.buf: list[str] = []
        self.last_flush = time.time()

    def write(self, s):
        try:
            self.orig.write(s)
        except Exception:
            pass
        for line in s.splitlines():
            if line.strip():
                self.buf.append(line)
        if len(self.buf) >= _FLUSH_EVERY or (time.time() - self.last_flush) > _FLUSH_INTERVAL:
            self.flush_db()
        return len(s)

    def flush_db(self):
        if self.buf:
            jobs.append_log(self.job_id, "\n".join(self.buf))
            self.buf = []
            self.last_flush = time.time()

    def flush(self):
        try:
            self.orig.flush()
        except Exception:
            pass


@contextmanager
def job_run(kind: str, source: str = "手动", invalidate_cache: bool = False, job_id: int | None = None):
    """创建（或复用）job_runs 记录，捕获期间 stdout 到日志，异常记 error，结束收尾。

    invalidate_cache=True 时（数据同步类任务），成功后 bump dataver 使读缓存失效。
    job_id 非空时复用该行（由触发接口预建，使"running"状态入队即可见，消除轮询竞态）；
    为空时自建（如 beat 派发的采集任务）。
    """
    if job_id is None:
        job_id = jobs.create_job(kind, source)
    old = sys.stdout
    writer = _JobLogWriter(old, job_id)
    sys.stdout = writer
    error = ""
    try:
        yield job_id
        if invalidate_cache:
            bump_dataver_sync()
    except Exception as e:  # noqa: BLE001
        error = str(e)
        print(f"❌ 出错：{e}")
    finally:
        writer.flush_db()
        sys.stdout = old
        jobs.finish_job(job_id, error)
