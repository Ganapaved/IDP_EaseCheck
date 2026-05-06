"""
DFA Extractor — CV + VLM Pipeline
──────────────────────────────────
Stage 1 (CV)  : Contour-based circle detection → verified states, final states, labels
Stage 2 (VLM) : Ollama/qwen2.5vl reads transitions ONLY, grounded by CV template
Stage 3 (Merge): VLM output is validated against CV ground truth → hallucinations removed
"""

import cv2
import numpy as np
import easyocr
import ollama
import json
import re
from pathlib import Path


def detect_content_type(image_path) -> dict :
    img = cv2.imread(image_path)
    if img is None:
        raise FileNotFoundError(f"Cannot open {image_path}")
    
    gray = cv2.cvtColor(img,cv2.COLOR_BGR2GRAY)
    h,w = gray.shape

    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    kernel    = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    binary    = cv2.dilate(binary, kernel, iterations=1)

    diagram_circles = find_circular_contours(binary, min_radius=25, max_radius=100)
    has_diagram     = len(diagram_circles) >= 2

    circle_mask = np.zeros((h, w), dtype=np.uint8)
    for (cx, cy, r) in diagram_circles:
        cv2.circle(circle_mask, (cx, cy), r + 20, 255, -1)   # +20px margin

    text_regions = []
    text_content = ""

    bands = [
        ("top" ,0,int(h*0.25)),
        ("bottom",int(h*0.75),h),
        ("middle",int(h*0.25),int(h*0.75))
    ]

    reader = easyocr.Reader(['en'],verbose=False)
    for band_name, y_start, y_end in bands:
        band_img    = gray[y_start:y_end, 0:w]
        band_mask   = circle_mask[y_start:y_end, 0:w]
 
        # Blank out circle areas in this band
        band_clean  = band_img.copy()
        band_clean[band_mask > 0] = 255   # white out circles
 
        # Check if there's meaningful content (non-white pixels)
        non_white = np.sum(band_clean < 200)
        if non_white < 500:   # too little content
            continue
 
        # Run OCR on this band
        ocr_results = reader.readtext(band_clean, detail=1)
        band_texts  = []
        for (bbox, text, conf) in ocr_results:
            if conf > 0.3 and len(text.strip()) > 1:
                # Convert bbox to absolute coords
                pts    = np.array(bbox)
                x1, y1 = int(pts[:, 0].min()), int(pts[:, 1].min()) + y_start
                x2, y2 = int(pts[:, 0].max()), int(pts[:, 1].max()) + y_start
                text_regions.append((x1, y1, x2, y2))
                band_texts.append(text.strip())
    if band_texts:
        text_content += f"\n[{band_name}] " + " ".join(band_texts)

    meaningful_text = len(text_content.strip()) > 20
    has_text        = meaningful_text
 
    if has_diagram and has_text:
        content_type = "diagram+text"
    elif has_diagram:
        content_type = "diagram"
    else:
        content_type = "text"
 
    print(f"  [Detect] Type={content_type}  "
          f"circles={len(diagram_circles)}  "
          f"text_chars={len(text_content.strip())}")
 
    return {
        "type":            content_type,
        "has_diagram":     has_diagram,
        "has_text":        has_text,
        "diagram_regions": diagram_circles,
        "text_regions":    text_regions,
        "text_content":    text_content.strip(),
    }


def extract_from_page(
    image_path: str,
    output_image: str = "annotated_output.png",
    extra_text: str = "",          # any additional text the teacher typed in
) -> dict:
    """
    Main entry point for the server.
    Auto-detects content type, then routes to the right extractor.
 
    Returns:
    {
      "content_type": "diagram" | "text" | "diagram+text",
      "text_content": str,          # all text found (OCR + extra_text)
      "dfa_json":     dict | None,  # populated only if diagram detected
      "combined_text": str,         # text_content + dfa_json as text (for KG builder)
    }
    """
    print(f"\n[Extract] Analysing: {image_path}")
 
    # ── Detect content type ───────────────────────────────────────────────────
    detection = detect_content_type(image_path)
    ctype     = detection["type"]
 
    result = {
        "content_type": ctype,
        "text_content": detection["text_content"],
        "dfa_json":     None,
        "combined_text": "",
    }
 
    # ── Route based on detected type ──────────────────────────────────────────
 
    if detection["has_diagram"]:
        # Run full CV + VLM DFA extraction pipeline
        print(f"  [Extract] Diagram detected → running CV+VLM pipeline")
        try:
            dfa_json = extract_dfa(image_path, output_image)
            result["dfa_json"] = dfa_json
            dfa_text = _dfa_json_to_text(dfa_json)
        except Exception as e:
            print(f"  [Extract] CV+VLM failed: {e} — will use image directly")
            dfa_text = ""
    else:
        dfa_text = ""
 
    # ── Combine all text sources ──────────────────────────────────────────────
    parts = []
    if dfa_text:
        parts.append(dfa_text)
    if detection["text_content"]:
        parts.append(detection["text_content"])
    if extra_text.strip():
        parts.append(extra_text.strip())
 
    result["combined_text"] = "\n\n".join(parts)
    result["content_type"]  = ctype   # may be overridden if both present
    result['has_diagram'] = detection['has_diagram']
 
    print(f"  [Extract] Done. type={ctype}  "
          f"combined_text_len={len(result['combined_text'])}")
 
    return result

