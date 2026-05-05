"""
TOC Knowledge Graph Pipeline — Separate Databases
══════════════════════════════════════════════════
Schema KG  → Neo4j database: ischema
Student KG → Neo4j database: istudent

Fixes applied vs previous version:
  1. Migrated from deprecated google.generativeai → google.genai
  2. Uses gemini-1.5-flash (free tier; NOT gemini-2.5-pro which exhausts quota)
  3. Exponential backoff retry on 429 rate limit errors
  4. Fixed datetime.utcnow() → datetime.now(timezone.utc)
  5. Separate Neo4j databases per role (ischema / istudent)
  6. Credentials loaded from environment variables — never hardcode them

Setup:
  1. pip install google-genai neo4j
  2. In Neo4j Browser (localhost:7474) run once as admin:
       CREATE DATABASE ischema IF NOT EXISTS
       CREATE DATABASE istudent IF NOT EXISTS
  3. Set environment variables (PowerShell):
       $env:GEMINI_API_KEY  = "your_new_key"
       $env:NEO4J_PASSWORD  = "your_password"
"""

import os, json, re, uuid, time
from pathlib import Path
from datetime import datetime, timezone
from dotenv import load_dotenv

from google import genai
from google.genai import types
from neo4j import GraphDatabase


# ══════════════════════════════════════════════════════════
#  CONFIG — all secrets from environment, never hardcoded
# ══════════════════════════════════════════════════════════
load_dotenv()

NEO4J_URI      = os.getenv("NEO4J_URI",      "bolt://localhost:7687")
NEO4J_USER     = os.getenv("NEO4J_USER",     "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")        # set via env var
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")        # set via env var

# Free-tier model — do NOT change to gemini-2.5-pro (quota exhausted instantly)
GEMINI_MODEL = "gemini-2.5-flash"

# The two separate Neo4j databases
DB_SCHEMA  = "ischema"
DB_STUDENT = "istudent"

UNIVERSAL_NODE_LABELS = [
    "Concept", "State", "Symbol", "Rule", "Property",
    "Language", "Relation", "Proof_step", "Answer", "Question",
]


# ══════════════════════════════════════════════════════════
#  NEO4J — one connection class, database selected per use
# ══════════════════════════════════════════════════════════

class Neo4jConn:
    """
    Wraps Neo4j driver. Pass database="ischema" or "istudent"
    to every operation to keep them fully separate.
    """

    def __init__(self):
        if not NEO4J_PASSWORD:
            raise ValueError("NEO4J_PASSWORD env var is not set.")
        self.driver = GraphDatabase.driver(
            NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD)
        )
        # Ensure both databases have uniqueness constraints
        for db in (DB_SCHEMA, DB_STUDENT):
            self._ensure_constraints(db)

    def _ensure_constraints(self, database: str):
        with self.driver.session(database=database) as s:
            for label in UNIVERSAL_NODE_LABELS:
                try:
                    s.run(f"""
                        CREATE CONSTRAINT IF NOT EXISTS
                        FOR (n:{label}) REQUIRE n.id IS UNIQUE
                    """)
                except Exception:
                    pass   # already exists

    def close(self):
        self.driver.close()

    def run(self, cypher: str, database: str, **params):
        """Run any Cypher query against a specific database."""
        with self.driver.session(database=database) as s:
            return list(s.run(cypher, **params))

    def upsert_node(self, database: str, node_id: str, label: str, props: dict):
        safe_label = label if label in UNIVERSAL_NODE_LABELS else "Concept"
        props["id"] = node_id
        self.run(
            f"MERGE (n:{safe_label} {{id:$id}}) SET n += $props",
            database=database,
            id=node_id,
            props=props,
        )

    def upsert_edge(self, database: str, from_id: str, to_id: str,
                    relation: str, props: dict = {}):
        rel = re.sub(
            r"[^A-Z0-9_]", "",
            relation.upper().replace(" ", "_").replace("-", "_")
        ) or "RELATED_TO"
        self.run(
            f"MATCH (a {{id:$f}}),(b {{id:$t}}) MERGE (a)-[r:{rel}]->(b) SET r += $props",
            database=database,
            f=from_id, t=to_id, props=props,
        )

    def clear_question(self, database: str, question_id: str):
        """Remove all nodes for a specific question_id from one database."""
        self.run(
            "MATCH (n {question_id:$q}) DETACH DELETE n",
            database=database, q=question_id,
        )

    def summary(self, database: str):
        n = self.run("MATCH (n) RETURN count(n) AS c", database=database)[0]["c"]
        e = self.run("MATCH ()-[r]->() RETURN count(r) AS c", database=database)[0]["c"]
        print(f"  [{database}]  {n} nodes · {e} relationships")


