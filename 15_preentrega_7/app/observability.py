from uuid import uuid4


def execution_config(job):
    run_id = uuid4()
    batch = job['request'].get('batch_id')
    return dict(configurable={'thread_id': job['job_id']}, recursion_limit=32,
                run_id=run_id, run_name='preentrega7', tags=[batch] if batch else [],
                metadata={'job_id': job['job_id'], 'batch_id': batch}), str(run_id)
