# Explainable Automated Answer Script Evaluation Using Knowledge Graph Alignment and Large Language Models

> Interdisciplinary Project (XX367P) — RV College of Engineering, Bengaluru (2025–26)

**Authors:** Abhilash L Pattar · Vedaksha M · Raghav N · K Nagaraja
**Guide:** Dr. Shanta Rangaswamy, Professor & Head, Dept. of CSE

---

## Overview

Manual grading of descriptive answers is slow, subjective, and doesn't scale. This system automates it using a hybrid pipeline that combines:

- **OCR** to digitize scanned answer sheets
- **Knowledge Graphs** (Neo4j) to represent teacher and student answers as structured concept graphs
- **Multi-layer scoring** — exact match, semantic similarity, graph structure, and LLM judgment
- **Explainable feedback** — tells students and teachers *why* a score was given (missing concepts, wrong relations, incomplete reasoning)

It handles **text answers**, **diagram-based answers** (DFAs, FSMs), and **mathematical derivations** — not just plain prose.

---

## Architecture

```
Upload (teacher schema / student answer)
        │
        ▼
Content Type Detection  ──── text / diagram / diagram+text
        │
        ▼
Extraction Layer
  ├── OCR (EasyOCR)            ← text content
  └── CV + VLM Pipeline        ← diagram content (states, transitions)
        │
        ▼
Triple Extraction (Gemini)
  subject – predicate – object triples
        │
        ▼
Knowledge Graph Storage (Neo4j)
  ├── ischema  ← teacher reference graph (keyed by question_id)
  └── istudent ← student graph (keyed by question_id + student_id)
        │
        ▼
Four-Layer Evaluation Engine
  ├── Layer 1: Exact Match       (entity & relation overlap)
  ├── Layer 2: Semantic Sim      (Sentence-BERT embeddings)
  ├── Layer 3: Graph Structure   (NetworkX topology comparison)
  └── Layer 4: LLM Judge         (Gemini-based holistic feedback)
        │
        ▼
Weighted Score + Explainable Feedback Report
```

For **math answers**, three additional layers run in place of the standard graph layer:
- Formula Exact Match
- Symbolic Equivalence (SymPy)
- Step-Order Comparison (LCS-based)

---

## Tech Stack

| Component | Technology |
|---|---|
| API Server | FastAPI |
| Graph Database | Neo4j |
| OCR | EasyOCR |
| Image Processing | OpenCV |
| Diagram Understanding | Vision Language Model (Ollama VLM) |
| Triple Extraction | Gemini (Google Generative AI) |
| Semantic Similarity | Sentence-BERT (SBERT) |
| Graph Analysis | NetworkX |
| Math Evaluation | SymPy |
| Embedding / Reasoning | Graph Embeddings (TransE / RotatE) |

---

## Project Structure

```
.
├── server.py            # FastAPI app — API routes and orchestration
├── dfsm_extract.py      # Content-type detection + diagram extraction (CV + VLM)
├── graph_create.py      # Triple extraction (Gemini) + Neo4j graph storage
├── evaluation.py        # Four-layer scoring engine + feedback generation
├── math_extract.py      # Math-specific formula and LaTeX extraction
├── math_graph.py        # Math knowledge graph builder
└── math_evaluation.py   # Formula match, symbolic equivalence, step-order scoring
```

---

## API Endpoints

| Route | Method | Purpose |
|---|---|---|
| `/schema/upload` | POST | Upload teacher marking scheme; stores as reference KG in `ischema` |
| `/student/upload` | POST | Upload student answer; stores KG in `istudent` |
| `/evaluate/{question_id}` | POST | Evaluate one student for a given question |
| `/evaluate/all` | POST | Batch evaluate all students for a question |
| `/results/{question_id}` | GET | Retrieve cached evaluation reports and feedback |

---

## Evaluation Layer Weights

The scoring weights shift based on the type of answer submitted:

| Question Type | Exact | Semantic | Graph | LLM |
|---|---|---|---|---|
| Diagram | 0.25 | 0.15 | 0.35 | 0.25 |
| Text | 0.10 | 0.35 | 0.15 | 0.40 |
| Diagram + Text | 0.20 | 0.25 | 0.25 | 0.30 |

When a schema has fewer than 3 edges, weight is redistributed away from graph structure toward semantic and LLM layers automatically.

---

## Knowledge Graph Design

- **`ischema` DB** — teacher reference graphs, stored by `question_id`
- **`istudent` DB** — student answer graphs, stored by `question_id_student_id` (namespaced to prevent collisions)
- **Node types:** `Concept`, `State`, `Symbol`, `Rule`, `Property`, `Relation`, `ProofStep`
- **Edges** are directed triples extracted from the answer content

---

## Feedback Output

The system produces a structured feedback report per student per question, including:

- Final weighted score
- Per-layer scores (exact, semantic, graph, LLM)
- Missing entities and relations
- Incorrect/extra entities
- Graph structure mismatch flags
- LLM-generated qualitative feedback (strengths, weaknesses)

For math answers, it additionally reports: missing formulas, unmatched symbolic expressions, and missing/out-of-order derivation steps.

---

## Results (Pilot)

Validated on a Discrete Mathematical Structures (DMS) paper — 2 students, 4 sub-questions:

| Metric | Value |
|---|---|
| Pearson Correlation (r) with human grader | 0.845 |
| Mean Absolute Error (MAE) | 1.21 marks |
| RMSE | 1.48 |
| Independent Item Accuracy | 78.62% |

The system consistently preserved student rank ordering. A conservative under-marking bias was observed on formula-heavy questions (layers 1–3), partially offset by the LLM judge on questions with correct overall reasoning.

> **Note:** Pilot results (n = 8 data points). Full validation across a larger dataset is planned for future work.

---

## Limitations and Known Issues

- OCR noise affects downstream triple extraction quality — handwritten scripts with messy formatting degrade accuracy
- Formula matching is sensitive to LaTeX formatting differences (same expression, different notation = missed match)
- LLM-based layers depend on external API availability and response stability
- Named entity consistency in graphs affects alignment quality; slight wording variations can cause misses in exact-match layer

---

## Future Work

- Improve OCR preprocessing for handwritten answer scripts
- Extend KG extraction to richer relation types and partial credit
- Fairness and bias analysis across student demographics
- Multilingual answer evaluation
- Teacher-in-the-loop review/moderation mode
- Broader subject coverage beyond TOC and DMS

---

## Institution

**RV College of Engineering®, Bengaluru**
Autonomous institution affiliated to VTU, Belagavi
Department of Computer Science and Engineering | 2025–26