# ══════════════════════════════════════════════════════════
#  GEMINI — new google.genai SDK with retry
# ══════════════════════════════════════════════════════════

def get_gemini_client() -> genai.Client:
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY env var is not set.")
    return genai.Client(api_key=GEMINI_API_KEY)


def call_gemini(
    client: genai.Client,
    prompt: str,
    image_path: str | None = None,
    max_retries: int = 4,
) -> str:
    """Call Gemini with exponential backoff on 429 quota errors."""
    contents = []

    if image_path and Path(image_path).exists():
        mime = "image/png" if image_path.endswith(".png") else "image/jpeg"
        with open(image_path, "rb") as f:
            contents.append(types.Part.from_bytes(data=f.read(), mime_type=mime))

    contents.append(prompt)

    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=contents,
            )
            return response.text.strip()

        except Exception as e:
            msg = str(e)
            if "429" in msg or "quota" in msg.lower() or "ResourceExhausted" in msg:
                wait = (2 ** attempt) * 5      # 5s → 10s → 20s → 40s
                print(f"  [Gemini] Rate limited. Retrying in {wait}s "
                      f"(attempt {attempt + 1}/{max_retries})...")
                time.sleep(wait)
            else:
                raise   # non-quota error, fail immediately

    raise RuntimeError("Gemini failed after max retries due to rate limiting.")


PROMPT_BASE = """
You are a knowledge graph builder for Theory of Computation (TOC) exam answers.

STEP 1 — Detect topic from: DFA, NFA, CFG, CFL, PDA, TuringMachine,
  PumpingLemma, ClosureProperty, RegularLanguage, ContextFreeLanguage,
  Decidability, Complexity, GeneralTOC

STEP 2 — Extract triples. Rules:
  - node_type must be one of: {node_labels}
  - predicates: short snake_case (has_state, is_final, transitions_on, produces...)
  - Extract every transition / production rule / proof step.
  - Do NOT invent anything not stated in the content.

STEP 3 — Return ONLY valid JSON (no markdown, no prose):
{{
  "topic": "DFA",
  "triples": [
    {{
      "subject": "q0", "subject_type": "State",
      "predicate": "transitions_on",
      "object": "q3", "object_type": "State",
      "symbol": "0"
    }}
  ],
  "entities": {{
    "q0": {{"node_type": "State", "properties": {{"is_start": true, "is_final": false}}}}
  }}
}}

Content:
\"\"\"{content}\"\"\"
"""

_EXTRA = {
    "diagram": """
  - The content below was extracted from a DFA diagram using computer vision.
  - Every transition listed is a directed arrow from the diagram.
  - Focus on extracting the exact (state, symbol, next_state) triples.""",
 
    "text": """
  - The content is a free-text exam answer.
  - Extract conceptual entities and their relationships.
  - For theory questions, extract definitions, properties, and comparisons.""",
 
    "diagram+text": """
  - The content combines diagram data (extracted by CV) AND textual explanation.
  - First extract all DFA transitions from the structured part.
  - Then extract any additional concepts or corrections from the text part.
  - Prefer the structured diagram data for transitions; use text for concepts.""",
}


