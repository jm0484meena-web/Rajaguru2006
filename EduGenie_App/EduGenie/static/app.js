/* EduGenie frontend. No libraries needed. */
(function () {
  "use strict";

  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

  // ---------- safe text helpers ----------
  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }

  // Tiny markdown -> HTML (headings, bullets, numbers, bold). Text is escaped FIRST, so it is safe.
  function renderMarkdown(text) {
    const lines = escapeHtml(text).split(/\r?\n/);
    const inline = (s) => {
      const linked = s.replace(/https?:\/\/[^\s<]+/g, (url) => {
        const clean = url.replace(/[),.;!?]+$/, "");
        return `<a href="${clean}" target="_blank" rel="noopener noreferrer">${clean}</a>${url.slice(clean.length)}`;
      });
      return linked.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>").replace(/`(.+?)`/g, "<code>$1</code>");
    };
    let html = "";
    let list = null; // "ul" | "ol" | null
    const close = () => { if (list) { html += `</${list}>`; list = null; } };
    for (const raw of lines) {
      const line = raw.trim();
      let m;
      if (!line) { close(); continue; }
      if ((m = line.match(/^#{1,4}\s+(.*)$/))) { close(); html += `<h4>${inline(m[1])}</h4>`; }
      else if ((m = line.match(/^[-*•]\s+(.*)$/))) { if (list !== "ul") { close(); html += "<ul>"; list = "ul"; } html += `<li>${inline(m[1])}</li>`; }
      else if ((m = line.match(/^\d+[.)]\s+(.*)$/))) { if (list !== "ol") { close(); html += "<ol>"; list = "ol"; } html += `<li>${inline(m[1])}</li>`; }
      else { close(); html += `<p>${inline(line)}</p>`; }
    }
    close();
    return html;
  }

  // ---------- tabs (mouse, touch and arrow keys) ----------
  const tabs = $$(".tab");
  function selectTab(tab, focus) {
    tabs.forEach((t) => {
      const on = t === tab;
      t.setAttribute("aria-selected", on ? "true" : "false");
      t.tabIndex = on ? 0 : -1;
      $("#" + t.getAttribute("aria-controls")).hidden = !on;
    });
    if (focus) tab.focus();
  }
  tabs.forEach((tab, i) => {
    tab.addEventListener("click", () => selectTab(tab, false));
    tab.addEventListener("keydown", (e) => {
      let next = null;
      if (e.key === "ArrowRight" || e.key === "ArrowDown") next = tabs[(i + 1) % tabs.length];
      if (e.key === "ArrowLeft" || e.key === "ArrowUp") next = tabs[(i - 1 + tabs.length) % tabs.length];
      if (e.key === "Home") next = tabs[0];
      if (e.key === "End") next = tabs[tabs.length - 1];
      if (next) { e.preventDefault(); selectTab(next, true); }
    });
  });

  // ---------- API call ----------
  async function callApi(url, body, method = "POST") {
    let res;
    try {
      res = await fetch(url, {
        method,
        headers: body ? { "Content-Type": "application/json" } : {},
        body: body ? JSON.stringify(body) : undefined,
      });
    } catch (e) {
      throw new Error("Cannot reach the server. Check your internet and that the app is running.");
    }
    let data = {};
    try { data = await res.json(); } catch (e) { /* ignore */ }
    if (!res.ok) throw new Error(data.detail || "Something went wrong. Please try again.");
    return data;
  }

  // ---------- result renderers ----------
  function showLoading(box) {
    box.hidden = false;
    box.className = "result";
    box.setAttribute("aria-busy", "true");
    box.innerHTML = '<div class="loading"><div class="spinner" aria-hidden="true"></div><span>EduGenie is thinking…</span></div>';
  }

  function showError(box, message) {
    box.hidden = false;
    box.className = "result error";
    box.setAttribute("aria-busy", "false");
    box.setAttribute("role", "alert");
    box.innerHTML = `<strong>Oops!</strong>${escapeHtml(message)}`;
  }

  function showText(box, title, text) {
    box.className = "result";
    box.removeAttribute("role");
    box.setAttribute("aria-busy", "false");
    box.innerHTML = `<h3>${escapeHtml(title)}</h3>${renderMarkdown(text)}
      <div class="result-actions"><button type="button" class="btn ghost copy-btn">Copy</button></div>`;
    $(".copy-btn", box).addEventListener("click", async (e) => {
      try { await navigator.clipboard.writeText(text); e.target.textContent = "Copied ✓"; }
      catch (err) { e.target.textContent = "Press Ctrl+C to copy"; }
      setTimeout(() => (e.target.textContent = "Copy"), 2000);
    });
  }

  function showQuiz(box, data) {
    box.className = "result";
    box.removeAttribute("role");
    box.setAttribute("aria-busy", "false");
    const questions = data.questions;
    let answered = 0;
    let score = 0;

    box.innerHTML = "<h3>Quiz</h3>";
    questions.forEach((q, qi) => {
      const fs = document.createElement("fieldset");
      fs.className = "q";
      const opts = q.options.map((o, oi) =>
        `<label class="opt"><input type="radio" name="q${qi}" value="${oi}"><span>${escapeHtml(o)}</span></label>`).join("");
      fs.innerHTML = `<legend>Q${qi + 1}. ${escapeHtml(q.question)}</legend>${opts}
        <button type="button" class="btn small check">Check Answer</button>
        <p class="feedback" aria-live="polite"></p>`;
      box.appendChild(fs);

      const checkBtn = $(".check", fs);
      const feedback = $(".feedback", fs);
      checkBtn.addEventListener("click", () => {
        const chosen = $(`input[name="q${qi}"]:checked`, fs);
        if (!chosen) { feedback.className = "feedback bad"; feedback.textContent = "Please pick an answer first."; return; }
        const picked = q.options[Number(chosen.value)];
        const right = picked === q.answer;
        $$(".opt", fs).forEach((label, oi) => {
          if (q.options[oi] === q.answer) label.classList.add("correct");
          else if (label.contains(chosen)) label.classList.add("wrong");
          $("input", label).disabled = true;
        });
        checkBtn.disabled = true;
        feedback.className = "feedback " + (right ? "good" : "bad");
        feedback.innerHTML = (right ? "✅ Correct!" : `❌ Not quite. Correct answer: ${escapeHtml(q.answer)}`) +
          (q.explanation ? `<small>${escapeHtml(q.explanation)}</small>` : "");
        if (right) score += 1;
        answered += 1;
        if (answered === questions.length) finishQuiz();
      });
    });

    function finishQuiz() {
      const msg = score === questions.length ? "Perfect score! 🎉" : score >= 2 ? "Great job! 👏" : "Keep practising, you will get there! 💪";
      const div = document.createElement("div");
      div.className = "score";
      div.setAttribute("role", "status");
      div.textContent = `You scored ${score} / ${questions.length}. ${msg}`;
      box.appendChild(div);
    }
  }

  // ---------- forms ----------
  $$(".task-form").forEach((form) => {
    const task = form.dataset.task;
    const kind = form.dataset.kind;
    const endpoint = form.dataset.endpoint;
    const input = $("textarea", form);
    const counter = $(".counter", form);
    const button = $('button[type="submit"]', form);
    const box = $("#result-" + task);
    const max = Number(input.getAttribute("maxlength")) || 4000;

    const updateCount = () => { counter.textContent = `${input.value.length} / ${max}`; };
    input.addEventListener("input", updateCount);

    $$(".chip", form).forEach((chip) => chip.addEventListener("click", () => {
      input.value = chip.dataset.example;
      updateCount();
      input.focus();
    }));

    // Ctrl+Enter (or Cmd+Enter) submits
    input.addEventListener("keydown", (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "Enter") { e.preventDefault(); form.requestSubmit(); }
    });

    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const text = input.value.trim();
      if (!text) { showError(box, "Please type something first."); input.focus(); return; }

      const original = button.textContent;
      button.disabled = true;
      button.textContent = "Thinking…";
      showLoading(box);

      try {
        let data;
        if (kind === "path") {
          data = await callApi(endpoint, { topic: text, level: $("select", form).value });
          showText(box, `Learning path for “${data.topic}” (${data.level})`, data.recommendation);
        } else if (kind === "quiz") {
          data = await callApi(endpoint, { text });
          showQuiz(box, data);
        } else {
          data = await callApi(endpoint, { text });
          const title = { qa: "Answer", explain: "Explanation", summary: "Summary" }[task] || "Result";
          showText(box, title, data.answer || data.explanation || data.summary || "");
        }
      } catch (err) {
        showError(box, err.message);
      } finally {
        button.disabled = false;
        button.textContent = original;
      }
    });
  });

})();
