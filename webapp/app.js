/* ────────────────────────────────────────────────────────────────────
   Specter & Associates — Casebook controller
   Two-pane shell: sidebar lists cases stored in localStorage; main pane
   shows the selected case as a 5-message stream + verdict + conflicts.
   The composer at the bottom always opens a NEW case (atomic, not
   multi-turn) and persists it to local storage on success.
   API contract is unchanged from /v1/case + /v1/case/personas.
   ──────────────────────────────────────────────────────────────────── */

const API_BASE = "";
const STORAGE_KEY = "specter:cases:v1";
const STORAGE_VERSION = 1;
const MAX_STORED_CASES = 50;

/* ─── Persona fallback (stays in lockstep with specter/agents/personas.py) */

const DEFAULT_PERSONAS = [
  { voice: "harvey",  name: "Harvey Specter",  title: "Senior partner — the closer",  color: "#1B2D4A", accent_color: "#A03A2C", catchphrase: "When you're backed against the wall, break the goddamn thing down." },
  { voice: "mike",    name: "Mike Ross",       title: "Photographic-memory associate", color: "#1B3A6B", accent_color: "#6CB4EE", catchphrase: "I read it once, I know it." },
  { voice: "rachel",  name: "Rachel Zane",     title: "Paralegal who runs the case",   color: "#A8324A", accent_color: "#F5E6E0", catchphrase: "Let's frame this properly." },
  { voice: "louis",   name: "Louis Litt",      title: "Adversarial scrutiny",          color: "#5C2A86", accent_color: "#D4A017", catchphrase: "You just got Litt up." },
  { voice: "jessica", name: "Jessica Pearson", title: "Managing partner — the ruling", color: "#0E0F12", accent_color: "#1F8A4C", catchphrase: "My firm. My ruling." },
];

const PERSONA_INITIALS = {
  harvey: "HS", mike: "MR", rachel: "RZ", louis: "LL", jessica: "JP",
};

const ROLE_LABELS = {
  "":                                "no role",
  "provider":                        "provider",
  "deployer":                        "deployer",
  "importer":                        "importer",
  "distributor":                     "distributor",
  "authorised representative":       "authorised representative",
  "product manufacturer":            "product manufacturer",
  "general-purpose AI provider":     "GPAI provider",
  "general-purpose AI deployer":     "GPAI deployer",
  "notified body":                   "notified body",
};

/* ─── DOM hooks ─────────────────────────────────────────────────────── */

const $ = (id) => document.getElementById(id);

const els = () => ({
  app:            $("app"),
  sidebar:        $("sidebar"),
  sidebarToggle:  $("sidebar-toggle"),
  newCaseBtn:     $("new-case-btn"),
  caseList:       $("case-list"),
  caseNavEmpty:   $("case-nav-empty"),
  emptyState:     $("empty-state"),
  emptyRoster:    $("empty-roster"),
  caseDetail:     $("case-detail"),
  caseHeaderId:   $("case-header-id"),
  caseHeaderTitle:$("case-header-title"),
  caseHeaderMeta: $("case-header-meta"),
  messageStream:  $("message-stream"),
  verdict:        $("verdict"),
  verdictText:    $("verdict-text"),
  verdictRefs:    $("verdict-refs"),
  conflicts:      $("conflicts"),
  conflictsList:  $("conflicts-list"),
  composer:       $("composer"),
  question:       $("composer-question"),
  role:           $("composer-role"),
  submit:         $("composer-submit"),
  composerError:  $("composer-error"),
});

/* ─── localStorage-backed case store ───────────────────────────────── */

