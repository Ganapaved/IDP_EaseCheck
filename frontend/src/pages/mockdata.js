export const mockevaluation = {
  "final_score": 52.29,
  "content_type": "derivation",
  "weights": {
    "formula_exact": 0.15,
    "symbolic": 0.25,
    "step_order": 0.3,
    "llm_judge": 0.3
  },
  "layer_scores": {
    "formula_exact": 9.02,
    "symbolic": 11.76,
    "step_order": 60.0,
    "llm_judge": 100.0
  },
  "layer_details": {
    "formula_exact": {
      "score": 9.02,
      "jaccard": 0.0588,
      "recall": 0.1111,
      "precision": 0.1111,
      "f1": 0.1111,
      "matched_count": 1,
      "schema_count": 9,
      "student_count": 9,
      "missing_formulas": [
        "2I = \\int_{0}^{\\pi/2} \\frac{\\cos^4 x + \\sin^4 x}{\\sin^4 x + \\cos^4 x} dx",
        "2I = \\int_{0}^{\\pi/2} dx = [x]_{0}^{\\pi/2} = [\\frac{\\pi}{2} - 0]",
        "\\Rightarrow \\int_{0}^{\\pi/2} \\frac{\\cos^4 x}{\\sin^4 x + \\cos^4 x} dx \\text{ ...(ii)}",
        "[\\because \\int_{0}^{a} f(x) = \\int_{0}^{a} f(a-x)]",
        "\\int_{0}^{\\pi/2} \\frac{\\sin^4 x}{\\sin^4 x + \\cos^4 x} dx",
        "\\int_{0}^{a} f(x) = \\int_{0}^{a} f(a-x)"
      ],
      "extra_formulas": [
        "\\int_0^{\\pi/2} \\frac{\\sin^4 x}{\\sin^4 x + \\cos^4 x} dx",
        "2I = \\int_0^{\\pi/2} dx = [x]_0^{\\pi/2} = [ \\frac{\\pi}{2} - 0 ]",
        "I = \\int_0^{\\pi/2} \\frac{\\sin^4 x}{\\sin^4 x + \\cos^4 x} dx",
        "= \\int_0^{\\pi/2} \\frac{\\sin^4 ( \\frac{\\pi}{2} - x )}{\\sin^4 ( \\frac{\\pi}{2} - x ) + \\cos^4 ( \\frac{\\pi}{2} - x )} dx"
      ]
    },
    "symbolic": {
      "score": 11.76,
      "matched_count": 2,
      "schema_count": 17,
      "equivalent_pairs": [
        [
          "2I = \\frac{\\pi}{2} \\Rightarrow I = \\frac{\\pi}{4}",
          "2I = \\frac{\\pi}{2} \\Rightarrow I = \\frac{\\pi}{4}"
        ],
        [
          "2I = \\frac{\\pi}{2} \\Rightarrow I = \\frac{\\pi}{4}",
          "2I = \\frac{\\pi}{2} \\Rightarrow I = \\frac{\\pi}{4}"
        ]
      ],
      "unmatched_formulas": [
        "= \\int_{0}^{\\pi/2} \\frac{\\sin^4 \\left(\\frac{\\pi}{2} - x\\right)}{\\sin^4 \\left(\\frac{\\pi}{2} - x\\right) + \\cos^4 \\left(\\frac{\\pi}{2} - x\\right)} dx",
        "I = \\int_{0}^{\\pi/2} \\frac{\\cos^4 x}{\\cos^4 x + \\sin^4 x} dx",
        "\\Rightarrow \\int_{0}^{\\pi/2} \\frac{\\cos^4 x}{\\sin^4 x + \\cos^4 x} dx \\text{ ...(ii)}",
        "2I = \\int_{0}^{\\pi/2} \\frac{\\cos^4 x + \\sin^4 x}{\\sin^4 x + \\cos^4 x} dx",
        "2I = \\int_{0}^{\\pi/2} dx = [x]_{0}^{\\pi/2} = \\left[\\frac{\\pi}{2} - 0\\right]"
      ],
      "sympy_available": true
    },
    "step_order": {
      "score": 60.0,
      "coverage": 0.5,
      "order_score": 0.5,
      "completeness": 1.0,
      "schema_steps": 6,
      "student_steps": 14,
      "lcs_length": 3,
      "missing_at_positions": [
        1,
        3,
        5
      ]
    },
    "llm_judge": {
      "score": 100.0,
      "dimensions": {
        "formulas": {
          "score": 25,
          "max": 25,
          "errors": [],
          "notes": "All necessary formulas including the integral property and trigonometric identities were correctly stated and used."
        },
        "steps": {
          "score": 35,
          "max": 35,
          "errors": [],
          "notes": "The logical flow from applying the reflection property to adding the two integrals and evaluating the final result was perfect."
        },
        "theorems": {
          "score": 20,
          "max": 20,
          "errors": [],
          "notes": "Correct application of the reflection property for definite integrals."
        },
        "variables": {
          "score": 10,
          "max": 10,
          "errors": [],
          "notes": "Variables I and x were handled correctly with appropriate bounds."
        },
        "concepts": {
          "score": 10,
          "max": 10,
          "errors": [],
          "notes": "Full understanding of the symmetry-based method for solving this type of integral."
        }
      },
      "correct_steps": [
        "Step 1: Correctly defined the initial integral I.",
        "Step 2: Correctly applied the property f(a-x).",
        "Step 3: Correctly converted sine to cosine in the numerator and denominator.",
        "Step 4: Correctly added equation (i) and (ii) to eliminate the trigonometric terms.",
        "Step 5: Correctly evaluated the integral of 1 over the interval.",
        "Step 6: Correctly solved for I."
      ],
      "wrong_steps": [],
      "missing": [],
      "overall_feedback": "The student provided a perfect solution. Every step follows the schema precisely, all formulas are correctly written, and the final answer is correct. No errors were found."
    }
  },
  "feedback": [
    "Partial credit. Key steps or formulas are missing or wrong.",
    "Missing formulas: ['2I = \\\\int_{0}^{\\\\pi/2} \\\\frac{\\\\cos^4 x + \\\\sin^4 x}{\\\\sin^4 x + \\\\cos^4 x} dx', '2I = \\\\int_{0}^{\\\\pi/2} dx = [x]_{0}^{\\\\pi/2} = [\\\\frac{\\\\pi}{2} - 0]', '\\\\Rightarrow \\\\int_{0}^{\\\\pi/2} \\\\frac{\\\\cos^4 x}{\\\\sin^4 x + \\\\cos^4 x} dx \\\\text{ ...(ii)}']",
    "Incorrect/extra formulas written: ['\\\\int_0^{\\\\pi/2} \\\\frac{\\\\sin^4 x}{\\\\sin^4 x + \\\\cos^4 x} dx', '2I = \\\\int_0^{\\\\pi/2} dx = [x]_0^{\\\\pi/2} = [ \\\\frac{\\\\pi}{2} - 0 ]']",
    "These schema formulas could not be matched symbolically: ['= \\\\int_{0}^{\\\\pi/2} \\\\frac{\\\\sin^4 \\\\left(\\\\frac{\\\\pi}{2} - x\\\\right)}{\\\\sin^4 \\\\left(\\\\frac{\\\\pi}{2} - x\\\\right) + \\\\cos^4 \\\\left(\\\\frac{\\\\pi}{2} - x\\\\right)} dx', 'I = \\\\int_{0}^{\\\\pi/2} \\\\frac{\\\\cos^4 x}{\\\\cos^4 x + \\\\sin^4 x} dx', '\\\\Rightarrow \\\\int_{0}^{\\\\pi/2} \\\\frac{\\\\cos^4 x}{\\\\sin^4 x + \\\\cos^4 x} dx \\\\text{ ...(ii)}']",
    "Steps missing at positions: [1, 3, 5]",
    "Derivation steps are present but in wrong order."
  ],
  "correct_steps": [
    "Step 1: Correctly defined the initial integral I.",
    "Step 2: Correctly applied the property f(a-x).",
    "Step 3: Correctly converted sine to cosine in the numerator and denominator.",
    "Step 4: Correctly added equation (i) and (ii) to eliminate the trigonometric terms.",
    "Step 5: Correctly evaluated the integral of 1 over the interval.",
    "Step 6: Correctly solved for I."
  ],
  "wrong_steps": [],
  "llm_feedback": "The student provided a perfect solution. Every step follows the schema precisely, all formulas are correctly written, and the final answer is correct. No errors were found."
}


