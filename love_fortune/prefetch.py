"""prefetch.py, 챕터 AI 풀이를 미리 만들어 두는 작업 대기열.

입력을 받자마자 모든 탭의 챕터를 대기열에 넣고, 일꾼 스레드가 앞에서부터 AI 로 만든다.
화면이 어떤 챕터를 달라고 하면 그 챕터를 맨 앞으로 당긴다.
- 같은 사실표·챕터는 한 번만 만든다 (두 사람이 같은 챕터를 기다려도 AI 호출은 한 번).
- 일꾼 수는 AI 동시 호출 수보다 하나 적게 둔다. 남는 한 자리는 상담 채팅용이다.
- 만든 풀이는 chapters.generate 가 content.db 에 저장하므로 서버를 다시 켜도 남는다.
"""
from __future__ import annotations

import heapq
import itertools
import threading
import time

from . import ai, chapters

URGENT = -1                 # 화면이 지금 달라고 한 챕터
KEEP = 30 * 60              # 끝난 작업 결과를 들고 있는 시간(초)

_cv = threading.Condition()
_heap: list[tuple[int, int, str]] = []
_jobs: dict[str, "Job"] = {}
_seq = itertools.count()
_workers: list[threading.Thread] = []


class Job:
    __slots__ = ("tab", "chapter", "facts", "prio", "running", "done", "result", "finished")

    def __init__(self, tab: str, chapter: str, facts: dict, prio: int):
        self.tab, self.chapter, self.facts, self.prio = tab, chapter, facts, prio
        self.running = False
        self.done = threading.Event()
        self.result: dict | None = None
        self.finished = 0.0


def worker_count() -> int:
    return max(1, ai.PARALLEL - 1)


def _ensure_workers() -> None:
    while len(_workers) < worker_count():
        t = threading.Thread(target=_work, name=f"prefetch-{len(_workers)}", daemon=True)
        _workers.append(t)
        t.start()


def _purge(now: float) -> None:
    for k in [k for k, j in _jobs.items() if j.done.is_set() and now - j.finished > KEEP]:
        del _jobs[k]


def submit(tab: str, chapter: str, facts: dict, prio: int) -> Job:
    """작업을 넣는다. 이미 있으면 우선순위만 당긴다."""
    key = chapters.key_of(tab, chapter, facts)
    with _cv:
        _purge(time.time())
        job = _jobs.get(key)
        if job is None:
            job = _jobs[key] = Job(tab, chapter, facts, prio)
            heapq.heappush(_heap, (prio, next(_seq), key))
        elif not job.running and not job.done.is_set() and prio < job.prio:
            job.prio = prio          # 예전 항목은 꺼낼 때 우선순위가 달라 건너뛴다
            heapq.heappush(_heap, (prio, next(_seq), key))
        _ensure_workers()
        _cv.notify()
    return job


def submit_all(facts: dict) -> int:
    """모든 탭의 챕터를 탭 순서(총운 먼저), 챕터 순서대로 넣는다."""
    n = 0
    for ti, (tab, t) in enumerate(chapters.TABS.items()):
        for ci, ch in enumerate(t["chapters"]):
            submit(tab, ch["id"], facts, ti * 100 + ci)
            n += 1
    return n


def _next_job() -> tuple[str, Job]:
    with _cv:
        while True:
            while _heap:
                prio, _, key = heapq.heappop(_heap)
                job = _jobs.get(key)
                if job and not job.running and not job.done.is_set() and prio == job.prio:
                    job.running = True
                    return key, job
            _cv.wait()


def _work() -> None:
    while True:
        _key, job = _next_job()
        try:
            job.result = chapters.generate(job.tab, job.chapter, job.facts, use_ai=True)
        except Exception:  # noqa: BLE001  한 챕터가 실패해도 일꾼은 산다
            job.result = None
        finally:
            job.finished = time.time()
            job.done.set()


def wait(tab: str, chapter: str, facts: dict, timeout: float) -> dict | None:
    """AI 풀이를 기다려 받는다. 저장돼 있으면 바로. 시간 안에 못 받으면 None."""
    from . import content_store
    hit = content_store.get_chapter(chapters.key_of(tab, chapter, facts))
    if hit:
        return hit
    job = submit(tab, chapter, facts, URGENT)
    if not job.done.wait(timeout):
        return None
    return job.result


def pending() -> int:
    with _cv:
        return sum(1 for j in _jobs.values() if not j.done.is_set())
