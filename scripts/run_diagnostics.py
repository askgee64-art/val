#!/usr/bin/env python3
"""VAL System Diagnostics Utility — Prompt Spec §8, §9 & Document 24.

Run this script to inspect laptop / server hardware and produce a structured
VAL capability report.
"""

import asyncio
import json
import os
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from val.tools.builtins import SystemInfoTool


async def run_diagnostics():
    tool = SystemInfoTool()
    res = await tool.execute({})
    data = res.output or {}

    print("=" * 60)
    print("      VAL HARDWARE & RUNTIME DIAGNOSTIC REPORT")
    print("=" * 60)
    print(f"OS:               {data.get('os')}")
    print(f"Python:           {data.get('python_version')}")
    print(f"CPU Cores:        {data.get('cpu_cores')}")
    print(f"System RAM:       {data.get('ram_total_mb')} MB total (Available: {data.get('ram_available_mb')} MB)")
    print(f"Disk Storage:     {data.get('disk_free_gb')} GB free / {data.get('disk_total_gb')} GB total")
    print("-" * 60)
    print("Local Runtimes:")
    for k, v in data.get("local_runtimes", {}).items():
        status = "AVAILABLE" if v else "NOT FOUND / DISABLED"
        print(f"  - {k:<25}: {status}")
    print("-" * 60)
    print("Hardware Classification & Workload Recommendations:")
    cls = data.get("classification", {})
    print(f"  - Hardware Tier:          {cls.get('hardware_tier')}")
    print(f"  - Quantized Model Capable:{cls.get('local_quantized_capable')}")
    print(f"  - Recommended Mode:       {cls.get('recommended_mode')}")
    print("=" * 60)

    # Dump JSON report to disk
    report_path = Path("/home/user/val/data/diagnostic_report.json")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"\nSaved raw JSON diagnostic report to: {report_path}\n")


if __name__ == "__main__":
    asyncio.run(run_diagnostics())
