"""
math_graph.py — Mathematics Knowledge Graph Builder
════════════════════════════════════════════════════
Builds a KG from transcribed math content.

Node types (math-specific):
  Concept    — integral, derivative, limit, matrix, series...
  Formula    — a specific LaTeX expression
  Step       — one derivation step
  Variable   — mathematical variable with domain/type
  Condition  — domain constraint, boundary condition
  Proof      — a proof structure (induction, contradiction...)
  Theorem    — named theorem referenced (e.g. Pythagoras, FTC)

Two Neo4j databases:
  imath_schema  → correct answer KG
  imath_student → student answer KG

Edge types:
  USES_FORMULA, DERIVED_FROM, NEXT_STEP, DEFINES_VARIABLE,
  APPLIES_THEOREM, HAS_CONDITION, IS_EQUIVALENT_TO,
  CONTAINS, HAS_ANSWER
"""

import os, json, re, uuid, time
from pathlib import Path
from datetime import datetime, timezone
from dotenv import load_dotenv

from google import genai
from google.genai import types
from neo4j import GraphDatabase

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL   = "gemini-3-flash-preview"
NEO4J_URI      = os.getenv("NEO4J_URI",      "bolt://localhost:7687")
NEO4J_USER     = os.getenv("NEO4J_USER",     "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")

DB_SCHEMA  = "ischema"
DB_STUDENT = "istudent"

MATH_NODE_LABELS = [
    "Concept",    # mathematical concepts: integral, derivative, matrix...
    "Formula",    # specific LaTeX expression
    "Step",       # derivation step
    "Variable",   # mathematical variable
    "Condition",  # constraints, domain, boundary conditions
    "Proof",      # proof method: induction, contradiction...
    "Theorem",    # named theorems
    "Answer",     # root answer node
    "Question",   # root question node
]


# ══════════════════════════════════════════════════════════
#  NEO4J
# ══════════════════════════════════════════════════════════

class MathNeo4j:
    def __init__(self):
        if not NEO4J_PASSWORD:
            raise ValueError("NEO4J_PASSWORD not set")
        self.driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        self._setup_databases()

    def _setup_databases(self):
        """Create math databases if they don't exist."""
        with self.driver.session(database="system") as s:
            s.run(f"CREATE DATABASE {DB_SCHEMA}  IF NOT EXISTS")
            s.run(f"CREATE DATABASE {DB_STUDENT} IF NOT EXISTS")
        for db in (DB_SCHEMA, DB_STUDENT):
            self._ensure_constraints(db)

    def _ensure_constraints(self, database: str):
        with self.driver.session(database=database) as s:
            for label in MATH_NODE_LABELS:
                try:
                    s.run(f"""
                        CREATE CONSTRAINT IF NOT EXISTS
                        FOR (n:{label}) REQUIRE n.id IS UNIQUE
                    """)
                except Exception:
                    pass

    def close(self):
        self.driver.close()

    def run(self, cypher: str, database: str, **params):
        with self.driver.session(database=database) as s:
            return list(s.run(cypher, **params))

    def upsert_node(self, database: str, node_id: str, label: str, props: dict):
        safe = label if label in MATH_NODE_LABELS else "Concept"
        props["id"] = node_id
        self.run(
            f"MERGE (n:{safe} {{id:$id}}) SET n += $props",
            database=database, id=node_id, props=props,
        )

    def upsert_edge(self, database: str, from_id: str, to_id: str,
                    relation: str, props: dict = {}):
        rel = re.sub(r"[^A-Z0-9_]", "",
                     relation.upper().replace(" ", "_").replace("-", "_")
                     ) or "RELATED_TO"
        self.run(
            f"MATCH (a {{id:$f}}),(b {{id:$t}}) MERGE (a)-[r:{rel}]->(b) SET r += $props",
            database=database, f=from_id, t=to_id, props=props,
        )

    def clear_question(self, database: str, question_id: str):
        self.run(
            "MATCH (n {question_id:$q}) DETACH DELETE n",
            database=database, q=question_id,
        )

    def get_content_type(self, database: str, question_id: str) -> str:
        rows = self.run(
            "MATCH (n:Answer {question_id:$q}) RETURN n.content_type AS ct",
            database=database, q=question_id,
        )
        return rows[0]["ct"] if rows and rows[0]["ct"] else "formula"

    def summary(self, database: str):
        n = self.run("MATCH (n) RETURN count(n) AS c", database=database)[0]["c"]
        e = self.run("MATCH ()-[r]->() RETURN count(r) AS c", database=database)[0]["c"]
        print(f"  [{database}]  {n} nodes · {e} edges")