def extract_triples(
    client: genai.Client,
    text: str,
    image_path: str | None = None,
    content_type:str='text'
) -> dict:
    extra = _EXTRA.get(content_type, _EXTRA["text"])
    prompt = PROMPT_BASE.format(
        node_labels=", ".join(UNIVERSAL_NODE_LABELS),
        extra_instruction = extra,
        content=text or "(no text — analyse the image)",
    )
    print(f"  [Gemini] Extracting triples (content_type={content_type})...")
    raw = call_gemini(client, prompt, image_path)

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
    print("  [Gemini] WARNING: could not parse JSON. Raw response:")
    print(raw[:400])
    return {"topic": "unknown", "triples": [], "entities": {}}


# ══════════════════════════════════════════════════════════
#  PUSH KG TO A SPECIFIC DATABASE
# ══════════════════════════════════════════════════════════

def push_kg(
    neo4j: Neo4jConn,
    data: dict,
    database: str,      # "ischema" or "istudent"
    question_id: str,
    content_type:str='text'
):
    """
    Writes extracted triples + entities into the specified Neo4j database.
    Each node is tagged with question_id and topic for easy querying.
    """
    topic    = data.get("topic", "unknown")
    triples  = data.get("triples", [])
    entities = data.get("entities", {})
    now      = datetime.now(timezone.utc).isoformat()

    base = {
        "question_id": question_id,
        "topic":       topic,
        "content_type":content_type,
        "created_at":  now,
        "database":    database,
    }

    # ── Root nodes ────────────────────────────────────────────────────────────
    q_node  = f"question:{question_id}"
    a_node  = f"answer:{question_id}"

    neo4j.upsert_node(database, q_node, "Question",
                      {**base, "label": f"Question {question_id}"})
    neo4j.upsert_node(database, a_node, "Answer",
                      {**base, "label": f"Answer for {question_id}", "topic": topic,"content_type": content_type})
    neo4j.upsert_edge(database, q_node, a_node, "HAS_ANSWER")

    # ── Entity nodes ──────────────────────────────────────────────────────────
    for name, meta in entities.items():
        nid   = f"{question_id}:{name}"
        label = meta.get("node_type", "Concept")
        props = {**base, "label": name, **meta.get("properties", {})}
        neo4j.upsert_node(database, nid, label, props)
        neo4j.upsert_edge(database, a_node, nid, "CONTAINS")

    # ── Triple edges ──────────────────────────────────────────────────────────
    for t in triples:
        subj  = t.get("subject", "").strip()
        obj   = t.get("object",  "").strip()
        pred  = t.get("predicate", "related_to").strip()
        stype = t.get("subject_type", "Concept")
        otype = t.get("object_type",  "Concept")
        extra = {k: v for k, v in t.items()
                 if k not in ("subject","object","predicate","subject_type","object_type")}

        if not subj or not obj:
            continue

        sid = f"{question_id}:{subj}"
        oid = f"{question_id}:{obj}"

        # Ensure nodes exist even if Gemini didn't list them in entities{}
        neo4j.upsert_node(database, sid, stype, {**base, "label": subj})
        neo4j.upsert_node(database, oid, otype, {**base, "label": obj})
        neo4j.upsert_edge(database, sid, oid, pred, {**base, **extra})

    print(f"  [{database}] Stored {len(triples)} triples, "
          f"{len(entities)} entities  (topic={topic})")
    return topic


# ══════════════════════════════════════════════════════════
#  EVALUATION — queries both databases
# ══════════════════════════════════════════════════════════

