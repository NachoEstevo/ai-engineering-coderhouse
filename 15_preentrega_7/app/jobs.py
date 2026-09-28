import json
import time
from uuid import uuid4

from redis.asyncio import Redis

JSON_FIELDS = ('request', 'result', 'error', 'interruption')


def encode_payloads(record: dict) -> dict:
    """Keep nested JSON opaque to Lua cjson, which loses empty array types."""
    return {key: json.dumps(value) if key in JSON_FIELDS else value
            for key, value in record.items()}


def decode_record(raw: str | bytes) -> dict:
    record = json.loads(raw)
    for key in JSON_FIELDS:
        if isinstance(record.get(key), str):
            record[key] = json.loads(record[key])
    return record

CREATE = '''
redis.call('SET', KEYS[1], ARGV[1])
redis.call('RPUSH', KEYS[2], ARGV[2])
return 1
'''
TRANSITION = '''
local raw = redis.call('GET', KEYS[1])
if not raw then return -1 end
local job = cjson.decode(raw)
if job.status ~= ARGV[1] then return 0 end
local patch = cjson.decode(ARGV[2])
for k,v in pairs(patch) do job[k] = v end
redis.call('SET', KEYS[1], cjson.encode(job))
if ARGV[3] ~= '' then redis.call('RPUSH', KEYS[2], ARGV[3]) end
return 1
'''
CLAIM = '''
local id = redis.call('LPOP', KEYS[1])
if not id then return nil end
local key = ARGV[1] .. ':job:' .. id
local raw = redis.call('GET', key)
if not raw then return nil end
local job = cjson.decode(raw)
if job.status ~= 'PENDING' then return nil end
job.status = 'RUNNING'
job.started_at = tonumber(ARGV[2])
redis.call('SET', key, cjson.encode(job))
redis.call('ZADD', KEYS[2], tonumber(ARGV[2]) + tonumber(ARGV[3]), id)
return cjson.encode(job)
'''
FINISH = '''
local raw = redis.call('GET', KEYS[1])
if not raw then return 0 end
local job = cjson.decode(raw)
if job.status ~= 'RUNNING' then return 0 end
local patch = cjson.decode(ARGV[1])
for k,v in pairs(patch) do job[k] = v end
redis.call('SET', KEYS[1], cjson.encode(job))
redis.call('ZREM', KEYS[2], ARGV[2])
return 1
'''
EXPIRE = '''
local ids = redis.call('ZRANGEBYSCORE', KEYS[1], '-inf', ARGV[1])
for _,id in ipairs(ids) do
 local key = ARGV[2] .. ':job:' .. id
 local raw = redis.call('GET', key)
 if raw then
  local job = cjson.decode(raw)
  if job.status == 'RUNNING' then
   job.status = 'FAILED'
   job.error = {code='WORKER_LOST', message='Worker execution lease expired; submit a new task.'}
   redis.call('SET', key, cjson.encode(job))
  end
 end
 redis.call('ZREM', KEYS[1], id)
end
return #ids
'''


class JobStore:
    def __init__(self, redis: Redis, prefix: str):
        self.redis, self.prefix = redis, prefix
        self.queue = f'{prefix}:queue'
        self.active = f'{prefix}:active'

    def key(self, job_id):
        return f'{self.prefix}:job:{job_id}'

    def result_key(self, job_id):
        return f'{self.prefix}:result:{job_id}'

    async def create(self, request):
        job_id = str(uuid4())
        job = dict(job_id=job_id, status='PENDING', request=request.model_dump(),
                   result=None, error=None, interruption=None, trace_id=None,
                   created_at=time.time(), resume=False)
        await self.redis.eval(CREATE, 2, self.key(job_id), self.queue,
                              json.dumps(encode_payloads(job)), job_id)
        return job

    async def get(self, job_id):
        raw = await self.redis.get(self.key(job_id))
        return decode_record(raw) if raw else None

    async def approve(self, job_id, approved):
        patch = dict(status='PENDING', resume=True, approved=approved, interruption=None)
        return await self.redis.eval(TRANSITION, 2, self.key(job_id), self.queue,
                                     'WAITING_APPROVAL', json.dumps(encode_payloads(patch)), str(job_id))

    async def claim(self, timeout):
        raw = await self.redis.eval(CLAIM, 2, self.queue, self.active,
                                    self.prefix, time.time(), timeout + 10)
        return decode_record(raw) if raw else None

    async def finish(self, job_id, **patch):
        return await self.redis.eval(FINISH, 2, self.key(job_id), self.active,
                                    json.dumps(encode_payloads(patch)), str(job_id))

    async def mark_trace(self, job_id, trace_id):
        return await self.redis.eval(TRANSITION, 2, self.key(job_id), self.queue,
                                     'RUNNING', json.dumps({'trace_id': trace_id}), '')

    async def recover(self):
        return await self.redis.eval(EXPIRE, 1, self.active, time.time(), self.prefix)
