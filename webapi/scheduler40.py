from __future__ import annotations

import json
import logging
import threading
import time

from fastapi import HTTPException
from webapi.runtime37 import connection, utcnow

logger = logging.getLogger(__name__)


class Scheduler40:
    def __init__(self):
        self.stop_event = threading.Event()
        self.thread = None
        self._tick_lock = threading.Lock()

    def start(self):
        if self.thread and self.thread.is_alive():
            return True
        self.stop_event.clear()
        self.thread = threading.Thread(target=self.loop, name='Desktop-Scheduler40', daemon=True)
        self.thread.start()
        return True

    def stop(self):
        self.stop_event.set()
        thread = self.thread
        if thread:
            thread.join(timeout=5)
            if thread.is_alive():
                logger.error('Scheduler thread did not stop within timeout; refusing to start a duplicate thread')
                return False
        self.thread = None
        return True

    def loop(self):
        while not self.stop_event.wait(10):
            try:
                self.tick()
            except Exception:
                logger.exception('Scheduler tick failed')

    def tick(self):
        # Prevent manual/overlapping invocations from claiming the same schedule.
        if not self._tick_lock.acquire(blocking=False):
            return
        try:
            now = time.time()
            with connection() as c:
                due = [dict(r) for r in c.execute(
                    'SELECT * FROM web_schedules40 WHERE enabled=1 AND COALESCE(next_epoch,0)<=? ORDER BY id LIMIT 8',
                    (now,),
                )]
            for row in due:
                try:
                    with connection() as c:
                        user = c.execute(
                            'SELECT id,username,role,enabled FROM app_users WHERE id=?',
                            (row['actor_id'],),
                        ).fetchone()
                    if not user or not user['enabled']:
                        raise RuntimeError('Schedule owner disabled')
                    submit_schedule(row['id'], dict(user), manual=False)
                except Exception as exc:
                    logger.warning('Scheduled task id=%s failed: %s', row.get('id'), exc)
                    status = (str(exc.detail) if isinstance(exc, HTTPException) else str(exc) or type(exc).__name__)[:80]
                    # Retry failed submissions soon instead of silently skipping an
                    # entire schedule interval. A successful submit advances normally.
                    with connection() as c:
                        c.execute(
                            'UPDATE web_schedules40 SET last_run=?,last_status=?,next_epoch=?,updated_at=? WHERE id=?',
                            (utcnow(), status, time.time() + 60, utcnow(), row['id']),
                        )
        finally:
            self._tick_lock.release()


def submit_schedule(sid, user, manual=False):
    from webapi.jobs37 import engine, ROLES

    with connection() as c:
        row = c.execute('SELECT * FROM web_schedules40 WHERE id=?', (sid,)).fetchone()
    if not row:
        raise HTTPException(404, 'Schedule not found')
    row = dict(row)
    operation = row['operation']
    if user['role'] not in ROLES.get(operation, ()):
        raise HTTPException(403, 'TASK_PERMISSION_DENIED')
    payload = {
        'device_ids': json.loads(row['device_ids_json'] or '[]'),
        'network': row['network'] or '',
        'parameters': json.loads(row['parameters_json'] or '{}'),
    }
    out = engine.submit(operation, payload, user)
    next_epoch = time.time() + max(1, int(row['interval_minutes'])) * 60

    # Advance only after the durable job has actually been accepted.
    with connection() as c:
        c.execute(
            'UPDATE web_schedules40 SET last_run=?,last_status=?,last_job_id=?,next_epoch=?,updated_at=? WHERE id=?',
            (utcnow(), 'Queued', out['id'], next_epoch, utcnow(), sid),
        )
    with connection() as c:
        current = c.execute('SELECT status FROM web_jobs37 WHERE id=?', (out['id'],)).fetchone()
        if current:
            c.execute(
                'UPDATE web_schedules40 SET last_status=?,updated_at=? WHERE id=?',
                (current['status'], utcnow(), sid),
            )
    return out


scheduler = Scheduler40()
