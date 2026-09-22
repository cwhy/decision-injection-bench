"""Commands for planning, running, searching, freezing and scoring v2."""

import argparse
import json
from pathlib import Path
from .cases import corpus, digest, make_plan, selection_load
from .runtime import execute_plan
from .scoring import markdown_report, score_run, score_search
from .search import execute_search, freeze


def common(parser):
    parser.add_argument(
        "--dataset",
        type=Path,
        help="Optional versioned JSON corpus; groups must not cross splits",
    )
    parser.add_argument(
        "--defenses",
        nargs="+",
        choices=["basic", "hardened", "strict"],
        default=["basic", "hardened", "strict"],
    )
    parser.add_argument(
        "--orders",
        nargs="+",
        choices=["normal", "reversed"],
        default=["normal", "reversed"],
    )
    parser.add_argument("--seed", type=int, default=20260922)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="decision-injection-bench comprehensive")
    sub = parser.add_subparsers(dest="command", required=True)
    plan = sub.add_parser(
        "plan",
        help="Offline: generate immutable static or transferred evaluation cases",
    )
    common(plan)
    plan.add_argument(
        "--split", choices=["development", "validation", "test"], default="test"
    )
    plan.add_argument("--repeats", type=int, default=2)
    plan.add_argument("--selection", type=Path)
    plan.add_argument("--out", type=Path, required=True)
    run = sub.add_parser("run", help="Explicit live evaluation of a saved plan")
    run.add_argument("--plan", type=Path, required=True)
    run.add_argument("--backend", required=True)
    run.add_argument("--adapter")
    run.add_argument("--max-calls", type=int, required=True)
    run.add_argument("--out", type=Path, required=True)
    run.add_argument("--resume", action="store_true")
    search = sub.add_parser(
        "search",
        help="Defense-aware development search; never uses test/validation items",
    )
    common(search)
    search.add_argument("--backend", required=True)
    search.add_argument("--adapter")
    search.add_argument("--method", choices=["bon", "iterative", "beam"], required=True)
    search.add_argument(
        "--attacker",
        help="module:function proposal plugin; required for iterative/beam",
    )
    search.add_argument(
        "--budget",
        type=int,
        default=32,
        help="Defender calls per item/policy/order, including 2 controls",
    )
    search.add_argument("--attacker-budget", type=int, default=32)
    search.add_argument("--max-calls", type=int, required=True)
    search.add_argument("--width", type=int, default=4)
    search.add_argument("--branching", type=int, default=3)
    search.add_argument(
        "--feedback", choices=["probability", "label"], default="probability"
    )
    search.add_argument("--max-wrapper-characters", type=int, default=32000)
    search.add_argument("--dry-run", action="store_true")
    search.add_argument("--out", type=Path, required=True)
    frozen = sub.add_parser(
        "freeze",
        help="Offline: freeze transfer attacks from completed development searches",
    )
    frozen.add_argument("--dataset", type=Path)
    frozen.add_argument("--searches", nargs="+", type=Path, required=True)
    frozen.add_argument("--top-k", type=int, default=3)
    frozen.add_argument("--out", type=Path, required=True)
    score = sub.add_parser(
        "score", help="Offline: score a plan-backed run or development search"
    )
    score.add_argument("run", type=Path)
    score.add_argument("--search", action="store_true")
    score.add_argument("--markdown", type=Path)
    args = parser.parse_args(argv)
    if args.command == "plan":
        data = corpus(args.dataset)
        selection = selection_load(args.selection, data) if args.selection else None
        p = make_plan(
            data,
            args.split,
            args.defenses,
            args.orders,
            args.repeats,
            args.seed,
            selection,
        )
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("x") as file:
            json.dump(p, file, ensure_ascii=False)
        result = dict(
            plan_sha256=p["sha256"],
            calls_per_backend=len(p["cases"]),
            scenario_groups=len({e["item"]["group"] for e in p["cases"]}),
            items=len({e["item"]["id"] for e in p["cases"]}),
            split=args.split,
            model_calls_made=0,
        )
    elif args.command == "run":
        result = execute_plan(
            json.loads(args.plan.read_text()),
            args.out,
            args.backend,
            args.adapter,
            args.max_calls,
            args.resume,
        )
    elif args.command == "search":
        data = corpus(args.dataset)
        if (
            args.budget < 3
            or args.width < 1
            or args.branching < 1
            or args.attacker_budget < 1
            or args.max_wrapper_characters < 1
        ):
            parser.error(
                "Search limits must be positive; budget must include two controls plus an attack"
            )
        if len(set(args.defenses)) != len(args.defenses) or len(
            set(args.orders)
        ) != len(args.orders):
            parser.error("Duplicate conditions")
        n = (
            sum(i["split"] == "development" for i in data["items"])
            * len(args.defenses)
            * len(args.orders)
        )
        if args.dry_run:
            result = dict(
                corpus_sha256=digest(data),
                conditions=n,
                max_defender_calls=n * args.budget,
                max_attacker_invocations=n * args.attacker_budget
                if args.method != "bon"
                else 0,
                provided_defender_budget=args.max_calls,
                model_calls_made=0,
            )
        else:
            result = execute_search(
                data,
                args.out,
                args.backend,
                args.method,
                args.defenses,
                args.orders,
                args.budget,
                args.max_calls,
                args.seed,
                args.adapter,
                args.attacker,
                args.attacker_budget,
                args.width,
                args.branching,
                args.feedback,
                args.max_wrapper_characters,
            )
    elif args.command == "freeze":
        result = freeze(corpus(args.dataset), args.searches, args.out, args.top_k)
        result = {
            "sha256": result["sha256"],
            "selected_per_category": {k: len(v) for k, v in result["attacks"].items()},
            "source_split": "development",
        }
    else:
        result = score_search(args.run) if args.search else score_run(args.run)
        if args.markdown:
            if args.search:
                parser.error("--markdown is for evaluation runs")
            with args.markdown.open("x") as file:
                file.write(markdown_report(result))
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