# ══════════════════════════════════════════════════════════
#  GEMINI
# ══════════════════════════════════════════════════════════

def get_gemini_client():
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY not set")
    return genai.Client(api_key=GEMINI_API_KEY)


def call_gemini(client, prompt: str, max_retries: int = 4) -> str:
    for attempt in range(max_retries):
        try:
            r = client.models.generate_content(model=GEMINI_MODEL, contents=[prompt])
            return r.text.strip()
        except Exception as e:
            if "429" in str(e) or "quota" in str(e).lower():
                wait = (2 ** attempt) * 5
                print(f"  [Gemini] Rate limited. Retrying in {wait}s...")
                time.sleep(wait)
            else:
                raise
    raise RuntimeError("Gemini failed after max retries")


# ══════════════════════════════════════════════════════════
#  MATH-SPECIFIC TRIPLE EXTRACTION PROMPT
# ══════════════════════════════════════════════════════════

MATH_PROMPT = """
You are a knowledge graph builder for mathematics exam answers.

STEP 1 — Detect the math topic from:
  Calculus, Integration, Differentiation, Limits, Series, LinearAlgebra,
  Matrices, Probability, Statistics, Geometry, Trigonometry, NumberTheory,
  DifferentialEquations, ComplexNumbers, Algebra, Proof, GeneralMath

STEP 2 — Extract triples. Node types MUST be one of:
  Concept, Formula, Step, Variable, Condition, Proof, Theorem, Answer, Question

Predicate rules:
  - uses_formula       : Concept → Formula
  - derived_from       : Formula → Formula  (one step leads to next)
  - next_step          : Step → Step
  - defines_variable   : Step/Concept → Variable
  - applies_theorem    : Step → Theorem
  - has_condition      : Formula/Step → Condition
  - is_equivalent_to   : Formula → Formula  (symbolic equality)
  - is_a               : Concept → Concept  (is a type of)
  - has_step           : Proof/Concept → Step

Special rules for math:
  - Every LaTeX formula becomes a Formula node with property latex=<string>
  - Every derivation step becomes a Step node with property order=<int>
  - Variables get domain property (real, integer, complex, etc.)
  - Theorems get name property (Pythagorean, Fundamental Theorem of Calculus...)
  - Preserve the LaTeX strings EXACTLY as given
  - Do NOT simplify or rewrite formulas

Content to analyse:
\"\"\"{content}\"\"\"

STEP 3 — Return ONLY valid JSON:
{{
  "topic": "Calculus",
  "triples": [
    {{
      "subject": "integral",
      "subject_type": "Concept",
      "predicate": "uses_formula",
      "object": "\\\\int_a^b f(x)dx",
      "object_type": "Formula"
    }}
  ],
  "entities": {{
    "integral": {{
      "node_type": "Concept",
      "properties": {{}}
    }},
    "\\\\int_a^b f(x)dx": {{
      "node_type": "Formula",
      "properties": {{"latex": "\\\\int_a^b f(x)dx", "order": 1}}
    }}
  }}
}}
"""


def extract_math_triples(
    client,
    combined_text: str,
    latex_blocks: list[str],
    steps: list[dict],
    variables: dict,
) -> dict:
    """
    Sends combined content to Gemini for math-specific triple extraction.
    Enriches the prompt with structured data from math_extract.
    """
    # Build rich context for Gemini
    content_parts = [combined_text]

    if latex_blocks:
        content_parts.append("\nExtracted LaTeX formulas (in order):")
        for i, lb in enumerate(latex_blocks, 1):
            content_parts.append(f"  [{i}] {lb}")

    if steps:
        content_parts.append("\nDerivation steps (numbered):")
        for s in steps:
            content_parts.append(f"  Step {s['step']}: {s['content']}")

    if variables:
        content_parts.append("\nVariable definitions:")
        for var, defn in variables.items():
            content_parts.append(f"  {var} = {defn}")

    content = "\n".join(content_parts)
    prompt  = MATH_PROMPT.format(content=content)

    print("  [Gemini] Extracting math triples...")
    raw = call_gemini(client, prompt)

    cleaned = re.sub(r"```(?:json)?|```", "", raw).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        m = re.search(r'\{.*\}', cleaned, re.DOTALL)
        if m:
            try:
                return json.loads(m.group())
            except Exception:
                pass
    print("  [Gemini] WARNING: could not parse JSON")
    return {"topic": "unknown", "triples": [], "entities": {}}


