from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .schema import InputError
from .workflow import evaluate_artifact


def _format_markdown(result: dict[str, Any]) -> str:
    lines = [
        f"# ProofMark Evaluation",
        "",
        f"Verdict: {result['verdict']}",
        f"Overall score: {result['overall_score']}/100",
        "",
        "## Rubric",
    ]
    for item in result["rubric"]:
        lines.extend(
            [
                f"- {item['name']}: {item['score']}/5",
                f"  Evidence: {item['evidence']}",
                f"  Feedback: {item['feedback']}",
            ]
        )
    lines.extend(["", "## Missing Gaps"])
    for gap in result["missing_gaps"]:
        lines.append(f"- {gap}")
    step = result["next_best_step"]
    lines.extend(
        [
            "",
            "## Next Best Step",
            f"{step['title']}: {step['instructions']}",
            "",
            "Acceptance criteria:",
        ]
    )
    for criterion in step.get("acceptance_criteria", []):
        lines.append(f"- {criterion}")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate a learner artifact as proof-of-work.")
    parser.add_argument("--artifact-file", required=True, help="Path to the learner artifact text file.")
    parser.add_argument("--goal", required=True, help="Learner goal or objective.")
    parser.add_argument("--type", default="brief", dest="artifact_type", help="Artifact type: brief, draft, code, case-study, reflection, other.")
    parser.add_argument("--level", default="intermediate", help="Learner level.")
    parser.add_argument("--output-goal", default="Improve this artifact enough to show credible proof-of-work.")
    parser.add_argument("--provider", choices=("auto", "local", "openai"), default="auto")
    parser.add_argument("--format", choices=("json", "markdown"), default="markdown")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    artifact_path = Path(args.artifact_file)
    try:
        artifact = artifact_path.read_text(encoding="utf-8")
        result = evaluate_artifact(
            {
                "artifact": artifact,
                "learner_goal": args.goal,
                "artifact_type": args.artifact_type,
                "level": args.level,
                "output_goal": args.output_goal,
            },
            provider=args.provider,
        )
    except FileNotFoundError:
        print(f"Artifact file not found: {artifact_path}", file=sys.stderr)
        return 2
    except UnicodeDecodeError:
        print(f"Artifact file must be UTF-8 text: {artifact_path}", file=sys.stderr)
        return 2
    except InputError as exc:
        print(json.dumps(exc.to_dict(), indent=2), file=sys.stderr)
        return 2

    if args.format == "json":
        print(json.dumps(result, indent=2))
    else:
        print(_format_markdown(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