const caseStore = {
  _read() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return { v: STORAGE_VERSION, cases: [] };
      const parsed = JSON.parse(raw);
      if (!parsed || typeof parsed !== "object" || !Array.isArray(parsed.cases)) {
        return { v: STORAGE_VERSION, cases: [] };
      }
      return parsed;
    } catch {
      return { v: STORAGE_VERSION, cases: [] };
    }
  },
  _write(state) {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    } catch {
      // QuotaExceeded or storage disabled — silently no-op.
    }
  },
  list() {
    const state = this._read();
    return [...state.cases].sort((a, b) => (b.saved_at || 0) - (a.saved_at || 0));
  },
  get(caseId) {
    const state = this._read();
    return state.cases.find((c) => c.case_id === caseId) || null;
  },
  upsert(dialogue) {
    const state = this._read();
    const now = Date.now();
    const idx = state.cases.findIndex((c) => c.case_id === dialogue.case_id);
    const objected = (dialogue.turns || []).some(
      (t) => t.speaker === "louis" && (t.flags || []).includes("objection")
    );
    const record = {
      case_id: dialogue.case_id,
      question: dialogue.question,
      role: dialogue.role,
      saved_at: now,
      objected,
      dialogue,
    };
    if (idx >= 0) state.cases[idx] = record;
    else state.cases.push(record);

    // Keep the store bounded — drop the oldest beyond MAX_STORED_CASES.
    if (state.cases.length > MAX_STORED_CASES) {
      state.cases.sort((a, b) => (b.saved_at || 0) - (a.saved_at || 0));
      state.cases.length = MAX_STORED_CASES;
    }
    this._write(state);
  },
  remove(caseId) {
    const state = this._read();
    state.cases = state.cases.filter((c) => c.case_id !== caseId);
    this._write(state);
  },
};

/* ─── App state ───────────────────────────────────────────────────── */

let activeCaseId = null;

/* ─── Init ────────────────────────────────────────────────────────── */

document.addEventListener("DOMContentLoaded", () => { void init(); });

async function init() {
  const personas = await fetchPersonas();
  renderEmptyRoster(personas);

  renderSidebar();

  const cases = caseStore.list();
  if (cases.length > 0) {
    selectCase(cases[0].case_id);
  } else {
    showEmptyState();
  }

  // On phone widths, the sidebar is an overlay — start it closed so the
  // empty state / case detail is visible on first paint. Desktop keeps the
  // sidebar permanently in the grid.
  if (window.matchMedia("(max-width: 860px)").matches) {
    const app = els().app;
    if (app) {
      app.dataset.sidebar = "closed";
      els().sidebarToggle?.setAttribute("aria-expanded", "false");
    }
  }

  attachListeners();
  autoGrowTextarea(els().question);
}

/* ─── Personas + roster ───────────────────────────────────────────── */

async function fetchPersonas() {
  try {
    const res = await fetch(`${API_BASE}/v1/case/personas`, { headers: { Accept: "application/json" } });
    if (!res.ok) throw new Error(`status ${res.status}`);
    const data = await res.json();
    if (!Array.isArray(data) || data.length === 0) throw new Error("empty");
    return data;
  } catch {
    return DEFAULT_PERSONAS;
  }
}

function renderEmptyRoster(personas) {
  const list = els().emptyRoster;
  if (!list) return;
  // Working voices only — Harvey is the brand line in the sidebar.
  const working = personas.filter((p) => p.voice !== "harvey");
  list.innerHTML = "";
  for (const p of working) {
    const li = document.createElement("li");
    li.className = "empty-roster__item";
    li.innerHTML = `
      <span class="avatar-initials empty-roster__avatar" data-voice="${escAttr(p.voice)}" aria-hidden="true">${escHtml(PERSONA_INITIALS[p.voice] || initialsFromName(p.name))}</span>
      <span>
        <span class="empty-roster__name">${escHtml(p.name)}</span>
        <span class="empty-roster__title">${escHtml(p.title)}</span>
      </span>
    `;
    list.appendChild(li);
  }
}

/* ─── Sidebar / case list ─────────────────────────────────────────── */

