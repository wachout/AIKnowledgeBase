# -*- coding:utf-8 -*-

from Agent.EntityRelationSplitAgent.entity_relation_split_agent import run_graph


def entity_relation_split_run(query):
    initial_state = {
        "original_query": query,
        "revision_count": 0, # Initialize revision count
        }
    app = run_graph()
    result = app.invoke(initial_state)
    return result





