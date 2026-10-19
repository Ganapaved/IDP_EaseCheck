"""
math_extract.py — Mathematics Transcription Pipeline (Fixed Content Classification)
════════════════════════════════════════════════════════════════════════════════════
Handles all math answer types and accurately overrides content classification 
using Gemini's spatial and contextual awareness.
"""

import cv2
import numpy as np
import re
import json
import base64
import os
import time
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()
from datetime import datetime, timezone

import easyocr
from google import genai
from google.genai import types

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL   = "gemini-3-flash-preview"

# ── Try importing Pix2Text (optional — falls back to Gemini Vision) ───────────
try:
    from pix2text import Pix2Text
    PIX2TEXT_AVAILABLE = True
except ImportError:
    PIX2TEXT_AVAILABLE = False
    print("[math_extract] pix2text not installed — using Gemini Vision for OCR")

_easyocr_reader = None
_pix2text_model  = None


# ══════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════

def get_gemini_client() -> genai.Client:
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY env var not set")
    return genai.Client(api_key=GEMINI_API_KEY)


def call_gemini(client, prompt: str, image_path: str | None = None,
                max_retries: int = 4) -> str:
    contents = []
    if image_path and Path(image_path).exists():
        mime = "image/png" if image_path.endswith(".png") else "image/jpeg"
        with open(image_path, "rb") as f:
            contents.append(types.Part.from_bytes(data=f.read(), mime_type=mime))
    contents.append(prompt)
    for attempt in range(max_retries):
        try:
            r = client.models.generate_content(model=GEMINI_MODEL, contents=contents)
            return r.text.strip()
        except Exception as e:
            if "429" in str(e) or "quota" in str(e).lower():
                wait = (2 ** attempt) * 5
                print(f"  [Gemini] Rate limited. Retrying in {wait}s...")
                time.sleep(wait)
            else:
                raise
    raise RuntimeError("Gemini failed after max retries")


def get_easyocr():
    global _easyocr_reader
    if _easyocr_reader is None:
        _easyocr_reader = easyocr.Reader(['en'], gpu=False, verbose=False)
    return _easyocr_reader


def get_pix2text():
    global _pix2text_model
    if _pix2text_model is None and PIX2TEXT_AVAILABLE:
        _pix2text_model = Pix2Text.from_config()
    return _pix2text_model


# ══════════════════════════════════════════════════════════
#  STEP 1 — INITIAL HEURISTIC DETECTION
# ══════════════════════════════════════════════════════════

def detect_math_content_type(image_path: str) -> dict:
    """
    Initial heuristic pass. Note: The content type calculated here 
    acts as a fallback and will be updated dynamically during the AI pass.
    """
    img  = cv2.imread(image_path)
    if img is None:
        raise FileNotFoundError(f"Cannot open: {image_path}")
    gray  = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    reader   = get_easyocr()
    ocr_full = reader.readtext(gray, detail=1)

    all_text       = " ".join([t[1] for t in ocr_full if t[2] > 0.2])
    formula_syms   = set("=∫∑√∂∞∈∉∀∃±×÷∧∨∩∪⊂⊃⊆⊇→←↔⟹⟺αβγδεζηθλμπσφψω")
    math_char_count = sum(1 for c in all_text if c in formula_syms or c in "^_{}\\")

    horizontal_lines = 0
    contours, _   = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for cnt in contours:
        x, y, cw, ch = cv2.boundingRect(cnt)
        aspect = cw / (ch + 1e-6)
        if aspect > 5 and 2 <= ch <= 8 and cw > 30:
            horizontal_lines += 1

    step_pattern = re.compile(r'^\s*(\d+[\.\)]|step\s*\d+)', re.IGNORECASE | re.MULTILINE)
    step_matches = step_pattern.findall(all_text)
    has_steps    = len(step_matches) >= 2

    circles_found  = 0
    lines_found    = 0
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < 200: continue
        perimeter = cv2.arcLength(cnt, True)
        if perimeter == 0: continue
        circularity = (4 * np.pi * area) / (perimeter ** 2)
        if circularity > 0.75 and 20 < np.sqrt(area / np.pi) < 120:
            circles_found += 1
        _, _, cw, ch = cv2.boundingRect(cnt)
        aspect = cw / (ch + 1e-6)
        if aspect > 4 or aspect < 0.25:
            lines_found += 1

    has_formulas  = math_char_count > 5 or horizontal_lines > 1
    has_text      = len([t for t in ocr_full if t[2] > 0.3 and len(t[1]) > 3]) > 4
    has_diagram   = circles_found >= 2 or (lines_found > 5 and circles_found >= 1)

    if has_diagram and has_formulas:
        ctype = "mixed"
    elif has_diagram and not has_formulas:
        ctype = "diagram"
    elif has_formulas and has_steps:
        ctype = "derivation"
    elif has_formulas:
        ctype = "formula"
    else:
        ctype = "text"

    return {
        "type":         ctype,
        "has_formulas": has_formulas,
        "has_text":     has_text,
        "has_diagram":  has_diagram,
        "has_steps":    has_steps,
    }

