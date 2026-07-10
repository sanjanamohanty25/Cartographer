import os
import json
import logging
from typing import Any, Dict, Union
from neuro_san.interfaces.coded_tool import CodedTool

try:
    from _paths import cost_rate_card_path
except ImportError:
    from coded_tools.migration_intelligence._paths import cost_rate_card_path

logger = logging.getLogger(__name__)

class CostReferenceTool(CodedTool):
    """CodedTool that reads local cost_rate_card.json and returns rates for cited resources."""

    def invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> Union[Dict[str, Any], str]:
        logger.info("********** CostReferenceTool started **********")
        request_id = args.get("request_id")
        resources = args.get("resources", [])

        if not request_id:
            return {"error": "Missing request_id"}

        # Define file path (dynamic — COST_RATE_CARD_PATH or repo default)
        rate_card_path = cost_rate_card_path()

        if not os.path.exists(rate_card_path):
            return {"error": f"Cost rate-card file not found at: {rate_card_path}"}

        # Load rate card data
        try:
            with open(rate_card_path, "r", encoding="utf-8") as f:
                rate_card = json.load(f)
        except Exception as e:
            return {"error": f"Failed to parse cost_rate_card.json: {e}"}

        # Index rate card entries by ID for fast lookup
        rate_map = {item["id"]: item for item in rate_card}

        matched_entries = {}
        missing_ids = []

        for res_id in resources:
            if res_id in rate_map:
                matched_entries[res_id] = rate_map[res_id]
            else:
                missing_ids.append(res_id)

        logger.info("********** CostReferenceTool completed **********")

        if missing_ids:
            # Rejects request containing invalid citation IDs
            return {
                "status": "error",
                "message": f"Validation failed: The following cited resource IDs were not found in the rate card: {missing_ids}",
                "missing_resources": missing_ids,
                "available_ids": list(rate_map.keys())
            }
        else:
            return {
                "status": "success",
                "rate_card_entries": matched_entries
            }
