# src/agents/synthesizer.py
"""Synthesizer Agent — crafts professional analyst-style narrative from results."""

import json
from core.llm_client import LLMRouter
from config import ANALYST_SYSTEM_PROMPT


class SynthesizerAgent:
    """Takes analysis results and creates compelling data stories."""

    def __init__(self, llm: LLMRouter):
        self.llm = llm

    def synthesize(self, user_query: str, plan: dict, analysis_result: dict,
                   summary_data: dict, profile: dict, conversation_history: list = None) -> str:
        """Generate a professional analyst narrative.

        Args:
            user_query: Original user question
            plan: Analysis plan from Planner
            analysis_result: Raw results from Executor
            summary_data: Key stats
            profile: CSV profile
            conversation_history: Previous messages for context

        Returns:
            Markdown-formatted analyst narrative
        """
        # Build context for the LLM
        result_text = json.dumps(analysis_result, indent=2, default=str)
        # Truncate if too long
        if len(result_text) > 3000:
            result_text = result_text[:3000] + "\n... (truncated)"

        summary_text = json.dumps(summary_data, indent=2, default=str)
        plan_text = json.dumps(plan, indent=2, default=str)

        # Build messages
        messages = [{"role": "system", "content": ANALYST_SYSTEM_PROMPT}]

        # Add conversation history for context
        if conversation_history:
            for msg in conversation_history[-6:]:  # Last 6 messages
                messages.append(msg)

        messages.append({
            "role": "user",
            "content": f"""The user asked: "{user_query}"

Dataset: {profile.get('filename', 'uploaded.csv')} ({profile.get('row_count', '?')} rows)

Analysis plan executed:
{plan_text}

Analysis results:
{result_text}

Dataset summary:
{summary_text}

Now write a professional analyst response. Be specific with numbers. 
If a visualization was generated, reference it naturally in your narrative (e.g., "As shown in the chart below...").
Keep the response focused, insightful, and actionable.""",
        })

        response = self.llm.chat(messages, temperature=0.5)
        return response

    def answer_question(self, user_query: str, df_info: str, profile: dict,
                        conversation_history: list = None) -> str:
        """Answer a general question about the data without full analysis pipeline."""
        messages = [{"role": "system", "content": ANALYST_SYSTEM_PROMPT}]

        if conversation_history:
            for msg in conversation_history[-6:]:
                messages.append(msg)

        messages.append({
            "role": "user",
            "content": f"""The user asked: "{user_query}"

Dataset: {profile.get('filename', 'uploaded.csv')} ({profile.get('row_count', '?')} rows)

Data overview:
{df_info}

Provide a clear, data-backed answer. Reference specific numbers from the data.""",
        })

        response = self.llm.chat(messages, temperature=0.5)
        return response
