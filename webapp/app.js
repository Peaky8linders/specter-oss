/* ─────────────────────────────────────────────────────────────────────────
   SPECTER & ASSOCIATES — Comic-book SPA controller
   ─────────────────────────────────────────────────────────────────────────

   Wires the static markup in index.html to the agent-layer API:

   * GET  /v1/case/personas — bootstraps the roster strip + panel colours
   * POST /v1/case          — runs a deterministic 5-turn dialogue and
                              gets back a CaseDialogue we render as a
                              5-panel comic page.

   Falls through to a hardcoded persona table + DEMO_DIALOGUE when the
   file is opened directly via file:// (no API). Vanilla ES2022, no
   frameworks, no build step.
   ──────────────────────────────────────────────────────────────────────── */

const API_BASE = "";  // same-origin; the dev app mounts the SPA at /webapp/

// ─── Fallback persona table (kept in lockstep with specter/agents/personas.py)
const DEFAULT_PERSONAS = [
  {
    voice: "harvey", name: "Harvey Specter",
    title: "Senior partner — the closer (project mascot)",
    color: "#1B2D4A", accent_color: "#A03A2C",
    catchphrase: "When you're backed against the wall, break the goddamn thing down.",
  },
  {
    voice: "mike", name: "Mike Ross",
    title: "Photographic-memory associate",
    color: "#1B3A6B", accent_color: "#6CB4EE",
    catchphrase: "I read it once, I know it.",
  },
  {
    voice: "rachel", name: "Rachel Zane",
    title: "Paralegal who runs the case",
    color: "#A8324A", accent_color: "#F5E6E0",
    catchphrase: "Let's frame this properly.",
  },
  {
    voice: "louis", name: "Louis Litt",
    title: "The anti-Specter — adversarial scrutiny",
    color: "#5C2A86", accent_color: "#D4A017",
    catchphrase: "You just got Litt up.",
  },
  {
    voice: "jessica", name: "Jessica Pearson",
    title: "Managing partner — final ruling",
    color: "#0E0F12", accent_color: "#1F8A4C",
    catchphrase: "My firm. My ruling.",
  },
];

// ─── DEMO_DIALOGUE — used when the API isn't reachable (file:// preview)
const DEMO_DIALOGUE = {
  case_id: "EUAIA-0001",
  question:
    "My SaaS deploys a high-risk biometric verification system in France — what must I do as a deployer?",
  role: "deployer",
  turns: [
    {
      speaker: "rachel", name: "Rachel Zane",
      claim: "We've got a deployer of a high-risk biometric system. Mike — pull every obligation that hits this.",
      citations: [],
      confidence: 0.7, flags: [], panel_kind: "narration",
    },
    {
      speaker: "mike", name: "Mike Ross",
      claim: "Filed. Art. 26(1), 26(3), 27 and 13(1)(a) — all apply. Highlights are in the margin.",
      citations: [
        { article_ref: "Article 13.1.a", snippet: null },
        { article_ref: "Article 26.1", snippet: null },
        { article_ref: "Article 26.3", snippet: null },
        { article_ref: "Article 27", snippet: null },
        { article_ref: "Annex IV.2", snippet: null },
      ],
      confidence: 0.88, flags: [], panel_kind: "speech",
    },
    {
      speaker: "louis", name: "Louis Litt",
      claim: "OBJECTION! He cited Art. 27 but missed the FRA pre-deployment notification under Art. 27(1).",
      citations: [{ article_ref: "Article 27", snippet: null }],
      confidence: 0.75, flags: ["objection"], panel_kind: "shout",
    },
    {
      speaker: "rachel", name: "Rachel Zane",
      claim: "Louis's right on the FRA. Mike — fold Art. 27(1) into the checklist.",
      citations: [],
      confidence: 0.7, flags: [], panel_kind: "thought",
    },
    {
      speaker: "jessica", name: "Jessica Pearson",
      claim: "Ruling: comply with Arts. 13, 26, 27 — and run the Art. 27 FRA before you deploy. Document it. Move on.",
      citations: [
        { article_ref: "Article 13", snippet: null },
        { article_ref: "Article 26", snippet: null },
        { article_ref: "Article 27", snippet: null },
      ],
      confidence: 0.86, flags: [], panel_kind: "speech",
    },
  ],
  verdict: "Ruling: comply with Arts. 13, 26, 27 — and run the Art. 27 FRA before you deploy. Document it. Move on.",
  references: ["Article 13", "Article 13.1.a", "Article 26", "Article 26.1", "Article 26.3", "Article 27", "Annex IV.2"],
  confidence: 0.84,
  conflicts: ["Louis flagged: Art. 27(1) FRA was missing from Mike's recall — Rachel folded it back in."],
};