def evaluate(neo4j: Neo4jConn, question_id: str) -> dict:
    """
    Reads schema KG from `ischema` and student KG from `istudent`,
    compares them, returns a scored report.
    """
    q = question_id

    def get_labels(db):
        rows = neo4j.run(
            "MATCH (n {question_id:$q}) "
            "WHERE NOT n:Answer AND NOT n:Question AND n.label IS NOT NULL "
            "RETURN n.label AS label",
            database=db, q=q,
        )
        return {r["label"] for r in rows}

    def get_rels(db):
        rows = neo4j.run(
            "MATCH (a {question_id:$q})-[r]->(b {question_id:$q}) "
            "WHERE NOT a:Answer AND NOT a:Question "
            "RETURN a.label AS s, type(r) AS p, b.label AS o",
            database=db, q=q,
        )
        return {(r["s"], r["p"], r["o"]) for r in rows}

    schema_labels  = get_labels(DB_SCHEMA)
    student_labels = get_labels(DB_STUDENT)
    schema_rels    = get_rels(DB_SCHEMA)
    student_rels   = get_rels(DB_STUDENT)

    def jaccard(a, b):
        return round(len(a & b) / len(a | b), 3) if (a | b) else 1.0

    node_j  = jaccard(schema_labels, student_labels)
    rel_j   = jaccard(schema_rels,   student_rels)
    score   = round((0.35 * node_j + 0.65 * rel_j) * 100, 1)

    missing_nodes = schema_labels  - student_labels
    extra_nodes   = student_labels - schema_labels
    missing_rels  = schema_rels    - student_rels
    wrong_rels    = student_rels   - schema_rels

    feedback = []
    if score >= 85:
        feedback.append("Excellent — closely matches schema.")
    elif score >= 60:
        feedback.append("Good attempt, some gaps found.")
    else:
        feedback.append("Significant gaps. Please review.")

    if missing_nodes:
        feedback.append(f"Missing concepts: {sorted(missing_nodes)[:8]}")
    if extra_nodes:
        feedback.append(f"Extra/wrong concepts: {sorted(extra_nodes)[:5]}")
    if missing_rels:
        feedback.append(f"Missing relations: {list(missing_rels)[:5]}")
    if wrong_rels:
        feedback.append(f"Wrong relations: {list(wrong_rels)[:5]}")

    return {
        "question_id":       q,
        "final_score":       score,
        "node_score":        round(node_j * 100, 1),
        "relation_score":    round(rel_j  * 100, 1),
        "missing_nodes":     list(missing_nodes)[:10],
        "extra_nodes":       list(extra_nodes)[:10],
        "missing_relations": [list(r) for r in list(missing_rels)[:5]],
        "wrong_relations":   [list(r) for r in list(wrong_rels)[:5]],
        "feedback":          feedback,
    }


# ══════════════════════════════════════════════════════════
#  NEO4J BROWSER QUERIES
# ══════════════════════════════════════════════════════════

def print_browser_queries(question_id: str):
    q = question_id
    sep = "=" * 55
    print(f"\n{sep}")
    print("  PASTE IN Neo4j BROWSER  (localhost:7474)")
    print(f"{sep}")

    print(f"\n-- Switch to ischema, then run:")
    print(f':use ischema')
    print(f'MATCH (n {{question_id:"{q}"}})-[r]->(m) RETURN n,r,m')

    print(f"\n-- Switch to istudent, then run:")
    print(f':use istudent')
    print(f'MATCH (n {{question_id:"{q}"}})-[r]->(m) RETURN n,r,m')

    print(f"\n-- Find missing nodes (run in ischema):")
    print(f':use ischema')
    print(f"""MATCH (s {{question_id:"{q}"}})
WHERE NOT s:Answer AND NOT s:Question
  AND NOT EXISTS {{
    MATCH (x {{question_id:"{q}", label:s.label}})
  }}
RETURN s.label AS missing, labels(s) AS type""")


# ══════════════════════════════════════════════════════════
#  MAIN PIPELINE
# ══════════════════════════════════════════════════════════

