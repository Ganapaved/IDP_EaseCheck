"""
math_evaluation.py — Mathematics KG Evaluation Engine
═══════════════════════════════════════════════════════
4-layer evaluation specifically designed for mathematics:

Layer 1 — Formula exact match
    Jaccard on normalized LaTeX strings.
    Handles minor whitespace / bracket differences.

Layer 2 — Symbolic equivalence  (SymPy)
    For each schema formula, checks whether any student formula
    is SYMBOLICALLY EQUAL via SymPy — catches x^2+y^2 == y^2+x^2,
    2*sin(x)*cos(x) == sin(2x), etc.

Layer 3 — Step sequence analysis
    Compares derivation step ORDER and COVERAGE.
    Checks: are all required steps present? Are they in correct order?
    Penalises skipped steps and wrong order.

Layer 4 — LLM judge  (Gemini)
    Reads both KGs + original LaTeX blocks.
    Gives per-concept, per-step scores with specific error messages.
    Handles conceptual errors that symbolic checking misses.

Weights (adapt by question type):
    "formula"     → (0.30, 0.35, 0.05, 0.30)
    "derivation"  → (0.15, 0.25, 0.30, 0.30)
    "text"        → (0.10, 0.15, 0.15, 0.60)
    "diagram"     → (0.15, 0.20, 0.15, 0.50)
    "mixed"       → (0.05, 0.20, 0.35, 0.40)

Install:
    pip install sympy sentence-transformers google-genai neo4j networkx numpy
"""

import os, json, re, time
from datetime import datetime, timezone

import numpy as np
import networkx as nx
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()

# ── optional imports with graceful fallback ───────────────────────────────────
try:
    from sympy.parsing.latex import parse_latex
    from sympy import simplify, sympify, SympifyError
    SYMPY_AVAILABLE = True
except ImportError:
    SYMPY_AVAILABLE = False
    print("[math_eval] sympy not available — symbolic layer will use string match")

try:
    from sentence_transformers import SentenceTransformer, util as st_util
    _embedder = None
    EMBEDDER_AVAILABLE = True
except ImportError:
    EMBEDDER_AVAILABLE = False
    print("[math_eval] sentence-transformers not available — semantic layer disabled")

from google import genai

# ══════════════════════════════════════════════════════════
#  CONFIG
# ══════════════════════════════════════════════════════════

NEO4J_URI      = os.getenv("NEO4J_URI",      "bolt://localhost:7687")
NEO4J_USER     = os.getenv("NEO4J_USER",     "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY2", "")
GEMINI_MODEL   = "gemini-3-flash-preview"

DB_SCHEMA  = "ischema"
DB_STUDENT = "istudent"

# (exact, symbolic, step_order, llm)
WEIGHTS = {
    "formula":    (0.05, 0.30, 0.25, 0.40),
    "derivation": (0.1, 0.20, 0.30, 0.40),
    "text":       (0.10, 0.15, 0.15, 0.60),
    "diagram":    (0.15, 0.20, 0.15, 0.50),
    "mixed":      (0.20, 0.25, 0.20, 0.35),
}


# ══════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════

def get_embedder():
    global _embedder
    if not EMBEDDER_AVAILABLE:
        return None
    if _embedder is None:
        print("  [Embed] Loading model...")
        _embedder = SentenceTransformer("all-MiniLM-L6-v2")
    return _embedder


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


def normalize_latex(s: str) -> str:
    """
    Canonical form of a LaTeX string.
    Removes formatting differences so \\frac{a}{b} == \\frac{ a }{ b }.
    """
    s = re.sub(r'^\$\$|\$\$$', '', s.strip()).strip()
    s = re.sub(r'^\$|\$$', '', s).strip()
    s = s.replace('\\left(', '(').replace('\\right)', ')')
    s = s.replace('\\left[', '[').replace('\\right]', ']')
    s = s.replace('\\left\\{', '{').replace('\\right\\}', '}')
    s = s.replace('\\,', ' ').replace('\\;', ' ').replace('\\:', ' ')
    s = re.sub(r'\s+', ' ', s).strip()
    return s


# ══════════════════════════════════════════════════════════
#  NEO4J FETCH LAYER
# ══════════════════════════════════════════════════════════