// ─── DOM hook lookups ─────────────────────────────────────────────────────

const els = {
  rosterList:    () => document.getElementById("roster-list"),
  caseForm:      () => document.getElementById("case-form"),
  question:      () => document.getElementById("case-question"),
  role:          () => document.getElementById("case-role"),
  formError:     () => document.getElementById("case-form-error"),
  openBtn:       () => document.getElementById("open-case-btn"),
  newBtn:        () => document.getElementById("new-case-btn"),
  hero:          () => document.getElementById("hero"),
  caseFormWrap:  () => document.getElementById("case-form-wrap"),
  comicPage:     () => document.getElementById("comic-page"),
  comicTitle:    () => document.getElementById("comic-page-title"),
  comicSub:      () => document.getElementById("comic-page-sub"),
  comicGrid:     () => document.getElementById("comic-grid"),
  conflicts:     () => document.getElementById("conflicts"),
  conflictsList: () => document.getElementById("conflicts-list"),
  verdictBanner: () => document.getElementById("verdict-banner"),
  verdictText:   () => document.getElementById("verdict-text"),
  verdictRefs:   () => document.getElementById("verdict-refs"),
};

// ─── Bootstrap ────────────────────────────────────────────────────────────

document.addEventListener("DOMContentLoaded", () => {
  void init();
});

/** Wire up the page on DOMContentLoaded. */
async function init() {
  // Pre-fill so the demo lands a clean first impression.
  const q = els.question();
  if (q && !q.value) {
    q.value =
      "My SaaS deploys a high-risk biometric verification system in France — what must I do as a deployer?";
  }
  const r = els.role();
  if (r && !r.value) r.value = "deployer";

  await renderRoster();

  els.caseForm()?.addEventListener("submit", onSubmit);
  els.newBtn()?.addEventListener("click", resetToHero);
  attachShortcuts();
}

// ─── Roster strip ─────────────────────────────────────────────────────────

/** Fetch personas from the API; fall back to DEFAULT_PERSONAS on any failure. */
async function fetchPersonas() {
  try {
    const res = await fetch(`${API_BASE}/v1/case/personas`, {
      headers: { Accept: "application/json" },
    });
    if (!res.ok) throw new Error(`status ${res.status}`);
    const payload = await res.json();
    if (!Array.isArray(payload) || payload.length === 0) throw new Error("empty");
    return payload;
  } catch {
    return DEFAULT_PERSONAS;
  }
}

async function renderRoster() {
  const list = els.rosterList();
  if (!list) return;

  const personas = await fetchPersonas();
  // Working agents only — Harvey already headlines the hero.
  const roster = personas.filter((p) => p.voice !== "harvey");

  list.innerHTML = "";
  for (const p of roster) {
    const li = document.createElement("li");
    li.className = "roster__card";
    li.style.setProperty("--card-color", p.color);
    li.style.setProperty("--card-accent", p.accent_color);
    li.innerHTML = `
      <span class="roster__avatar avatar-initials" data-voice="${escAttr(p.voice)}" aria-hidden="true">${escHtml(PERSONA_INITIALS[p.voice] || initialsFromName(p.name))}</span>
      <span class="roster__meta">
        <span class="roster__name">${escHtml(p.name)}</span>
        <span class="roster__title">${escHtml(p.title)}</span>
      </span>
    `;
    list.appendChild(li);
  }
}

// ─── Submit + render ──────────────────────────────────────────────────────

/**
 * Form submit handler — runs the case and swaps the view to the comic page.
 * @param {SubmitEvent} ev
 */
async function onSubmit(ev) {
  ev.preventDefault();
  const question = (els.question()?.value || "").trim();
  const role = els.role()?.value || null;

  if (!question) {
    showError("Add the facts of the case first, counselor.");
    return;
  }
  hideError();

  els.openBtn()?.setAttribute("disabled", "true");

  try {
    const dialogue = await submitCase(question, role || null);
    renderDialogue(dialogue);
  } catch (err) {
    // Last-ditch fallback: render the demo dialogue with a small banner.
    renderDialogue({ ...DEMO_DIALOGUE, question, role: role || null }, { demo: true });
  } finally {
    els.openBtn()?.removeAttribute("disabled");
  }
}

/**
 * POST /v1/case. Throws on any non-2xx so the caller can fall through.
 * @param {string} question
 * @param {string | null} role
 * @returns {Promise<object>}
 */
async function submitCase(question, role) {
  const res = await fetch(`${API_BASE}/v1/case`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify({ question, role, enable_louis_objection: true }),
  });
  if (!res.ok) throw new Error(`case failed: ${res.status}`);
  return res.json();
}