export const mockmath = {
  "content_type": "derivation",
  "latex_blocks": [
    "\\int_{0}^{\\pi/2} \\frac{\\sin^4 x}{\\sin^4 x + \\cos^4 x} dx",
    "= \\int_{0}^{\\pi/2} \\frac{\\sin^4 \\left( \\frac{\\pi}{2} - x \\right)}{\\sin^4 \\left( \\frac{\\pi}{2} - x \\right) + \\cos^4 \\left( \\frac{\\pi}{2} - x \\right)} dx",
    "\\left[ \\because \\int_{0}^{a} f(x) dx = \\int_{0}^{a} f(a - x) dx \\right]",
    "I = \\int_{0}^{\\pi/2} \\frac{\\cos^4 x}{\\cos^4 x + \\sin^4 x} dx",
    "\\Rightarrow \\int_{0}^{\\pi/2} \\frac{\\cos^4 x}{\\sin^4 x + \\cos^4 x} dx",
    "2I = \\int_{0}^{\\pi/2} \\frac{\\cos^4 x + \\sin^4 x}{\\sin^4 x + \\cos^4 x} dx",
    "2I = \\int_{0}^{\\pi/2} dx = [x]_{0}^{\\pi/2} = \\left[ \\frac{\\pi}{2} - 0 \\right]",
    "2I = \\frac{\\pi}{2} \\Rightarrow I = \\frac{\\pi}{4}"
  ],
  "text_blocks": [
    "Q. 30. Evaluate",
    "Sol. Given, ...(i)",
    "Step 3: Adding Eqs. (i) and (ii), we have"
  ],
  "steps": [
    {
      "step": 1,
      "content": "$= \\int_{0}^{\\pi/2} \\frac{\\sin^4 \\left( \\frac{\\pi}{2} - x \\right)}{\\sin^4 \\left( \\frac{\\pi}{2} - x \\right) + \\cos^4 \\left( \\frac{\\pi}{2} - x \\right)} dx$\n$\\left[ \\because \\int_{0}^{a} f(x) dx = \\int_{0}^{a} f(a - x) dx \\right]$",
      "latex": [
        "= \\int_{0}^{\\pi/2} \\frac{\\sin^4 \\left( \\frac{\\pi}{2} - x \\right)}{\\sin^4 \\left( \\frac{\\pi}{2} - x \\right) + \\cos^4 \\left( \\frac{\\pi}{2} - x \\right)} dx",
        "\\left[ \\because \\int_{0}^{a} f(x) dx = \\int_{0}^{a} f(a - x) dx \\right]"
      ]
    },
    {
      "step": 2,
      "content": "$I = \\int_{0}^{\\pi/2} \\frac{\\cos^4 x}{\\cos^4 x + \\sin^4 x} dx$\n$\\Rightarrow \\int_{0}^{\\pi/2} \\frac{\\cos^4 x}{\\sin^4 x + \\cos^4 x} dx$ ...(ii)",
      "latex": [
        "I = \\int_{0}^{\\pi/2} \\frac{\\cos^4 x}{\\cos^4 x + \\sin^4 x} dx",
        "\\Rightarrow \\int_{0}^{\\pi/2} \\frac{\\cos^4 x}{\\sin^4 x + \\cos^4 x} dx"
      ]
    },
    {
      "step": 3,
      "content": "Adding Eqs. (i) and (ii), we have\n$2I = \\int_{0}^{\\pi/2} \\frac{\\cos^4 x + \\sin^4 x}{\\sin^4 x + \\cos^4 x} dx$",
      "latex": [
        "2I = \\int_{0}^{\\pi/2} \\frac{\\cos^4 x + \\sin^4 x}{\\sin^4 x + \\cos^4 x} dx"
      ]
    },
    {
      "step": 4,
      "content": "$2I = \\int_{0}^{\\pi/2} dx = [x]_{0}^{\\pi/2} = \\left[ \\frac{\\pi}{2} - 0 \\right]$",
      "latex": [
        "2I = \\int_{0}^{\\pi/2} dx = [x]_{0}^{\\pi/2} = \\left[ \\frac{\\pi}{2} - 0 \\right]"
      ]
    },
    {
      "step": 5,
      "content": "$2I = \\frac{\\pi}{2} \\Rightarrow I = \\frac{\\pi}{4}$",
      "latex": [
        "2I = \\frac{\\pi}{2} \\Rightarrow I = \\frac{\\pi}{4}"
      ]
    }
  ],
  "variables": {},
  "combined_text": "Mathematical expressions:\n  \\int_{0}^{\\pi/2} \\frac{\\sin^4 x}{\\sin^4 x + \\cos^4 x} dx\n  = \\int_{0}^{\\pi/2} \\frac{\\sin^4 \\left( \\frac{\\pi}{2} - x \\right)}{\\sin^4 \\left( \\frac{\\pi}{2} - x \\right) + \\cos^4 \\left( \\frac{\\pi}{2} - x \\right)} dx\n  \\left[ \\because \\int_{0}^{a} f(x) dx = \\int_{0}^{a} f(a - x) dx \\right]\n  I = \\int_{0}^{\\pi/2} \\frac{\\cos^4 x}{\\cos^4 x + \\sin^4 x} dx\n  \\Rightarrow \\int_{0}^{\\pi/2} \\frac{\\cos^4 x}{\\sin^4 x + \\cos^4 x} dx\n  2I = \\int_{0}^{\\pi/2} \\frac{\\cos^4 x + \\sin^4 x}{\\sin^4 x + \\cos^4 x} dx\n  2I = \\int_{0}^{\\pi/2} dx = [x]_{0}^{\\pi/2} = \\left[ \\frac{\\pi}{2} - 0 \\right]\n  2I = \\frac{\\pi}{2} \\Rightarrow I = \\frac{\\pi}{4}\n\nDerivation steps:\n  Step 1: $= \\int_{0}^{\\pi/2} \\frac{\\sin^4 \\left( \\frac{\\pi}{2} - x \\right)}{\\sin^4 \\left( \\frac{\\pi}{2} - x \\right) + \\cos^4 \\left( \\frac{\\pi}{2} - x \\right)} dx$\n$\\left[ \\because \\int_{0}^{a} f(x) dx = \\int_{0}^{a} f(a - x) dx \\right]$\n  Step 2: $I = \\int_{0}^{\\pi/2} \\frac{\\cos^4 x}{\\cos^4 x + \\sin^4 x} dx$\n$\\Rightarrow \\int_{0}^{\\pi/2} \\frac{\\cos^4 x}{\\sin^4 x + \\cos^4 x} dx$ ...(ii)\n  Step 3: Adding Eqs. (i) and (ii), we have\n$2I = \\int_{0}^{\\pi/2} \\frac{\\cos^4 x + \\sin^4 x}{\\sin^4 x + \\cos^4 x} dx$\n  Step 4: $2I = \\int_{0}^{\\pi/2} dx = [x]_{0}^{\\pi/2} = \\left[ \\frac{\\pi}{2} - 0 \\right]$\n  Step 5: $2I = \\frac{\\pi}{2} \\Rightarrow I = \\frac{\\pi}{4}$\n\nExplanation:\n  Q. 30. Evaluate\n  Sol. Given, ...(i)\n  Step 3: Adding Eqs. (i) and (ii), we have",
  "raw_transcript": "CONTENT_CLASS: derivation\n\nQ. 30. Evaluate $\\int_{0}^{\\pi/2} \\frac{\\sin^4 x}{\\sin^4 x + \\cos^4 x} dx$\n\nSol. Given, $\\int_{0}^{\\pi/2} \\frac{\\sin^4 x}{\\sin^4 x + \\cos^4 x} dx$ ...(i)\n\nStep 1: $= \\int_{0}^{\\pi/2} \\frac{\\sin^4 \\left( \\frac{\\pi}{2} - x \\right)}{\\sin^4 \\left( \\frac{\\pi}{2} - x \\right) + \\cos^4 \\left( \\frac{\\pi}{2} - x \\right)} dx$\n$\\left[ \\because \\int_{0}^{a} f(x) dx = \\int_{0}^{a} f(a - x) dx \\right]$\n\nStep 2: $I = \\int_{0}^{\\pi/2} \\frac{\\cos^4 x}{\\cos^4 x + \\sin^4 x} dx$\n$\\Rightarrow \\int_{0}^{\\pi/2} \\frac{\\cos^4 x}{\\sin^4 x + \\cos^4 x} dx$ ...(ii)\n\nStep 3: Adding Eqs. (i) and (ii), we have\n$2I = \\int_{0}^{\\pi/2} \\frac{\\cos^4 x + \\sin^4 x}{\\sin^4 x + \\cos^4 x} dx$\n\nStep 4: $2I = \\int_{0}^{\\pi/2} dx = [x]_{0}^{\\pi/2} = \\left[ \\frac{\\pi}{2} - 0 \\right]$\n\nStep 5: $2I = \\frac{\\pi}{2} \\Rightarrow I = \\frac{\\pi}{4}$"
}

