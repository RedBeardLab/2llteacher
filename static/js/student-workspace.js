/* ============================================================
   LLTeacher — Student workspace (frontend-only)
   Powers the reasoning checker and the AI tutor quick-action
   panel on the section workspace. No backend calls.
   ============================================================ */
(function () {
    "use strict";

    /* ---------- Reasoning checker ---------- */
    const wsRoot = document.querySelector("[data-student-workspace]");
    if (wsRoot) initReasoningChecker(wsRoot);

    /* ---------- Tutor quick-action panel ---------- */
    const tutorPanel = document.querySelector("[data-student-tutor]");
    if (tutorPanel) initTutorPanel(tutorPanel, wsRoot);

    /* ============================================================ */

    function initReasoningChecker(root) {
        const textarea = root.querySelector(".reasoning-textarea");
        const meterFill = root.querySelector(".reasoning-meter .meter-fill");
        const keywordChips = root.querySelectorAll(".reasoning-keyword");
        const checkBtn = root.querySelector("[data-check-reasoning]");
        const feedback = root.querySelector(".reasoning-feedback");
        if (!textarea) return;

        const KEYWORDS = [
            { word: "calculation", re: /\b(calcul|computed|computation)/i },
            { word: "formula",     re: /\b(formula|equation|expression)\b/i },
            { word: "step",        re: /\b(step|steps|first|then|next|finally)\b/i },
            { word: "because",     re: /\b(because|since|therefore|so that|so,|thus|hence)\b/i },
            { word: "conclusion",  re: /\b(answer|result|conclude|conclusion)\b/i },
        ];

        function updateMeter() {
            const text = textarea.value || "";
            let hits = 0;
            KEYWORDS.forEach((k, i) => {
                const matched = k.re.test(text);
                const chip = keywordChips[i];
                if (chip) chip.classList.toggle("hit", matched);
                if (matched) hits++;
            });
            const pct = (hits / KEYWORDS.length) * 100;
            if (meterFill) {
                meterFill.style.width = pct + "%";
                if (pct >= 80) meterFill.style.background = "var(--s-green)";
                else if (pct >= 40) meterFill.style.background = "var(--s-amber)";
                else meterFill.style.background = "var(--s-red)";
            }
            return { hits, total: KEYWORDS.length, length: text.trim().length };
        }

        function showFeedback(kind, title, body) {
            if (!feedback) return;
            feedback.className = "reasoning-feedback " + kind;
            feedback.innerHTML =
                '<div class="fb-body"><div class="fb-title">' + title + '</div><div>' + body + '</div></div>';
            feedback.hidden = false;
        }

        textarea.addEventListener("input", updateMeter);

        if (checkBtn) {
            checkBtn.addEventListener("click", function (e) {
                e.preventDefault();
                const r = updateMeter();
                if (r.length < 20) {
                    showFeedback("incorrect", "Write a bit more",
                        "Add a few sentences explaining how you worked through the problem before checking.");
                    return;
                }
                if (r.hits >= 4) {
                    showFeedback("correct", "Strong explanation",
                        "Your reasoning covers the key elements — the steps you took, why, and how you reached your conclusion.");
                } else if (r.hits >= 2) {
                    showFeedback("partial", "Good start",
                        "You're on the right track. Try to be more explicit about your steps, the formula or rule you used, and why your answer follows from it.");
                } else {
                    showFeedback("incorrect", "Explanation needs more detail",
                        "Walk through your calculation step by step. Mention the formula or rule you used and why your conclusion follows.");
                }
            });
        }

        updateMeter();
        // Expose meter helper for tutor panel
        root.__getReasoningStats = updateMeter;
    }

    function initTutorPanel(panel, wsRoot) {
        const response = panel.querySelector(".tp-response");
        const responseText = panel.querySelector(".tp-response .tp-text");

        const RESPONSES = {
            hint: "Start by writing down what you're given. Then identify what you need to find. The path between often points to the formula you should use.",
            formula: "Write the formula first, then substitute your values one step at a time. Say why each step follows from the one before it.",
            missing: "Compare your reasoning to your final answer. Does each step explain why your conclusion follows? If a step is implicit, make it explicit.",
            check: function () {
                if (!wsRoot || typeof wsRoot.__getReasoningStats !== "function") {
                    return "Open the reasoning textarea above and write a few sentences first. I'll check whether your explanation covers the key steps.";
                }
                const r = wsRoot.__getReasoningStats();
                if (r.length < 20) {
                    return "Write a few sentences in your reasoning textarea first, then I can check whether your explanation covers the steps, the rule you used, and the conclusion.";
                }
                if (r.hits >= 4) {
                    return "Your reasoning is solid — it covers steps, the rule behind them, and how you reached your answer. Ready to discuss anything specific?";
                }
                if (r.hits >= 2) {
                    return "Good direction. To make it stronger, be more explicit about the formula or rule you applied, and why your conclusion follows from it.";
                }
                return "Your explanation could use more structure. Walk through your steps one by one, name the rule or formula you used, and connect that to your answer.";
            },
        };

        function showResponse(text) {
            if (!response || !responseText) return;
            responseText.textContent = text;
            response.hidden = false;
            // Re-trigger entrance animation
            response.style.animation = "none";
            void response.offsetWidth;
            response.style.animation = "";
        }

        panel.addEventListener("click", function (e) {
            const btn = e.target.closest("[data-tutor-action]");
            if (!btn) return;
            e.preventDefault();
            const action = btn.dataset.tutorAction;
            const value = RESPONSES[action];
            const text = typeof value === "function" ? value() : value;
            if (text) showResponse(text);
        });
    }
})();
