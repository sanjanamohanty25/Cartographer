import os
import re
import logging
from typing import Any, Dict, Union
from neuro_san.interfaces.coded_tool import CodedTool

try:
    from _paths import request_dir
except ImportError:
    from coded_tools.migration_intelligence._paths import request_dir

logger = logging.getLogger(__name__)

class ReliabilityCheckTool(CodedTool):
    """CodedTool that checks backup, replication, and Multi-AZ config to score redundancy."""

    def invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> Union[Dict[str, Any], str]:
        logger.info("********** ReliabilityCheckTool started **********")
        request_id = args.get("request_id")

        if not request_id:
            return {"error": "Missing request_id"}

        # Define file path (dynamic)
        tf_path = os.path.join(request_dir(request_id), "blueprint.tf")

        if not os.path.exists(tf_path):
            return {"error": f"blueprint.tf not found for request_id: {request_id}"}

        # Read HCL
        with open(tf_path, "r", encoding="utf-8") as f:
            code = f.read()

        score = 0
        details = []

        # Check 1: Multi-AZ / Replication / zone redundancy
        #   aws: multi_az = true | azure: zone_redundant = true | gcp: availability_type = "REGIONAL"
        if (re.search(r"multi_az\s*=\s*true", code, re.IGNORECASE)
                or re.search(r"zone_redundant\s*=\s*true", code, re.IGNORECASE)
                or re.search(r'availability_type\s*=\s*"?REGIONAL', code, re.IGNORECASE)):
            score += 40
            details.append("Multi-Availability Zone (Multi-AZ) or regional/zone redundancy is enabled (+40 pts).")
        else:
            details.append("High availability warning: Single-AZ deployment detected. No zone redundancy defined.")

        # Check 2: Automated Backups
        #   aws: backup_retention_period=N | azure/gcp: retention_days=N
        backup_match = re.search(r"(?:backup_retention_period|retention_days)\s*=\s*(\d+)", code, re.IGNORECASE)
        if backup_match:
            days = int(backup_match.group(1))
            if days > 0:
                score += 30
                details.append(f"Automated backups are enabled with a retention period of {days} days (+30 pts).")
            else:
                details.append("Reliability warning: Automated backup retention period is set to 0 days.")
        else:
            # Check for general backup / snapshot blocks
            if "backup" in code.lower() or "snapshot" in code.lower():
                score += 20
                details.append("Backup or snapshot features are referenced in code (+20 pts).")
            else:
                details.append("Reliability warning: No backup policy or backup retention period was defined.")

        # Check 3: Load balancing / horizontal redundancy
        #   real LB resource, read replicas, or an instance count > 1 (not a bare "lb" substring)
        if (re.search(r"count\s*=\s*[2-9]", code)
                or re.search(r"(aws_lb|aws_elb|azurerm_lb|google_compute_(region_)?(backend|target|forwarding)|load_balancer|read_replica|replica_count|number_of_replicas)", code, re.IGNORECASE)):
            score += 30
            details.append("Compute resource scaling / read replicas or a load balancer are defined (+30 pts).")
        else:
            details.append("Scalability warning: No load balancer or instance scaling rules (count > 1) detected.")

        logger.info(f"Reliability scan finished. Redundancy Score: {score}/100")
        logger.info("********** ReliabilityCheckTool completed **********")

        return {
            "status": "success",
            "redundancy_score": score,
            "findings": details
        }
