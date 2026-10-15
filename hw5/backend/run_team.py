"""Run the Campus Customs agent team on the open tickets.

    python -m backend.run_team                      # Boss works every open ticket
    python -m backend.run_team --task "Handle ticket 102 only."
"""
import argparse
import asyncio
import sys

from .team import DEFAULT_TASK, run_team


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--task", default=DEFAULT_TASK, help="What to ask the Boss.")
    args = parser.parse_args()
    report = asyncio.run(run_team(args.task))
    print(report.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
