"""
server.py — Unified Exam Evaluation API  (TOC + Mathematics)
═════════════════════════════════════════════════════════════
Single FastAPI server routing to two subject-specific pipelines:

  Subject: toc   → dfsm_extract + graph_create + evaluation
  Subject: math  → math_extract + math_graph   + math_evaluation

Workflow:
  Step 1 → POST /subject           : declare subject per question_id (toc/math)
  Step 2 → POST /schema/upload     : upload correct answer (image/text)
  Step 3 → POST /student/upload    : upload student answer (image/text)
  Step 4 → POST /evaluate/{qid}    : evaluate one student
           POST /evaluate/all      : batch evaluate list of students
  Step 5 → GET  /results/{qid}     : get all scores for a question
           GET  /subjects          : list all registered question subjects

Run:
    uvicorn server:app --reload --port 8000
"""

import os, json, re, shutil
from pathlib import Path
from datetime import datetime, timezone

import networkx as nx
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

# ── TOC pipeline modules ──────────────────────────────────────────────────────
import dfsm_extract as dfa_cv
import graph_create as kg
import evaluation   as eval_engine

# ── Math pipeline modules ─────────────────────────────────────────────────────
import math_extract    as mx
import math_graph      as mg
import math_evaluation as me

# ══════════════════════════════════════════════════════════
#  APP + STORES
# ══════════════════════════════════════════════════════════

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

# subject_map[question_id] = "toc" | "math"
subject_map: dict[str, str]  = {}
# results[question_id][student_id] = report_dict
results:     dict[str, dict] = {}

VALID_SUBJECTS = {"toc", "math"}

