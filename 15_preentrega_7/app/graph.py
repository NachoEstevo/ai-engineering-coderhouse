from .hitl import save_result_node
from .orchestrator.graph import build_graph
from .orchestrator.state import AnalysisRequest


def create_graph(model, checkpointer, store):
    return build_graph(model, checkpointer=checkpointer, final_node=save_result_node(store))


def initial_state(request):
    return dict(request=AnalysisRequest.model_validate({k: request[k] for k in ('query', 'groups')}),
                contributions=[], events=[], messages=[], decisions=0, delegations=0,
                completed=False, response='', feedback='', save_result=request['save_result'],
                rejected=False, saved=False)
