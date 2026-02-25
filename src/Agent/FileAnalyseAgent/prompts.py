from langchain_core.prompts import PromptTemplate

# Prompt for content analysis
content_summary_prompt = PromptTemplate.from_template(
    """
    **Task**: Analyze the provided file content and extract key information.

    **File Content**:
    {content}

    **Instructions**:
    1. **Content Type**: Determine the type of content (e.g., code, documentation, text, data, configuration).
    2. **Language**: If this is code, identify the programming language. If not code, leave as null/None.
    3. **Main Topics**: Identify the primary topics or themes discussed in the content (3-5 main topics).
    4. **Summary**: Provide a concise summary of what this file contains (2-3 sentences).

    **Output Format**:
    {format_instructions}

    Analyze the content carefully and provide accurate classification and summary.
    """
)

# Prompt for keyword extraction
keyword_extraction_prompt = PromptTemplate.from_template(
    """
    **Task**: Extract important keywords, phrases, and entities from the provided file content.

    **File Content**:
    {content}

    **Instructions**:
    1. **Keywords**: Extract 5-10 important single words or technical terms that are central to the content.
    2. **Key Phrases**: Extract 3-5 important multi-word phrases or concepts that capture key ideas.
    3. **Entities**: Extract named entities like people, organizations, products, technologies, or specific terms.

    Focus on terms that would be most useful for understanding, searching, or categorizing this content.
    Prioritize technical terms, domain-specific vocabulary, and frequently mentioned concepts.

    **Output Format**:
    {format_instructions}

    Extract meaningful and representative terms from the content.
    """
)

# Prompt for file metadata description
metadata_description_prompt = PromptTemplate.from_template(
    """
    **Task**: Generate a natural language description of file metadata.

    **File Information**:
    - File Name: {file_name}
    - File Extension: {file_extension}
    - File Size: {file_size} bytes
    - Content Length: {content_length} characters

    **Instructions**:
    Write a concise, natural language description of this file's basic information.
    Make it conversational and informative, like you're describing the file to someone.
    Keep it to 2-3 sentences and focus on the key characteristics.

    Example style: "This is a PDF document named 'report.pdf' that's about 2MB in size with approximately 15,000 characters of content."

    Generate the description:
    """
)

# Prompt for content analysis description
content_analysis_description_prompt = PromptTemplate.from_template(
    """
    **Task**: Generate a natural language description of content analysis results.

    **Content Analysis Data**:
    - Content Type: {content_type}
    - Programming Language: {language}
    - Main Topics: {main_topics}
    - Summary: {summary}

    **Instructions**:
    Write a natural, conversational description of what this file contains based on the analysis data.
    Make it engaging and informative, as if you're explaining the file's content to someone curious about it.
    Focus on what the file is about, its main themes, and any notable characteristics.
    Keep it concise but comprehensive - aim for 3-5 sentences.

    Example style: "This appears to be a Python script focused on data processing and analysis. The main topics include machine learning algorithms, data visualization, and statistical analysis. It's a comprehensive tool for handling large datasets with built-in error handling and performance optimizations."

    Generate the description:
    """
)

# Prompt for keyword analysis description
keyword_analysis_description_prompt = PromptTemplate.from_template(
    """
    **Task**: Generate a natural language description of keyword analysis results.

    **Keyword Analysis Data**:
    - Keywords: {keywords}
    - Key Phrases: {key_phrases}
    - Named Entities: {entities}

    **Instructions**:
    Write a natural description of the key terms, phrases, and entities found in this file.
    Make it conversational and helpful, explaining what these terms reveal about the file's content and focus areas.
    Group related concepts together and highlight the most important or distinctive terms.
    Keep it to 2-4 sentences.

    Example style: "The document frequently mentions terms like 'machine learning', 'neural networks', and 'data processing'. Key concepts include 'deep learning algorithms' and 'predictive modeling'. Notable entities mentioned are TensorFlow, Python, and scikit-learn frameworks."

    Generate the description:
    """
)

# Prompt for comprehensive natural language file analysis
comprehensive_file_analysis_prompt = PromptTemplate.from_template(
    """
    **Task**: Provide a comprehensive, natural language analysis of the provided file.

    **File Information**:
    - File Name: {file_name}
    - File Extension: {file_extension}
    - File Size: {file_size} bytes
    - Content Length: {content_length} characters

    **User Question**: {query}

    **File Content**:
    {content}

    **Instructions**:
    Write a comprehensive, engaging, and natural language analysis of this file that directly addresses the user's question. Think of yourself as an expert file analyst having a conversation with someone who's asking a specific question about this file.

    First, briefly acknowledge and answer the user's specific question, then provide additional context and analysis that would be helpful.

    Cover these key aspects in your analysis, focusing on information relevant to the user's question:

    - What type of file this is and its basic characteristics
    - What the file actually contains - summarize the main topics, themes, or purposes, especially as they relate to the question
    - How the content is organized and structured
    - Any important technical details, patterns, or methodologies (if applicable) that help answer the question
    - Key terms, concepts, or entities that stand out and are relevant to the question
    - Who might use this file and in what contexts, particularly regarding the question asked
    - Any special features, unique aspects, or notable insights that directly address the user's inquiry

    **Style Guidelines**:
    - Write conversationally, like you're explaining the file to a colleague or friend who asked a specific question
    - Start by directly addressing the user's question, then provide supporting context
    - Use natural transitions between topics rather than formal section headers
    - Include relevant emojis occasionally to make it more engaging (like 📄 for file info, 🔍 for details, 💡 for insights)
    - Keep it comprehensive but conversational - aim for substance with personality
    - Use examples from the content when helpful to illustrate your points
    - End with a clear sense of what makes this file valuable or interesting in relation to the question

    Make your analysis informative yet approachable, structured yet flowing naturally. Avoid sounding like a technical specification document.

    Example tone: "Regarding your question about data processing in this Python script, I can see that this code implements several sophisticated algorithms for handling large datasets. Looking at the code, it's clear the author has put together a comprehensive toolkit..."
    """
)