function renderSidebar() {
  const { caseList, caseNavEmpty } = els();
  const cases = caseStore.list();
  caseList.innerHTML = "";

  if (cases.length === 0) {
    caseNavEmpty.hidden = false;
    return;
  }
  caseNavEmpty.hidden = true;

  for (const c of cases) {
    const li = document.createElement("li");
    li.role = "listitem";

    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "case-item";
    btn.setAttribute("aria-current", c.case_id === activeCaseId ? "true" : "false");
    btn.dataset.caseId = c.case_id;

    const title = document.createElement("span");
    title.className = "case-item__title";
    title.textContent = c.question || "(untitled)";

    const meta = document.createElement("span");
    meta.className = "case-item__meta";
    const roleLabel = c.role ? ROLE_LABELS[c.role] || c.role : "no role";
    meta.innerHTML = `
      <span class="case-item__role">${escHtml(roleLabel)}</span>
      <span aria-hidden="true">·</span>
      <span>${formatRelativeTime(c.saved_at)}</span>
      ${c.objected ? '<span class="case-item__objected">objected</span>' : ""}
    `;

    const body = document.createElement("span");
    body.style.minWidth = "0";
    body.appendChild(title);
    body.appendChild(meta);

    const del = document.createElement("span");
    del.className = "case-item__delete";
    del.setAttribute("role", "button");
    del.setAttribute("tabindex", "0");
    del.setAttribute("aria-label", `Delete case: ${title.textContent}`);
    del.textContent = "✕";
    del.addEventListener("click", (ev) => {
      ev.stopPropagation();
      deleteCase(c.case_id);
    });
    del.addEventListener("keydown", (ev) => {
      if (ev.key === "Enter" || ev.key === " ") {
        ev.preventDefault();
        ev.stopPropagation();
        deleteCase(c.case_id);
      }
    });

    btn.appendChild(body);
    btn.appendChild(del);
    btn.addEventListener("click", () => selectCase(c.case_id));

    li.appendChild(btn);
    caseList.appendChild(li);
  }
}

function selectCase(caseId) {
  const stored = caseStore.get(caseId);
  if (!stored) return;
  activeCaseId = caseId;
  showCaseDetail(stored.dialogue);
  renderSidebar();
  closeMobileSidebar();
}

function deleteCase(caseId) {
  caseStore.remove(caseId);
  if (activeCaseId === caseId) {
    activeCaseId = null;
    showEmptyState();
  }
  renderSidebar();
}

function startNewCase() {
  activeCaseId = null;
  showEmptyState();
  renderSidebar();
  els().question?.focus();
  closeMobileSidebar();
}

/* ─── Showing empty state vs case detail ──────────────────────────── */

function showEmptyState() {
  const { emptyState, caseDetail, question, role, composerError } = els();
  emptyState.hidden = false;
  caseDetail.hidden = true;
  if (composerError) { composerError.hidden = true; composerError.textContent = ""; }
  // Reset composer for a brand new case.
  if (question) question.value = "";
  if (role) role.value = "";
  autoGrowTextarea(question);
}

function showCaseDetail(dialogue) {
  const { emptyState, caseDetail } = els();
  emptyState.hidden = true;
  caseDetail.hidden = false;
  renderCaseHeader(dialogue);
  renderMessageStream(dialogue.turns || []);
  renderVerdict(dialogue);
  renderConflicts(dialogue.conflicts || []);
  // Reset composer placeholder; user can submit again to open ANOTHER case.
  const q = els().question;
  if (q) { q.value = ""; autoGrowTextarea(q); }
}

function renderCaseHeader(dialogue) {
  const { caseHeaderId, caseHeaderTitle, caseHeaderMeta } = els();
  caseHeaderId.textContent = `Case · ${dialogue.case_id || "—"}`;
  caseHeaderTitle.textContent = dialogue.question || "(untitled case)";

  const roleLabel = dialogue.role ? ROLE_LABELS[dialogue.role] || dialogue.role : "no role";
  const refCount = (dialogue.references || []).length;
  const confidence = (dialogue.confidence || 0).toFixed(2);
  caseHeaderMeta.innerHTML = `
    <span class="case-header__pill">${escHtml(roleLabel)}</span>
    <span>${refCount} citation${refCount === 1 ? "" : "s"}</span>
    <span aria-hidden="true">·</span>
    <span>confidence ${escHtml(confidence)}</span>
  `;
}

/* ─── Message stream ──────────────────────────────────────────────── */

function renderMessageStream(turns) {
  const stream = els().messageStream;
  stream.innerHTML = "";
  turns.forEach((turn, idx) => stream.appendChild(renderMessage(turn, idx)));
}

