"""
Layer 1 : Exact match          (Jaccard on nodes + triples)
Layer 2 : Semantic similarity  (sentence-transformer embeddings)
Layer 3 : Graph structure      (WL kernel + Graph Edit Distance)
Layer 4 : LLM-as-judge         (Gemini reasons over both KGs)

Final score = weighted combination, weights shift by question_type.py
"""

import os, json, re, time
from datetime import datetime, timezone

import numpy as np
import networkx as nx
from neo4j import GraphDatabase
from sentence_transformers import SentenceTransformer, util as st_util
from google import genai
from dotenv import load_dotenv
load_dotenv()



NEO4J_URI      = os.getenv("NEO4J_URI",      "bolt://localhost:7687")
NEO4J_USER     = os.getenv("NEO4J_USER",     "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL   = "gemini-3-flash-preview"

DB_SCHEMA  = "ischema"
DB_STUDENT = "istudent"


WEIGHTS = {
    "diagram":      (0.25, 0.15, 0.35, 0.25),
    "text":         (0.10, 0.35, 0.15, 0.40),
    "diagram+text": (0.20, 0.25, 0.25, 0.30),
}

_embedder = None   # lazy-loaded once




def get_embedder() -> SentenceTransformer:
    global _embedder
    if _embedder is None:
        print("  [Embed] Loading sentence-transformer model...")
        _embedder = SentenceTransformer("all-MiniLM-L6-v2")
    return _embedder


def get_gemini_client() -> genai.Client:
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY env var not set")
    return genai.Client(api_key=GEMINI_API_KEY)


def call_gemini(client: genai.Client, prompt: str, max_retries: int = 4) -> str:
    for attempt in range(max_retries):
        try:
            r = client.models.generate_content(model=GEMINI_MODEL, contents=[prompt])
            return r.text.strip()
        except Exception as e:
            if "429" in str(e) or "quota" in str(e).lower():
                wait = (2 ** attempt) * 5
                print(f"  [Gemini] Rate limited — retrying in {wait}s...")
                time.sleep(wait)
            else:
                raise
    raise RuntimeError("Gemini failed after max retries")



class Neo4jConn:
    def __init__(self):
        self.driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    def close(self):
        self.driver.close()

    def run(self, cypher: str, database: str, **params):
        with self.driver.session(database=database) as s:
            return list(s.run(cypher, **params))

    def get_nodes(self, database: str, question_id: str) -> list[dict]:
        """Returns all content nodes (excludes Answer/Question root nodes)."""
        rows = self.run("""
            MATCH (n {question_id: $q})
            WHERE NOT n:Answer AND NOT n:Question
              AND n.label IS NOT NULL
            RETURN n.label AS label,
                   labels(n)[0] AS node_type,
                   properties(n) AS props
        """, database=database, q=question_id)
        return [{"label": r["label"],
                 "node_type": r["node_type"],
                 "props": dict(r["props"])} for r in rows]

    def get_edges(self, database: str, question_id: str) -> list[dict]:
        """Returns all content edges as (subject_label, predicate, object_label)."""
        rows = self.run("""
            MATCH (a {question_id: $q})-[r]->(b {question_id: $q})
            WHERE NOT a:Answer AND NOT a:Question
              AND a.label IS NOT NULL AND b.label IS NOT NULL
            RETURN a.label AS subj, type(r) AS pred, b.label AS obj,
                   properties(r) AS props
        """, database=database, q=question_id)
        return [{"subj": r["subj"], "pred": r["pred"],
                 "obj": r["obj"], "props": dict(r["props"])} for r in rows]

    def build_nx_graph(self, database: str, question_id: str) -> nx.DiGraph:
        """Builds a NetworkX DiGraph from Neo4j data for graph algorithms."""
        G = nx.DiGraph()
        for n in self.get_nodes(database, question_id):
            G.add_node(n["label"], node_type=n["node_type"])
        for e in self.get_edges(database, question_id):
            G.add_edge(e["subj"], e["obj"],
                       pred=e["pred"],
                       label=e["pred"])
        return G
    
    def get_content_type(self, database: str, question_id: str) -> str:
        """Retrieve the content_type stored on the Answer node."""
        rows = self.run("""
            MATCH (n:Answer {question_id: $q})
            RETURN n.content_type AS ct
        """, database=database, q=question_id)
        if rows and rows[0]["ct"]:
            return rows[0]["ct"]
        return "text"   # safe defaul




def layer1_exact_match(
    schema_nodes: list[dict],
    student_nodes: list[dict],
    schema_edges: list[dict],
    student_edges: list[dict],
) -> dict:
    """
    Jaccard similarity on:
      - node label sets
      - edge triple sets  (subj, pred, obj)
    Node score weighted 35%, edge score 65%
    (transitions matter more than just naming states).
    """
    sc_labels = {n["label"] for n in schema_nodes}
    st_labels = {n["label"] for n in student_nodes}

    sc_triples = {(e["subj"], e["pred"], e["obj"]) for e in schema_edges}
    st_triples = {(e["subj"], e["pred"], e["obj"]) for e in student_edges}

    def jaccard(a: set, b: set) -> float:
        return len(a & b) / len(a | b) if (a | b) else 1.0

    node_j  = jaccard(sc_labels, st_labels)
    edge_j  = jaccard(sc_triples, st_triples)
    score   = 0.35 * node_j + 0.65 * edge_j

    return {
        "score":           round(score * 100, 2),
        "node_jaccard":    round(node_j, 4),
        "edge_jaccard":    round(edge_j, 4),
        "missing_nodes":   sorted(sc_labels - st_labels),
        "extra_nodes":     sorted(st_labels - sc_labels),
        "missing_edges":   [list(t) for t in sc_triples - st_triples][:8],
        "wrong_edges":     [list(t) for t in st_triples - sc_triples][:8],
    }




def layer2_semantic(
    schema_nodes: list[dict],
    student_nodes: list[dict],
    schema_edges: list[dict],
    student_edges: list[dict],
) -> dict:
    """
    Embeds node labels and edge labels with sentence-transformers.
    Uses bipartite best-match: for each schema item, find the
    highest-cosine student item. Averages those best scores.

    This handles synonyms:
      "final state" ↔ "accepting state"  → high cosine similarity
      "is_final"    ↔ "is_accepting"     → high cosine similarity
    """
    embedder = get_embedder()

    def best_match_score(schema_texts: list[str], student_texts: list[str]) -> float:
        if not schema_texts or not student_texts:
            return 0.0
        sc_emb = embedder.encode(schema_texts, convert_to_tensor=True)
        st_emb = embedder.encode(student_texts, convert_to_tensor=True)
        # cosine_scores[i][j] = similarity between schema[i] and student[j]
        cosine_scores = st_util.cos_sim(sc_emb, st_emb)
        # For each schema item, take best match
        best = cosine_scores.max(dim=1).values.tolist()
        return float(np.mean(best))

    # Node label similarity
    sc_node_labels = [n["label"] for n in schema_nodes]
    st_node_labels = [n["label"] for n in student_nodes]
    node_sim = best_match_score(sc_node_labels, st_node_labels)

    # Edge label similarity (predicate strings)
    sc_edge_labels = [f"{e['subj']} {e['pred']} {e['obj']}" for e in schema_edges]
    st_edge_labels = [f"{e['subj']} {e['pred']} {e['obj']}" for e in student_edges]
    edge_sim = best_match_score(sc_edge_labels, st_edge_labels)

    # Also embed node_type labels for type-level similarity
    sc_types = [n["node_type"] for n in schema_nodes]
    st_types = [n["node_type"] for n in student_nodes]
    type_sim = best_match_score(sc_types, st_types) if sc_types and st_types else 1.0

    score = 0.35 * node_sim + 0.50 * edge_sim + 0.15 * type_sim

    return {
        "score":              round(score * 100, 2),
        "node_similarity":    round(node_sim, 4),
        "edge_similarity":    round(edge_sim, 4),
        "type_similarity":    round(type_sim, 4),
    }




def _wl_hash(G: nx.DiGraph, iterations: int = 3) -> dict[str, str]:
    """
    Weisfeiler-Lehman node hashing.
    Each node's hash encodes its label + its neighbors' labels (iteratively).
    Nodes with the same WL hash have the same local neighborhood structure.
    """
    # Initial labels from node attributes
    labels = {n: str(G.nodes[n].get("node_type", n)) for n in G.nodes()}

    for _ in range(iterations):
        new_labels = {}
        for node in G.nodes():
            # Collect neighbor labels (both in and out for directed)
            neighbor_labels = sorted(
                [labels[nb] for nb in G.predecessors(node)] +
                [labels[nb] for nb in G.successors(node)]
            )
            # Hash: own label + sorted neighbor labels + edge predicates
            out_preds = sorted(G[node][nb].get("pred", "") for nb in G.successors(node))
            combined  = labels[node] + "|" + ",".join(neighbor_labels) + "|" + ",".join(out_preds)
            new_labels[node] = str(hash(combined) % (10**9))
        labels = new_labels

    return labels


def _wl_kernel_score(G_schema: nx.DiGraph, G_student: nx.DiGraph) -> float:
    """
    WL subtree kernel score.
    Compares the multiset of WL hashes between schema and student graphs.
    More matching hashes = more similar local neighborhood structure.
    """
    sc_hashes = _wl_hash(G_schema)
    st_hashes = _wl_hash(G_student)

    sc_counts: dict[str, int] = {}
    st_counts: dict[str, int] = {}

    for h in sc_hashes.values():
        sc_counts[h] = sc_counts.get(h, 0) + 1
    for h in st_hashes.values():
        st_counts[h] = st_counts.get(h, 0) + 1

    # Intersection of multisets
    all_keys = set(sc_counts) | set(st_counts)
    intersection = sum(min(sc_counts.get(k, 0), st_counts.get(k, 0)) for k in all_keys)
    union        = sum(max(sc_counts.get(k, 0), st_counts.get(k, 0)) for k in all_keys)

    return intersection / union if union > 0 else 1.0


def _ged_score(G_schema: nx.DiGraph, G_student: nx.DiGraph, timeout: int = 8) -> float:
    """
    Approximate Graph Edit Distance.
    Normalized: score = 1 - GED / max_possible_GED
    Falls back to node/edge count diff if GED times out.
    """
    try:
        ged_gen = nx.optimize_graph_edit_distance(
            G_schema.to_undirected(),
            G_student.to_undirected(),
            timeout=timeout,
        )
        ged = next(ged_gen)
    except Exception:
        # Fallback: simple structural diff
        ged = (abs(G_schema.number_of_nodes() - G_student.number_of_nodes()) +
               abs(G_schema.number_of_edges() - G_student.number_of_edges()))

    max_ged = G_schema.number_of_nodes() + G_schema.number_of_edges()
    if max_ged == 0:
        return 1.0
    return max(0.0, 1.0 - ged / max_ged)


def _subgraph_coverage(G_schema: nx.DiGraph, G_student: nx.DiGraph) -> float:
    """
    What fraction of schema edges are covered by student edges
    (ignoring node name differences, matching by edge predicate patterns).
    Useful when student uses different state names but correct structure.
    """
    sc_preds = [G_schema[u][v].get("pred", "") for u, v in G_schema.edges()]
    st_preds = [G_student[u][v].get("pred", "") for u, v in G_student.edges()]

    if not sc_preds:
        return 1.0

    sc_set = {}
    for p in sc_preds:
        sc_set[p] = sc_set.get(p, 0) + 1
    st_set = {}
    for p in st_preds:
        st_set[p] = st_set.get(p, 0) + 1

    covered = sum(min(sc_set[p], st_set.get(p, 0)) for p in sc_set)
    return covered / sum(sc_set.values())


def layer3_graph_structure(
    G_schema: nx.DiGraph,
    G_student: nx.DiGraph,
) -> dict:
    """
    Combines three graph algorithms:
      - WL kernel   : neighborhood topology match
      - GED         : minimum edit operations
      - Subgraph coverage : edge predicate pattern coverage
    """
    if G_schema.number_of_nodes() == 0:
        return {"score": 0.0, "wl": 0.0, "ged": 0.0, "coverage": 0.0}

    wl       = _wl_kernel_score(G_schema, G_student)
    ged      = _ged_score(G_schema, G_student)
    coverage = _subgraph_coverage(G_schema, G_student)

    score = 0.40 * wl + 0.35 * ged + 0.25 * coverage

    return {
        "score":              round(score * 100, 2),
        "wl_kernel":          round(wl, 4),
        "ged_score":          round(ged, 4),
        "subgraph_coverage":  round(coverage, 4),
    }




LLM_JUDGE_PROMPT = """
You are an expert examiner for Theory of Computation (TOC) courses.

You are given two knowledge graphs extracted from exam answers:
  - SCHEMA KG  = the correct answer
  - STUDENT KG = the student's answer

Your job is to score the student answer out of 100.

SCHEMA KG:
{schema_kg}

STUDENT KG:
{student_kg}

Score on these dimensions (marks in brackets):
1. Correct entities / states / symbols identified        [20]
2. Correct start state and final states                  [20]
3. Correct transition function / production rules        [40]
4. Conceptual understanding (correct predicates/relations) [20]

For each dimension:
  - Give the score awarded
  - List specific errors found
  - Explain any deduction

Rules:
  - Penalise wrong transitions heavily (they change the language accepted)
  - Award partial credit for correct structure even if labels differ slightly
  - Do NOT hallucinate errors that are not evidenced in the KG data
  - Return ONLY valid JSON, no markdown, no prose outside the JSON

Required JSON schema:
{{
  "total_score": 85,
  "dimensions": {{
    "entities":     {{"score": 18, "max": 20, "errors": [], "notes": "..."}},
    "start_final":  {{"score": 16, "max": 20, "errors": ["q4 not marked final"], "notes": "..."}},
    "transitions":  {{"score": 32, "max": 40, "errors": ["q1 on 1 → q5 wrong, should be q4"], "notes": "..."}},
    "concepts":     {{"score": 19, "max": 20, "errors": [], "notes": "..."}}
  }},
  "overall_feedback": "Good attempt but one final state and one transition are wrong.",
  "strengths": ["Correct alphabet", "All states identified"],
  "weaknesses": ["Missed q4 as final state", "Wrong transition q1-1->q5"]
}}
"""


def layer4_llm_judge(
    client: genai.Client,
    schema_nodes: list[dict],
    schema_edges: list[dict],
    student_nodes: list[dict],
    student_edges: list[dict],
) -> dict:
    """
    Sends both KGs as compact JSON to Gemini and asks for a scored evaluation.
    Falls back gracefully if Gemini fails or returns invalid JSON.
    """
    def kg_summary(nodes, edges):
        return {
            "nodes": [{"label": n["label"], "type": n["node_type"],
                       "is_final": n["props"].get("is_final", False),
                       "is_start": n["props"].get("is_start", False)}
                      for n in nodes],
            "edges": [{"from": e["subj"], "relation": e["pred"], "to": e["obj"]}
                      for e in edges],
        }

    prompt = LLM_JUDGE_PROMPT.format(
        schema_kg  = json.dumps(kg_summary(schema_nodes, schema_edges),  indent=2),
        student_kg = json.dumps(kg_summary(student_nodes, student_edges), indent=2),
    )

    print("  [Gemini] Running LLM-as-judge evaluation...")
    try:
        raw     = call_gemini(client, prompt)
        cleaned = re.sub(r"```(?:json)?|```", "", raw).strip()
        result  = json.loads(cleaned)
        score   = float(result.get("total_score", 0))
        return {
            "score":            round(score, 2),
            "dimensions":       result.get("dimensions", {}),
            "overall_feedback": result.get("overall_feedback", ""),
            "strengths":        result.get("strengths", []),
            "weaknesses":       result.get("weaknesses", []),
        }
    except Exception as e:
        print(f"  [Gemini] Judge failed: {e}")
        return {"score": 0.0, "error": str(e),
                "dimensions": {}, "overall_feedback": "LLM judge unavailable"}




def combine_scores(
    l1: dict,
    l2: dict,
    l3: dict,
    l4: dict,
    question_type: str |None = None,
    schema_edge_count:int = 999
) -> dict:
    """
    Combines all four layer scores with question-type-specific weights.
    Produces a final 0-100 score and unified feedback.
    """
    w1, w2, w3, w4 = WEIGHTS.get(question_type, WEIGHTS["diagram+text"])

    if schema_edge_count < 3:
        shift = w3 * 0.6
        w3   -= shift
        w4   += shift * 0.7
        w2   += shift * 0.3
        total = w1 + w2 + w3 + w4
        w1, w2, w3, w4 = w1/total, w2/total, w3/total, w4/total

    final = (w1 * l1["score"] +
             w2 * l2["score"] +
             w3 * l3["score"] +
             w4 * l4["score"])

    # Collect all feedback into one list
    feedback = []

    if final >= 85:
        feedback.append("Excellent answer.")
    elif final >= 65:
        feedback.append("Good attempt with some errors.")
    elif final >= 45:
        feedback.append("Partial understanding shown.")
    else:
        feedback.append("Significant gaps — needs revision.")

    # Layer 1 specifics
    if l1["missing_nodes"]:
        feedback.append(f"Missing entities: {l1['missing_nodes'][:5]}")
    if l1["extra_nodes"]:
        feedback.append(f"Extra/incorrect entities: {l1['extra_nodes'][:5]}")
    if l1["missing_edges"]:
        feedback.append(f"Missing relations: {l1['missing_edges'][:3]}")
    if l1["wrong_edges"]:
        feedback.append(f"Wrong relations: {l1['wrong_edges'][:3]}")

    # Layer 2: low semantic sim means wrong concepts used
    if l2["score"] < 60:
        feedback.append("Concepts described using incorrect terminology.")

    # Layer 3: WL mismatch means topology is wrong
    if l3.get("wl_kernel", 1.0) < 0.5:
        feedback.append("Graph structure significantly differs from schema.")
    if l3.get("subgraph_coverage", 1.0) < 0.6:
        feedback.append("Many relation types are missing or incorrect.")

    # Layer 4: LLM specific feedback
    if l4.get("weaknesses"):
        feedback.extend(l4["weaknesses"][:3])

    return {
        "final_score":   round(final, 2),
        "question_type": question_type,
        "weights":       {"exact": w1, "semantic": w2, "graph": w3, "llm": w4},
        "layer_scores": {
            "exact_match":    l1["score"],
            "semantic":       l2["score"],
            "graph_structure": l3["score"],
            "llm_judge":      l4["score"],
        },
        "layer_details": {
            "exact_match":    l1,
            "semantic":       l2,
            "graph_structure": l3,
            "llm_judge":      l4,
        },
        "feedback":      feedback,
        "llm_feedback":  l4.get("overall_feedback", ""),
        "strengths":     l4.get("strengths", []),
    }




def evaluate(
    question_id:   str,
    student_qid:str | None = None,
    question_type: str | None=None,   # "diagram" | "text" | "diagram+text"
    skip_llm:      bool = False,           # set True to save API calls during testing
) -> dict:
    """
    Full 4-layer evaluation for a given question_id.
    Reads schema from `ischema` DB, student from `istudent` DB.
    """
    print(f"\n{'='*55}")
    print(f"  EVALUATING  |  question={question_id}  type={question_type}")
    print(f"{'='*55}")

    neo4j  = Neo4jConn()
    client = get_gemini_client()

    if question_type is None:
        question_type = neo4j.get_content_type(DB_SCHEMA, question_id)
        print(f"  [Eval] Auto-detected type from Neo4j: {question_type}")

    # ── Fetch from Neo4j ──────────────────────────────────────────────────────
    print("\n[Fetch] Loading KGs from Neo4j...")
    schema_nodes  = neo4j.get_nodes(DB_SCHEMA,  question_id)
    schema_edges  = neo4j.get_edges(DB_SCHEMA,  question_id)
    student_nodes = neo4j.get_nodes(DB_STUDENT, question_id)
    student_edges = neo4j.get_edges(DB_STUDENT, question_id)

    print(f"  Schema  : {len(schema_nodes)} nodes, {len(schema_edges)} edges")
    print(f"  Student : {len(student_nodes)} nodes, {len(student_edges)} edges")

    # ── Layer 1 ───────────────────────────────────────────────────────────────
    print("\n[L1] Exact match...")
    l1 = layer1_exact_match(schema_nodes, student_nodes, schema_edges, student_edges)
    print(f"  Score: {l1['score']}")

    # ── Layer 2 ───────────────────────────────────────────────────────────────
    print("\n[L2] Semantic similarity...")
    l2 = layer2_semantic(schema_nodes, student_nodes, schema_edges, student_edges)
    print(f"  Score: {l2['score']}")

    # ── Layer 3 ───────────────────────────────────────────────────────────────
    print("\n[L3] Graph structure (WL kernel + GED)...")
    G_schema  = neo4j.build_nx_graph(DB_SCHEMA,  question_id)   
    G_student = neo4j.build_nx_graph(DB_STUDENT, question_id)
    l3 = layer3_graph_structure(G_schema, G_student)
    print(f"  Score: {l3['score']}  "
          f"(WL={l3['wl_kernel']}, GED={l3['ged_score']}, "
          f"Coverage={l3['subgraph_coverage']})")

    # ── Layer 4 ───────────────────────────────────────────────────────────────
    if skip_llm:
        print("\n[L4] LLM judge skipped.")
        l4 = {"score": 0.0, "overall_feedback": "Skipped",
              "dimensions": {}, "strengths": [], "weaknesses": []}
        # Redistribute weight to other layers when LLM is skipped
        w1, w2, w3, _ = WEIGHTS.get(question_type, WEIGHTS["diagram+text"])
        total = w1 + w2 + w3
        adjusted = (w1/total, w2/total, w3/total, 0.0)
        # Temporarily override weights
        original = WEIGHTS[question_type]
        WEIGHTS[question_type] = adjusted
    else:
        print("\n[L4] LLM-as-judge...")
        l4 = layer4_llm_judge(client, schema_nodes, schema_edges,
                              student_nodes, student_edges)
        print(f"  Score: {l4['score']}")

   
    print("\n[Final] Combining scores...")
    report = combine_scores(l1, l2, l3, l4, question_type)

    if skip_llm:
        WEIGHTS[question_type] = original   # restore

    neo4j.close()

    # ── Print summary ───────────
    print(f"\n{'='*55}")
    print(f"  RESULT")
    print(f"{'='*55}")
    print(f"  Final score      : {report['final_score']} / 100")
    print(f"  Exact match      : {report['layer_scores']['exact_match']}")
    print(f"  Semantic         : {report['layer_scores']['semantic']}")
    print(f"  Graph structure  : {report['layer_scores']['graph_structure']}")
    print(f"  LLM judge        : {report['layer_scores']['llm_judge']}")
    print(f"\n  Weights used     : {report['weights']}")
    print(f"\n  Feedback:")
    for msg in report["feedback"]:
        print(f"    • {msg}")
    if report["llm_feedback"]:
        print(f"\n  LLM summary: {report['llm_feedback']}")
    if report["strengths"]:
        print(f"  Strengths: {report['strengths']}")

    # Save report
    out = f"eval_{question_id}_{datetime.now(timezone.utc).strftime('%H%M%S')}.json"
    with open(out, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\n  Report saved → {out}")

    return report



if __name__ == "__main__":

    # DFA question (schema + student already in Neo4j from previous pipeline)
    report1 = evaluate(
        question_id   = "q1_dfa",
        question_type = "diagram+text",
        skip_llm      = False,
    )

    # Text-only pumping lemma question
    report2 = evaluate(
        question_id   = "q2_pumping",
        question_type = "text",
        skip_llm      = False,
    )

    # Diagram-only question
    report3 = evaluate(
        question_id   = "q3_cfg",
        question_type = "diagram",
        skip_llm      = False,
    )