def run_pipeline(
    schema_text:    str,
    student_text:   str,
    image_path:     str | None = None,
    question_id:    str | None = None,
    clear_existing: bool = True,
) -> dict:
    qid = question_id or f"q_{uuid.uuid4().hex[:8]}"

    print(f"\n{'='*55}")
    print(f"  TOC KG PIPELINE  |  question = {qid}")
    print(f"  Schema DB  → {DB_SCHEMA}")
    print(f"  Student DB → {DB_STUDENT}")
    print(f"{'='*55}")

    neo4j  = Neo4jConn()
    client = get_gemini_client()

    if clear_existing:
        neo4j.clear_question(DB_SCHEMA,  qid)
        neo4j.clear_question(DB_STUDENT, qid)
        print(f"  Cleared existing data for question '{qid}'")

    # ── Schema → ischema ──────────────────────────────────────────────────────
    print(f"\n[1] Extracting schema KG → {DB_SCHEMA}...")
    schema_data = extract_triples(client, schema_text)
    topic = push_kg(neo4j, schema_data, DB_SCHEMA, qid)
    print(f"  Topic detected: {topic}")

    # ── Student → istudent ────────────────────────────────────────────────────
    print(f"\n[2] Extracting student KG → {DB_STUDENT}...")
    student_data = extract_triples(client, student_text, image_path)
    push_kg(neo4j, student_data, DB_STUDENT, qid)

    # ── Database summaries ────────────────────────────────────────────────────
    print("\n[3] Database summaries:")
    neo4j.summary(DB_SCHEMA)
    neo4j.summary(DB_STUDENT)

    # ── Evaluate ──────────────────────────────────────────────────────────────
    print("\n[4] Evaluating...")
    report = evaluate(neo4j, qid)

    print(f"\n  Final score   : {report['final_score']} / 100")
    print(f"  Node score    : {report['node_score']}")
    print(f"  Relation score: {report['relation_score']}")
    print("\n  Feedback:")
    for msg in report["feedback"]:
        print(f"    • {msg}")

    print_browser_queries(qid)
    neo4j.close()
    return report


# ══════════════════════════════════════════════════════════
#  EXAMPLES
# ══════════════════════════════════════════════════════════

if __name__ == "__main__":

    # dfa_schema = """
    # A Turing Machine (TM) is a mathematical model of computation consisting of an infinite tape, a tape head, and a state register. While the Deterministic Turing Machine (DTM) is the standard form, several variations exist:Multi-Tape Turing Machine: Features multiple tapes and heads that can move independently. While it can be faster for certain operations, it does not increase the class of computable languages.Non-Deterministic Turing Machine (NTM): Allows for multiple possible transitions for a single state-symbol pair. Any NTM can be simulated by a DTM, though potentially with exponential time complexity.Multi-Dimensional Turing Machine: Uses a grid-like tape (2D or higher) instead of a linear one.Universal Turing Machine (UTM): A TM capable of simulating any other TM when provided with its description and input.
    # """
    dfa_schema = """
    DFA with Q={q0,q1,q2,q3,q4,q5}, Sigma={0,1}, start=q0, F={q1,q2,q4}.
    Transitions: q0-0->q3, q0-1->q1, q1-0->q2, q1-1->q4,
    q3-0->q0, q3-1->q4, q4-0->q5, q4-1->q2, q2-0->q2, q2-1->q5,
    q5-0->q2, q5-1->q2.
    """

    # dfa_student = """
    # There are many types of Turing Machiness that we studied in class. First, the Deterministic one is the basic one where the head only moves in one direction. Then there is the Multi-Tape machine, which has extra tapes. This makes it more powerful than a normal machine because it can solve problems that a single tape machine can't solve at all.There is also the Non-Deterministic Turing Machine. In this one, the machine can be in two states at the exact same time. These are way better because they can solve NP problems in linear time, unlike the regular ones. Finally, the Universal Turing Machine is like a super-computer that is built out of hardware instead of math, and it can run any program you give it.
    # """
    dfa_student = """
    States q0-q5, start q0, final states q1 and q2.
    q0 on 0->q3, on 1->q1. q1 on 0->q2, on 1->q5 .
    q3 on 0->q0, on 1->q4. q4 on 0->q5, on 1->q2.
    q2 on 0->q2, on 1->q5. q5 on 0->q2, on 1->q2.
    """

    report = run_pipeline(
        schema_text  = dfa_schema,
        student_text = dfa_student,
        question_id  = "q1_dfa",
    )