import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import llm_client
from db.models.plan import Plan, PlanStep
from models import SessionLocal

PLAN_PROMPT = """You are a task planner. Break the user's complex request into 2-5 clear, sequential steps.
Each step should be a specific, actionable task.
For each step, list which EARLIER steps it depends on, by their 1-based number. A step
depends on another ONLY if it needs that step's output. Independent steps that can stand
alone must have an empty list. Never depend on a later step or on itself.
Output JSON only, no markdown:
{"steps": [{"task": "...", "depends_on": []}, {"task": "...", "depends_on": [1, 2]}]}"""

SYNTHESIZE_PROMPT = """You are a synthesizer. The user asked a complex question that was broken into steps and executed.
Combine all step results into a single clear, comprehensive final response. Do not mention the steps explicitly."""


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        if text.endswith("```"):
            text = text.rsplit("```", 1)[0]
    return text.strip()


def _normalize_steps(raw: list) -> list[dict]:
    """Coerce LLM output into [{"task": str, "depends_on": [int, ...]}].

    Keeps only dependencies that point to a strictly earlier step (1-based),
    so a bad/forward/self/circular reference from the LLM is dropped.
    """
    steps = []
    for i, item in enumerate(raw):
        num = i + 1
        if isinstance(item, str):
            steps.append({"task": item, "depends_on": []})
            continue
        if isinstance(item, dict):
            task = item.get("task") or item.get("description") or ""
            deps = item.get("depends_on") or []
            deps = [d for d in deps if isinstance(d, int) and 1 <= d < num]
            if task:
                steps.append({"task": task, "depends_on": deps})
    return steps


def generate_steps(goal: str) -> list[dict]:
    response = llm_client.call_haiku([
        {"role": "user", "content": f"{PLAN_PROMPT}\n\nRequest: {goal}"}
    ])
    try:
        data = json.loads(_strip_fences(response["content"]))
        steps = _normalize_steps(data.get("steps", []))
    except (json.JSONDecodeError, KeyError, AttributeError):
        steps = []
    return steps if steps else [{"task": goal, "depends_on": []}]


def create_plan(conversation_id: int, user_id: int, goal: str, steps: list[dict]) -> tuple[int, list[tuple[int, int, str, list[int]]]]:
    """Persist plan + steps. Returns (plan_id, [(step_id, step_number, description, depends_on), ...])."""
    db = SessionLocal()
    try:
        plan = Plan(conversation_id=conversation_id, user_id=user_id, goal=goal, status="running")
        db.add(plan)
        db.flush()
        plan_steps = []
        for i, step in enumerate(steps):
            ps = PlanStep(
                plan_id=plan.id,
                step_number=i + 1,
                description=step["task"],
                depends_on=json.dumps(step["depends_on"]),
                status="pending",
            )
            db.add(ps)
            plan_steps.append(ps)
        db.commit()
        db.refresh(plan)
        for s in plan_steps:
            db.refresh(s)
        return plan.id, [(s.id, s.step_number, s.description, json.loads(s.depends_on or "[]")) for s in plan_steps]
    finally:
        db.close()


def complete_step(step_id: int, result: str):
    db = SessionLocal()
    try:
        step = db.query(PlanStep).filter_by(id=step_id).first()
        if step:
            step.status = "done"
            step.result = result
            db.commit()
    finally:
        db.close()


def complete_plan(plan_id: int):
    db = SessionLocal()
    try:
        plan = db.query(Plan).filter_by(id=plan_id).first()
        if plan:
            plan.status = "done"
            db.commit()
    finally:
        db.close()


def synthesize(goal: str, steps: list[str], results: list[str], messages: list):
    """Stream a synthesized final answer from all step results."""
    step_summary = "\n\n".join(
        f"Step {i + 1}: {step}\nResult: {result}"
        for i, (step, result) in enumerate(zip(steps, results))
    )
    synth_messages = [m for m in messages if m.get("role") == "system"] + [
        {
            "role": "user",
            "content": (
                f"{SYNTHESIZE_PROMPT}\n\n"
                f"Original request: {goal}\n\n"
                f"Step results:\n{step_summary}"
            ),
        }
    ]
    yield from llm_client.stream(synth_messages)
