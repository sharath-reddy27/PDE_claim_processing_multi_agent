import os
from langchain_core.tools import tool

SOP_DIR = "sop"


def load_sop(error_code: str) -> str:
    sop_path = os.path.join(SOP_DIR, f"SOP_PDE_{error_code}.txt")
    if not os.path.exists(sop_path):
        raise FileNotFoundError(f"SOP not found for error code {error_code}")
    return open(sop_path, "r", encoding="utf-8").read()


@tool
def tool_load_sop(error_code: str) -> str:
    """
    Load the Standard Operating Procedure (SOP) document for a given PDE error code.
    Use this to retrieve the official resolution steps before deciding what action to take.
    Supported error codes: 781 (missing/invalid provider ID), 935 (already adjudicated).
    """
    try:
        sop = load_sop(error_code)
        return f"SOP for error code {error_code}:\n\n{sop}"
    except FileNotFoundError as e:
        return f"ERROR: {e}"