def extract_latex_pix2text(image_path: str) -> list[str]:
    """
    Uses Pix2Text to extract LaTeX from formula regions.
    Returns list of LaTeX strings.
    """
    p2t = get_pix2text()
    if p2t is None:
        return []

    try:
        result = p2t(image_path)
        # pix2text returns a string or list depending on version
        if isinstance(result, str):
            # Split on newlines — each line is usually one formula or text block
            return [line.strip() for line in result.split('\n') if line.strip()]
        elif isinstance(result, list):
            latex_blocks = []
            for item in result:
                if isinstance(item, dict):
                    text = item.get('text', item.get('latex', ''))
                else:
                    text = str(item)
                if text.strip():
                    latex_blocks.append(text.strip())
            return latex_blocks
    except Exception as e:
        print(f"  [Pix2Text] Error: {e}")
    return []


# ══════════════════════════════════════════════════════════
#  STEP 2a — FORMULA EXTRACTION WITH CLASSIFICATION
# ══════════════════════════════════════════════════════════

# Updated prompt to explicitly detect content types upfront
MATH_OCR_PROMPT = """
You are a mathematics OCR and document layout expert. 

CRITICAL FIRST STEP:
Analyze the structural content layout of the image and output exactly ONE classification line at the very beginning of your response in this exact format:
CONTENT_CLASS: <type>
Where <type> MUST be exactly one of: formula, derivation, text, diagram, mixed

Use these evaluation guidelines for the layout:
- "formula": Pure formulas, standalone equations, or expressions without execution steps.
- "derivation": Step-by-step mathematical solutions, proofs, or numbered derivations.
- "diagram": Geometry drawings, vector layouts, graphs, or coordinate plots without dense formulas.
- "mixed": A combination containing diagrams/plots along with formulas or text explanations.
- "text": Standard narrative wording or explanations containing minimal to no mathematical notation.

After providing the CONTENT_CLASS line, perform the mathematical transcription following these rules:
1. Convert every formula, equation, and expression to LaTeX format.
   - Inline math: $...$
   - Display math (standalone equations): $$...$$
2. Keep plain text explanation as-is (not in LaTeX).
3. Preserve the ORDER of content exactly as it appears top-to-bottom.
4. Number each derivation step if steps are present (Step 1, Step 2 ...).
5. For diagrams: describe what is drawn (axes, curves, labels, intersections).
6. For variables: note their definitions if stated (e.g. "where x ∈ ℝ").
7. Do NOT interpret or simplify — transcribe exactly what is written.
8. If handwriting is unclear, write [unclear] for that part.
"""

def extract_latex_gemini(image_path: str, client) -> str:
    print("  [Gemini] Transcribing math content & detecting layout type...")
    return call_gemini(client, MATH_OCR_PROMPT, image_path)


# ══════════════════════════════════════════════════════════
#  STEP 2b — PARSE TRANSCRIPTION AND EXTRACT TYPE OVERWRITE
# ══════════════════════════════════════════════════════════

def parse_math_transcription(raw: str) -> dict:
    latex_blocks = []
    text_blocks  = []
    steps        = []
    variables    = {}
    detected_type_overwrite = None

    # ── Check for the explicit AI Content Class line ─────────────────────────
    class_match = re.search(r'CONTENT_CLASS:\s*(formula|derivation|text|diagram|mixed)', raw, re.IGNORECASE)
    if class_match:
        detected_type_overwrite = class_match.group(1).lower().strip()
        # Clean the control line from raw string so it doesn't leak into text blocks
        raw = re.sub(r'CONTENT_CLASS:\s*\w+', '', raw, flags=re.IGNORECASE).strip()

    # ── Extract display math $$...$$ ─────────────────────────────────────────
    display_math = re.findall(r'\$\$(.+?)\$\$', raw, re.DOTALL)
    latex_blocks.extend([m.strip() for m in display_math])

    # ── Extract inline math $...$ (not inside $$) ─────────────────────────────
    temp = re.sub(r'\$\$.+?\$\$', '', raw, flags=re.DOTALL)
    inline_math = re.findall(r'\$([^$]+?)\$', temp)
    latex_blocks.extend([m.strip() for m in inline_math if len(m.strip()) > 1])

    seen = set()
    unique_latex = []
    for lb in latex_blocks:
        key = re.sub(r'\s+', '', lb)
        if key not in seen:
            seen.add(key)
            unique_latex.append(lb)
    latex_blocks = unique_latex

    # ── Extract steps ─────────────────────────────────────────────────────────
    step_re = re.compile(
        r'(?:^|\n)\s*(?:Step\s*(\d+)|(\d+)[\.\)])\s*[:\-]?\s*(.+?)(?=\n\s*(?:Step\s*\d+|\d+[\.\)])|$)',
        re.IGNORECASE | re.DOTALL
    )
    for m in step_re.finditer(raw):
        step_num    = m.group(1) or m.group(2)
        step_content = m.group(3).strip()
        if step_content:
            steps.append({
                "step":    int(step_num),
                "content": step_content,
                "latex":   re.findall(r'\$\$?(.+?)\$\$?', step_content, re.DOTALL),
            })

    # ── Extract variable definitions ──────────────────────────────────────────
    var_patterns = [
        r'(?:where|let|given|define)\s+([a-zA-Zαβγδεζηθλμπσφψω])\s*[=∈]\s*([^\n,]+)',
        r'([a-zA-Zαβγδεζηθλμπσφψω])\s+is\s+(?:the|a|an)\s+([^\n,\.]+)',
    ]
    for pat in var_patterns:
        for m in re.finditer(pat, raw, re.IGNORECASE):
            var_name = m.group(1).strip()
            var_defn = m.group(2).strip()
            variables[var_name] = var_defn

    # ── Plain text blocks ─────────────────────────────────────────────────────
    for line in raw.split('\n'):
        clean = re.sub(r'\$\$?.+?\$\$?', '', line).strip()
        clean = re.sub(r'\s+', ' ', clean)
        if len(clean) > 10 and not re.match(r'^\s*\d+[\.\)]\s*$', clean):
            text_blocks.append(clean)

    return {
        "latex_blocks": latex_blocks,
        "text_blocks":  text_blocks,
        "steps":        steps,
        "variables":    variables,
        "ai_type_overwrite": detected_type_overwrite
    }