/**
 * Paint a CaseDialogue onto the comic page.
 * @param {object} dialogue
 * @param {{ demo?: boolean }} [opts]
 */
function renderDialogue(dialogue, opts = {}) {
  const grid = els.comicGrid();
  const page = els.comicPage();
  if (!grid || !page) return;

  // Header
  const title = els.comicTitle();
  const sub = els.comicSub();
  if (title) title.textContent = `THE CASE · ${dialogue.case_id || "—"}${opts.demo ? " · DEMO" : ""}`;
  if (sub) {
    const role = dialogue.role ? `As ${dialogue.role}: ` : "";
    sub.textContent = `${role}${dialogue.question || ""}`;
  }

  // Panels
  grid.innerHTML = "";
  (dialogue.turns || []).forEach((turn, idx) => {
    grid.appendChild(renderPanel(turn, idx));
  });

  // Conflicts
  const conflicts = dialogue.conflicts || [];
  const conflictsBox = els.conflicts();
  const conflictsList = els.conflictsList();
  if (conflictsBox && conflictsList) {
    conflictsList.innerHTML = "";
    if (conflicts.length === 0) {
      conflictsBox.hidden = true;
    } else {
      for (const c of conflicts) {
        const li = document.createElement("li");
        li.className = "conflict-note";
        li.textContent = c;
        conflictsList.appendChild(li);
      }
      conflictsBox.hidden = false;
    }
  }

  // Verdict banner
  const banner = els.verdictBanner();
  const text = els.verdictText();
  const refs = els.verdictRefs();
  if (banner && text && refs) {
    text.textContent = dialogue.verdict || "";
    refs.textContent = (dialogue.references || []).join(" · ");
    banner.hidden = !(dialogue.verdict);
  }

  // Reveal
  els.hero()?.setAttribute("data-collapsed", "true");
  els.caseFormWrap()?.setAttribute("data-collapsed", "true");
  page.hidden = false;
  page.scrollIntoView({ behavior: prefersReducedMotion() ? "auto" : "smooth", block: "start" });
}

// ─── Panel rendering ──────────────────────────────────────────────────────

const PANEL_POSITIONS = [
  "panel--rachel-narr",   // turn 0 — Rachel narration
  "panel--mike",          // turn 1 — Mike speech
  "panel--louis",         // turn 2 — Louis (shout / speech)
  "panel--rachel-thought",// turn 3 — Rachel thought
  "panel--jessica",       // turn 4 — Jessica verdict
];

const PERSONA_TITLES = {
  harvey:  "Senior partner",
  mike:    "Photographic-memory associate",
  rachel:  "Paralegal",
  louis:   "Adversarial scrutiny",
  jessica: "Managing partner",
};

// Two-letter initials per voice — used as the typographic placeholder while
// avatar artwork is paused. Picked from the persona name (Harvey Specter → HS,
// Mike Ross → MR, Rachel Zane → RZ, Louis Litt → LL, Jessica Pearson → JP).
const PERSONA_INITIALS = {
  harvey:  "HS",
  mike:    "MR",
  rachel:  "RZ",
  louis:   "LL",
  jessica: "JP",
};

/**
 * Render a single Turn as a `.panel` article.
 * @param {object} turn
 * @param {number} idx
 * @returns {HTMLElement}
 */
