import secrets
from contextlib import asynccontextmanager
from uuid import UUID

from fastapi import Depends, FastAPI, Header, HTTPException
from dotenv import load_dotenv
from langgraph.checkpoint.redis.aio import AsyncRedisSaver
from redis.asyncio import Redis
from redis.exceptions import RedisError

from .config import BASE_DIR, Settings, create_model
from .graph import create_graph
from .jobs import JobStore
from .schemas import ApprovalRequest, TaskRequest
from .worker import Workers


def create_app(settings=None, model=None, *, start_workers=True):
    load_dotenv(BASE_DIR / '.env', override=False)
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app):
        redis = Redis.from_url(settings.redis_url, decode_responses=True)
        await redis.ping()
        store = JobStore(redis, settings.redis_prefix)
        async with AsyncRedisSaver.from_conn_string(settings.redis_url) as saver:
            await saver.asetup()
            graph = create_graph(model if model is not None else create_model(), saver, store)
            workers = Workers(store, graph, settings)
            app.state.store, app.state.graph, app.state.workers = store, graph, workers
            if start_workers:
                workers.start()
            try:
                yield
            finally:
                await workers.stop()
                await redis.aclose()

    app = FastAPI(title='Pre-entrega 7', lifespan=lifespan)

    async def authenticate(x_api_key: str = Header(default='')):
        if not secrets.compare_digest(x_api_key, settings.api_key.get_secret_value()):
            raise HTTPException(401, 'Invalid API key')

    @app.exception_handler(RedisError)
    async def redis_error(request, exc):
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=503, content={'detail': 'Redis unavailable'})

    @app.get('/health')
    async def health():
        await app.state.store.redis.ping()
        return {'status': 'ok', 'redis': 'ok'}

    @app.post('/tasks', status_code=202, dependencies=[Depends(authenticate)])
    async def submit(request: TaskRequest):
        job = await app.state.store.create(request)
        return {'job_id': job['job_id'], 'status': 'PENDING'}

    @app.get('/tasks/{job_id}', dependencies=[Depends(authenticate)])
    async def get_task(job_id: UUID):
        job = await app.state.store.get(str(job_id))
        if job is None:
            raise HTTPException(404, 'Task not found')
        return {key: job[key] for key in ('job_id', 'status', 'result', 'error', 'interruption', 'trace_id')}

    @app.post('/tasks/{job_id}/approve', status_code=202, dependencies=[Depends(authenticate)])
    async def approve(job_id: UUID, request: ApprovalRequest, x_approval_key: str = Header(default='')):
        if not secrets.compare_digest(x_approval_key, settings.approval_key.get_secret_value()):
            raise HTTPException(403, 'Invalid approval key')
        transitioned = await app.state.store.approve(str(job_id), request.approved)
        if transitioned == -1:
            raise HTTPException(404, 'Task not found')
        if transitioned == 0:
            raise HTTPException(409, 'Task is not awaiting approval')
        return {'job_id': str(job_id), 'status': 'PENDING'}

    return app
