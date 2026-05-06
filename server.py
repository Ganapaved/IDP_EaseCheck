"""
server.py — TOC Exam Evaluation API  (stateless, no sessions)
══════════════════════════════════════════════════════════════
Routes:
  POST /schema/upload              → upload schema image/text → builds ischema KG
  POST /student/upload             → upload student image/text → builds istudent KG
  POST /evaluate/{question_id}     → run 4-layer evaluation for one student
  POST /evaluate/all               → batch evaluate list of students for a question
  GET  /results/{question_id}      → get all stored scores for a question

No session system. Every request is self-contained.
question_id and student_id are passed directly on every call.

Run:
  uvicorn server:app --reload --port 8000

Install:
  pip install fastapi uvicorn python-multipart aiofiles python-dotenv
"""

import os, json, re, shutil
from pathlib import Path
from datetime import datetime, timezone

import networkx as nx
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

import dfsm_extract as dfa_cv
import graph_create as kg
import evaluation   as eval_engine

# ── Upload folder ─────────────────────────────────────────────────────────────
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

# ── Lightweight in-memory results store ───────────────────────────────────────
# results[question_id][student_id] = report_dict
# Persists only until server restarts — fine for exam sessions
results: dict[str, dict] = {}

app = FastAPI(title="TOC Exam Evaluation API", version="3.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)


# ══════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════

def save_upload(file: UploadFile, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)
    return dest


# ══════════════════════════════════════════════════════════
#  HEALTH CHECK
# ══════════════════════════════════════════════════════════

@app.get("/")
def health():
    return {
        "status":  "running",
        "version": "3.0.0",
        "routes": {
            "1": "POST /schema/upload",
            "2": "POST /student/upload",
            "3": "POST /evaluate/{question_id}",
            "4": "POST /evaluate/all",
            "5": "GET  /results/{question_id}",
        },
    }


# ══════════════════════════════════════════════════════════
#  ROUTE 1 — UPLOAD SCHEMA
# ══════════════════════════════════════════════════════════

@app.post("/schema/upload")
async def upload_schema(
    question_id: str        = Form(..., description="e.g. q1"),
    image:       UploadFile = File(None, description="Scanned schema page (optional)"),
    extra_text:  str        = Form("",   description="Schema answer as text (optional)"),
):
    """
    Upload the correct answer (schema) for a question.

    Accepts image, text, or both — at least one required.
    Auto-detects content type: diagram / text / diagram+text.
    Stores KG in Neo4j ischema database under question_id.
    """
    if (not image or not image.filename) and not extra_text.strip():
        raise HTTPException(400, "Provide at least an image or extra_text.")

    # ── Save image if provided ────────────────────────────────────────────────
    img_path = None
    if image and image.filename:
        img_path = save_upload(
            image,
            UPLOAD_DIR / "schema" / f"{question_id}_{image.filename}",
        )

    print(f"\n[SERVER] Schema upload: question_id={question_id}")

    # ── Extract content ───────────────────────────────────────────────────────
    if img_path:
        extraction = dfa_cv.extract_from_page(
            image_path   = str(img_path),
            output_image = str(UPLOAD_DIR / "schema" /
                               f"{question_id}_annotated.png"),
            extra_text   = extra_text,
        )
        content_type  = extraction["content_type"]
        combined_text = extraction["combined_text"]
        has_diagram   = extraction.get("has_diagram", False)
    else:
        # Pure text — no image
        content_type  = "text"
        combined_text = extra_text.strip()
        has_diagram   = False

    if not combined_text.strip():
        raise HTTPException(400,
            "No content could be extracted. "
            "Check image quality or provide extra_text.")

    # ── Build KG in ischema ───────────────────────────────────────────────────
    neo4j  = kg.Neo4jConn()
    # client = kg.get_gemini_client()

    neo4j.clear_question(kg.DB_SCHEMA, question_id)

    schema_data = kg.extract_triples(
        combined_text,
        image_path   = str(img_path) if has_diagram else None,
        content_type = content_type,
    )
    topic = kg.push_kg(
        neo4j, schema_data, kg.DB_SCHEMA, question_id, content_type
    )
    neo4j.close()

    return {
        "status":        "schema_stored",
        "question_id":   question_id,
        "content_type":  content_type,
        "topic":         topic,
        "triples_count": len(schema_data.get("triples", [])),
        "next_step":     "POST /student/upload",
    }


# ══════════════════════════════════════════════════════════
#  ROUTE 2 — UPLOAD STUDENT ANSWER
# ══════════════════════════════════════════════════════════

@app.post("/student/upload")
async def upload_student(
    question_id: str        = Form(..., description="Same question_id as schema"),
    student_id:  str        = Form(..., description="Student roll number or ID"),
    image:       UploadFile = File(None, description="Scanned student answer page"),
    extra_text:  str        = Form("",   description="Student answer as text"),
):
    """
    Upload one student's answer for a question.

    Accepts image, text, or both — at least one required.
    Stores KG in Neo4j istudent database under {question_id}_{student_id}.
    """
    if (not image or not image.filename) and not extra_text.strip():
        raise HTTPException(400, "Provide at least an image or extra_text.")

    # ── Save image if provided ────────────────────────────────────────────────
    img_path = None
    if image and image.filename:
        img_path = save_upload(
            image,
            UPLOAD_DIR / "students" /
            f"{question_id}_{student_id}_{image.filename}",
        )

    print(f"\n[SERVER] Student upload: q={question_id} student={student_id}")

    # ── Extract content ───────────────────────────────────────────────────────
    if img_path:
        extraction = dfa_cv.extract_from_page(
            image_path   = str(img_path),
            output_image = str(UPLOAD_DIR / "students" /
                               f"{question_id}_{student_id}_annotated.png"),
            extra_text   = extra_text,
        )
        content_type  = extraction["content_type"]
        combined_text = extraction["combined_text"]
        has_diagram   = extraction.get("has_diagram", False)
    else:
        content_type  = "text"
        combined_text = extra_text.strip()
        has_diagram   = False

    # Namespaced ID — keeps multiple students separate in Neo4j
    neo4j_qid = f"{question_id}_{student_id}"

    neo4j  = kg.Neo4jConn()
    # client = kg.get_gemini_client()

    neo4j.clear_question(kg.DB_STUDENT, neo4j_qid)

    student_data = kg.extract_triples(
        combined_text,
        image_path   = str(img_path) if has_diagram else None,
        content_type = content_type,
    )
    topic = kg.push_kg(
        neo4j, student_data, kg.DB_STUDENT, neo4j_qid, content_type
    )
    neo4j.close()

    return {
        "status":        "student_kg_stored",
        "question_id":   question_id,
        "student_id":    student_id,
        "neo4j_qid":     neo4j_qid,
        "content_type":  content_type,
        "topic":         topic,
        "triples_count": len(student_data.get("triples", [])),
        "next_step":     f"POST /evaluate/{question_id}",
    }


# ══════════════════════════════════════════════════════════
#  ROUTE 3 — EVALUATE ONE STUDENT
# ══════════════════════════════════════════════════════════

@app.post("/evaluate/{question_id}")
def evaluate_one(
    question_id: str,
    student_id:  str  = Form(...),
    skip_llm:    bool = Form(False, description="Set True to skip Gemini judge"),
):
    """
    Run 4-layer evaluation for one student on one question.

    Reads schema from ischema  → question_id
    Reads student from istudent → question_id_student_id

    content_type is auto-read from Neo4j Answer node.
    Returns full scored report with per-layer breakdown and feedback.
    """
    neo4j_qid = f"{question_id}_{student_id}"

    report = _run_evaluation(
        schema_qid  = question_id,
        student_qid = neo4j_qid,
        skip_llm    = skip_llm,
    )

    # Cache in memory
    results.setdefault(question_id, {})[student_id] = report

    return {
        "question_id": question_id,
        "student_id":  student_id,
        "report":      report,
    }


# ══════════════════════════════════════════════════════════
#  ROUTE 4 — BATCH EVALUATE ALL STUDENTS FOR A QUESTION
# ══════════════════════════════════════════════════════════

@app.post("/evaluate/all")
def evaluate_all(
    question_id: str  = Form(...),
    student_ids: str  = Form(..., description="Comma-separated: STU001,STU002"),
    skip_llm:    bool = Form(False),
):
    """
    Batch evaluate multiple students for one question.

    Example body:
        question_id = "q1"
        student_ids = "STU001,STU002,STU003"
    """
    ids         = [s.strip() for s in student_ids.split(",")]
    all_reports = {}

    for student_id in ids:
        neo4j_qid = f"{question_id}_{student_id}"
        try:
            report = _run_evaluation(
                schema_qid  = question_id,
                student_qid = neo4j_qid,
                skip_llm    = skip_llm,
            )
            results.setdefault(question_id, {})[student_id] = report
            all_reports[student_id] = {
                "final_score":  report["final_score"],
                "layer_scores": report["layer_scores"],
                "feedback":     report["feedback"],
            }
        except Exception as e:
            all_reports[student_id] = {"error": str(e)}

    return {
        "question_id": question_id,
        "evaluated":   len([r for r in all_reports.values() if "error" not in r]),
        "failed":      len([r for r in all_reports.values() if "error"     in r]),
        "results":     all_reports,
    }


# ══════════════════════════════════════════════════════════
#  ROUTE 5 — GET RESULTS
# ══════════════════════════════════════════════════════════

@app.get("/results/{question_id}")
def get_results(question_id: str):
    """
    Get all stored evaluation results for a question.
    Results stay in memory until the server restarts.
    """
    q_results = results.get(question_id, {})
    if not q_results:
        raise HTTPException(404,
            f"No results for '{question_id}'. "
            f"Run POST /evaluate/{question_id} first.")

    return {
        "question_id":    question_id,
        "total_students": len(q_results),
        "students": {
            stu_id: {
                "final_score":  r.get("final_score"),
                "layer_scores": r.get("layer_scores"),
                "feedback":     r.get("feedback", []),
                "strengths":    r.get("strengths", []),
                "llm_feedback": r.get("llm_feedback", ""),
            }
            for stu_id, r in q_results.items()
        },
    }


# ══════════════════════════════════════════════════════════
#  INTERNAL — evaluation bridge
# ══════════════════════════════════════════════════════════

def _run_evaluation(
    schema_qid:  str,
    student_qid: str,
    skip_llm:    bool = False,
) -> dict:
    """
    Reads schema from ischema using schema_qid.
    Reads student from istudent using student_qid (namespaced).
    content_type is read automatically from Neo4j Answer node.
    """
    neo4j  = eval_engine.Neo4jConn()
    client = eval_engine.get_gemini_client()

    # Auto-read content_type stored during upload
    content_type  = neo4j.get_content_type(eval_engine.DB_SCHEMA, schema_qid)

    schema_nodes  = neo4j.get_nodes(eval_engine.DB_SCHEMA,  schema_qid)
    schema_edges  = neo4j.get_edges(eval_engine.DB_SCHEMA,  schema_qid)
    student_nodes = neo4j.get_nodes(eval_engine.DB_STUDENT, student_qid)
    student_edges = neo4j.get_edges(eval_engine.DB_STUDENT, student_qid)

    print(f"[EVAL] schema={schema_qid}  student={student_qid}  type={content_type}")
    print(f"[EVAL] Schema : {len(schema_nodes)} nodes, {len(schema_edges)} edges")
    print(f"[EVAL] Student: {len(student_nodes)} nodes, {len(student_edges)} edges")

    # Layer 1 — exact match
    l1 = eval_engine.layer1_exact_match(
        schema_nodes, student_nodes, schema_edges, student_edges)

    # Layer 2 — semantic similarity
    l2 = eval_engine.layer2_semantic(
        schema_nodes, student_nodes, schema_edges, student_edges)

    # Layer 3 — graph structure
    G_sc = nx.DiGraph()
    G_st = nx.DiGraph()
    for n in schema_nodes:
        G_sc.add_node(n["label"], node_type=n["node_type"])
    for e in schema_edges:
        G_sc.add_edge(e["subj"], e["obj"], pred=e["pred"])
    for n in student_nodes:
        G_st.add_node(n["label"], node_type=n["node_type"])
    for e in student_edges:
        G_st.add_edge(e["subj"], e["obj"], pred=e["pred"])

    l3 = eval_engine.layer3_graph_structure(G_sc, G_st)

    # Layer 4 — LLM judge
    l4 = (
        {"score": 0.0, "overall_feedback": "Skipped",
         "dimensions": {}, "strengths": [], "weaknesses": []}
        if skip_llm else
        eval_engine.layer4_llm_judge(
            client, schema_nodes, schema_edges,
            student_nodes, student_edges)
    )

    neo4j.close()

    return eval_engine.combine_scores(
        l1, l2, l3, l4,
        question_type     = content_type,
        schema_edge_count = len(schema_edges),
    )