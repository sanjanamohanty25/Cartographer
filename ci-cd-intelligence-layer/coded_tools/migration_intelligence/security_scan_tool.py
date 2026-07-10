import os
import json
import subprocess
import shutil
import re
import logging
from typing import Any, Dict, List, Union
from neuro_san.interfaces.coded_tool import CodedTool

try:
    from _paths import request_dir
except ImportError:
    from coded_tools.migration_intelligence._paths import request_dir

logger = logging.getLogger(__name__)

class SecurityScanTool(CodedTool):
    """CodedTool that scans the blueprint.tf file using Checkov/Tfsec or fallback mock parser."""

    def invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> Union[Dict[str, Any], str]:
        logger.info("********** SecurityScanTool started **********")
        request_id = args.get("request_id")

        if not request_id:
            return {"error": "Missing request_id"}

        # Define file path (dynamic)
        tf_path = os.path.join(request_dir(request_id), "blueprint.tf")

        if not os.path.exists(tf_path):
            return {"error": f"blueprint.tf not found for request_id: {request_id}"}

        # Try to read code for static analysis
        with open(tf_path, "r", encoding="utf-8") as f:
            code = f.read()

        findings = []
        is_mock_run = True

        # Check for Checkov CLI
        if shutil.which("checkov"):
            try:
                logger.info("Checkov binary found. Running security scan...")
                res = subprocess.run(["checkov", "-f", tf_path, "--output", "json"], capture_output=True, text=True)
                findings = self._parse_checkov(res.stdout)
                is_mock_run = False
                logger.info(f"Checkov parsed {len(findings)} failed checks.")
            except Exception as e:
                logger.error(f"Failed to execute/parse Checkov: {e}. Falling back to mock scan.")
                findings = []
                is_mock_run = True

        if is_mock_run:
            logger.info("No scanning binaries found. Running Python-native static security audits (fallback mode)...")
            findings = self._run_mock_scan(code)

        logger.info(f"Scan finished. Found {len(findings)} security concerns.")
        logger.info("********** SecurityScanTool completed **********")

        return {
            "status": "completed",
            "findings": findings,
            "scan_mode": "mock_fallback" if is_mock_run else "checkov_cli"
        }

    def _parse_checkov(self, stdout: str) -> List[dict]:
        """Parse `checkov --output json` into findings. Handles single-object or
        multi-framework list output. Missing severity -> 'medium'."""
        if not stdout.strip():
            return []
        data = json.loads(stdout)
        blocks = data if isinstance(data, list) else [data]
        sev_norm = {"LOW": "low", "MEDIUM": "medium", "HIGH": "high", "CRITICAL": "critical"}
        findings: List[dict] = []
        for block in blocks:
            failed = (block.get("results") or {}).get("failed_checks", [])
            for chk in failed:
                raw_sev = (chk.get("severity") or "MEDIUM")
                findings.append({
                    "id": chk.get("check_id", "CKV_UNKNOWN"),
                    "severity": sev_norm.get(str(raw_sev).upper(), "medium"),
                    "category": chk.get("check_class", "Compliance"),
                    "description": chk.get("check_name", "Checkov policy violation"),
                })
        return findings

    def _run_mock_scan(self, code: str) -> list:
        findings = []

        # Check 1: Data at rest not encrypted
        #   aws: storage_encrypted/encrypted=false | azure: transparent_data_encryption_enabled=false
        if re.search(r"(storage_encrypted|transparent_data_encryption_enabled|encrypted)\s*=\s*(false|null)", code, re.IGNORECASE):
            findings.append({
                "id": "CKV_AWS_109",
                "severity": "high",
                "category": "Encryption",
                "description": "Data at rest is not encrypted. Enable storage/database encryption at rest (KMS/TDE/CMEK)."
            })

        # Check 2: Publicly accessible database
        #   aws: publicly_accessible=true | azure: public_network_access_enabled=true | gcp: ipv4_enabled=true
        if re.search(r"(publicly_accessible|public_network_access_enabled|ipv4_enabled)\s*=\s*true", code, re.IGNORECASE):
            findings.append({
                "id": "CKV_AWS_16",
                "severity": "critical",
                "category": "Network",
                "description": "Cloud database instance is publicly accessible from the internet. Restrict to private networking."
            })

        # Check 3: Overly permissive ingress (0.0.0.0/0) — SG / NSG rule / firewall source range
        if re.search(r"0\.0\.0\.0/0", code):
            findings.append({
                "id": "CKV_AWS_24",
                "severity": "critical",
                "category": "Networking",
                "description": "Ingress rule allows open public access (0.0.0.0/0). Limit source ranges to internal VPC/VNet CIDRs."
            })

        # Add a default informational check if no issues found
        if not findings:
            findings.append({
                "id": "INFO_CLEAN_01",
                "severity": "low",
                "category": "Audit",
                "description": "Static code checks passed. No high or critical severity vulnerabilities were detected in the HCL file."
            })

        return findings
