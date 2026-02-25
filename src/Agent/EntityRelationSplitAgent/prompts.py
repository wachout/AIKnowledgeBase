from langchain_core.prompts import PromptTemplate

# Prompt for decomposing the user's question
decompose_question_prompt = PromptTemplate.from_template(
    """
    **Task**: Decompose the user's query into its core components.

    **Instructions**:
    1.  Identify and extract the main **entities**. Entities are specific nouns or proper nouns (e.g., people, places, organizations).
    2.  Identify and extract meaningful **phrases**. Phrases are multi-word concepts that should be searched together (e.g., "artificial intelligence reports", "restaurants in Beijing").
    3.  Identify and extract relevant **keywords**. These are important single terms that describe the topic.
    4.  Identify and extract any **search conditions** or constraints (e.g., timeframes, locations, specific requirements).

    **User Query**:
    {query}

    **Output Format**:
    {format_instructions}
    """
)

# Prompt for generating the initial search query
generate_query_prompt = PromptTemplate.from_template(
    """
    **Task**: Generate a precise and effective search query based on the decomposed components of a user's request.

    **Decomposed Components**:
    - **Entities**: {entities}
    - **Phrases**: {phrases}
    - **Keywords**: {keywords}
    - **Search Conditions**: {search_conditions}

    **Instructions**:
    1.  Combine the entities, keywords, and search conditions into a single, coherent search query.
    2.  The query should be optimized for a search engine or database.
    3.  Be concise and use logical operators (like AND, OR) if necessary, but keep it simple and clear.

    **Generated Search Query**:
    """
)

# Prompt for critiquing the generated search query
critique_query_prompt = PromptTemplate.from_template(
    """
    **Task**: Critique the provided search query.

    **Context**:
    - **Original User Query**: {original_query}
    - **Generated Search Query**: {search_query}

    **Instructions**:
    1.  Review the `Generated Search Query` and compare it against the `Original User Query`.
    2.  Does the search query accurately capture the user's intent? Is it missing any key information?
    3.  Provide constructive feedback for improvement.
    4.  **Crucially**: If the query is perfect and needs no changes, you MUST end your response with the exact phrase on a new line:
    The query is perfect.

    **Critique**:
    """
)

# Prompt for revising the search query based on critique
revise_query_prompt = PromptTemplate.from_template(
    """
    **Task**: Revise the search query based on the provided critique.

    **Context**:
    - **Original User Query**: {original_query}
    - **Original Search Query**: {search_query}
    - **Critique**: {critique}

    **Instructions**:
    1.  Carefully read the critique and understand the required changes.
    2.  Rewrite the search query to address the feedback.
    3.  Ensure the revised query is more aligned with the user's original intent.

    **Revised Search Query**:
    """
)