# ══════════════════════════════════════════════════════════
#  PUSH KG TO NEO4J
# ══════════════════════════════════════════════════════════

def push_math_kg(
    neo4j: MathNeo4j,
    gemini_data: dict,
    extraction: dict,          # from math_extract.extract_from_math_page()
    database: str,
    question_id: str,
):
    """
    Writes math KG to Neo4j.
    Also directly writes Step nodes and Formula nodes from extraction
    (in case Gemini misses some).
    """
    topic        = gemini_data.get("topic", "unknown")
    triples      = gemini_data.get("triples", [])
    entities     = gemini_data.get("entities", {})
    content_type = extraction.get("content_type", "formula")
    now          = datetime.now(timezone.utc).isoformat()

    base = {
        "question_id":  question_id,
        "topic":        topic,
        "content_type": content_type,
        "created_at":   now,
    }

    # ── Root nodes ────────────────────────────────────────────────────────────
    q_node = f"question:{question_id}"
    a_node = f"answer:{question_id}"

    neo4j.upsert_node(database, q_node, "Question",
                      {**base, "label": f"Question {question_id}"})
    neo4j.upsert_node(database, a_node, "Answer",
                      {**base, "label": f"Answer {question_id}",
                       "topic": topic, "content_type": content_type})
    neo4j.upsert_edge(database, q_node, a_node, "HAS_ANSWER")

    # ── Directly write Formula nodes from extraction ──────────────────────────
    for i, latex in enumerate(extraction.get("latex_blocks", []), 1):
        nid = f"{question_id}:formula:{i}"
        neo4j.upsert_node(database, nid, "Formula", {
            **base,
            "label":     latex[:80],   # truncate for display
            "latex":     latex,
            "latex_norm": re.sub(r'\s+', '', latex),
            "order":     i,
        })
        neo4j.upsert_edge(database, a_node, nid, "CONTAINS")

    # ── Directly write Step nodes from extraction ─────────────────────────────
    prev_step_id = None
    for s in extraction.get("steps", []):
        nid = f"{question_id}:step:{s['step']}"
        neo4j.upsert_node(database, nid, "Step", {
            **base,
            "label":   f"Step {s['step']}",
            "content": s["content"][:200],
            "order":   s["step"],
        })
        neo4j.upsert_edge(database, a_node, nid, "HAS_STEP")
        if prev_step_id:
            neo4j.upsert_edge(database, prev_step_id, nid, "NEXT_STEP")
        prev_step_id = nid

    # ── Variable nodes ────────────────────────────────────────────────────────
    for var, defn in extraction.get("variables", {}).items():
        nid = f"{question_id}:var:{var}"
        neo4j.upsert_node(database, nid, "Variable", {
            **base,
            "label":      var,
            "definition": defn[:100],
        })
        neo4j.upsert_edge(database, a_node, nid, "DEFINES_VARIABLE")

    # ── Gemini entities ───────────────────────────────────────────────────────
    for name, meta in entities.items():
        nid   = f"{question_id}:{name[:60]}"
        label = meta.get("node_type", "Concept")
        props = {**base, "label": name[:80], **meta.get("properties", {})}
        neo4j.upsert_node(database, nid, label, props)
        neo4j.upsert_edge(database, a_node, nid, "CONTAINS")

    # ── Gemini triples ────────────────────────────────────────────────────────
    for t in triples:
        subj  = str(t.get("subject",  "")).strip()[:60]
        obj   = str(t.get("object",   "")).strip()[:60]
        pred  = t.get("predicate", "related_to").strip()
        stype = t.get("subject_type", "Concept")
        otype = t.get("object_type",  "Concept")
        extra = {k: v for k, v in t.items()
                 if k not in ("subject","object","predicate","subject_type","object_type")}
        if not subj or not obj:
            continue
        sid = f"{question_id}:{subj}"
        oid = f"{question_id}:{obj}"
        neo4j.upsert_node(database, sid, stype, {**base, "label": subj})
        neo4j.upsert_node(database, oid, otype, {**base, "label": obj})
        neo4j.upsert_edge(database, sid, oid, pred, {**base, **extra})

    print(f"  [{database}] Stored {len(triples)} triples, "
          f"{len(extraction.get('latex_blocks',[]))} formulas, "
          f"{len(extraction.get('steps',[]))} steps  (topic={topic})")
    return topic