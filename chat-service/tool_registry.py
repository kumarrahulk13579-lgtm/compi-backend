import os
import sys
import hashlib
import importlib.util
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.models import Tool
from models import SessionLocal

TOOLS_DIR = os.path.join(os.path.dirname(__file__), "tools")

_handlers: dict[str, callable] = {}


def _get_embedding(text: str) -> list[float]:
    provider = os.getenv("LLM_PROVIDER", "anthropic")
    if provider in ("azure", "openai"):
        from openai import AzureOpenAI, OpenAI
        if provider == "azure":
            client = AzureOpenAI(
                api_key=os.getenv("AZURE_OPENAI_API_KEY"),
                azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
                api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-01"),
            )
            model = os.getenv("AZURE_EMBEDDING_MODEL", "text-embedding-ada-002")
        else:
            client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            model = "text-embedding-ada-002"
        response = client.embeddings.create(model=model, input=text)
        return response.data[0].embedding
    else:
        # Anthropic has no embeddings API — fall back to OpenAI if key is set
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("No embedding provider available. Set OPENAI_API_KEY or use azure/openai provider.")
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        response = client.embeddings.create(model="text-embedding-ada-002", input=text)
        return response.data[0].embedding


def _load_tool_files() -> list[dict]:
    """Load all tool definition dicts from tools/ directory."""
    if not os.path.isdir(TOOLS_DIR):
        return []
    tools = []
    for filename in os.listdir(TOOLS_DIR):
        if not filename.endswith(".py") or filename.startswith("_"):
            continue
        path = os.path.join(TOOLS_DIR, filename)
        spec = importlib.util.spec_from_file_location(filename[:-3], path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        if hasattr(module, "DEFINITION"):
            tools.append({"definition": module.DEFINITION, "handler": getattr(module, "handler", None)})
    return tools


def register_all_tools():
    """Called on startup. Registers or updates tools from tools/ directory."""
    tool_files = _load_tool_files()
    if not tool_files:
        return

    db = SessionLocal()
    try:
        for item in tool_files:
            defn = item["definition"]
            name = defn["name"]
            description = defn["description"]
            desc_hash = hashlib.sha256(description.encode()).hexdigest()

            existing = db.query(Tool).filter(Tool.name == name).first()

            if existing and existing.description_hash == desc_hash:
                _handlers[name] = item["handler"]
                continue

            try:
                embedding = _get_embedding(description)
            except Exception:
                embedding = None

            if existing:
                existing.description = description
                existing.description_hash = desc_hash
                existing.parameters = defn.get("parameters", {})
                existing.state_schema = defn.get("state_schema", {})
                existing.response_types = defn.get("response_types", ["text"])
                existing.embedding = embedding
            else:
                db.add(Tool(
                    name=name,
                    description=description,
                    description_hash=desc_hash,
                    parameters=defn.get("parameters", {}),
                    state_schema=defn.get("state_schema", {}),
                    response_types=defn.get("response_types", ["text"]),
                    embedding=embedding,
                ))

            _handlers[name] = item["handler"]

        db.commit()
    finally:
        db.close()


def search_tools(queries: list[str], limit: int = 3) -> list[Tool]:
    """Semantic search for tools. Runs queries in parallel, deduplicates results."""
    if not queries:
        return []

    def _search_one(query: str) -> list[Tool]:
        embedding = _get_embedding(query)
        db = SessionLocal()
        try:
            return (
                db.query(Tool)
                .filter(Tool.enabled == True)
                .order_by(Tool.embedding.cosine_distance(embedding))
                .limit(limit)
                .all()
            )
        finally:
            db.close()

    with ThreadPoolExecutor() as executor:
        results_per_query = list(executor.map(_search_one, queries))

    seen = set()
    deduped = []
    for results in results_per_query:
        for tool in results:
            if tool.name not in seen:
                seen.add(tool.name)
                deduped.append(tool)

    return deduped


def get_by_names(names: list[str]) -> list[Tool]:
    if not names:
        return []
    db = SessionLocal()
    try:
        return db.query(Tool).filter(Tool.name.in_(names), Tool.enabled == True).all()
    finally:
        db.close()


def get_handler(name: str):
    return _handlers.get(name)
