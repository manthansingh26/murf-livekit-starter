import logging

from livekit.agents import RunContext, function_tool

logger = logging.getLogger("triage_tool")


class TriageTools:
    @function_tool
    async def analyze_symptoms(
        self, context: RunContext, symptoms: str, duration_days: int
    ) -> str:
        """Use this tool to analyze the user's reported symptoms and duration to determine urgency.

        Args:
            symptoms: A comma-separated list of symptoms the user is experiencing (e.g. 'fever, cough, chest pain').
            duration_days: How many days the user has had these symptoms.
        """
        logger.info(f"Analyzing symptoms: {symptoms} for {duration_days} days")

        symptoms_lower = symptoms.lower()

        # Simple mock logic for urgency based on common critical keywords
        critical_keywords = [
            "chest pain",
            "breathing",
            "breathlessness",
            "unconscious",
            "bleeding",
            "severe",
            "heart",
        ]
        for keyword in critical_keywords:
            if keyword in symptoms_lower:
                return "CRITICAL: Advise user to seek immediate emergency medical help or call an ambulance immediately. Do not provide home remedies."

        if duration_days > 7:
            return "HIGH: Symptoms have persisted for more than a week. Advise consulting a doctor at a primary health center soon."

        return "LOW/MODERATE: Suggest resting, monitoring symptoms, and visiting a local clinic if they worsen."
