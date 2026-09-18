import argparse
import json
import sys
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(description="Export task generation traces to multi-turn tool-use SFT training data")
    parser.add_argument("--tasks-dir", type=str, default="./tasks/")
    parser.add_argument("--output", type=str, default="./sft_data/taskgen_train.jsonl")
    parser.add_argument("--min-steps", type=int, default=3)
    return parser.parse_args()


def load_json(path):
    with open(path, "r") as f:
        return json.load(f)


def load_system_prompt():
    prompts_path = Path(__file__).resolve().parent.parent / "data_agent_bench" / "prompts" / "generation_prompts_v1.json"
    prompts = load_json(prompts_path)
    return prompts["TASK_GENERATOR_SYSTEM_PROMPT"], prompts.get("TASK_GENERATOR_TAG_GUIDANCE", ""), prompts.get("TASK_GENERATOR_NO_TAG_GUIDANCE", "")


def build_system_message(system_prompt_template, tag_guidance_template, no_tag_guidance_template, task_metadata):
    domain = task_metadata.get("domain", "General")
    difficulty = task_metadata.get("difficulty", "Medium")
    tags = task_metadata.get("tags", [])

    if tags:
        tag_guidance = tag_guidance_template.format(tags=", ".join(tags))
    else:
        tag_guidance = no_tag_guidance_template.format(domain=domain)

    system_prompt = system_prompt_template.format(
        domain=domain,
        difficulty=difficulty,
        tag_guidance=tag_guidance,
        difficulty_constraints="",
    )
    return system_prompt


def build_user_message(task_metadata):
    domain = task_metadata.get("domain", "General")
    difficulty = task_metadata.get("difficulty", "Medium")
    tags = task_metadata.get("tags", [])

    parts = [
        f"Generate a {difficulty.lower()} difficulty benchmark task for the {domain} domain."
    ]
    if tags:
        parts.append(f"The task should focus on: {', '.join(tags)}.")
    parts.append("Use the provided seed dataset to create the task data, then solve it to produce ground truth.")
    return " ".join(parts)


def build_submit_task_arguments(task_json, expected_output):
    submit_payload = {
        "instance_id": task_json.get("instance_id"),
        "task_metadata": task_json.get("task_metadata"),
        "context": task_json.get("context"),
        "environment_config": task_json.get("environment_config"),
        "ground_truth": expected_output,
    }
    return json.dumps(submit_payload, ensure_ascii=False)


def convert_task(task_dir, system_prompt_template, tag_guidance_template, no_tag_guidance_template, min_steps):
    task_path = task_dir / "task.json"
    meta_path = task_dir / "generation_meta.json"
    gt_path = task_dir / "ground_truth" / "expected_output.json"

    if not task_path.exists() or not meta_path.exists():
        return None, "missing_files"

    task_json = load_json(task_path)
    meta_json = load_json(meta_path)

    trace = meta_json.get("trace")
    if not trace or len(trace) < min_steps:
        return None, "insufficient_steps"

    expected_output = load_json(gt_path) if gt_path.exists() else {}
    task_metadata = task_json.get("task_metadata", {})
    verified = meta_json.get("verified", False)

    system_content = build_system_message(
        system_prompt_template, tag_guidance_template, no_tag_guidance_template, task_metadata
    )
    user_content = build_user_message(task_metadata)

    messages = [
        {"role": "system", "content": system_content},
        {"role": "user", "content": user_content},
    ]

    call_counter = 0

    for step in trace:
        action = step.get("action")

        if action == "python_repl":
            call_counter += 1
            call_id = f"call_{call_counter}"
            code = step.get("full_code", step.get("args_preview", ""))
            messages.append({
                "role": "assistant",
                "content": None,
                "tool_calls": [{
                    "id": call_id,
                    "type": "function",
                    "function": {
                        "name": "python_repl",
                        "arguments": json.dumps({"code": code}, ensure_ascii=False),
                    },
                }],
            })
            result_preview = step.get("result_preview", "(no output)")
            messages.append({
                "role": "tool",
                "tool_call_id": call_id,
                "content": result_preview,
            })

        elif action == "think":
            content = step.get("content_preview", "")
            if content:
                messages.append({
                    "role": "assistant",
                    "content": content,
                })

        elif action == "submit_task":
            call_counter += 1
            call_id = f"call_{call_counter}"
            submit_args = build_submit_task_arguments(task_json, expected_output)
            messages.append({
                "role": "assistant",
                "content": None,
                "tool_calls": [{
                    "id": call_id,
                    "type": "function",
                    "function": {
                        "name": "submit_task",
                        "arguments": submit_args,
                    },
                }],
            })

        elif action == "web_search":
            call_counter += 1
            call_id = f"call_{call_counter}"
            query = ""
            args_preview = step.get("args_preview", "")
            if "'query':" in args_preview:
                try:
                    query = args_preview.split("'query': '")[1].rstrip("'}")
                except (IndexError, ValueError):
                    query = args_preview
            messages.append({
                "role": "assistant",
                "content": None,
                "tool_calls": [{
                    "id": call_id,
                    "type": "function",
                    "function": {
                        "name": "web_search",
                        "arguments": json.dumps({"query": query}, ensure_ascii=False),
                    },
                }],
            })
            result_preview = step.get("result_preview", "(no results)")
            messages.append({
                "role": "tool",
                "tool_call_id": call_id,
                "content": result_preview,
            })

    quality_tier = "verified" if verified else "unverified"

    record = {
        "messages": messages,
        "metadata": {
            "instance_id": task_json.get("instance_id"),
            "domain": task_metadata.get("domain"),
            "difficulty": task_metadata.get("difficulty"),
            "generator": meta_json.get("generator"),
            "quality_tier": quality_tier,
            "num_turns": len(messages),
        },
    }

    return record, None


def main():
    args = parse_args()
    tasks_dir = Path(args.tasks_dir)
    output_path = Path(args.output)

    if not tasks_dir.exists():
        print(f"Error: tasks directory '{tasks_dir}' does not exist.")
        sys.exit(1)

    system_prompt_template, tag_guidance_template, no_tag_guidance_template = load_system_prompt()

    task_dirs = sorted([d for d in tasks_dir.iterdir() if d.is_dir()])
    total = len(task_dirs)
    exported = 0
    skipped = 0
    skip_reasons = {}
    total_turns = 0

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w") as out_f:
        for task_dir in task_dirs:
            record, skip_reason = convert_task(
                task_dir,
                system_prompt_template,
                tag_guidance_template,
                no_tag_guidance_template,
                args.min_steps,
            )
            if record is None:
                skipped += 1
                skip_reasons[skip_reason] = skip_reasons.get(skip_reason, 0) + 1
                continue

            out_f.write(json.dumps(record, ensure_ascii=False) + "\n")
            exported += 1
            total_turns += record["metadata"]["num_turns"]

    avg_turns = total_turns / exported if exported > 0 else 0

    print("=" * 60)
    print("Export Statistics")
    print("=" * 60)
    print(f"Total tasks scanned:     {total}")
    print(f"Exported:                {exported}")
    print(f"Skipped:                 {skipped}")
    if skip_reasons:
        for reason, count in sorted(skip_reasons.items()):
            print(f"  - {reason}: {count}")
    print(f"Avg conversation length: {avg_turns:.1f} messages")
    print(f"Output written to:       {output_path}")
    print("=" * 60)


if __name__ == "__main__":
    main()
