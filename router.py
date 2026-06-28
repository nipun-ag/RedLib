import logging
from typing import Any, List
from llama_index.core.query_engine import RetrieverQueryEngine, RouterQueryEngine
from llama_index.core.tools import QueryEngineTool, ToolMetadata
from llama_index.core.selectors import LLMSingleSelector

logger = logging.getLogger(__name__)


def get_query_engine_tools(retriever, reranker, synthesizer) -> List[QueryEngineTool]:
    """Create query engine tools for semantic search and conceptual questions.

    Args:
        retriever: Configured QueryFusionRetriever
        reranker: Configured CohereRerank postprocessor
        synthesizer: Configured ResponseSynthesizer

    Returns:
        List of two QueryEngineTool objects for routing
    """
    try:
        # Create semantic search tool (retriever + reranker + synthesizer)
        semantic_engine = RetrieverQueryEngine.from_args(
            retriever=retriever,
            node_postprocessors=[reranker],
            response_synthesizer=synthesizer,
        )

        semantic_tool = QueryEngineTool(
            query_engine=semantic_engine,
            metadata=ToolMetadata(
                name="semantic_search",
                description=(
                    "Use this tool for searches over the jailbreak prompt corpus. "
                    "Use when the query is looking for real prompt examples, "
                    "attack patterns, or technique demonstrations."
                ),
            ),
        )

        logger.info("Semantic search tool configured")

        # Create conceptual question tool (direct Haiku, no retrieval)
        conceptual_engine = RetrieverQueryEngine.from_args(
            retriever=None,
            response_synthesizer=synthesizer,
        )

        conceptual_tool = QueryEngineTool(
            query_engine=conceptual_engine,
            metadata=ToolMetadata(
                name="conceptual_qa",
                description=(
                    "Use this tool for conceptual questions about jailbreak "
                    "techniques, definitions, or AI safety concepts. Use when "
                    "the query asks what something is or how something works."
                ),
            ),
        )

        logger.info("Conceptual question tool configured")

        return [semantic_tool, conceptual_tool]

    except Exception as e:
        logger.error(f"Failed to create query engine tools: {type(e).__name__}: {e}")
        raise


def get_router(tools: List[QueryEngineTool], llm: Any) -> RouterQueryEngine:
    """Configure RouterQueryEngine with LLMSingleSelector.

    Args:
        tools: List of QueryEngineTool objects
        llm: Configured LLM for routing decisions

    Returns:
        Configured RouterQueryEngine
    """
    try:
        # Create selector
        selector = LLMSingleSelector.from_defaults(llm=llm)

        # Create router
        router = RouterQueryEngine(
            selector=selector,
            query_engine_tools=tools,
        )

        logger.info("RouterQueryEngine configured with LLMSingleSelector")
        return router

    except Exception as e:
        logger.error(f"Failed to create router: {type(e).__name__}: {e}")
        raise