function renderMessage(turn, idx) {
  const li = document.createElement("li");
  li.className = `message message--${escAttr(turn.panel_kind || "speech")}`;
  li.dataset.voice = turn.speaker;
  li.setAttribute("aria-label", `${turn.name || turn.speaker}, message ${idx + 1}`);

  const avatar = document.createElement("span");
  avatar.className = "avatar-initials message__avatar";
  avatar.dataset.voice = turn.speaker;
  avatar.setAttribute("aria-hidden", "true");
  avatar.textContent = PERSONA_INITIALS[turn.speaker] || initialsFromName(turn.name);

  const body = document.createElement("div");
  body.className = "message__body";

  // Header row: name + role + tags.
  const head = document.createElement("div");
  head.className = "message__head";

  const nameEl = document.createElement("span");
  nameEl.className = "message__name";
  nameEl.textContent = turn.name || titleCase(turn.speaker);
  head.appendChild(nameEl);

  const roleEl = document.createElement("span");
  roleEl.className = "message__role";
  roleEl.textContent = personaRoleLabel(turn.speaker);
  head.appendChild(roleEl);

  const tag = tagForTurn(turn);
  if (tag) head.appendChild(tag);

  body.appendChild(head);

  // Claim
  const claim = document.createElement("p");
  claim.className = "message__claim";
  claim.textContent = turn.claim || "";
  body.appendChild(claim);

  // Footer: citations + flags + confidence
  const footer = document.createElement("div");
  footer.className = "message__footer";

  const cites = document.createElement("span");
  cites.className = "citations";
  for (const c of turn.citations || []) {
    const pill = document.createElement("span");
    pill.className = "citation-pill";
    pill.textContent = c.article_ref || "";
    cites.appendChild(pill);
  }
  for (const flag of turn.flags || []) {
    if (flag === "objection") continue; // already surfaced as a tag
    const chip = document.createElement("span");
    chip.className = "flag-chip";
    chip.textContent = flag;
    cites.appendChild(chip);
  }
  footer.appendChild(cites);

  const conf = renderConfidence(turn.confidence || 0);
  footer.appendChild(conf);

  // Only show footer if it has anything to show.
  if (cites.children.length > 0 || (turn.confidence || 0) > 0) {
    body.appendChild(footer);
  }

  li.appendChild(avatar);
  li.appendChild(body);
  return li;
}

function tagForTurn(turn) {
  const flags = new Set(turn.flags || []);
  if (turn.speaker === "louis" && flags.has("objection")) {
    return makeTag("OBJECTION!", "tag--objection");
  }
  if (turn.speaker === "mike" && (turn.confidence || 0) >= 0.7) {
    return makeTag("FILED", "tag--filed");
  }
  if (turn.speaker === "jessica") {
    return makeTag("RULING", "tag--ruling");
  }
  return null;
}

function makeTag(text, modifier) {
  const el = document.createElement("span");
  el.className = `tag ${modifier}`;
  el.textContent = text;
  return el;
}

function renderConfidence(value) {
  const wrap = document.createElement("span");
  wrap.className = "confidence";
  wrap.setAttribute("aria-label", `Confidence: ${(value * 100).toFixed(0)}%`);

  const label = document.createElement("span");
  label.textContent = `${Math.round(value * 100)}%`;
  wrap.appendChild(label);

  const dots = document.createElement("span");
  dots.className = "confidence__dots";
  const filled = Math.max(0, Math.min(5, Math.round(value * 5)));
  for (let i = 0; i < 5; i++) {
    const dot = document.createElement("span");
    dot.className = "confidence__dot" + (i < filled ? " confidence__dot--on" : "");
    dots.appendChild(dot);
  }
  wrap.appendChild(dots);
  return wrap;
}

/* ─── Verdict + conflicts ─────────────────────────────────────────── */

function renderVerdict(dialogue) {
  const { verdict, verdictText, verdictRefs } = els();
  if (!dialogue.verdict) {
    verdict.hidden = true;
    return;
  }
  verdictText.textContent = dialogue.verdict;
  const refs = dialogue.references || [];
  verdictRefs.textContent = refs.length
    ? refs.join(" · ")
    : "(no references on the record)";
  verdict.hidden = false;
}

function renderConflicts(conflicts) {
  const { conflicts: box, conflictsList } = els();
  conflictsList.innerHTML = "";
  if (!conflicts || conflicts.length === 0) {
    box.hidden = true;
    return;
  }
  for (const c of conflicts) {
    const li = document.createElement("li");
    li.className = "conflict-note";
    li.textContent = c;
    conflictsList.appendChild(li);
  }
  box.hidden = false;
}

/* ─── Submit + listeners ─────────────────────────────────────────── */