export const mocktocext = 
{
  "Q": [
    "q0",
    "q3",
    "q1",
    "q4",
    "q2",
    "q5"
  ],
  "Sigma": [
    "0",
    "1"
  ],
  "q0": "q0",
  "F": [
    "q1",
    "q4",
    "q2"
  ],
  "delta": {
    "q0": {
      "0": "q3",
      "?": "q0"
    },
    "q3": {
      "1": "q4",
      "?": "q3"
    },
    "q1": {
      "0": "q0",
      "1": "q5"
    },
    "q2": {
      "0": "q4",
      "1": "q2"
    },
    "q4": {
      "0": "q5",
      "1": "q2"
    },
    "q5": {
      "0": "?",
      "1": "q2"
    }
  }
}

export const mocktoceval = 
{
  "final_score": 1.64,
  "content_type": "mixed",
  "weights": {
    "formula_exact": 0.2,
    "symbolic": 0.25,
    "step_order": 0.2,
    "llm_judge": 0.35
  },
  "layer_scores": {
    "formula_exact": 0.0,
    "symbolic": 0.0,
    "step_order": 100.0,
    "llm_judge": 60.0
  },
  "layer_details": {
    "formula_exact": {
      "score": 0.0,
      "jaccard": 0.0,
      "recall": 0.0,
      "precision": 0.0,
      "f1": 0.0,
      "matched_count": 0,
      "schema_count": 9,
      "student_count": 18,
      "missing_formulas": [
        "\\begin{array}{ccc} & S.P(x) & I.B(y) \\\\ P & 2000 & 1500 \\\\ si & 5 & 3 & 300 \\\\ la & 3 & 4 & 240 \\end{array}",
        "3x + 4y \\le 240",
        "\\text{subject to:}",
        "x, y \\ge 0",
        "x - 2y \\le 0",
        "1a"
      ],
      "extra_formulas": [
        "Z = 90,000",
        "Z = 120,000",
        "5x + 3y \\leq 300",
        "3x + 4y \\leq 240"
      ]
    },
    "symbolic": {
      "score": 0.0,
      "matched_count": 0,
      "schema_count": 16,
      "equivalent_pairs": [],
      "unmatched_formulas": [
        "5x + 3y \\le 300",
        "5x + 3y \\le 300",
        "3x + 4y \\le 240",
        "3x + 4y \\le 240",
        "x - 2y \\le 0"
      ],
      "sympy_available": true
    },
    "step_order": {
      "score": 100.0,
      "coverage": 1.0,
      "order_score": 1.0,
      "completeness": 1.0,
      "schema_steps": 1,
      "student_steps": 10,
      "lcs_length": 1,
      "missing_at_positions": []
    },
    "llm_judge": {
      "score": 60.0,
      "dimensions": {
        "formulas": {
          "score": 20,
          "max": 25,
          "errors": [
            "Missing constraint: x - 2y \u2264 0 (or y \u2265 x/2)"
          ],
          "notes": "The student successfully identified the objective function and two of the primary constraints, but missed the relational constraint between x and y."
        },
        "steps": {
          "score": 15,
          "max": 35,
          "errors": [
            "Failed to determine the feasible region.",
            "Included points (e.g., (80,0)) that violate other constraints.",
            "Did not calculate the intersection point of the boundary lines."
          ],
          "notes": "While the student correctly calculated intercepts for individual lines, they did not find the intersection of the constraints or verify if the points belonged to the feasible region."
        },
        "theorems": {
          "score": 12,
          "max": 20,
          "errors": [
            "Improper application of the Corner Point Method."
          ],
          "notes": "The student knows to check boundary points for a maximum, but failed to identify which points are valid vertices of the feasible region defined by the system of inequalities."
        },
        "variables": {
          "score": 8,
          "max": 10,
          "errors": [],
          "notes": "Variables x and y are used consistently, and non-negativity constraints are stated."
        },
        "concepts": {
          "score": 5,
          "max": 10,
          "errors": [
            "Misunderstanding of 'subject to' constraints in Linear Programming."
          ],
          "notes": "The student treated each constraint in isolation rather than as a simultaneous system."
        }
      },
      "correct_steps": [
        "Correct identification of the objective function Z = 2000x + 1500y.",
        "Correct calculation of intercepts for the line 5x + 3y = 300.",
        "Correct calculation of intercepts for the line 3x + 4y = 240."
      ],
      "wrong_steps": [
        "Step 4: Claiming Z = 160,000 at (80, 0) is valid; (80,0) violates 5x + 3y \u2264 300 (400 \u2264 300 is false).",
        "Ignoring the constraint x - 2y \u2264 0 entirely during point testing."
      ],
      "missing": [
        "The constraint x - 2y \u2264 0.",
        "Calculation of the intersection point of 5x + 3y = 300 and 3x + 4y = 240.",
        "Feasibility check for the boundary points."
      ],
      "overall_feedback": "The student demonstrates a basic grasp of setting up an LP problem and calculating objective values. However, they failed to recognize that the solution must satisfy all constraints simultaneously. The chosen 'maximum' point (80,0) is outside the feasible region defined by the first constraint. Greater attention to the intersection of inequalities and the feasible region is needed."
    }
  },
  "feedback": [
    "Significant mathematical errors. Please review.",
    "Missing formulas: ['\\\\begin{array}{ccc} & S.P(x) & I.B(y) \\\\\\\\ P & 2000 & 1500 \\\\\\\\ si & 5 & 3 & 300 \\\\\\\\ la & 3 & 4 & 240 \\\\end{array}', '3x + 4y \\\\le 240', '\\\\text{subject to:}']",
    "Incorrect/extra formulas written: ['Z = 90,000', 'Z = 120,000']",
    "These schema formulas could not be matched symbolically: ['5x + 3y \\\\le 300', '5x + 3y \\\\le 300', '3x + 4y \\\\le 240']",
    "Step error: Step 4: Claiming Z = 160,000 at (80, 0) is valid; (80,0) violates 5x + 3y \u2264 300 (400 \u2264 300 is false).",
    "Step error: Ignoring the constraint x - 2y \u2264 0 entirely during point testing.",
    "Missing: The constraint x - 2y \u2264 0.",
    "Missing: Calculation of the intersection point of 5x + 3y = 300 and 3x + 4y = 240."
  ],
  "correct_steps": [
    "Correct identification of the objective function Z = 2000x + 1500y.",
    "Correct calculation of intercepts for the line 5x + 3y = 300.",
    "Correct calculation of intercepts for the line 3x + 4y = 240."
  ],
  "wrong_steps": [
    "Step 4: Claiming Z = 160,000 at (80, 0) is valid; (80,0) violates 5x + 3y \u2264 300 (400 \u2264 300 is false).",
    "Ignoring the constraint x - 2y \u2264 0 entirely during point testing."
  ],
  "llm_feedback": "The student demonstrates a basic grasp of setting up an LP problem and calculating objective values. However, they failed to recognize that the solution must satisfy all constraints simultaneously. The chosen 'maximum' point (80,0) is outside the feasible region defined by the first constraint. Greater attention to the intersection of inequalities and the feasible region is needed."
}

