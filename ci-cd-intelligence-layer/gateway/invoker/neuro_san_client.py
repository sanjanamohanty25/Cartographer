import os
import json
import httpx
import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)

class NeuroSanClient:
    """Client wrapper for calling the Neuro-SAN server's streaming_chat API."""

    def __init__(self):
        self.base_url = os.environ.get("NEURO_SAN_URL", "http://localhost:8080")
        # Neuro-SAN serves a network by its registry name (manifest key), not by the
        # frontman agent's name. Our registry is migration_intelligence.hocon.
        self.network_name = os.environ.get("NEURO_SAN_NETWORK", "migration_intelligence")
        logger.info(f"NeuroSanClient initialized: {self.base_url} / network={self.network_name}")

    async def trigger_migration_analysis(self, request_id: str, prompt: str, project_json: str) -> Dict[str, Any]:
        """
        Sends the migration request details to the LeadArchitect frontman agent.
        """
        # Compose a detailed prompt message containing the parameters
        # The LLM will parse this text to extract parameters for calling the coded tools
        composed_text = (
            f"REQUEST_ID: {request_id}\n\n"
            f"MIGRATION_PROMPT: {prompt}\n\n"
            f"PROJECT_JSON_SPECIFICATIONS:\n{project_json}"
        )

        chat_request = {
            "user_message": {
                "type": 2,  # User message type
                "text": composed_text
            },
            "sly_data": {
                "request_id": request_id,
                "prompt": prompt
            },
            "chat_context": {},
            "chat_filter": {}
        }

        api_url = f"{self.base_url}/api/v1/{self.network_name}/streaming_chat"
        logger.info(f"Triggering agent network via: {api_url}")

        timeout = httpx.Timeout(300.0, read=None)  # Large timeout for agent network analysis
        
        last_parsed = {}
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream("POST", api_url, json=chat_request) as response:
                    if response.status_code != 200:
                        logger.error(f"Neuro-SAN server returned error status: {response.status_code}")
                        return {"error": f"Server error: {response.status_code}"}
                        
                    async for line in response.aiter_lines():
                        if line.strip():
                            try:
                                last_parsed = json.loads(line)
                                # Log progress text if present
                                resp = last_parsed.get("response", {})
                                text = resp.get("text", "")
                                if text:
                                    logger.info(f"[Agent Network] {text}")
                            except Exception as parse_err:
                                logger.warning(f"Error parsing log line: {parse_err}")
            
            logger.info("Neuro-SAN agent network analysis finished.")
            return last_parsed

        except Exception as e:
            logger.error(f"Failed to communicate with Neuro-SAN server: {e}")
            return {"error": str(e)}
