
# from Agent.EmbGraphChatAgent_bak.emb_graph_chat import build_agent
from Agent.EmbGraphChatAgent.emb_graph_chat import run_sync
from Agent.EmbGraphChatAgent.emb_graph_stream import run_stream_sync

def emb_graph_chat_run(query, graph_data, milvus_data):
    
    initial_state = {
        "query": query,
        "emb_data": milvus_data,
        "graph_data": graph_data
    }
    
    result = run_sync(initial_state, model_type="tongyi")
    # result = run_sync(initial_state, model_type="deepseek")
    return result


def emb_graph_chat_stream_run(query, graph_data, milvus_data):
    initial_state = {
        "query": query,
        "emb_data": milvus_data,
        "graph_data": graph_data
    }
    model_type = "deepseek"
    # model_type = "tongyi"
    # 直接返回生成器对象
    return run_stream_sync(initial_state, model_type=model_type)