app = FastAPI(
    title       = "Exam Evaluation API — TOC + Mathematics",
    description = (
        "Unified evaluation server for two subjects.\n"
        "Step 1: POST /subject  →  declare subject (toc or math) per question.\n"
        "Step 2–5: upload schema, student, evaluate, get results."
    ),
    version = "4.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)


# ══════════════════════════════════════════════════════════
#  SHARED HELPER
# ══════════════════════════════════════════════════════════

def save_upload(file: UploadFile, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)
    return dest


def require_subject(question_id: str) -> str:
    """Return the subject for a question_id or raise HTTP 400."""
    subj = subject_map.get(question_id)
    if not subj:
        raise HTTPException(
            400,
            f"No subject declared for question '{question_id}'. "
            f"Call POST /subject with question_id and subject=toc|math first."
        )
    return subj


# ══════════════════════════════════════════════════════════
#  ROUTE — HEALTH CHECK
# ══════════════════════════════════════════════════════════

@app.get("/")
def health():
    return {
        "status":   "running",
        "version":  "4.0.0",
        "subjects": list(VALID_SUBJECTS),
        "workflow": {
            "1": "POST /subject           → register subject (toc | math)",
            "2": "POST /schema/upload     → upload correct answer",
            "3": "POST /student/upload    → upload student answer",
            "4": "POST /evaluate/{qid}    → evaluate one student",
            "4b": "POST /evaluate/all     → batch evaluate",
            "5": "GET  /results/{qid}     → get all scores",
            "6": "GET  /subjects          → list registered questions",
        },
    }


# ══════════════════════════════════════════════════════════
#  ROUTE 1 — DECLARE SUBJECT
# ══════════════════════════════════════════════════════════

@app.post("/subject")
def declare_subject(
    question_id: str = Form(..., description="e.g. q1  or  q2_integration"),
    subject:     str = Form(..., description="toc   or   math"),
):
    """
    Step 1 — Register which subject a question belongs to.

    Must be called before any upload or evaluation for that question.

      subject = toc  → Theory of Computation pipeline
                       (DFA, NFA, TM, CFG, pumping lemma, etc.)

      subject = math → Mathematics pipeline
                       (formulas, derivations, integration, matrices, etc.)
    """
    subject = subject.strip().lower()
    if subject not in VALID_SUBJECTS:
        raise HTTPException(
            400,
            f"Invalid subject '{subject}'. Valid choices: {sorted(VALID_SUBJECTS)}"
        )

    subject_map[question_id] = subject

    pipeline = (
        "dfsm_extract → graph_create → evaluation  (Neo4j: ischema / istudent)"
        if subject == "toc" else
        "math_extract → math_graph   → math_evaluation  (Neo4j: imath_schema / imath_student)"
    )

    return {
        "status":      "subject_registered",
        "question_id": question_id,
        "subject":     subject,
        "pipeline":    pipeline,
        "next_step":   f"POST /schema/upload  with question_id={question_id}",
    }


@app.get("/subjects")
def list_subjects():
    """List all registered question_id → subject mappings."""
    return {
        "total":      len(subject_map),
        "registered": subject_map,
    }


# ══════════════════════════════════════════════════════════
#  ROUTE 2 — UPLOAD SCHEMA
# ══════════════════════════════════════════════════════════

@app.post("/schema/upload")
async def upload_schema(
    question_id: str        = Form(...),
    image:       UploadFile = File(None, description="Scanned answer page (optional)"),
    extra_text:  str        = Form("",   description="Text / LaTeX content (optional)"),
):
    """
    Step 2 — Upload correct answer (schema) for a question.

    Routes to TOC or Math pipeline automatically based on declared subject.
    Accepts image, text, or both — at least one required.

    TOC  pipeline: auto-detects diagram / text / diagram+text
    Math pipeline: auto-detects formula / derivation / text / mixed
    """
    if (not image or not image.filename) and not extra_text.strip():
        raise HTTPException(400, "Provide at least an image or extra_text.")

    subject  = require_subject(question_id)
    img_path = None

    if image and image.filename:
        img_path = save_upload(
            image,
            UPLOAD_DIR / subject / "schema" / f"{question_id}_{image.filename}",
        )

    print(f"\n[SERVER] Schema upload — q={question_id}  subject={subject}")

    if subject == "toc":
        return await _toc_schema(question_id, img_path, extra_text)
    else:
        return await _math_schema(question_id, img_path, extra_text)


# ══════════════════════════════════════════════════════════
#  ROUTE 3 — UPLOAD STUDENT ANSWER
# ══════════════════════════════════════════════════════════

@app.post("/student/upload")
async def upload_student(
    question_id: str        = Form(...),
    student_id:  str        = Form(..., description="Student roll number or ID"),
    image:       UploadFile = File(None),
    extra_text:  str        = Form(""),
):
    """
    Step 3 — Upload one student's answer for a question.

    Routes to TOC or Math pipeline automatically.
    Student KG stored as {question_id}_{student_id} in respective database.
    """
    if (not image or not image.filename) and not extra_text.strip():
        raise HTTPException(400, "Provide at least an image or extra_text.")

    subject  = require_subject(question_id)
    img_path = None

    if image and image.filename:
        img_path = save_upload(
            image,
            UPLOAD_DIR / subject / "students" /
            f"{question_id}_{student_id}_{image.filename}",
        )

    print(f"\n[SERVER] Student upload — q={question_id} "
          f"student={student_id}  subject={subject}")

    if subject == "toc":
        return await _toc_student(question_id, student_id, img_path, extra_text)
    else:
        return await _math_student(question_id, student_id, img_path, extra_text)


# ══════════════════════════════════════════════════════════
#  ROUTE 4 — EVALUATE ONE STUDENT
# ══════════════════════════════════════════════════════════

@app.post("/evaluate/{question_id}")
def evaluate_one(
    question_id: str,
    student_id:  str  = Form(...),
    skip_llm:    bool = Form(False, description="True to skip Gemini judge (saves quota)"),
):
    """
    Step 4 — Run evaluation for one student on one question.

    TOC  evaluation: exact match + semantic + WL kernel/GED + LLM judge
    Math evaluation: formula exact + SymPy symbolic + step sequence + LLM judge

    content_type is auto-read from Neo4j — no need to specify.
    """
    subject   = require_subject(question_id)
    neo4j_qid = f"{question_id}_{student_id}"

    print(f"\n[SERVER] Evaluate — q={question_id} "
          f"student={student_id}  subject={subject}")

    if subject == "toc":
        report = _run_toc_eval(question_id, neo4j_qid, skip_llm)
    else:
        report = _run_math_eval(question_id, neo4j_qid, skip_llm)

    results.setdefault(question_id, {})[student_id] = report

    return {
        "question_id": question_id,
        "student_id":  student_id,
        "subject":     subject,
        "report":      report,
    }


# ══════════════════════════════════════════════════════════
#  ROUTE 4b — BATCH EVALUATE
# ══════════════════════════════════════════════════════════

@app.post("/evaluate/all")
def evaluate_all(
    question_id: str  = Form(...),
    student_ids: str  = Form(..., description="Comma-separated: STU001,STU002,STU003"),
    skip_llm:    bool = Form(False),
):
    """Batch evaluate multiple students for one question."""
    subject     = require_subject(question_id)
    ids         = [s.strip() for s in student_ids.split(",") if s.strip()]
    all_reports = {}

    for student_id in ids:
        neo4j_qid = f"{question_id}_{student_id}"
        try:
            report = (_run_toc_eval(question_id, neo4j_qid, skip_llm)
                      if subject == "toc" else
                      _run_math_eval(question_id, neo4j_qid, skip_llm))

            results.setdefault(question_id, {})[student_id] = report
            all_reports[student_id] = {
                "final_score":  report["final_score"],
                "layer_scores": report["layer_scores"],
                "feedback":     report["feedback"][:3],
            }
        except Exception as e:
            all_reports[student_id] = {"error": str(e)}

    return {
        "question_id": question_id,
        "subject":     subject,
        "evaluated":   len([r for r in all_reports.values() if "error" not in r]),
        "failed":      len([r for r in all_reports.values() if "error"     in r]),
        "results":     all_reports,
    }


# ══════════════════════════════════════════════════════════
#  ROUTE 5 — GET RESULTS
# ══════════════════════════════════════════════════════════

@app.get("/results/{question_id}")
def get_results(question_id: str):
    """Get all stored evaluation results for a question."""
    q_results = results.get(question_id, {})
    if not q_results:
        raise HTTPException(
            404,
            f"No results for '{question_id}'. "
            f"Run POST /evaluate/{question_id} first."
        )
    subject = subject_map.get(question_id, "unknown")
    return {
        "question_id":    question_id,
        "subject":        subject,
        "total_students": len(q_results),
        "students": {
            stu_id: {
                "final_score":   r.get("final_score"),
                "layer_scores":  r.get("layer_scores"),
                "feedback":      r.get("feedback", []),
                "llm_feedback":  r.get("llm_feedback", ""),
                # TOC fields
                "strengths":     r.get("strengths",     []),
                # Math fields
                "correct_steps": r.get("correct_steps", []),
                "wrong_steps":   r.get("wrong_steps",   []),
            }
            for stu_id, r in q_results.items()
        },
    }


# ══════════════════════════════════════════════════════════
#  TOC PIPELINE — internal functions
# ══════════════════════════════════════════════════════════

async def _toc_schema(question_id: str, img_path, extra_text: str) -> dict:
    if img_path:
        ext = dfa_cv.extract_from_page(
            image_path   = str(img_path),
            output_image = str(UPLOAD_DIR / "toc" / "schema" /
                               f"{question_id}_annotated.png"),
            extra_text   = extra_text,
        )
        content_type  = ext["content_type"]
        combined_text = ext["combined_text"]
        has_diagram   = ext.get("has_diagram", False)
    else:
        content_type  = "text"
        combined_text = extra_text.strip()
        has_diagram   = False

    if not combined_text.strip():
        raise HTTPException(400, "No content extracted.")

    neo4j  = kg.Neo4jConn()
    
    neo4j.clear_question(kg.DB_SCHEMA, question_id)

    data  = kg.extract_triples( combined_text,
                                image_path   = str(img_path) if has_diagram else None,
                                content_type = content_type)
    topic = kg.push_kg(neo4j, data, kg.DB_SCHEMA, question_id, content_type)
    neo4j.close()

    return {
        "status": "schema_stored", "subject": "toc",
        "question_id": question_id, "content_type": content_type,
        "topic": topic, "triples_count": len(data.get("triples", [])),
        "next_step": "POST /student/upload",
        "extracted":ext
    }


async def _toc_student(question_id: str, student_id: str,
                        img_path, extra_text: str) -> dict:
    if img_path:
        ext = dfa_cv.extract_from_page(
            image_path   = str(img_path),
            output_image = str(UPLOAD_DIR / "toc" / "students" /
                               f"{question_id}_{student_id}_annotated.png"),
            extra_text   = extra_text,
        )
        content_type  = ext["content_type"]
        combined_text = ext["combined_text"]
        has_diagram   = ext.get("has_diagram", False)
    else:
        content_type  = "text"
        combined_text = extra_text.strip()
        has_diagram   = False

    neo4j_qid = f"{question_id}_{student_id}"
    neo4j     = kg.Neo4jConn()
    
    neo4j.clear_question(kg.DB_STUDENT, neo4j_qid)

    data  = kg.extract_triples( combined_text,
                                image_path   = str(img_path) if has_diagram else None,
                                content_type = content_type)
    topic = kg.push_kg(neo4j, data, kg.DB_STUDENT, neo4j_qid, content_type)
    neo4j.close()

    return {
        "status": "student_kg_stored", "subject": "toc",
        "question_id": question_id, "student_id": student_id,
        "neo4j_qid": neo4j_qid, "content_type": content_type,
        "topic": topic, "triples_count": len(data.get("triples", [])),
        "next_step": f"POST /evaluate/{question_id}",
        "extracted":ext
    }


def _run_toc_eval(schema_qid: str, student_qid: str, skip_llm: bool) -> dict:
    neo4j  = eval_engine.Neo4jConn()
    client = eval_engine.get_gemini_client()

    ct            = neo4j.get_content_type(eval_engine.DB_SCHEMA, schema_qid)
    schema_nodes  = neo4j.get_nodes(eval_engine.DB_SCHEMA,  schema_qid)
    schema_edges  = neo4j.get_edges(eval_engine.DB_SCHEMA,  schema_qid)
    student_nodes = neo4j.get_nodes(eval_engine.DB_STUDENT, student_qid)
    student_edges = neo4j.get_edges(eval_engine.DB_STUDENT, student_qid)

    print(f"[TOC] Schema : {len(schema_nodes)} nodes, {len(schema_edges)} edges")
    print(f"[TOC] Student: {len(student_nodes)} nodes, {len(student_edges)} edges")

    l1 = eval_engine.layer1_exact_match(
        schema_nodes, student_nodes, schema_edges, student_edges)
    l2 = eval_engine.layer2_semantic(
        schema_nodes, student_nodes, schema_edges, student_edges)

    G_sc, G_st = nx.DiGraph(), nx.DiGraph()
    for n in schema_nodes:  G_sc.add_node(n["label"], node_type=n["node_type"])
    for e in schema_edges:  G_sc.add_edge(e["subj"], e["obj"], pred=e["pred"])
    for n in student_nodes: G_st.add_node(n["label"], node_type=n["node_type"])
    for e in student_edges: G_st.add_edge(e["subj"], e["obj"], pred=e["pred"])

    l3 = eval_engine.layer3_graph_structure(G_sc, G_st)
    l4 = ({"score": 0.0, "overall_feedback": "Skipped",
            "dimensions": {}, "strengths": [], "weaknesses": []}
          if skip_llm else
          eval_engine.layer4_llm_judge(
              client, schema_nodes, schema_edges, student_nodes, student_edges))

    neo4j.close()
    return eval_engine.combine_scores(l1, l2, l3, l4,
                                       question_type=ct,
                                       schema_edge_count=len(schema_edges))


# ══════════════════════════════════════════════════════════
#  MATH PIPELINE — internal functions
# ══════════════════════════════════════════════════════════

def _math_text_extraction(extra_text: str) -> dict:
    """Build extraction dict from plain text/LaTeX when no image given."""
    return {
        "content_type":   "formula" if "$" in extra_text else "text",
        "latex_blocks":   re.findall(r'\$\$?(.+?)\$\$?', extra_text, re.DOTALL),
        "text_blocks":    [extra_text],
        "steps":          [],
        "variables":      {},
        "combined_text":  extra_text,
        "raw_transcript": extra_text,
    }


async def _math_schema(question_id: str, img_path, extra_text: str) -> dict:
    ext = (mx.extract_from_math_page(
               image_path   = str(img_path),
               extra_text   = extra_text,
               output_image = str(UPLOAD_DIR / "math" / "schema" /
                                  f"{question_id}_annotated.png"))
           if img_path else _math_text_extraction(extra_text))

    if not ext["combined_text"].strip():
        raise HTTPException(400, "No content extracted.")

    neo4j  = mg.MathNeo4j()
    client = mg.get_gemini_client()
    neo4j.clear_question(mg.DB_SCHEMA, question_id)

    gdata = mg.extract_math_triples(client,
                                    combined_text = ext["combined_text"],
                                    latex_blocks  = ext["latex_blocks"],
                                    steps         = ext["steps"],
                                    variables     = ext["variables"])
    topic = mg.push_math_kg(neo4j, gdata, ext, mg.DB_SCHEMA, question_id)
    neo4j.close()

    return {
        "status": "schema_stored", "subject": "math",
        "question_id": question_id, "content_type": ext["content_type"],
        "topic": topic, "formulas_found": len(ext["latex_blocks"]),
        "steps_found": len(ext["steps"]),
        "triples_count": len(gdata.get("triples", [])),
        "next_step": "POST /student/upload",
        "extracted":ext
    }


async def _math_student(question_id: str, student_id: str,
                         img_path, extra_text: str) -> dict:
    ext = (mx.extract_from_math_page(
               image_path   = str(img_path),
               extra_text   = extra_text,
               output_image = str(UPLOAD_DIR / "math" / "students" /
                                  f"{question_id}_{student_id}_annotated.png"))
           if img_path else _math_text_extraction(extra_text))

    neo4j_qid = f"{question_id}_{student_id}"
    neo4j     = mg.MathNeo4j()
    client    = mg.get_gemini_client()
    neo4j.clear_question(mg.DB_STUDENT, neo4j_qid)

    gdata = mg.extract_math_triples(client,
                                    combined_text = ext["combined_text"],
                                    latex_blocks  = ext["latex_blocks"],
                                    steps         = ext["steps"],
                                    variables     = ext["variables"])
    topic = mg.push_math_kg(neo4j, gdata, ext, mg.DB_STUDENT, neo4j_qid)
    neo4j.close()

    return {
        "status": "student_kg_stored", "subject": "math",
        "question_id": question_id, "student_id": student_id,
        "neo4j_qid": neo4j_qid, "content_type": ext["content_type"],
        "topic": topic, "formulas_found": len(ext["latex_blocks"]),
        "steps_found": len(ext["steps"]),
        "triples_count": len(gdata.get("triples", [])),
        "next_step": f"POST /evaluate/{question_id}",
        "extracted":ext
    }


def _run_math_eval(schema_qid: str, student_qid: str, skip_llm: bool) -> dict:
    return me.evaluate_math(
        question_id = schema_qid,
        student_qid = student_qid,
        skip_llm    = skip_llm,
    )