function renderPanel(turn, idx) {
  const article = document.createElement("article");
  const positionClass = PANEL_POSITIONS[idx] || "panel--mike";
  article.className = `panel ${positionClass}`;
  article.setAttribute("aria-label", `${turn.name || turn.speaker}, panel ${idx + 1}`);

  // Stamp overlay on Mike (high-confidence FILED), Louis (OBJECTION),
  // Jessica (RULING).
  const stamp = stampForTurn(turn);
  if (stamp) article.appendChild(stamp);

  // Head: avatar + name plate
  const head = document.createElement("div");
  head.className = "panel__head";
  head.innerHTML = `
    <span class="panel__avatar avatar-initials" data-voice="${escAttr(turn.speaker)}" aria-hidden="true">${escHtml(PERSONA_INITIALS[turn.speaker] || initialsFromName(turn.name))}</span>
    <span class="panel__who">
      <span class="panel__name">${escHtml(turn.name || titleCase(turn.speaker))}</span>
      <span class="panel__role">${escHtml(PERSONA_TITLES[turn.speaker] || "")}</span>
    </span>
  `;
  article.appendChild(head);

  // Body: bubble (kind-specific)
  const body = document.createElement("div");
  body.className = "panel__body";

  const kind = turn.panel_kind || "speech";
  if (kind === "shout") {
    const burst = document.createElement("div");
    burst.className = "shout-burst";
    burst.setAttribute("aria-hidden", "true");
    body.appendChild(burst);
  }

  const bubble = document.createElement("p");
  bubble.className = `bubble bubble--${turn.speaker}`;
  if (kind === "narration")  bubble.classList.add("bubble--narration");
  if (kind === "thought")    bubble.classList.add("bubble--thought");
  if (kind === "shout")      bubble.classList.add("bubble--shout");
  bubble.textContent = turn.claim || "";
  body.appendChild(bubble);

  if (kind === "thought") {
    const tail = document.createElement("span");
    tail.className = "thought-tail";
    tail.setAttribute("aria-hidden", "true");
    tail.innerHTML = "<span></span><span></span><span></span>";
    body.appendChild(tail);
  }

  article.appendChild(body);

  // Footer: citations + flags + confidence
  const footer = document.createElement("div");
  footer.className = "panel__footer";

  const citesWrap = document.createElement("span");
  citesWrap.className = "citations";
  for (const cite of turn.citations || []) {
    const pill = document.createElement("span");
    pill.className = "citation-pill";
    pill.textContent = (cite.article_ref || "").toUpperCase();
    citesWrap.appendChild(pill);
  }
  for (const flag of turn.flags || []) {
    const chip = document.createElement("span");
    chip.className = "flag-chip";
    chip.textContent = flag;
    citesWrap.appendChild(chip);
  }
  footer.appendChild(citesWrap);
  footer.appendChild(renderConfidence(turn.confidence || 0));

  article.appendChild(footer);
  return article;
}

/** Build the 5-dot confidence meter. */
function renderConfidence(value) {
  const wrap = document.createElement("span");
  wrap.className = "confidence";
  wrap.setAttribute("aria-label", `Confidence: ${(value * 100).toFixed(0)}%`);
  const filled = Math.max(0, Math.min(5, Math.round(value * 5)));
  for (let i = 0; i < 5; i++) {
    const dot = document.createElement("span");
    dot.className = "confidence__dot" + (i < filled ? " confidence__dot--on" : "");
    wrap.appendChild(dot);
  }
  return wrap;
}

/** Decide which `.stamp` overlay to drop on this panel, if any. */
function stampForTurn(turn) {
  const speaker = turn.speaker;
  const flags = new Set(turn.flags || []);
  const confidence = turn.confidence || 0;

  if (speaker === "louis" && flags.has("objection")) {
    return makeStamp("OBJECTION!", "stamp--objection");
  }
  if (speaker === "mike" && confidence >= 0.7) {
    return makeStamp("FILED", "stamp--filed");
  }
  if (speaker === "jessica") {
    return makeStamp("RULING!", "stamp--ruling");
  }
  return null;
}

function makeStamp(text, modifier) {
  const el = document.createElement("span");
  el.className = `stamp ${modifier}`;
  el.textContent = text;
  return el;
}

// ─── Reset to hero ────────────────────────────────────────────────────────

function resetToHero() {
  els.comicPage().hidden = true;
  els.hero()?.removeAttribute("data-collapsed");
  els.caseFormWrap()?.removeAttribute("data-collapsed");
  hideError();
  els.hero()?.scrollIntoView({ behavior: prefersReducedMotion() ? "auto" : "smooth", block: "start" });
  els.question()?.focus();
}

// ─── Errors ───────────────────────────────────────────────────────────────

function showError(msg) {
  const err = els.formError();
  if (!err) return;
  err.textContent = msg;
  err.hidden = false;
}

function hideError() {
  const err = els.formError();
  if (!err) return;
  err.textContent = "";
  err.hidden = true;
}

// ─── Keyboard ─────────────────────────────────────────────────────────────

function attachShortcuts() {
  document.addEventListener("keydown", (ev) => {
    const isEnter = ev.key === "Enter" || ev.key === "Return";
    const meta = ev.metaKey || ev.ctrlKey;
    if (isEnter && meta) {
      ev.preventDefault();
      els.caseForm()?.requestSubmit();
    }
  });
}

// ─── Helpers ──────────────────────────────────────────────────────────────

function prefersReducedMotion() {
  return window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
}

function escHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
  ));
}

function escAttr(s) {
  return escHtml(s).replace(/\s+/g, "-");
}

function titleCase(s) {
  return String(s || "").charAt(0).toUpperCase() + String(s || "").slice(1);
}

/** Fallback two-letter initials when a voice isn't in PERSONA_INITIALS. */
function initialsFromName(name) {
  const parts = String(name || "").trim().split(/\s+/);
  if (parts.length === 0) return "??";
  if (parts.length === 1) return (parts[0].slice(0, 2) || "??").toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}