# ══════════════════════════════════════════════════════════
#  MAIN ENTRY POINT (With type updates)
# ══════════════════════════════════════════════════════════

def extract_from_math_page(
    image_path: str,
    extra_text: str = "",
    output_image: str = "math_annotated.png",
) -> dict:
    """
    Full math transcription pipeline with dynamic Vision-based 
    layout classification overwrites.
    """
    print(f"\n[MathExtract] Analysing: {image_path}")

    # ── 1. Calculate Initial CV2 Heuristics Fallback ──────────────────────────
    detection = detect_math_content_type(image_path)
    ctype     = detection["type"] 

    client    = get_gemini_client()
    raw_transcript = ""

    # ── 2. Run Main Engine Pass ───────────────────────────────────────────────
    # If it is treated as simple text or contains complex diagrams, go direct to Gemini
    if not detection["has_formulas"] or detection["has_diagram"]:
        raw_transcript = extract_latex_gemini(image_path, client)
    else:
        # If it looks like flat math syntax, try local Pix2Text first
        if PIX2TEXT_AVAILABLE:
            print("  [MathExtract] Using Pix2Text for formula extraction...")
            from pix2text import Pix2Text
            p2t_blocks = extract_latex_pix2text(image_path)
            if p2t_blocks:
                raw_transcript = "\n".join(p2t_blocks)
        
        # Fallback to Gemini if Pix2Text execution didn't yield anything
        if not raw_transcript.strip():
            raw_transcript = extract_latex_gemini(image_path, client)

    # Append downstream structural payload notes
    if extra_text.strip():
        raw_transcript += "\n" + extra_text.strip()

    # ── 3. Parse and Overwrite Layout Class Type ──────────────────────────────
    parsed = parse_math_transcription(raw_transcript)
    
    # Overwrite heuristic layout type if the multimodal engine provided a structural assessment
    if parsed["ai_type_overwrite"]:
        print(f"  [Override] Overwriting layout type: '{ctype}' ➔ '{parsed['ai_type_overwrite']}' based on AI Vision response.")
        ctype = parsed["ai_type_overwrite"]

    # ── 4. Build Document Structure output for Graph Pipelines ────────────────
    parts = []
    if parsed["latex_blocks"]:
        parts.append("Mathematical expressions:")
        for lb in parsed["latex_blocks"]:
            parts.append(f"  {lb}")
    if parsed["steps"]:
        parts.append("\nDerivation steps:")
        for s in parsed["steps"]:
            parts.append(f"  Step {s['step']}: {s['content']}")
    if parsed["text_blocks"]:
        parts.append("\nExplanation:")
        for tb in parsed["text_blocks"][:10]:
            parts.append(f"  {tb}")
    if parsed["variables"]:
        parts.append("\nVariable definitions:")
        for var, defn in parsed["variables"].items():
            parts.append(f"  {var} = {defn}")

    combined = "\n".join(parts)

    result = {
        "content_type":  ctype,
        "latex_blocks":  parsed["latex_blocks"],
        "text_blocks":   parsed["text_blocks"],
        "steps":         parsed["steps"],
        "variables":     parsed["variables"],
        "combined_text": combined,
        "raw_transcript": raw_transcript,
    }

    print(f"  [MathExtract] Done: {len(parsed['latex_blocks'])} formulas, "
          f"{len(parsed['steps'])} steps, Final Content Type Class={ctype}")
    
    # out = f"math_extract.json"
    # with open(out,'w') as f:
    #     json.dump(result,f,indent=2)
    out = f"math_extract_{datetime.now(timezone.utc).strftime('%H%M%S')}.json"
    with open(out, "w") as f:
        json.dump(result, f, indent=2)

    return result


if __name__ == "__main__":
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else "mathematics.jpeg"
    result = extract_from_math_page(path)
    print(f"\nFinal Verified Content type : {result['content_type']}")
    print(f"LaTeX blocks : {len(result['latex_blocks'])}")
    print(f"Steps        : {len(result['steps'])}")
    print(result)