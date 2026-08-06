import logging
from livekit.agents import function_tool, RunContext

logger = logging.getLogger("escalation_tool")

class EscalationTools:
    @function_tool
    async def find_emergency_contact(self, context: RunContext, location_type: str) -> str:
        """Use this tool when you need to provide emergency contact numbers to the user in India.
        
        Args:
            location_type: The type of location or specific need (e.g. 'general', 'ambulance', 'women helpline', 'health helpline').
        """
        logger.info(f"Fetching emergency contact for: {location_type}")
        
        contacts = {
            "general": "National Emergency Number is 112",
            "ambulance": "Ambulance number is 108",
            "women helpline": "Women Helpline number is 1091",
            "health helpline": "Health Helpline number is 104"
        }
        
        return contacts.get(location_type.lower(), "National Emergency Number is 112 and Ambulance is 108")
