import os,json,re,uuid,shutil
from pathlib import Path
from datetime import datetime,timezone
from typing import Optional
import networkx as nx
from fastapi import FastAPI,UploadFile,File,Form,HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

import dfsm_extract as dfa_cv
import graph_create as kg
import evaluation as eval_engine

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)
sessions: dict[str, dict] = {}

app = FastAPI(title="TOC Exam Evaluation API", version="2.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])

def save_upload(file, dest):
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)
    return dest
 
def get_session(sid):
    if sid not in sessions:
        raise HTTPException(404, f"Session '{sid}' not found")
    return sessions[sid]
 
def get_question(session, qid):
    if qid not in session["questions"]:
        raise HTTPException(404, f"Question '{qid}' not in session")
    return session["questions"][qid]

@app.get("/")
def health():
    return {"status": "running", "version": "2.0.0",
            "routes": {
                "1": "POST /session/create",
                "2": "POST /schema/upload",
                "3": "POST /student/upload",
                "4": "POST /evaluate/{question_id}",
                "5": "POST /evaluate/session/{session_id}/all",
                "6": "GET  /results/{session_id}",
                "7": "GET  /session/{session_id}/status",
            }}

@app.post("/session/create")
def create_session(
    subject:      str = Form(...),
    question_ids: str = Form(..., description="Comma-separated: q1,q2,q3"),
):
    """
    Step 1 — Create exam session.
    No need to specify question types — auto-detected from scanned images.
    """
    ids        = [q.strip() for q in question_ids.split(",")]
    session_id = f"sess_{uuid.uuid4().hex[:10]}"
    sessions[session_id] = {
        "subject":    subject,
        "questions":  {qid: {"content_type": None, "schema_done": False,
                              "topic": None} for qid in ids},
        "students":   {},
        "results":    {},
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    return {"session_id": session_id, "subject": subject, "questions": ids,
            "next_step": f"POST /schema/upload with session_id={session_id}"}


@app.post("/schema/upload")
async def upload_schema(
    session_id:  str        = Form(...),
    question_id: str        = Form(...),
    image:       UploadFile = File(...),
    extra_text:  str        = Form(""),
):
    """
    Step 2 — Upload scanned schema page.
    Auto-detects: diagram / text / diagram+text.
    Runs CV+VLM if diagram found.
    Stores KG in ischema Neo4j database.
    """
    session  = get_session(session_id)
    question = get_question(session, question_id)
 
    img_path = save_upload(image,
        UPLOAD_DIR / session_id / f"schema_{question_id}_{image.filename}")
 
    print(f"\n[SERVER] Schema upload: session={session_id} q={question_id}")
    extraction = dfa_cv.extract_from_page(
        image_path   = str(img_path),
        output_image = str(UPLOAD_DIR / session_id /
                           f"schema_{question_id}_annotated.png"),
        extra_text   = extra_text,
    )
 
    content_type  = extraction["content_type"]
    combined_text = extraction["combined_text"]
 
    if not combined_text.strip():
        raise HTTPException(400,
            "No content extracted. Check image quality or add extra_text.")
 
    neo4j  = kg.Neo4jConn()
    client = kg.get_gemini_client()
    neo4j.clear_question(kg.DB_SCHEMA, question_id)
 
    schema_data = kg.extract_triples(
        client, combined_text,
        image_path   = str(img_path) if extraction["has_diagram"] else None,
        content_type = content_type,
    )
    topic = kg.push_kg(neo4j, schema_data, kg.DB_SCHEMA,
                       question_id, content_type)
    neo4j.close()
 
    sessions[session_id]["questions"][question_id].update({
        "content_type": content_type,
        "schema_done":  True,
        "topic":        topic,
    })
 
    return {
        "status": "schema_stored", "session_id": session_id,
        "question_id": question_id, "content_type": content_type,
        "topic": topic, "triples_count": len(schema_data.get("triples", [])),
        "next_step": f"POST /student/upload with session_id={session_id}",
    }


@app.post("/student/upload")
async def upload_student(
    session_id:  str        = Form(...),
    question_id: str        = Form(...),
    student_id:  str        = Form(...),
    image:       UploadFile = File(...),
    extra_text:  str        = Form(""),
):
    """
    Step 3 — Upload scanned student answer page.
    Auto-detects content type. Stores KG as question_id_student_id in istudent.
    """
    session  = get_session(session_id)
    question = get_question(session, question_id)
 
    if not question["schema_done"]:
        raise HTTPException(400,
            f"Schema for '{question_id}' not uploaded. Run /schema/upload first.")
 
    img_path = save_upload(image,
        UPLOAD_DIR / session_id /
        f"student_{student_id}_{question_id}_{image.filename}")
 
    print(f"\n[SERVER] Student upload: {student_id} q={question_id}")
    extraction = dfa_cv.extract_from_page(
        image_path   = str(img_path),
        output_image = str(UPLOAD_DIR / session_id /
                           f"student_{student_id}_{question_id}_annotated.png"),
        extra_text   = extra_text,
    )
 
    content_type  = extraction["content_type"]
    combined_text = extraction["combined_text"]
    neo4j_qid     = f"{question_id}_{student_id}"   # namespaced
 
    neo4j  = kg.Neo4jConn()
    client = kg.get_gemini_client()
    neo4j.clear_question(kg.DB_STUDENT, neo4j_qid)
 
    student_data = kg.extract_triples(
        client, combined_text,
        image_path   = str(img_path) if extraction["has_diagram"] else None,
        content_type = content_type,
    )
    topic = kg.push_kg(neo4j, student_data, kg.DB_STUDENT,
                       neo4j_qid, content_type)
    neo4j.close()
 
    sessions[session_id]["students"].setdefault(student_id, {})[question_id] = {
        "neo4j_qid":    neo4j_qid,
        "content_type": content_type,
        "triples_count": len(student_data.get("triples", [])),
    }
 
    return {
        "status": "student_kg_stored", "session_id": session_id,
        "question_id": question_id, "student_id": student_id,
        "neo4j_qid": neo4j_qid, "content_type": content_type,
        "topic": topic,
        "triples_count": len(student_data.get("triples", [])),
    }

@app.post("/evaluate/{question_id}")
def evaluate_question(
    question_id: str,
    session_id:  str  = Form(...),
    student_id:  str  = Form(...),
    skip_llm:    bool = Form(False),
):
    """Step 4 — Run 4-layer evaluation. content_type auto-read from Neo4j."""
    session = get_session(session_id)
    get_question(session, question_id)
 
    student_info = (sessions[session_id].get("students", {})
                    .get(student_id, {}).get(question_id))
    if not student_info:
        raise HTTPException(400,
            f"No KG for student={student_id} q={question_id}. "
            f"Run /student/upload first.")
 
    report = eval_engine(question_id, student_info["neo4j_qid"], skip_llm)
    sessions[session_id]["results"].setdefault(question_id, {})[student_id] = report
 
    return {"session_id": session_id, "question_id": question_id,
            "student_id": student_id, "report": report}


def _run_evaluation(schema_qid, student_qid, skip_llm=False):
    """
    Bridge: reads schema from ischema, student from istudent.
    content_type and sparse-schema adjustment are automatic.
    """
    neo4j  = eval_engine.Neo4jConn()
    client = eval_engine.get_gemini_client()
 
    content_type  = neo4j.get_content_type(eval_engine.DB_SCHEMA, schema_qid)
    schema_nodes  = neo4j.get_nodes(eval_engine.DB_SCHEMA,  schema_qid)
    schema_edges  = neo4j.get_edges(eval_engine.DB_SCHEMA,  schema_qid)
    student_nodes = neo4j.get_nodes(eval_engine.DB_STUDENT, student_qid)
    student_edges = neo4j.get_edges(eval_engine.DB_STUDENT, student_qid)
 
    l1 = eval_engine.layer1_exact_match(
        schema_nodes, student_nodes, schema_edges, student_edges)
    l2 = eval_engine.layer2_semantic(
        schema_nodes, student_nodes, schema_edges, student_edges)
 
    G_sc = nx.DiGraph()
    G_st = nx.DiGraph()
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
 
    return eval_engine.combine_scores(
        l1, l2, l3, l4,
        question_type     = content_type,
        schema_edge_count = len(schema_edges),
    )