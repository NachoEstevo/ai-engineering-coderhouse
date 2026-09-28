import asyncio
from uuid import uuid4

import httpx
import pytest
from langgraph.checkpoint.redis.aio import AsyncRedisSaver
from redis.asyncio import Redis

from app.config import Settings
from app.graph import create_graph
from app.main import create_app
from app.worker import Workers
from app.schemas import TaskRequest
from tests.test_graph import ScriptedModel

REQUEST = dict(query='Comparar promedio y dispersion', groups=[
    dict(name='A', unit='ms', values=[100,110,90,100,100]),
    dict(name='B', unit='ms', values=[80,120,100,90,110])], save_result=True)


@pytest.fixture
def settings():
    return Settings(api_key='synthetic-api-key-123', approval_key='synthetic-approver-123',
                    redis_prefix='test-pre7-' + uuid4().hex, _env_file=None)


@pytest.fixture
async def application(settings):
    app = create_app(settings, ScriptedModel(['research', 'analysis', 'synthesis']), start_workers=False)
    async with app.router.lifespan_context(app):
        yield app
        keys = [key async for key in app.state.store.redis.scan_iter(settings.redis_prefix + ':*')]
        if keys:
            await app.state.store.redis.delete(*keys)


async def test_api_pending_validation_auth_and_approval(application):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=application), base_url='http://test') as client:
        assert (await client.get('/health')).status_code == 200
        assert (await client.post('/tasks', json=REQUEST)).status_code == 401
        headers = {'X-API-Key':'synthetic-api-key-123'}
        assert (await client.post('/tasks', json={'query':' '}, headers=headers)).status_code == 422
        assert (await client.post('/tasks', json={**REQUEST, 'groups':[{'name':'A','unit':'ms','values':[True,2]}]}, headers=headers)).status_code == 422
        submitted = await client.post('/tasks', json=REQUEST, headers=headers)
        assert submitted.status_code == 202
        job_id = submitted.json()['job_id']
        job = (await client.get('/tasks/'+job_id, headers=headers)).json()
        assert job['status'] == 'PENDING'
        assert (await client.post('/tasks/'+job_id+'/approve', json={'approved':True}, headers=headers)).status_code == 403
        approved_headers = {**headers,'X-Approval-Key':'synthetic-approver-123'}
        assert (await client.post('/tasks/'+job_id+'/approve', json={'approved':True}, headers=approved_headers)).status_code == 409
        claimed = await application.state.store.claim(180)
        await application.state.workers.execute(claimed)
        assert (await application.state.store.get(job_id))['status'] == 'WAITING_APPROVAL'
        assert await application.state.store.redis.get(application.state.store.result_key(job_id)) is None
        responses = await asyncio.gather(*[client.post('/tasks/'+job_id+'/approve', json={'approved':True}, headers=approved_headers) for _ in range(2)])
        assert sorted(r.status_code for r in responses) == [202,409]
        claimed = await application.state.store.claim(180)
        # Rebuild the graph and Redis checkpointer, demonstrating persisted resume.
        async with AsyncRedisSaver.from_conn_string(application.state.workers.settings.redis_url) as saver:
            await saver.asetup()
            no_calls = ScriptedModel([])
            graph = create_graph(no_calls, saver, application.state.store)
            await Workers(application.state.store, graph, application.state.workers.settings).execute(claimed)
            assert no_calls.calls == []
        assert (await application.state.store.get(job_id))['status'] == 'DONE'
        assert await application.state.store.redis.get(application.state.store.result_key(job_id))


async def test_rejection_and_single_claim(application):
    store = application.state.store
    job = await store.create(TaskRequest(**REQUEST))
    claims = await asyncio.gather(store.claim(180), store.claim(180))
    assert sum(c is not None for c in claims) == 1
    await application.state.workers.execute(next(c for c in claims if c))
    assert await store.approve(job['job_id'], False) == 1
    await application.state.workers.execute(await store.claim(180))
    assert (await store.get(job['job_id']))['status'] == 'REJECTED'
    assert await store.redis.get(store.result_key(job['job_id'])) is None


