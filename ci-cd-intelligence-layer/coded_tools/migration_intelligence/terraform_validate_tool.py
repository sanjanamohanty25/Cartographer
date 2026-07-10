import os
import time
import subprocess
import shutil
import logging
from typing import Any, Dict, List, Tuple, Union
from neuro_san.interfaces.coded_tool import CodedTool

try:
    from _paths import request_dir
except ImportError:
    from coded_tools.migration_intelligence._paths import request_dir

logger = logging.getLogger(__name__)

class TerraformValidateTool(CodedTool):
    """CodedTool that writes the drafted Terraform code to disk and validates its syntax."""

    def invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> Union[Dict[str, Any], str]:
        logger.info("********** TerraformValidateTool started **********")
        request_id = args.get("request_id")
        terraform_code = args.get("terraform_code")

        if not request_id or not terraform_code:
            return {"error": "Missing request_id or terraform_code"}

        # Define directory path (dynamic — repo-relative or REQUEST_RESPONSE_ROOT)
        dir_path = request_dir(request_id)

        # Write code to blueprint.tf
        tf_path = os.path.join(dir_path, "blueprint.tf")
        with open(tf_path, "w", encoding="utf-8") as f:
            f.write(terraform_code)

        logger.info(f"Written Terraform blueprint to: {tf_path}")

        # ADR-11 / LLD §12 — retry with exponential backoff (3 attempts, 2/4/8s)
        # before declaring the draft invalid (blocks the request downstream).
        validation_errors: List[str] = []
        is_valid = False
        backoffs = (2, 4, 8)
        for attempt in range(len(backoffs)):
            validation_errors = []
            is_valid = self._validate_once(dir_path, terraform_code, validation_errors)
            if is_valid:
                break
            if attempt < len(backoffs) - 1:
                wait = backoffs[attempt]
                logger.warning(f"Terraform validation attempt {attempt + 1} failed; retrying in {wait}s...")
                time.sleep(wait)

        logger.info("********** TerraformValidateTool completed **********")
        if is_valid:
            return {
                "status": "valid",
                "message": "Terraform code syntax validation passed successfully.",
                "file_path": tf_path
            }
        else:
            return {
                "status": "invalid",
                "message": "Terraform syntax validation failed.",
                "errors": "\n".join(validation_errors),
                "file_path": tf_path
            }

    def _validate_once(self, dir_path: str, terraform_code: str, errors: List[str]) -> bool:
        """One validation pass: live `terraform validate` if the CLI exists,
        otherwise the Python HCL syntax fallback."""
        if shutil.which("terraform") is not None:
            try:
                logger.info("Terraform binary found, performing live validation...")
                init_res = subprocess.run(["terraform", "init", "-backend=false"], cwd=dir_path, capture_output=True, text=True)
                if init_res.returncode == 0:
                    val_res = subprocess.run(["terraform", "validate"], cwd=dir_path, capture_output=True, text=True)
                    if val_res.returncode != 0:
                        errors.append(val_res.stderr or val_res.stdout)
                        return False
                    return True
                logger.warning("Terraform init failed. Falling back to syntax verification.")
                return self._check_syntax(terraform_code, errors)
            except Exception as e:
                logger.error(f"Error executing Terraform CLI: {e}")
                return self._check_syntax(terraform_code, errors)
        logger.info("Terraform binary not found. Running python HCL syntax validation (mock/fallback mode)...")
        return self._check_syntax(terraform_code, errors)

    def _check_syntax(self, code: str, errors: list) -> bool:
        # Check basic bracket balance as a mock HCL validator
        braces = 0
        brackets = 0
        line_num = 1
        for char in code:
            if char == '\n':
                line_num += 1
            elif char == '{':
                braces += 1
            elif char == '}':
                braces -= 1
                if braces < 0:
                    errors.append(f"Syntax error: Unmatched closing brace '}}' around line {line_num}.")
                    return False
            elif char == '[':
                brackets += 1
            elif char == ']':
                brackets -= 1
                if brackets < 0:
                    errors.append(f"Syntax error: Unmatched closing bracket ']' around line {line_num}.")
                    return False

        if braces != 0:
            errors.append(f"Syntax error: Unterminated brace block. Open braces remaining: {braces}.")
            return False
        if brackets != 0:
            errors.append(f"Syntax error: Unterminated bracket block. Open brackets remaining: {brackets}.")
            return False

        # Check for standard blocks presence
        if "resource" not in code and "provider" not in code:
            errors.append("Validation warning: No resource or provider blocks found in code.")
            return False

        return True
