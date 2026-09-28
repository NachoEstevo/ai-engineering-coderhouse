import json

from langgraph.types import interrupt
from langchain_core.runnables import RunnableConfig


def save_result_node(store):
    async def save_result(state, config: RunnableConfig):
        if not state.get('completed') or not state.get('save_result'):
            return {}
        approved = interrupt({'action': 'save_result', 'critical': True,
                              'reason': 'Definitive result persistence requires human approval',
                              'response': state['response']})
        if approved is not True:
            return {'rejected': True}
        job_id = config['configurable']['thread_id']
        # UUID ownership plus SET NX make the definitive write idempotent on replay.
        await store.redis.set(store.result_key(job_id), json.dumps({'response': state['response']}), nx=True)
        return {'saved': True}
    return save_result