class MathNeo4jFetch:
    """Read-only Neo4j access for evaluation."""

    def __init__(self):
        self.driver = GraphDatabase.driver(
            NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    def close(self):
        self.driver.close()

    def run(self, cypher: str, database: str, **params):
        with self.driver.session(database=database) as s:
            return list(s.run(cypher, **params))

    # ── Fetch formula nodes ───────────────────────────────────────────────────
    def get_formulas(self, database: str, question_id: str) -> list[dict]:
        """Returns all Formula nodes with their latex property."""
        rows = self.run("""
            MATCH (n:Formula {question_id: $q})
            RETURN n.label AS label, n.latex AS latex,
                   n.latex_norm AS norm, n.order AS order
            ORDER BY n.order
        """, database=database, q=question_id)
        return [
            {
                "label": r["label"] or "",
                "latex": r["latex"] or r["label"] or "",
                "norm":  r["norm"]  or normalize_latex(r["label"] or ""),
                "order": r["order"] or 0,
            }
            for r in rows
        ]

    # ── Fetch step nodes ──────────────────────────────────────────────────────
    def get_steps(self, database: str, question_id: str) -> list[dict]:
        """Returns Step nodes in their derivation order."""
        rows = self.run("""
            MATCH (n:Step {question_id: $q})
            RETURN n.label AS label, n.content AS content, n.order AS order
            ORDER BY n.order
        """, database=database, q=question_id)
        return [
            {
                "label":   r["label"]   or "",
                "content": r["content"] or "",
                "order":   r["order"]   or 0,
            }
            for r in rows
        ]

    # ── Fetch concept nodes ───────────────────────────────────────────────────
    def get_concepts(self, database: str, question_id: str) -> list[dict]:
        rows = self.run("""
            MATCH (n {question_id: $q})
            WHERE NOT n:Answer AND NOT n:Question AND n.label IS NOT NULL
            RETURN n.label AS label, labels(n)[0] AS ntype,
                   properties(n) AS props
        """, database=database, q=question_id)
        return [
            {"label": r["label"], "type": r["ntype"], "props": dict(r["props"])}
            for r in rows
        ]

    # ── Fetch edges ───────────────────────────────────────────────────────────
    def get_edges(self, database: str, question_id: str) -> list[dict]:
        rows = self.run("""
            MATCH (a {question_id:$q})-[r]->(b {question_id:$q})
            WHERE NOT a:Answer AND NOT a:Question
              AND a.label IS NOT NULL AND b.label IS NOT NULL
            RETURN a.label AS subj, type(r) AS pred, b.label AS obj
        """, database=database, q=question_id)
        return [{"subj": r["subj"], "pred": r["pred"], "obj": r["obj"]}
                for r in rows]

    # ── Fetch content_type ────────────────────────────────────────────────────
    def get_content_type(self, database: str, question_id: str) -> str:
        rows = self.run(
            "MATCH (n:Answer {question_id:$q}) RETURN n.content_type AS ct",
            database=database, q=question_id)
        return rows[0]["ct"] if rows and rows[0]["ct"] else "formula"

    # ── Build networkx graph ──────────────────────────────────────────────────
    def build_nx(self, database: str, question_id: str) -> nx.DiGraph:
        G = nx.DiGraph()
        for n in self.get_concepts(database, question_id):
            G.add_node(n["label"], ntype=n["type"])
        for e in self.get_edges(database, question_id):
            G.add_edge(e["subj"], e["obj"], pred=e["pred"])
        return G


# ══════════════════════════════════════════════════════════
#  LAYER 1 — FORMULA EXACT MATCH
# ══════════════════════════════════════════════════════════

def layer1_formula_exact(
    schema_formulas: list[dict],
    student_formulas: list[dict],
) -> dict:
    """
    Compares sets of normalized LaTeX strings using Jaccard similarity.

    Also checks:
    - How many schema formulas are PRESENT in student (recall)
    - How many student formulas are NOT in schema (precision penalty)

    Why Jaccard and not just recall:
      A student who writes 20 correct formulas but also 20 wrong ones
      should not score 100%. Jaccard balances both sides.
    """
    sc_norms = {normalize_latex(f["latex"]) for f in schema_formulas
                if f["latex"].strip()}
    st_norms = {normalize_latex(f["latex"]) for f in student_formulas
                if f["latex"].strip()}

    if not sc_norms and not st_norms:
        return {"score": 100.0, "note": "no formulas in either KG"}
    if not sc_norms:
        return {"score": 0.0,  "note": "schema has no formulas"}

    intersection = sc_norms & st_norms
    union        = sc_norms | st_norms

    jaccard  = len(intersection) / len(union)
    recall   = len(intersection) / len(sc_norms)   # fraction of schema formulas covered
    precision = len(intersection) / len(st_norms) if st_norms else 0.0

    # F1-weighted: recall matters more than precision for exam marking
    f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

    # Final: 60% F1 + 40% Jaccard
    score = 0.60 * f1 + 0.40 * jaccard

    missing = sc_norms - st_norms
    extra   = st_norms - sc_norms

    return {
        "score":          round(score * 100, 2),
        "jaccard":        round(jaccard, 4),
        "recall":         round(recall,  4),
        "precision":      round(precision, 4),
        "f1":             round(f1, 4),
        "matched_count":  len(intersection),
        "schema_count":   len(sc_norms),
        "student_count":  len(st_norms),
        "missing_formulas": list(missing)[:6],
        "extra_formulas":   list(extra)[:4],
    }


# ══════════════════════════════════════════════════════════
#  LAYER 2 — SYMBOLIC EQUIVALENCE  (SymPy)
# ══════════════════════════════════════════════════════════

def _try_sympy_equiv(latex_a: str, latex_b: str) -> bool:
    """
    Returns True if two LaTeX expressions are symbolically equivalent.
    Falls back to normalized string match if SymPy fails.
    """
    if not SYMPY_AVAILABLE:
        return normalize_latex(latex_a) == normalize_latex(latex_b)

    try:
        ea = parse_latex(normalize_latex(latex_a))
        eb = parse_latex(normalize_latex(latex_b))
        diff = simplify(ea - eb)
        return diff == 0
    except Exception:
        # SymPy can't parse complex LaTeX — fallback to string
        return normalize_latex(latex_a) == normalize_latex(latex_b)


def layer2_symbolic(
    schema_formulas: list[dict],
    student_formulas: list[dict],
) -> dict:
    """
    For each schema formula, checks if ANY student formula is
    symbolically equivalent (not just textually equal).

    This catches:
      x^2 + y^2  ==  y^2 + x^2           (commutativity)
      2sin(x)cos(x)  ==  sin(2x)          (trig identity)
      \\frac{d}{dx}x^n  ==  nx^{n-1}      (derivative rule)
      \\int_a^b f dx = F(b)-F(a)          (FTC — if both sides present)
    """
    if not schema_formulas:
        return {"score": 100.0, "note": "no schema formulas to check"}
    if not student_formulas:
        return {"score": 0.0,   "note": "no student formulas"}

    sc_latex = [f["latex"] for f in schema_formulas if f["latex"].strip()]
    st_latex = [f["latex"] for f in student_formulas if f["latex"].strip()]

    matched      = []
    unmatched    = []
    equiv_pairs  = []

    for sc in sc_latex:
        found = False
        for st in st_latex:
            if _try_sympy_equiv(sc, st):
                matched.append(sc)
                equiv_pairs.append((sc, st))
                found = True
                break
        if not found:
            unmatched.append(sc)

    score = len(matched) / len(sc_latex) if sc_latex else 1.0

    return {
        "score":              round(score * 100, 2),
        "matched_count":      len(matched),
        "schema_count":       len(sc_latex),
        "equivalent_pairs":   [(a[:50], b[:50]) for a, b in equiv_pairs[:5]],
        "unmatched_formulas": unmatched[:5],
        "sympy_available":    SYMPY_AVAILABLE,
    }


# ══════════════════════════════════════════════════════════
#  LAYER 3 — STEP SEQUENCE ANALYSIS
# ══════════════════════════════════════════════════════════

def _lcs_length(seq_a: list, seq_b: list) -> int:
    """Longest Common Subsequence length — O(n*m)."""
    n, m = len(seq_a), len(seq_b)
    if n == 0 or m == 0:
        return 0
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            if seq_a[i-1] == seq_b[j-1]:
                dp[i][j] = dp[i-1][j-1] + 1
            else:
                dp[i][j] = max(dp[i-1][j], dp[i][j-1])
    return dp[n][m]


def _step_signature(step: dict) -> str:
    """
    Creates a comparable signature for a step.
    Extracts key tokens: LaTeX fragments + keywords.
    """
    content = step.get("content", "")
    # Extract all LaTeX fragments
    latex_frags = re.findall(r'\$\$?(.+?)\$\$?', content, re.DOTALL)
    # Key math keywords
    keywords = re.findall(
        r'\b(integral|derivative|limit|sum|matrix|substitute|simplify|'
        r'factor|expand|differentiate|integrate|evaluate|solve|apply|'
        r'let|assume|given|therefore|hence|thus|proof|qed)\b',
        content, re.IGNORECASE
    )
    sig = " ".join(latex_frags[:3] + keywords[:3])
    return normalize_latex(sig) if sig.strip() else f"step_{step.get('order', 0)}"


def layer3_step_sequence(
    schema_steps: list[dict],
    student_steps: list[dict],
) -> dict:
    """
    Evaluates derivation step coverage and order.

    Three sub-scores:
    1. Coverage  : what fraction of schema steps are present in student
    2. Order     : LCS / len(schema) — are present steps in right order
    3. Completeness : penalises if student has far fewer steps than schema

    Missing a step in the middle of a derivation is penalised more
    than missing the last step (partial credit logic).
    """
    if not schema_steps:
        # No steps in schema — cannot evaluate step order
        return {
            "score":      100.0 if not student_steps else 85.0,
            "note":       "no steps in schema KG",
            "coverage":   1.0,
            "order_score": 1.0,
        }

    sc_sigs = [_step_signature(s) for s in sorted(schema_steps,
                                                    key=lambda x: x.get("order", 0))]
    st_sigs = [_step_signature(s) for s in sorted(student_steps,
                                                    key=lambda x: x.get("order", 0))]

    if not st_sigs:
        return {
            "score":         0.0,
            "coverage":      0.0,
            "order_score":   0.0,
            "missing_steps": len(sc_sigs),
            "student_steps": 0,
            "schema_steps":  len(sc_sigs),
            "note":          "no steps found in student answer",
        }

    # ── Coverage: how many schema step signatures appear in student ───────────
    sc_set = set(sc_sigs)
    st_set = set(st_sigs)
    covered = sc_set & st_set
    coverage = len(covered) / len(sc_set) if sc_set else 1.0

    # ── Order: LCS of step signatures ────────────────────────────────────────
    lcs    = _lcs_length(sc_sigs, st_sigs)
    order_score = lcs / len(sc_sigs) if sc_sigs else 1.0

    # ── Completeness: penalise if student wrote far fewer steps ──────────────
    completeness = min(1.0, len(st_sigs) / max(len(sc_sigs), 1))

    # ── Missing step positions (which steps were skipped) ─────────────────────
    missing_indices = [
        i + 1 for i, sig in enumerate(sc_sigs) if sig not in st_set
    ]

    # Weighted: order matters most for derivations
    score = 0.40 * coverage + 0.40 * order_score + 0.20 * completeness

    return {
        "score":           round(score * 100, 2),
        "coverage":        round(coverage, 4),
        "order_score":     round(order_score, 4),
        "completeness":    round(completeness, 4),
        "schema_steps":    len(sc_sigs),
        "student_steps":   len(st_sigs),
        "lcs_length":      lcs,
        "missing_at_positions": missing_indices[:8],
    }


# ══════════════════════════════════════════════════════════
#  LAYER 4 — LLM-AS-JUDGE  (Gemini)
# ══════════════════════════════════════════════════════════

MATH_JUDGE_PROMPT = """
You are an expert mathematics examiner.

Compare the STUDENT answer against the SCHEMA (correct answer) for a mathematics question.

SCHEMA KG — correct answer:
Formulas (LaTeX): {schema_formulas}
Steps: {schema_steps}
Concepts: {schema_concepts}
Variables: {schema_variables}

STUDENT KG — student answer:
Formulas (LaTeX): {student_formulas}
Steps: {student_steps}
Concepts: {student_concepts}
Variables: {student_variables}

Score the student out of 100 on these dimensions:

1. Correct formulas and expressions written    [25 marks]
   - Are the right formulas present?
   - Minor notation differences (e.g. dx vs \\,dx) should NOT be penalised.
   - Wrong formulas must be penalised.

2. Correctness of each derivation step         [35 marks]
   - Are steps logically valid?
   - Are intermediate steps correct even if final answer differs?
   - Award partial credit for partially correct steps.

3. Correct application of theorems / rules     [20 marks]
   - Did the student correctly identify and apply the right theorem?
   - E.g. integration by parts, chain rule, L'Hopital, etc.

4. Variable definitions and conditions         [10 marks]
   - Are variables correctly defined with right domain?
   - Are boundary conditions / constraints stated?

5. Conceptual understanding                    [10 marks]
   - Does the student understand WHY each step is taken?
   - Is the explanation logically coherent?

Rules:
  - Do NOT penalise for equivalent but differently written expressions.
  - DO penalise for wrong signs, wrong bounds, wrong operations.
  - Award partial credit for correct approach with arithmetic errors.
  - Return ONLY valid JSON, no markdown, no explanation outside JSON.

Required JSON:
{{
  "total_score": 78,
  "dimensions": {{
    "formulas":     {{"score": 20, "max": 25, "errors": ["..."], "notes": "..."}},
    "steps":        {{"score": 28, "max": 35, "errors": ["..."], "notes": "..."}},
    "theorems":     {{"score": 15, "max": 20, "errors": ["..."], "notes": "..."}},
    "variables":    {{"score":  8, "max": 10, "errors": [], "notes": "..."}},
    "concepts":     {{"score":  7, "max": 10, "errors": [], "notes": "..."}}
  }},
  "correct_steps": ["Step 1 is correct", "..."],
  "wrong_steps":   ["Step 3 has wrong sign", "..."],
  "missing":       ["Did not apply integration by parts", "..."],
  "overall_feedback": "..."
}}
"""


def layer4_llm_judge(
    client,
    schema_data: dict,
    student_data: dict,
) -> dict:
    """
    Sends both KGs to Gemini with math-specific rubric.
    schema_data / student_data are dicts with keys:
      formulas, steps, concepts, variables
    """
    def fmt_formulas(fmts):
        return "\n".join([f"  [{i+1}] {f['latex']}"
                          for i, f in enumerate(fmts[:12])]) or "  (none)"

    def fmt_steps(steps):
        return "\n".join([f"  Step {s['order']}: {s['content'][:120]}"
                          for s in steps[:10]]) or "  (none)"

    def fmt_concepts(concepts):
        return ", ".join([c["label"] for c in concepts[:15]]) or "(none)"

    def fmt_vars(variables):
        return "\n".join([f"  {k} = {v}"
                          for k, v in variables.items()]) or "  (none)"

    prompt = MATH_JUDGE_PROMPT.format(
        schema_formulas   = fmt_formulas(schema_data.get("formulas",  [])),
        schema_steps      = fmt_steps(schema_data.get("steps",       [])),
        schema_concepts   = fmt_concepts(schema_data.get("concepts",  [])),
        schema_variables  = fmt_vars(schema_data.get("variables",    {})),
        student_formulas  = fmt_formulas(student_data.get("formulas", [])),
        student_steps     = fmt_steps(student_data.get("steps",      [])),
        student_concepts  = fmt_concepts(student_data.get("concepts", [])),
        student_variables = fmt_vars(student_data.get("variables",   {})),
    )

    print("  [Gemini] Running math LLM judge...")
    try:
        raw     = call_gemini(client, prompt)
        cleaned = re.sub(r"```(?:json)?|```", "", raw).strip()
        result  = json.loads(cleaned)
        return {
            "score":            round(float(result.get("total_score", 0)), 2),
            "dimensions":       result.get("dimensions",        {}),
            "correct_steps":    result.get("correct_steps",     []),
            "wrong_steps":      result.get("wrong_steps",       []),
            "missing":          result.get("missing",           []),
            "overall_feedback": result.get("overall_feedback",  ""),
        }
    except Exception as e:
        print(f"  [Gemini] Judge failed: {e}")
        return {
            "score": 0.0, "error": str(e),
            "dimensions": {}, "overall_feedback": "LLM judge unavailable",
            "correct_steps": [], "wrong_steps": [], "missing": [],
        }


# ══════════════════════════════════════════════════════════
#  COMBINE SCORES
# ══════════════════════════════════════════════════════════

def combine_math_scores(
    l1: dict,
    l2: dict,
    l3: dict,
    l4: dict,
    content_type: str    = "formula",
    schema_formula_count: int = 999,
) -> dict:
    """
    Weighted combination of all four layers.

    Sparse schema adjustment:
      If schema has < 2 formulas, L1 and L2 are unreliable.
      Weight shifts to L4 (LLM judge).
    """
    w1, w2, w3, w4 = WEIGHTS.get(content_type, WEIGHTS["formula"])

    # Sparse schema adjustment
    if schema_formula_count < 2:
        shift = (w1 + w2) * 0.5
        w1   *= 0.5
        w2   *= 0.5
        w4   += shift
        total = w1 + w2 + w3 + w4
        w1, w2, w3, w4 = w1/total, w2/total, w3/total, w4/total

    final = (w1 * l1["score"] +
             w2 * l2["score"] +
             w3 * l3["score"] +
             w4 * l4["score"])
    
    final = final *0.05

    # ── Build feedback ────────────────────────────────────────────────────────
    feedback = []

    if final >= 85 * 0.05:
        feedback.append("Excellent answer — well-structured and mathematically correct.")
    elif final >= 70 *0.05:
        feedback.append("Good answer with minor errors.")
    elif final >= 50 *0.05:
        feedback.append("Partial credit. Key steps or formulas are missing or wrong.")
    else:
        feedback.append("Significant mathematical errors. Please review.")

    # Layer 1 feedback
    if l1.get("missing_formulas"):
        feedback.append(f"Missing formulas: {l1['missing_formulas'][:3]}")
    if l1.get("extra_formulas"):
        feedback.append(f"Incorrect/extra formulas written: {l1['extra_formulas'][:2]}")

    # Layer 2 feedback
    if l2.get("unmatched_formulas"):
        feedback.append(
            f"These schema formulas could not be matched symbolically: "
            f"{l2['unmatched_formulas'][:3]}"
        )

    # Layer 3 feedback
    if l3.get("missing_at_positions"):
        feedback.append(
            f"Steps missing at positions: {l3['missing_at_positions'][:5]}"
        )
    if l3.get("order_score", 1.0) < 0.6:
        feedback.append("Derivation steps are present but in wrong order.")

    # Layer 4 feedback (LLM specifics)
    for ws in l4.get("wrong_steps", [])[:3]:
        feedback.append(f"Step error: {ws}")
    for ms in l4.get("missing", [])[:2]:
        feedback.append(f"Missing: {ms}")

    return {
        "final_score":   round(final, 2),
        "content_type":  content_type,
        "weights": {
            "formula_exact": round(w1, 3),
            "symbolic":      round(w2, 3),
            "step_order":    round(w3, 3),
            "llm_judge":     round(w4, 3),
        },
        "layer_scores": {
            "formula_exact": l1["score"],
            "symbolic":      l2["score"],
            "step_order":    l3["score"],
            "llm_judge":     l4["score"],
        },
        "layer_details": {
            "formula_exact": l1,
            "symbolic":      l2,
            "step_order":    l3,
            "llm_judge":     l4,
        },
        "feedback":         feedback,
        "correct_steps":    l4.get("correct_steps",    []),
        "wrong_steps":      l4.get("wrong_steps",      []),
        "llm_feedback":     l4.get("overall_feedback", ""),
    }


# ══════════════════════════════════════════════════════════
#  MAIN EVALUATION ENTRY POINT
# ══════════════════════════════════════════════════════════

def evaluate_math(
    question_id:  str,
    student_qid:  str | None = None,
    skip_llm:     bool = False,
) -> dict:
    """
    Full 4-layer math evaluation.

    Reads:
      imath_schema  → question_id
      imath_student → student_qid  (default: same as question_id)

    Returns evaluation report dict.
    """
    neo4j  = MathNeo4jFetch()
    client = get_gemini_client()
    s_qid  = student_qid or question_id

    content_type = neo4j.get_content_type(DB_SCHEMA, question_id)

    print(f"\n{'='*55}")
    print(f"  MATH EVAL  |  schema={question_id}  "
          f"student={s_qid}  type={content_type}")
    print(f"{'='*55}")

    # ── Fetch from Neo4j ──────────────────────────────────────────────────────
    print("\n[Fetch] Loading math KGs from Neo4j...")

    sc_formulas  = neo4j.get_formulas(DB_SCHEMA,  question_id)
    sc_steps     = neo4j.get_steps(DB_SCHEMA,     question_id)
    sc_concepts  = neo4j.get_concepts(DB_SCHEMA,  question_id)
    sc_edges     = neo4j.get_edges(DB_SCHEMA,     question_id)

    st_formulas  = neo4j.get_formulas(DB_STUDENT, s_qid)
    st_steps     = neo4j.get_steps(DB_STUDENT,    s_qid)
    st_concepts  = neo4j.get_concepts(DB_STUDENT, s_qid)
    st_edges     = neo4j.get_edges(DB_STUDENT,    s_qid)

    # Extract variable dicts from concept props
    sc_vars = {
        c["label"]: c["props"].get("definition", "")
        for c in sc_concepts if c["type"] == "Variable"
    }
    st_vars = {
        c["label"]: c["props"].get("definition", "")
        for c in st_concepts if c["type"] == "Variable"
    }

    print(f"  Schema  : {len(sc_formulas)} formulas, {len(sc_steps)} steps, "
          f"{len(sc_concepts)} concepts")
    print(f"  Student : {len(st_formulas)} formulas, {len(st_steps)} steps, "
          f"{len(st_concepts)} concepts")

    # ── Layer 1 — formula exact ───────────────────────────────────────────────
    print("\n[L1] Formula exact match...")
    l1 = layer1_formula_exact(sc_formulas, st_formulas)
    print(f"  Score: {l1['score']}  "
          f"(recall={l1['recall']:.3f}  precision={l1.get('precision', 0):.3f})")

    # ── Layer 2 — symbolic equivalence ───────────────────────────────────────
    print("\n[L2] Symbolic equivalence (SymPy)...")
    l2 = layer2_symbolic(sc_formulas, st_formulas)
    print(f"  Score: {l2['score']}  "
          f"({l2['matched_count']}/{l2['schema_count']} symbolically matched)")

    # ── Layer 3 — step sequence ───────────────────────────────────────────────
    print("\n[L3] Step sequence analysis...")
    l3 = layer3_step_sequence(sc_steps, st_steps)
    print(f"  Score: {l3['score']}  "
          f"coverage={l3.get('coverage', 0):.3f}  "
          f"order={l3.get('order_score', 0):.3f}")

    # ── Layer 4 — LLM judge ───────────────────────────────────────────────────
    if skip_llm:
        print("\n[L4] LLM judge skipped.")
        l4 = {"score": 0.0, "overall_feedback": "Skipped",
              "dimensions": {}, "correct_steps": [],
              "wrong_steps": [], "missing": []}
    else:
        print("\n[L4] LLM math judge...")
        l4 = layer4_llm_judge(
            client,
            schema_data  = {"formulas": sc_formulas, "steps": sc_steps,
                             "concepts": sc_concepts, "variables": sc_vars},
            student_data = {"formulas": st_formulas, "steps": st_steps,
                            "concepts": st_concepts, "variables": st_vars},
        )
        print(f"  Score: {l4['score']}")

    # ── Combine ───────────────────────────────────────────────────────────────
    report = combine_math_scores(
        l1, l2, l3, l4,
        content_type         = content_type,
        schema_formula_count = len(sc_formulas),
    )

    neo4j.close()

    # ── Print summary ─────────────────────────────────────────────────────────
    print(f"\n{'='*55}  RESULT")
    print(f"  Final score  : {report['final_score']} / 100")
    print(f"  Layer scores : {report['layer_scores']}")
    print(f"  Weights used : {report['weights']}")
    print("\n  Feedback:")
    for msg in report["feedback"]:
        print(f"    • {msg}")
    if report.get("correct_steps"):
        print(f"\n  Correct steps:")
        for cs in report["correct_steps"][:3]:
            print(f"    ✓ {cs}")
    if report.get("wrong_steps"):
        print(f"\n  Wrong steps:")
        for ws in report["wrong_steps"][:3]:
            print(f"    ✗ {ws}")
    if report["llm_feedback"]:
        print(f"\n  LLM: {report['llm_feedback']}")

    # Save
    out = f"math_eval_{question_id}_{datetime.now(timezone.utc).strftime('%H%M%S')}.json"
    with open(out, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\n  Report saved → {out}")

    return report


# ══════════════════════════════════════════════════════════
#  STANDALONE TEST
# ══════════════════════════════════════════════════════════

if __name__ == "__main__":
    report = evaluate_math(
        question_id  = "q1_integration",
        student_qid  = "q1_integration_STU001",
        skip_llm     = False,
    )