@pytest.mark.parametrize('failure', ['exception','timeout','cancel','incomplete'])
async def test_failures_are_terminal(application, failure):
    class Failing:
        async def ainvoke(self, *args, **kwargs):
            if failure == 'exception':
                raise ValueError('secret-sensitive')
            if failure == 'cancel':
                raise asyncio.CancelledError()
            if failure == 'incomplete':
                return {'completed':False}
            await asyncio.sleep(1)
    worker = application.state.workers
    worker.graph = Failing()
    worker.settings.job_timeout_seconds = 0.1
    job = await worker.store.create(TaskRequest(**REQUEST))
    claimed = await worker.store.claim(0.1)
    if failure == 'cancel':
        with pytest.raises(asyncio.CancelledError):
            await worker.execute(claimed)
    else:
        await worker.execute(claimed)
    final = await worker.store.get(job['job_id'])
    assert final['status'] == 'FAILED'
    assert 'secret-sensitive' not in str(final)


async def test_expired_worker_is_failed(application):
    store = application.state.store
    job = await store.create(TaskRequest(**REQUEST))
    await store.claim(0.1)
    await store.redis.zadd(store.active, {job['job_id']:0})
    assert await store.recover() == 1
    assert (await store.get(job['job_id']))['error']['code'] == 'WORKER_LOST'


async def test_five_consumers_execute_concurrently(application):
    active = 0
    peak = 0
    gate = asyncio.Event()
    class ConcurrentGraph:
        async def ainvoke(self, *args, **kwargs):
            nonlocal active, peak
            active += 1
            peak = max(peak, active)
            if active == 5:
                gate.set()
            await asyncio.wait_for(gate.wait(), timeout=2)
            active -= 1
            return {'completed':True, 'response':'Synthetic validated response'}
    worker = application.state.workers
    worker.graph = ConcurrentGraph()
    jobs = await asyncio.gather(*[worker.store.create(TaskRequest(**REQUEST)) for _ in range(5)])
    worker.start()
    try:
        for _ in range(100):
            states = await asyncio.gather(*[worker.store.get(job['job_id']) for job in jobs])
            if all(job['status'] == 'DONE' for job in states):
                break
            await asyncio.sleep(0.02)
        assert peak == 5
        assert all(job['status'] == 'DONE' for job in states)
    finally:
        await worker.stop()


async def test_omitted_groups_reaches_controlled_supervisor_clarification(application):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=application), base_url='http://test') as client:
        headers = {'X-API-Key': 'synthetic-api-key-123'}
        submitted = await client.post('/tasks', json={'query': 'Comparar'}, headers=headers)
        assert submitted.status_code == 202
        job_id = submitted.json()['job_id']
        claimed = await application.state.store.claim(180)
        assert claimed['request']['groups'] == []
        await application.state.workers.execute(claimed)
        response = await client.get('/tasks/' + job_id, headers=headers)
        final = response.json()
        assert final['status'] == 'FAILED'
        assert final['error']['code'] == 'ANALYSIS_INCOMPLETE'
        assert 'dos grupos' in final['result']['response']
        assert any(event['action'] == 'missing_groups' for event in final['result']['events'])


async def test_nested_json_arrays_survive_all_redis_transitions(application):
    store = application.state.store
    job = await store.create(TaskRequest(query='Comparar', groups=[]))
    claimed = await store.claim(180)
    assert claimed['request']['groups'] == []
    result = {'events': [], 'nested': [{'values': [], 'object': {}}]}
    interruption = {'actions': [], 'nested': {'options': []}}
    await store.mark_trace(job['job_id'], str(uuid4()))
    await store.finish(job['job_id'], status='WAITING_APPROVAL',
                       result=result, interruption=interruption)
    waiting = await store.get(job['job_id'])
    assert waiting['result'] == result
    assert waiting['interruption'] == interruption
    await store.approve(job['job_id'], True)
    resumed = await store.claim(180)
    assert resumed['request']['groups'] == []
    assert resumed['result'] == result
    await store.finish(job['job_id'], status='DONE', result=result)
    assert (await store.get(job['job_id']))['result'] == result
