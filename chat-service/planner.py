import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import llm_client
from db.models.plan import Plan, PlanStep
from models import SessionLocal

PLAN_PROMPT = """You are a task planner. Break the user's complex request into 2-5 clear, sequential steps.
Each step should be a specific, actionable task. Output JSON only:
{"steps": ["step 1", "step 2", ...]}"""

SYNTHESIZE_PROMPT = """You are a synthesizer. The user asked a complex question that was broken into steps and executed.
Combine all step results into a single clear, comprehensive final response. Do not mention the steps explicitly."""


def generate_steps(goal: str) -> list[str]:
    response = llm_client.call_haiku([
        {"role": "user", "content": f"{PLAN_PROMPT}\n\nRequest: {goal}"}
    ])
    try:
        data = json.loads(response["content"])
        steps = data.get("steps", [])
        return steps if steps else [goal]
    except (json.JSONDecodeError, KeyError):
        return [goal]


def create_plan(conversation_id: int, user_id: int, goal: str, steps: list[str]) -> tuple[int, list[tuple[int, str]]]:
    db = SessionLocal()
    try:
        plan = Plan(conversation_id=conversation_id, user_id=user_id, goal=goal, status="running")
        db.add(plan)
        db.flush()
        plan_steps = []
        for i, desc in enumerate(steps):
            step = PlanStep(plan_id=plan.id, step_number=i + 1, description=desc, status="pending")
            db.add(step)
            plan_steps.append(step)
        db.commit()
        db.refresh(plan)
        for s in plan_steps:
            db.refresh(s)
        return plan.id, [(s.id, s.description) for s in plan_steps]
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
