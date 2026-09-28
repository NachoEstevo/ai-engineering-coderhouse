import asyncio
import logging

from langgraph.types import Command
from redis.exceptions import RedisError

from .graph import initial_state
from .observability import execution_config

logger = logging.getLogger(__name__)


class Workers:
    def __init__(self, store, graph, settings):
        self.store, self.graph, self.settings = store, graph, settings
        self.tasks = []

    def start(self):
        self.tasks = [asyncio.create_task(self.loop()) for _ in range(self.settings.worker_concurrency)]

    async def stop(self):
        for task in self.tasks:
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)

    async def execute(self, job):
        job_id = job['job_id']
        config, trace_id = execution_config(job)
        await self.store.mark_trace(job_id, trace_id)
        try:
            payload = Command(resume=job['approved']) if job['resume'] else initial_state(job['request'])
            async with asyncio.timeout(self.settings.job_timeout_seconds):
                state = await self.graph.ainvoke(payload, config=config)
            interruptions = state.get('__interrupt__', [])
            result = dict(response=state.get('response'), completed=state.get('completed', False),
                          events=state.get('events', []), saved=state.get('saved', False))
            if interruptions:
                await self.store.finish(job_id, status='WAITING_APPROVAL', result=result,
                                        interruption=interruptions[0].value)
            elif state.get('rejected'):
                await self.store.finish(job_id, status='REJECTED', result=result)
            elif not state.get('completed'):
                await self.store.finish(job_id, status='FAILED', result=result,
                                        error={'code': 'ANALYSIS_INCOMPLETE', 'message': 'Analysis could not be validated.'})
            else:
                await self.store.finish(job_id, status='DONE', result=result)
        except asyncio.CancelledError:
            await asyncio.shield(self.store.finish(job_id, status='FAILED',
                error={'code': 'CANCELLED', 'message': 'Worker shut down during execution.'}))
            raise
        except Exception as exc:
            code = 'TIMEOUT' if isinstance(exc, TimeoutError) else 'EXECUTION_ERROR'
            logger.warning('job=%s error_type=%s', job_id, type(exc).__name__)
            await self.store.finish(job_id, status='FAILED', error={'code': code, 'message': 'Execution failed; submit a new task.'})

    async def loop(self):
        while True:
            try:
                await self.store.recover()
                job = await self.store.claim(self.settings.job_timeout_seconds)
                if job:
                    await self.execute(job)
                else:
                    await asyncio.sleep(0.1)
            except RedisError:
                logger.warning('Redis unavailable; queue consumer will reconnect')
                await asyncio.sleep(1)
