import json
import logging

from livekit.agents import RunContext, function_tool

from db import lookup_caller, save_caller

logger = logging.getLogger("memory_tool")


class MemoryTools:
    @function_tool
    async def lookup_caller_memory(self, context: RunContext, user_id: str) -> str:
        """Use this tool to find an existing caller's profile and retrieve relevant memory from previous calls.

        Args:
            user_id: The unique identifier for the caller (provided to you when the call starts).
        """
        logger.info(f"Looking up memory for caller: {user_id}")

        record = await lookup_caller(user_id)
        if record:
            try:
                # `facts` can be a string if asyncpg returns it unparsed, or a dict if parsed
                facts_data = record["facts"]
                if isinstance(facts_data, str):
                    facts_data = json.loads(facts_data)

                facts_str = ", ".join([f"{k}: {v}" for k, v in facts_data.items() if v])
                return f"Caller found. Name: {record['name']}. Language Preference: {record['language_preference']}. Known Facts: {facts_str}. Last Interaction: {record['last_interaction']}."
            except Exception as e:
                logger.error(f"Error parsing memory for {user_id}: {e}")
                return f"Caller found. Name: {record['name']}. Language Preference: {record['language_preference']}."
        else:
            return "No previous memory found for this caller."

    @function_tool
    async def save_caller_memory(
        self,
        context: RunContext,
        user_id: str,
        name: str,
        language_preference: str,
        age_band: str = "",
        ongoing_condition: str = "",
        last_triage_outcome: str = "",
    ) -> str:
        """Use this tool to explicitly persist newly learned information for the caller.

        CRITICAL RULE: You MUST ask the user for explicit consent before calling this tool.
        If they do not say 'Yes' to you remembering it, DO NOT call this tool.

        Args:
            user_id: The unique identifier for the caller (provided to you when the call starts).
            name: The caller's name.
            language_preference: The caller's preferred language.
            age_band: (Optional) The caller's age group (e.g., '18 to 25', '60+').
            ongoing_condition: (Optional) Brief description of an ongoing chronic condition. Do not store detailed medical notes.
            last_triage_outcome: (Optional) Brief note on triage outcome (e.g., 'Advised clinic visit').
        """
        logger.info(f"Saving memory for caller: {user_id} ({name})")

        facts = {}
        if age_band:
            facts["age_band"] = age_band
        if ongoing_condition:
            facts["ongoing_condition"] = ongoing_condition
        if last_triage_outcome:
            facts["last_triage_outcome"] = last_triage_outcome

        # First, fetch existing memory to avoid overwriting existing facts if we are just adding one.
        existing = await lookup_caller(user_id)
        if existing:
            try:
                existing_facts = existing["facts"]
                if isinstance(existing_facts, str):
                    existing_facts = json.loads(existing_facts)

                # Merge existing facts with new ones (new overrides old)
                for k, v in facts.items():
                    existing_facts[k] = v
                facts = existing_facts

                # Keep existing name/lang if not provided in this update
                name = name or existing["name"]
                language_preference = (
                    language_preference or existing["language_preference"]
                )
            except Exception as e:
                logger.error(f"Error merging facts for {user_id}: {e}")

        success = await save_caller(
            user_id=user_id,
            name=name,
            language_preference=language_preference,
            facts=facts,
        )

        if success:
            return "Memory saved successfully."
        else:
            return "Failed to save memory to database."