export const mocktoc2 = {
  "final_score": 84.49,
  "question_type": "diagram+text",
  "weights": {
    "exact": 0.2,
    "semantic": 0.25,
    "graph": 0.25,
    "llm": 0.3
  },
  "layer_scores": {
    "exact_match": 89.17,
    "semantic": 99.82,
    "graph_structure": 60.0,
    "llm_judge": 89.0
  },
  "layer_details": {
    "exact_match": {
      "score": 89.17,
      "node_jaccard": 1.0,
      "edge_jaccard": 0.8333,
      "missing_nodes": [],
      "extra_nodes": [],
      "missing_edges": [
        [
          "q1",
          "TRANSITIONS_ON",
          "q4"
        ]
      ],
      "wrong_edges": [
        [
          "q1",
          "TRANSITIONS_ON",
          "q5"
        ]
      ]
    },
    "semantic": {
      "score": 99.82,
      "node_similarity": 1.0,
      "edge_similarity": 0.9964,
      "type_similarity": 1.0
    },
    "graph_structure": {
      "score": 60.0,
      "wl_kernel": 0.0,
      "ged_score": 1.0,
      "subgraph_coverage": 1.0
    },
    "llm_judge": {
      "score": 89.0,
      "dimensions": {
        "entities": {
          "score": 20,
          "max": 20,
          "errors": [],
          "notes": "All 6 states (q0, q1, q2, q3, q4, q5) are correctly identified with their labels and `State` type, matching the schema perfectly."
        },
        "start_final": {
          "score": 17,
          "max": 20,
          "errors": [
            "State 'q4' is incorrectly marked as not a final state."
          ],
          "notes": "The start state `q0` is correctly identified. However, the student failed to mark `q4` as a final state, missing one out of three correct final states."
        },
        "transitions": {
          "score": 32,
          "max": 40,
          "errors": [
            "Transition from 'q1' to 'q5' is incorrect; it should be 'q1' to 'q4'."
          ],
          "notes": "10 out of 11 transitions are correctly identified. The transition originating from `q1` is incorrectly directed to `q5` instead of `q4`. This is a significant error as it alters the accepted language of the automaton, leading to a heavy penalty."
        },
        "concepts": {
          "score": 20,
          "max": 20,
          "errors": [],
          "notes": "The student has correctly used all specified predicates (`is_final`, `is_start`, `type`) and the relation (`TRANSITIONS_ON`) as defined in the schema. This demonstrates a strong conceptual understanding of how to represent the components and relationships of a finite automaton in a knowledge graph."
        }
      },
      "overall_feedback": "The student provided a largely accurate representation of the finite automaton. Most states, their properties, and transitions are correctly identified. However, there is a critical error in failing to mark one final state and an incorrect target for one transition, which significantly impacts the machine's behavior.",
      "strengths": [
        "All states are correctly identified with their labels and types.",
        "The start state is correctly identified.",
        "Most final states are correctly identified.",
        "The majority of transitions (10 out of 11) are accurate.",
        "Excellent conceptual understanding of using predicates and relations to represent automata components."
      ],
      "weaknesses": [
        "Failed to mark state 'q4' as a final state.",
        "Incorrectly represented the transition from 'q1', directing it to 'q5' instead of 'q4'."
      ]
    }
  },
  "feedback": [
    "Good attempt with some errors.",
    "Missing relations: [['q1', 'TRANSITIONS_ON', 'q4']]",
    "Wrong relations: [['q1', 'TRANSITIONS_ON', 'q5']]",
    "Graph structure significantly differs from schema.",
    "Failed to mark state 'q4' as a final state.",
    "Incorrectly represented the transition from 'q1', directing it to 'q5' instead of 'q4'."
  ],
  "llm_feedback": "The student provided a largely accurate representation of the finite automaton. Most states, their properties, and transitions are correctly identified. However, there is a critical error in failing to mark one final state and an incorrect target for one transition, which significantly impacts the machine's behavior.",
  "strengths": [
    "All states are correctly identified with their labels and types.",
    "The start state is correctly identified.",
    "Most final states are correctly identified.",
    "The majority of transitions (10 out of 11) are accurate.",
    "Excellent conceptual understanding of using predicates and relations to represent automata components."
  ]
}

