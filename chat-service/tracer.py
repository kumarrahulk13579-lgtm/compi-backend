import time
import uuid
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.models import Trace
from models import SessionLocal


class TraceContext:
    def __init__(self, trace_id: str, conversation_id: int, user_id: int):
        self.trace_id = trace_id
        self.conversation_id = conversation_id
        self.user_id = user_id

    def log(self, step: str, input: dict = None, output: dict = None, duration_ms: float = None, cost_usd: float = None):
        db = SessionLocal()
        try:
            db.add(Trace(
                trace_id=self.trace_id,
                conversation_id=self.conversation_id,
                user_id=self.user_id,
                step=step,
                input=input,
                output=output,
                duration_ms=duration_ms,
                cost_usd=cost_usd,
            ))
            db.commit()
        finally:
            db.close()


def new_trace(conversation_id: int, user_id: int) -> TraceContext:
    return TraceContext(
        trace_id=str(uuid.uuid4()),
        conversation_id=conversation_id,
        user_id=user_id,
    )


def timed(tracer: TraceContext, step: str, input: dict = None):
    """Context manager to time a step and log it."""
    return _TimedStep(tracer, step, input)


class _TimedStep:
    def __init__(self, tracer: TraceContext, step: str, input: dict):
        self.tracer = tracer
        self.step = step
        self.input = input
        self.output = None
        self.cost_usd = None

    def __enter__(self):
        self._start = time.monotonic()
        return self

    def set_output(self, output: dict, cost_usd: float = None):
        self.output = output
        self.cost_usd = cost_usd

    def __exit__(self, *_):
        duration_ms = (time.monotonic() - self._start) * 1000
        self.tracer.log(
            step=self.step,
            input=self.input,
            output=self.output,
            duration_ms=round(duration_ms, 2),
            cost_usd=self.cost_usd,
        )