function attachListeners() {
  const { composer, newCaseBtn, sidebarToggle, question } = els();

  composer?.addEventListener("submit", onSubmit);
  newCaseBtn?.addEventListener("click", startNewCase);

  sidebarToggle?.addEventListener("click", toggleSidebar);

  // Auto-grow textarea + Cmd/Ctrl+Enter.
  question?.addEventListener("input", () => autoGrowTextarea(question));
  question?.addEventListener("keydown", (ev) => {
    const isEnter = ev.key === "Enter" || ev.key === "Return";
    if (isEnter && (ev.metaKey || ev.ctrlKey)) {
      ev.preventDefault();
      composer.requestSubmit();
    }
  });

  // Close mobile sidebar when clicking outside.
  document.addEventListener("click", (ev) => {
    const { app, sidebar, sidebarToggle: tgl } = els();
    if (!app || app.dataset.sidebar !== "open") return;
    if (window.matchMedia("(min-width: 861px)").matches) return;
    if (sidebar.contains(ev.target) || tgl.contains(ev.target)) return;
    closeMobileSidebar();
  });
}

async function onSubmit(ev) {
  ev.preventDefault();
  const e = els();
  const question = (e.question?.value || "").trim();
  const role = e.role?.value || null;

  if (!question) {
    setComposerError("Add the facts of the case first, counselor.");
    return;
  }
  setComposerError("");

  e.submit?.setAttribute("disabled", "true");
  try {
    const dialogue = await postCase(question, role);
    caseStore.upsert(dialogue);
    activeCaseId = dialogue.case_id;
    renderSidebar();
    showCaseDetail(dialogue);
  } catch (err) {
    console.error(err);
    setComposerError("Couldn't open the case. Is the API up? Try again.");
  } finally {
    e.submit?.removeAttribute("disabled");
  }
}

async function postCase(question, role) {
  const res = await fetch(`${API_BASE}/v1/case`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify({ question, role: role || null, enable_louis_objection: true }),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`case failed: ${res.status} ${text}`);
  }
  return res.json();
}

/* ─── Sidebar mobile toggle ──────────────────────────────────────── */

function toggleSidebar() {
  const app = els().app;
  if (!app) return;
  const open = app.dataset.sidebar === "open";
  app.dataset.sidebar = open ? "closed" : "open";
  els().sidebarToggle?.setAttribute("aria-expanded", open ? "false" : "true");
}

function closeMobileSidebar() {
  if (!window.matchMedia("(max-width: 860px)").matches) return;
  const app = els().app;
  if (!app) return;
  app.dataset.sidebar = "closed";
  els().sidebarToggle?.setAttribute("aria-expanded", "false");
}

/* ─── Composer helpers ───────────────────────────────────────────── */

function setComposerError(msg) {
  const err = els().composerError;
  if (!err) return;
  err.textContent = msg;
  err.hidden = !msg;
}

function autoGrowTextarea(ta) {
  if (!ta) return;
  // Empty value → clear inline height and let the CSS min-height own the
  // resting size. Measuring scrollHeight on an empty textarea before fonts
  // settle can return the max-height clamp value, which jams the box at
  // ~240px on first paint.
  if (!ta.value) {
    ta.style.height = "";
    return;
  }
  ta.style.height = "auto";
  ta.style.height = Math.min(ta.scrollHeight, 240) + "px";
}

/* ─── Helpers ─────────────────────────────────────────────────────── */

function personaRoleLabel(voice) {
  const p = DEFAULT_PERSONAS.find((x) => x.voice === voice);
  return p ? p.title : "";
}

function initialsFromName(name) {
  const parts = String(name || "").trim().split(/\s+/);
  if (parts.length === 0) return "??";
  if (parts.length === 1) return (parts[0].slice(0, 2) || "??").toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

function titleCase(s) {
  return String(s || "").charAt(0).toUpperCase() + String(s || "").slice(1);
}

function escHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
  ));
}

function escAttr(s) {
  return escHtml(s).replace(/\s+/g, "-");
}

function formatRelativeTime(ts) {
  if (!ts) return "just now";
  const diff = Date.now() - ts;
  const sec = Math.floor(diff / 1000);
  if (sec < 60)   return `${sec}s ago`;
  const min = Math.floor(sec / 60);
  if (min < 60)   return `${min}m ago`;
  const hr = Math.floor(min / 60);
  if (hr < 24)    return `${hr}h ago`;
  const day = Math.floor(hr / 24);
  if (day < 7)    return `${day}d ago`;
  return new Date(ts).toLocaleDateString();
}