# ══════════════════════════════════════════════════════════
#  STAGE 1 — COMPUTER VISION  (ground truth extractor)
# ══════════════════════════════════════════════════════════


def preprocess(image_path):
    img = cv2.imread(image_path)
    if img is None:
        raise FileNotFoundError(f"Cannot open: {image_path}")
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    binary = cv2.dilate(binary, kernel, iterations=1)
    return img, gray, binary


def find_circular_contours(binary, min_radius=25, max_radius=100, circularity_thresh=0.72):
    contours, _ = cv2.findContours(binary, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    circles = []
    for cnt in contours:
        area = cv2.contourArea(cnt)
        perimeter = cv2.arcLength(cnt, True)
        if perimeter == 0:
            continue
        circularity = (4 * np.pi * area) / (perimeter ** 2)
        if circularity < circularity_thresh:
            continue
        (cx, cy), radius = cv2.minEnclosingCircle(cnt)
        cx, cy, radius = int(cx), int(cy), int(radius)
        if min_radius <= radius <= max_radius:
            circles.append((cx, cy, radius))
    return circles


def cluster_into_states(circles, center_tolerance=22, radius_gap_min=6, radius_gap_max=30):
    if not circles:
        return [], []
    circles = sorted(circles, key=lambda c: c[0])
    visited = [False] * len(circles)
    states, final_states = [], []
    for i in range(len(circles)):
        if visited[i]:
            continue
        group = [circles[i]]
        visited[i] = True
        x1, y1, _ = circles[i]
        for j in range(i + 1, len(circles)):
            if visited[j]:
                continue
            x2, y2, _ = circles[j]
            if np.hypot(x1 - x2, y1 - y2) < center_tolerance:
                group.append(circles[j])
                visited[j] = True
        cx = int(np.mean([c[0] for c in group]))
        cy = int(np.mean([c[1] for c in group]))
        radii = sorted([c[2] for c in group])
        outer_r = radii[-1]
        is_final = len(group) >= 2 and (radius_gap_min <= radii[-1] - radii[0] <= radius_gap_max)
        state = (cx, cy, outer_r)
        states.append(state)
        if is_final:
            final_states.append(state)
    return states, final_states


def ocr_states(img, states):
    reader = easyocr.Reader(['en'], gpu=False)
    results = []
    for (cx, cy, r) in states:
        pad = 6
        x1, y1 = max(cx - r + pad, 0), max(cy - r + pad, 0)
        x2, y2 = min(cx + r - pad, img.shape[1]), min(cy + r - pad, img.shape[0])
        roi = img[y1:y2, x1:x2]
        if roi.size == 0:
            results.append({"position": (cx, cy), "radius": r, "label": ""})
            continue
        roi_h, roi_w = roi.shape[:2]
        roi_gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        mask = np.zeros((roi_h, roi_w), dtype=np.uint8)
        inner_r = min(roi_w, roi_h) // 2 - 4
        cv2.circle(mask, (roi_w // 2, roi_h // 2), inner_r, 255, -1)
        clean = np.where(mask == 255, roi_gray, 255).astype(np.uint8)
        upscaled = cv2.resize(clean, (roi_w * 3, roi_h * 3), interpolation=cv2.INTER_CUBIC)
        _, thresh = cv2.threshold(upscaled, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        ocr_out = reader.readtext(thresh, detail=1)
        texts = []
        for (_, text, conf) in ocr_out:
            if conf < 0.25:
                continue
            text = (text.strip()
                    .replace('9', 'q').replace('O', '0').replace('o', '0')
                    .replace('|', '1').replace('I', '1')
                    .replace('=', '').replace('$', 'q').strip())
            if text:
                texts.append(text)
        results.append({"position": (cx, cy), "radius": r, "label": " ".join(texts)})
    return results


def run_cv_stage(image_path):
    """Returns cv_data dict with verified states and final states."""
    img, gray, binary = preprocess(image_path)
    raw_circles = find_circular_contours(binary)
    states, final_states = cluster_into_states(raw_circles)
    ocr_results = ocr_states(img, states)

    final_positions = {(s[0], s[1]) for s in final_states}

    # Detect start state: leftmost state (smallest x among detected states)
    start_candidate = min(ocr_results, key=lambda r: r["position"][0], default=None)

    cv_data = {
        "states": [r["label"] for r in ocr_results if r["label"]],
        "final_states": [r["label"] for r in ocr_results if r["position"] in final_positions and r["label"]],
        "start_state": start_candidate["label"] if start_candidate and start_candidate["label"] else "unknown",
        "state_details": ocr_results,   # full detail for debugging
    }
    return cv_data, img


# ══════════════════════════════════════════════════════════
#  STAGE 2 — VLM  (transition extractor, grounded by CV)
# ══════════════════════════════════════════════════════════

def build_grounded_prompt(cv_data: dict) -> str:
    """
    Passes CV-verified facts to the VLM so it cannot hallucinate states.
    The VLM is only asked to fill in transitions — what CV cannot do.
    """
    states_str       = ", ".join(cv_data["states"])      if cv_data["states"]       else "unknown"
    final_str        = ", ".join(cv_data["final_states"]) if cv_data["final_states"] else "none"
    start_str        = cv_data["start_state"]

    prompt = f"""
You are analyzing a DFA (Deterministic Finite Automaton) diagram.

VERIFIED FACTS from computer vision (do NOT change these):
  - States (Q)        : {states_str}
  - Start state (q0)  : {start_str}
  - Final states (F)  : {final_str}

YOUR ONLY TASK — read the arrows and edge labels in the image:
  - Determine the input alphabet (Sigma) from edge labels.
  - For every arrow, record: (from_state, input_symbol) -> to_state.
  - Self-loops count as transitions too.

STRICT RULES:
  1. Only use state names from this list: [{states_str}]. Do NOT invent new state names.
  2. If you cannot read an arrow clearly, use "?" as the symbol.
  3. Return ONLY valid JSON — no explanation, no markdown fences.

Required JSON schema:
{{
  "Q"     : ["list of states — copy exactly from above"],
  "Sigma" : ["list of input symbols"],
  "q0"    : "start state — copy exactly from above",
  "F"     : ["final states — copy exactly from above"],
  "delta" : {{
      "state_name": {{
          "symbol": "next_state",
          ...
      }},
      ...
  }}
}}
"""
    return prompt.strip()


def query_vlm(image_path: str, prompt: str) -> dict:
    """Calls Ollama VLM and parses JSON response."""
    print("\n[VLM] Sending grounded prompt to qwen2.5vl:3b ...")
    response = ollama.generate(
        model='qwen2.5vl:3b',
        prompt=prompt,
        images=[image_path]
    )
    raw = response['response']
    print(f"[VLM] Raw response:\n{raw}\n")

    # Strip markdown fences if model wraps in ```json ... ```
    cleaned = re.sub(r"```(?:json)?|```", "", raw).strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Try extracting JSON object with regex as fallback
        match = re.search(r'\{.*\}', cleaned, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
    print("[VLM] WARNING: Could not parse VLM response as JSON.")
    return {}


# ══════════════════════════════════════════════════════════
#  STAGE 3 — MERGE & VALIDATE  (anti-hallucination layer)
# ══════════════════════════════════════════════════════════

def merge_and_validate(cv_data: dict, vlm_data: dict) -> dict:
    """
    CV ground truth overrides VLM for states/start/final.
    VLM transitions are filtered to remove invented state names.
    """
    valid_states = set(cv_data["states"])

    # Override with CV-verified facts
    merged = {
        "Q"    : cv_data["states"],
        "Sigma": vlm_data.get("Sigma", []),
        "q0"   : cv_data["start_state"],
        "F"    : cv_data["final_states"],
        "delta": {}
    }

    # Validate transitions: reject any row/cell referencing unknown states
    raw_delta = vlm_data.get("delta", {})
    rejected = []

    for from_state, transitions in raw_delta.items():
        if from_state not in valid_states:
            rejected.append(f"  Dropped row '{from_state}' — not in CV states")
            continue
        merged["delta"][from_state] = {}
        if isinstance(transitions, dict):
            for symbol, to_state in transitions.items():
                if to_state not in valid_states and to_state != "?":
                    rejected.append(f"  Dropped ({from_state},{symbol})->'{to_state}' — unknown state")
                else:
                    merged["delta"][from_state][symbol] = to_state

    if rejected:
        print("\n[VALIDATE] Hallucinations removed:")
        for r in rejected:
            print(r)

    return merged


# ══════════════════════════════════════════════════════════
#  DRAW FINAL OUTPUT
# ══════════════════════════════════════════════════════════

def draw_output(img, cv_ocr_results, final_states_labels, output_path):
    output = img.copy()
    final_labels = set(final_states_labels)

    for r in cv_ocr_results:
        cx, cy = r["position"]
        radius = r["radius"]
        label = r["label"]
        is_final = label in final_labels

        color = (200, 100, 0) if is_final else (0, 180, 0)
        cv2.circle(output, (cx, cy), radius, color, 2)
        if is_final:
            cv2.circle(output, (cx, cy), radius - 10, (0, 0, 220), 2)

        tag = f"{label}*" if is_final else label
        cv2.putText(output, tag or "?", (cx - 18, cy - radius - 6),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (180, 0, 180), 2)

    cv2.imwrite(output_path, output)
    print(f"\n[DRAW] Saved annotated image → {output_path}")


# ══════════════════════════════════════════════════════════
#  MAIN PIPELINE
# ══════════════════════════════════════════════════════════

def extract_dfa(image_path: str, output_image: str = "dfa_final_output.png") -> dict:
    print("=" * 55)
    print("  DFA EXTRACTOR — CV + VLM Pipeline")
    print("=" * 55)

    # ── Stage 1: CV ──────────────────────────────────────
    print("\n[STAGE 1] Running computer vision analysis...")
    cv_data, img = run_cv_stage(image_path)

    print(f"  CV States found  : {cv_data['states']}")
    print(f"  CV Final states  : {cv_data['final_states']}")
    print(f"  CV Start state   : {cv_data['start_state']}")

    # ── Stage 2: VLM ─────────────────────────────────────
    print("\n[STAGE 2] Querying VLM for transitions...")
    prompt = build_grounded_prompt(cv_data)
    vlm_data = query_vlm(image_path, prompt)

    # ── Stage 3: Merge + Validate ─────────────────────────
    print("\n[STAGE 3] Merging CV facts with VLM transitions...")
    final_dfa = merge_and_validate(cv_data, vlm_data)

    # ── Draw output ───────────────────────────────────────
    draw_output(img, cv_data["state_details"], cv_data["final_states"], output_image)

    # ── Print result ──────────────────────────────────────
    print("\n" + "=" * 55)
    print("  FINAL DFA (7-tuple)")
    print("=" * 55)
    print(json.dumps(final_dfa, indent=2))

    # Save JSON
    json_path = output_image.replace(".png", ".json")
    with open(json_path, "w") as f:
        json.dump(final_dfa, f, indent=2)
    print(f"\n[DONE] DFA JSON saved")

    return final_dfa

def _dfa_json_to_text(dfa: dict) -> str:
    """Converts extracted DFA JSON to a text description for the KG builder."""
    lines = []
    Q     = dfa.get("Q", [])
    sigma = dfa.get("Sigma", [])
    q0    = dfa.get("q0", "unknown")
    F     = dfa.get("F", [])
    delta = dfa.get("delta", {})
    lines.append(f"DFA with states Q = {{{', '.join(Q)}}}.")
    lines.append(f"Input alphabet Sigma = {{{', '.join(sigma)}}}.")
    lines.append(f"Start state: {q0}.")
    lines.append(f"Final states F = {{{', '.join(F)}}}.")
    lines.append("Transitions:")
    for state, trans in delta.items():
        for sym, dest in trans.items():
            lines.append(f"  {state} on {sym} → {dest}")
    return "\n".join(lines)


# RUN
if __name__ == "__main__":
    import sys
    img_path =  "schema.jpg"
 
    result = extract_from_page(img_path)
    print(f"\nDetected type   : {result['content_type']}")
    print(f"Text content    : {result['text_content']}")
    print(f"DFA JSON present: {result['dfa_json'] is not None}")
    print(f"Combined text   :\n{result['combined_text']}")