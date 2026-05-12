/* ────────────────────────────────────────────────────────────────────
   Specter & Associates — Casebook controller
   Two-pane shell: sidebar lists cases stored in localStorage; main pane
   shows the selected case as a 5-message stream + verdict + conflicts.
   The composer at the bottom always opens a NEW case (atomic, not
   multi-turn) and persists it to local storage on success.

   Settings (BYOK): a small drawer lets the user pick a provider
   (Claude / OpenAI / server default) and paste their own API
   key. The key is stored in localStorage on the user's device and sent
   to the backend on every request as `X-Specter-LLM-Provider` /
   `X-Specter-LLM-Key`. The route uses the per-request retriever for
   that one call and never persists the key server-side.

   API contract is unchanged from /v1/case + /v1/case/personas.
   ──────────────────────────────────────────────────────────────────── */

const API_BASE = "";
const STORAGE_KEY = "specter:cases:v1";
const SETTINGS_KEY = "specter:settings:v1";
const TEAM_KEY = "specter:team:v1";
const STORAGE_VERSION = 1;
const MAX_STORED_CASES = 50;
const MAX_PROMPT_LEN = 4000;

const VALID_PROVIDERS = new Set(["", "claude", "openai"]);
// "inherit" means: use whatever the global Provider tab is set to
const VALID_TEAM_PROVIDERS = new Set(["inherit", "claude", "openai"]);
const WORKING_VOICES = ["mike", "rachel", "louis", "jessica"];

// Sensible model menus per provider — kept short on purpose.
const MODELS_PER_PROVIDER = {
  claude:  ["claude-opus-4-7", "claude-sonnet-4-6", "claude-haiku-4-5-20251001"],
  openai:  ["gpt-4o", "gpt-4o-mini"] 
};

const PROVIDER_LABELS = {
  "":        "default",
  "claude":  "Claude",
  "openai":  "ChatGPT"
};

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

// Mirrors the system_prompt strings in specter/agents/personas.py. We
// duplicate them here (not fetch from the server) so the user can edit
// the prompt offline and see the canonical text without an API round-
// trip. If the server ever drifts, the route still wins on the wire —
// these defaults are only used to seed the "Reset" button + the
// placeholder text in the team editor.
const DEFAULT_PERSONA_PROMPTS = {
  mike:
    "You are Mike Ross, photographic-memory associate at Pearson Hardman.\n" +
    "You read every regulation once and remember every cite.\n" +
    "- Speak in short, clipped sentences. Lead with the article number.\n" +
    "- Always cite. Never speculate.\n" +
    "- If you don't know, say \"Nothing on file.\" — don't invent articles.\n" +
    "- Tone: confident, precise, a little wry.",
  rachel:
    "You are Rachel Zane, paralegal — you frame the case before anyone speaks.\n" +
    "- Open by naming what we're being asked. Identify the role if given.\n" +
    "- Mediate disagreements between Mike and Louis in one line.\n" +
    "- Tone: pragmatic, structural, no theatrics.\n" +
    "- Never cite articles yourself; that's Mike's job. You point at his work.",
  louis:
    "You are Louis Litt — you exist to find what Mike missed.\n" +
    "- Object to anything that looks hallucinated, sloppy, or off-topic.\n" +
    "- If everything checks out, concede with a sneer (\"Fine, Ross.\").\n" +
    "- Tone: bombastic, sarcastic, prone to exclamation. \"Litt up.\" is yours.\n" +
    "- You speak in SHOUT panels when you object.",
  jessica:
    "You are Jessica Pearson, managing partner. The final ruling is yours.\n" +
    "- One line. Decide. Move on.\n" +
    "- If Louis raised a real objection, lower the verdict's confidence.\n" +
    "- Tone: terse, executive, irreversible.\n" +
    "- Sign off with the verdict, not a discussion.",
};

const ROLE_LABELS = {
  "":                          "no role",
  "provider":                  "provider",
  "deployer":                  "deployer",
  "importer":                  "importer",
  "distributor":               "distributor",
  "authorised_representative": "authorised rep",
  "product_manufacturer":      "product manufacturer",
  "gpai_provider":             "GPAI provider",
  "gpai_deployer":             "GPAI deployer",
  "notified_body":             "notified body",
};

/* ─── DOM hooks ─────────────────────────────────────────────────────── */

const $ = (id) => document.getElementById(id);

const els = () => ({
  app:                $("app"),
  sidebar:            $("sidebar"),
  sidebarToggle:      $("sidebar-toggle"),
  newCaseBtn:         $("new-case-btn"),
  caseList:           $("case-list"),
  caseNavEmpty:       $("case-nav-empty"),
  emptyState:         $("empty-state"),
  emptyRoster:        $("empty-roster"),
  caseDetail:         $("case-detail"),
  caseHeaderId:       $("case-header-id"),
  caseHeaderTitle:    $("case-header-title"),
  caseHeaderMeta:     $("case-header-meta"),
  messageStream:      $("message-stream"),
  verdict:            $("verdict"),
  verdictText:        $("verdict-text"),
  verdictRefs:        $("verdict-refs"),
  conflicts:          $("conflicts"),
  conflictsList:      $("conflicts-list"),
  composer:           $("composer"),
  question:           $("composer-question"),
  role:               $("composer-role"),
  submit:             $("composer-submit"),
  submitLabel:        document.querySelector(".composer__submit-label"),
  composerError:      $("composer-error"),
  composerProvider:   $("composer-provider"),
  // settings + shortcuts
  settingsBtn:        $("settings-btn"),
  settingsBadge:      $("settings-provider-badge"),
  settingsDialog:     $("settings-dialog"),
  settingsForm:       $("settings-form"),
  settingsKey:        $("settings-key"),
  settingsKeyReveal:  $("settings-key-reveal"),
  settingsKeyField:   $("settings-key-field"),
  settingsClear:      $("settings-clear"),
  settingsStatus:     $("settings-status"),
  settingsResetTeam:  $("settings-reset-team"),
  // tabs
  tabProvider:        $("tab-provider"),
  tabTeam:            $("tab-team"),
  paneProvider:       $("pane-provider"),
  paneTeam:           $("pane-team"),
  teamEditor:         $("team-editor"),
  shortcutsBtn:       $("shortcuts-btn"),
  shortcutsDialog:    $("shortcuts-dialog"),
  // toast
  toast:              $("toast"),
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
  upsert(dialogue, meta = {}) {
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
      provider: meta.provider || "",
      customised: !!meta.customised,
      dialogue,
    };
    if (idx >= 0) state.cases[idx] = record;
    else state.cases.push(record);

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

/* ─── localStorage-backed settings store (BYOK) ────────────────────── */

const settingsStore = {
  _default: { provider: "", api_key: "" },
  read() {
    try {
      const raw = localStorage.getItem(SETTINGS_KEY);
      if (!raw) return { ...this._default };
      const parsed = JSON.parse(raw);
      const provider = VALID_PROVIDERS.has(parsed?.provider) ? parsed.provider : "";
      const api_key = typeof parsed?.api_key === "string" ? parsed.api_key.slice(0, 2048) : "";
      return { provider, api_key };
    } catch {
      return { ...this._default };
    }
  },
  write(value) {
    const next = {
      provider: VALID_PROVIDERS.has(value?.provider) ? value.provider : "",
      api_key: typeof value?.api_key === "string" ? value.api_key.slice(0, 2048) : "",
    };
    try {
      localStorage.setItem(SETTINGS_KEY, JSON.stringify(next));
    } catch {
      // ignore — quota or disabled storage
    }
    return next;
  },
  clear() {
    try { localStorage.removeItem(SETTINGS_KEY); } catch { /* noop */ }
    return { ...this._default };
  },
};

/* ─── localStorage-backed team store (per-persona overrides) ───────── */

/* Schema:
 *   {
 *     mike:    { enabled: bool, provider: "inherit"|"claude"|..., model: str, system_prompt: str },
 *     rachel:  { ... },
 *     louis:   { ... },
 *     jessica: { ... },
 *   }
 * Only personas with `enabled === true` get sent to the server. Anything
 * else falls through to the deterministic claim. ``provider: "inherit"``
 * means "use whatever the global Provider tab is set to" — that's the
 * common case; users tweak prompts more often than they switch providers.
 */
const teamStore = {
  _default() {
    const out = {};
    for (const v of WORKING_VOICES) {
      out[v] = {
        enabled: false,
        provider: "inherit",
        model: "",
        system_prompt: "",
      };
    }
    return out;
  },
  read() {
    try {
      const raw = localStorage.getItem(TEAM_KEY);
      if (!raw) return this._default();
      const parsed = JSON.parse(raw);
      const merged = this._default();
      for (const v of WORKING_VOICES) {
        const row = parsed?.[v];
        if (row && typeof row === "object") {
          merged[v] = {
            enabled: !!row.enabled,
            provider: VALID_TEAM_PROVIDERS.has(row.provider) ? row.provider : "inherit",
            model: typeof row.model === "string" ? row.model.slice(0, 128) : "",
            system_prompt: typeof row.system_prompt === "string"
              ? row.system_prompt.slice(0, MAX_PROMPT_LEN)
              : "",
          };
        }
      }
      return merged;
    } catch {
      return this._default();
    }
  },
  write(value) {
    const sanitised = this._default();
    for (const v of WORKING_VOICES) {
      const row = value?.[v];
      if (row && typeof row === "object") {
        sanitised[v] = {
          enabled: !!row.enabled,
          provider: VALID_TEAM_PROVIDERS.has(row.provider) ? row.provider : "inherit",
          model: typeof row.model === "string" ? row.model.slice(0, 128) : "",
          system_prompt: typeof row.system_prompt === "string"
            ? row.system_prompt.slice(0, MAX_PROMPT_LEN)
            : "",
        };
      }
    }
    try { localStorage.setItem(TEAM_KEY, JSON.stringify(sanitised)); } catch { /* noop */ }
    return sanitised;
  },
  clear() {
    try { localStorage.removeItem(TEAM_KEY); } catch { /* noop */ }
    return this._default();
  },
  // True if any persona is enabled — used to decide whether to send the
  // overrides on the wire and to light up the "customised" badge.
  isCustomised(value) {
    const v = value || this.read();
    return WORKING_VOICES.some((voice) => v[voice]?.enabled);
  },
};

/* ─── App state ───────────────────────────────────────────────────── */

let activeCaseId = null;
let activeSettingsTab = "provider";  // "provider" | "team"

/* ─── Init ────────────────────────────────────────────────────────── */

document.addEventListener("DOMContentLoaded", () => { void init(); });

async function init() {
  const personas = await fetchPersonas();
  renderEmptyRoster(personas);

  renderSidebar();
  refreshProviderIndicators();

  const cases = caseStore.list();
  if (cases.length > 0) {
    selectCase(cases[0].case_id);
  } else {
    showEmptyState();
  }

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
  showCaseDetail(stored.dialogue, stored.provider, stored.customised);
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
  if (question) question.value = "";
  if (role) role.value = "";
  autoGrowTextarea(question);
}

function showCaseDetail(dialogue, provider, customised) {
  const { emptyState, caseDetail } = els();
  emptyState.hidden = true;
  caseDetail.hidden = false;
  renderCaseHeader(dialogue, provider, customised);
  renderMessageStream(dialogue.turns || []);
  renderVerdict(dialogue);
  renderConflicts(dialogue.conflicts || []);
  const q = els().question;
  if (q) { q.value = ""; autoGrowTextarea(q); }
  // Scroll the case detail to top so the user always lands at the case header.
  caseDetail.scrollTop = 0;
}

function renderCaseHeader(dialogue, provider, customised) {
  const { caseHeaderId, caseHeaderTitle, caseHeaderMeta } = els();
  caseHeaderId.textContent = `Case · ${dialogue.case_id || "—"}`;
  caseHeaderTitle.textContent = dialogue.question || "(untitled case)";

  const roleLabel = dialogue.role ? ROLE_LABELS[dialogue.role] || dialogue.role : "no role";
  const refCount = (dialogue.references || []).length;
  const confidence = (dialogue.confidence || 0).toFixed(2);
  const providerKey = provider && VALID_PROVIDERS.has(provider) && provider !== "" ? provider : "server";
  const providerLabel = providerKey === "server" ? "Server default" : (PROVIDER_LABELS[providerKey] || providerKey);
  const customBadge = customised
    ? `<span class="case-header__custom" title="One or more characters used a custom system prompt or model">Custom team</span>`
    : "";
  caseHeaderMeta.innerHTML = `
    <span class="case-header__pill">${escHtml(roleLabel)}</span>
    <span class="case-header__provider" data-provider="${escAttr(providerKey)}">${escHtml(providerLabel)}</span>
    ${customBadge}
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

  const claim = document.createElement("p");
  claim.className = "message__claim";
  claim.textContent = turn.claim || "";
  body.appendChild(claim);

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
    if (flag === "objection") continue;
    const chip = document.createElement("span");
    chip.className = "flag-chip";
    chip.textContent = flag;
    cites.appendChild(chip);
  }
  footer.appendChild(cites);

  const conf = renderConfidence(turn.confidence || 0);
  footer.appendChild(conf);

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
  const e = els();

  e.composer?.addEventListener("submit", onSubmit);
  e.newCaseBtn?.addEventListener("click", startNewCase);
  e.sidebarToggle?.addEventListener("click", toggleSidebar);

  // Composer textarea behaviour
  e.question?.addEventListener("input", () => autoGrowTextarea(e.question));
  e.question?.addEventListener("keydown", (ev) => {
    const isEnter = ev.key === "Enter" || ev.key === "Return";
    if (isEnter && (ev.metaKey || ev.ctrlKey)) {
      ev.preventDefault();
      e.composer.requestSubmit();
    }
  });

  // Settings dialog
  e.settingsBtn?.addEventListener("click", () => openSettings());
  e.shortcutsBtn?.addEventListener("click", () => openModal("shortcuts-dialog"));
  e.settingsForm?.addEventListener("submit", onSettingsSave);
  e.settingsClear?.addEventListener("click", onSettingsClear);
  e.settingsResetTeam?.addEventListener("click", onSettingsResetTeam);
  e.settingsKeyReveal?.addEventListener("click", toggleKeyReveal);
  e.settingsForm?.addEventListener("change", onSettingsProviderChange);
  e.tabProvider?.addEventListener("click", () => switchTab("provider"));
  e.tabTeam?.addEventListener("click", () => switchTab("team"));

  // Modal dismiss: any [data-modal-close] or backdrop click
  document.querySelectorAll("[data-modal-close]").forEach((el) => {
    el.addEventListener("click", (ev) => {
      const id = ev.currentTarget.getAttribute("data-modal-close");
      if (id) closeModal(id);
    });
  });

  // Global keyboard shortcuts
  document.addEventListener("keydown", onGlobalKeyDown);

  // Mobile sidebar dismissal on outside click
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

  setSubmitLoading(true);
  try {
    const settings = settingsStore.read();
    const team = teamStore.read();
    const dialogue = await postCase(question, role, settings, team);
    const customised = teamStore.isCustomised(team);
    caseStore.upsert(dialogue, { provider: settings.provider, customised });
    activeCaseId = dialogue.case_id;
    renderSidebar();
    showCaseDetail(dialogue, settings.provider, customised);
  } catch (err) {
    console.error(err);
    setComposerError("Couldn't open the case. Is the API up? Try again.");
  } finally {
    setSubmitLoading(false);
  }
}

async function postCase(question, role, settings, team) {
  const headers = { "Content-Type": "application/json", Accept: "application/json" };
  if (settings && settings.provider && settings.api_key) {
    headers["X-Specter-LLM-Provider"] = settings.provider;
    headers["X-Specter-LLM-Key"] = settings.api_key;
  }

  // Persona overrides — only the personas the user explicitly enabled,
  // and only the fields that differ from the defaults. Per-persona
  // provider/key fields are LEFT EMPTY when set to "inherit" so the
  // server falls through to the BYOK header pair above. Custom system
  // prompts always go (those are the whole point of the team tab).
  const overrides = [];
  if (team) {
    for (const voice of WORKING_VOICES) {
      const row = team[voice];
      if (!row?.enabled) continue;
      const o = { voice };
      if (row.system_prompt && row.system_prompt.trim()) {
        o.system_prompt = row.system_prompt.slice(0, MAX_PROMPT_LEN);
      }
      if (row.provider && row.provider !== "inherit") {
        o.provider = row.provider;
      }
      if (row.model) o.model = row.model;
      overrides.push(o);
    }
  }

  const body = {
    question,
    role: role || null,
    enable_louis_objection: true,
  };
  if (overrides.length > 0) body.persona_overrides = overrides;

  const res = await fetch(`${API_BASE}/v1/case`, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`case failed: ${res.status} ${text}`);
  }
  return res.json();
}

function setSubmitLoading(loading) {
  const e = els();
  if (!e.submit) return;
  if (loading) {
    e.submit.setAttribute("disabled", "true");
    e.submit.setAttribute("aria-busy", "true");
    if (e.submitLabel) e.submitLabel.textContent = "Working the case…";
  } else {
    e.submit.removeAttribute("disabled");
    e.submit.removeAttribute("aria-busy");
    if (e.submitLabel) e.submitLabel.textContent = "Open case";
  }
}

/* ─── Settings dialog ────────────────────────────────────────────── */

function openSettings(tab) {
  const e = els();
  const settings = settingsStore.read();
  const team = teamStore.read();

  // Fill the Provider tab from storage
  const radios = e.settingsForm?.querySelectorAll("input[name=provider]") || [];
  radios.forEach((r) => { r.checked = (r.value === settings.provider); });
  if (e.settingsKey) e.settingsKey.value = settings.api_key || "";
  if (e.settingsKey) e.settingsKey.type = "password";
  if (e.settingsKeyReveal) {
    e.settingsKeyReveal.setAttribute("aria-pressed", "false");
    e.settingsKeyReveal.textContent = "show";
  }
  if (e.settingsStatus) e.settingsStatus.textContent = "";
  reflectKeyFieldVisibility(settings.provider);

  // Render the Team tab
  renderTeamEditor(team);
  reflectTeamCustomisation(team);

  // Pick which tab to show
  switchTab(tab || activeSettingsTab || "provider");

  openModal("settings-dialog");
  setTimeout(() => {
    const focusEl = activeSettingsTab === "team"
      ? e.teamEditor?.querySelector(".team-card__toggle")
      : e.settingsForm?.querySelector("input[name=provider]:checked");
    focusEl?.focus();
  }, 30);
}

function switchTab(tab) {
  const e = els();
  activeSettingsTab = tab === "team" ? "team" : "provider";
  // Tab buttons
  [e.tabProvider, e.tabTeam].forEach((btn) => {
    if (!btn) return;
    btn.setAttribute("aria-selected", btn.dataset.tab === activeSettingsTab ? "true" : "false");
  });
  // Panes
  if (e.paneProvider) e.paneProvider.hidden = (activeSettingsTab !== "provider");
  if (e.paneTeam)     e.paneTeam.hidden     = (activeSettingsTab !== "team");
  if (e.settingsResetTeam) e.settingsResetTeam.hidden = (activeSettingsTab !== "team");
}

/* ─── Team editor: render + read-from-DOM ───────────────────────── */

function renderTeamEditor(team) {
  const root = els().teamEditor;
  if (!root) return;
  root.innerHTML = "";
  for (const voice of WORKING_VOICES) {
    root.appendChild(renderTeamCard(voice, team[voice]));
  }
}

function renderTeamCard(voice, row) {
  const persona = DEFAULT_PERSONAS.find((p) => p.voice === voice);
  const card = document.createElement("article");
  card.className = "team-card";
  card.dataset.voice = voice;
  card.dataset.on = row.enabled ? "true" : "false";

  // ─── Header: avatar + identity + on/off toggle ───
  const header = document.createElement("div");
  header.className = "team-card__header";
  header.innerHTML = `
    <span class="avatar-initials team-card__avatar" data-voice="${escAttr(voice)}" aria-hidden="true">${escHtml(PERSONA_INITIALS[voice] || "??")}</span>
    <span class="team-card__id">
      <span class="team-card__name">${escHtml(persona?.name || titleCase(voice))}</span>
      <span class="team-card__title">${escHtml(persona?.title || "")}</span>
    </span>
  `;
  const toggle = document.createElement("button");
  toggle.type = "button";
  toggle.className = "team-card__toggle";
  toggle.dataset.role = "toggle";
  toggle.setAttribute("aria-pressed", String(row.enabled));
  toggle.textContent = row.enabled ? "On — LLM voice" : "Off — deterministic";
  toggle.addEventListener("click", () => {
    const on = card.dataset.on !== "true";
    card.dataset.on = on ? "true" : "false";
    toggle.setAttribute("aria-pressed", String(on));
    toggle.textContent = on ? "On — LLM voice" : "Off — deterministic";
  });
  header.appendChild(toggle);
  card.appendChild(header);

  // ─── Body: provider, model, system prompt ───
  const body = document.createElement("div");
  body.className = "team-card__body";

  // Provider row
  const provider = teamRow(
    "Provider",
    (() => {
      const sel = document.createElement("select");
      sel.className = "team-card__select";
      sel.dataset.role = "provider";
      const opts = [
        ["inherit", "↑ Inherit (use Provider tab)"],
        ["claude", "Anthropic Claude"],
        ["openai", "OpenAI ChatGPT"]
      ];
      for (const [v, label] of opts) {
        const opt = document.createElement("option");
        opt.value = v;
        opt.textContent = label;
        if (v === row.provider) opt.selected = true;
        sel.appendChild(opt);
      }
      sel.addEventListener("change", () => {
        rebuildModelMenu(card, sel.value, row.model);
      });
      return sel;
    })(),
    "Picks which API your custom voice for this character uses. Inherit uses the global Provider tab key.",
  );
  body.appendChild(provider);

  // Model row
  const modelHolder = document.createElement("div");
  modelHolder.className = "team-card__model-holder";
  body.appendChild(teamRow("Model", modelHolder, ""));
  rebuildModelMenu(card, row.provider, row.model, modelHolder);

  // System prompt row
  const sysWrap = document.createElement("div");
  sysWrap.style.minWidth = "0";
  const sys = document.createElement("textarea");
  sys.className = "team-card__textarea";
  sys.dataset.role = "system_prompt";
  sys.rows = 6;
  sys.maxLength = MAX_PROMPT_LEN;
  sys.placeholder = DEFAULT_PERSONA_PROMPTS[voice] || "";
  sys.value = row.system_prompt || "";
  sysWrap.appendChild(sys);
  const sysHint = document.createElement("span");
  sysHint.className = "team-card__hint";
  sysHint.textContent = "Empty = use the canonical voice template (shown as placeholder).";
  sysWrap.appendChild(sysHint);

  body.appendChild(teamRow("Personality", sysWrap, ""));

  // Reset row
  const reset = document.createElement("button");
  reset.type = "button";
  reset.className = "team-card__reset";
  reset.textContent = "Reset to default";
  reset.addEventListener("click", () => {
    card.querySelector(".team-card__toggle").click();
    card.querySelector(".team-card__toggle").click();   // toggle on then off so on stays
    card.querySelector("[data-role=provider]").value = "inherit";
    rebuildModelMenu(card, "inherit", "");
    sys.value = "";
  });
  body.appendChild(reset);

  card.appendChild(body);
  return card;
}

function teamRow(label, controlEl, hint) {
  const wrap = document.createElement("div");
  wrap.className = "team-card__row";
  const labelEl = document.createElement("span");
  labelEl.className = "team-card__label";
  labelEl.textContent = label;
  wrap.appendChild(labelEl);
  wrap.appendChild(controlEl);
  if (hint) {
    const hintEl = document.createElement("span");
    hintEl.className = "team-card__hint";
    hintEl.textContent = hint;
    wrap.appendChild(hintEl);
  }
  return wrap;
}

function rebuildModelMenu(card, provider, currentValue, holder) {
  const target = holder || card.querySelector(".team-card__model-holder");
  if (!target) return;
  target.innerHTML = "";
  if (!provider || provider === "inherit") {
    const note = document.createElement("span");
    note.className = "team-card__hint";
    note.textContent = "Provider default model — pick a specific model only if you've selected an explicit provider above.";
    target.appendChild(note);
    return;
  }
  const sel = document.createElement("select");
  sel.className = "team-card__select";
  sel.dataset.role = "model";
  const optBlank = document.createElement("option");
  optBlank.value = "";
  optBlank.textContent = "Provider default";
  sel.appendChild(optBlank);
  for (const id of MODELS_PER_PROVIDER[provider] || []) {
    const opt = document.createElement("option");
    opt.value = id;
    opt.textContent = id;
    if (id === currentValue) opt.selected = true;
    sel.appendChild(opt);
  }
  target.appendChild(sel);
}

function readTeamFromDOM() {
  const root = els().teamEditor;
  const out = teamStore._default();
  if (!root) return out;
  for (const card of root.querySelectorAll(".team-card")) {
    const voice = card.dataset.voice;
    if (!WORKING_VOICES.includes(voice)) continue;
    out[voice] = {
      enabled: card.dataset.on === "true",
      provider: card.querySelector("[data-role=provider]")?.value || "inherit",
      model: card.querySelector("[data-role=model]")?.value || "",
      system_prompt: card.querySelector("[data-role=system_prompt]")?.value || "",
    };
  }
  return out;
}

function reflectTeamCustomisation(team) {
  const e = els();
  const customised = teamStore.isCustomised(team);
  if (e.tabTeam) {
    const subEl = e.tabTeam.querySelector(".settings-tab__sub");
    if (subEl) {
      subEl.textContent = customised
        ? "Customised — voices are LLM-driven"
        : "Customise voices & models";
    }
  }
}

function onSettingsProviderChange(ev) {
  const target = ev.target;
  if (target?.name !== "provider") return;
  reflectKeyFieldVisibility(target.value);
}

function reflectKeyFieldVisibility(provider) {
  const e = els();
  if (!e.settingsKeyField) return;
  // Hide the key field for the server-default option — no key needed.
  e.settingsKeyField.hidden = !provider;
}

function onSettingsSave(ev) {
  ev.preventDefault();
  const e = els();
  const provider = e.settingsForm?.querySelector("input[name=provider]:checked")?.value || "";
  const apiKey = (e.settingsKey?.value || "").trim();

  // Validate: a non-default provider needs a key.
  if (provider && !apiKey) {
    if (e.settingsStatus) {
      e.settingsStatus.textContent = "Add an API key for the chosen provider, or pick Server default.";
      e.settingsStatus.style.color = "#B12B17";
    }
    switchTab("provider");
    e.settingsKey?.focus();
    return;
  }

  // Persist Provider tab
  settingsStore.write({ provider, api_key: provider ? apiKey : "" });

  // Persist Team tab — read whatever the user typed even if they
  // didn't visit the tab; readTeamFromDOM() returns the default state
  // for personas they didn't touch.
  const teamFromDom = readTeamFromDOM();
  teamStore.write(teamFromDom);

  if (e.settingsStatus) {
    const customised = teamStore.isCustomised(teamFromDom);
    const teamSuffix = customised ? " · custom team active" : "";
    e.settingsStatus.textContent = provider
      ? `Saved. Using ${PROVIDER_LABELS[provider] || provider}${teamSuffix}.`
      : `Saved. Using server default${teamSuffix}.`;
    e.settingsStatus.style.color = "";
  }
  refreshProviderIndicators();
  reflectTeamCustomisation(teamFromDom);
  showToast(provider ? `Using ${PROVIDER_LABELS[provider] || provider}` : "Using server default");
  setTimeout(() => closeModal("settings-dialog"), 700);
}

function onSettingsClear() {
  const e = els();
  settingsStore.clear();
  teamStore.clear();
  e.settingsForm?.reset();
  if (e.settingsKey) e.settingsKey.value = "";
  reflectKeyFieldVisibility("");
  renderTeamEditor(teamStore.read());
  reflectTeamCustomisation(teamStore.read());
  if (e.settingsStatus) {
    e.settingsStatus.textContent = "Cleared everything. Falling back to server default.";
    e.settingsStatus.style.color = "";
  }
  refreshProviderIndicators();
  showToast("Settings cleared");
}

function onSettingsResetTeam() {
  teamStore.clear();
  renderTeamEditor(teamStore.read());
  reflectTeamCustomisation(teamStore.read());
  showToast("Team reset to defaults");
}

function toggleKeyReveal() {
  const e = els();
  if (!e.settingsKey || !e.settingsKeyReveal) return;
  const nowVisible = e.settingsKey.type === "password";
  e.settingsKey.type = nowVisible ? "text" : "password";
  e.settingsKeyReveal.setAttribute("aria-pressed", String(nowVisible));
  e.settingsKeyReveal.textContent = nowVisible ? "hide" : "show";
}

function refreshProviderIndicators() {
  const e = els();
  const settings = settingsStore.read();
  const label = settings.provider
    ? (PROVIDER_LABELS[settings.provider] || settings.provider)
    : "default";
  if (e.settingsBadge) {
    e.settingsBadge.textContent = label;
    if (settings.provider) {
      e.settingsBadge.dataset.provider = settings.provider;
    } else {
      delete e.settingsBadge.dataset.provider;
    }
  }
  if (e.composerProvider) {
    if (settings.provider) {
      e.composerProvider.textContent = `via ${PROVIDER_LABELS[settings.provider] || settings.provider}`;
      e.composerProvider.dataset.provider = settings.provider;
    } else {
      e.composerProvider.textContent = "";
      delete e.composerProvider.dataset.provider;
    }
  }
}

/* ─── Modal helpers ─────────────────────────────────────────────── */

function openModal(id) {
  const dlg = document.getElementById(id);
  if (!dlg) return;
  dlg.hidden = false;
  // Lock body scroll while a modal is open.
  document.body.style.overflow = "hidden";
}

function closeModal(id) {
  const dlg = document.getElementById(id);
  if (!dlg) return;
  dlg.hidden = true;
  // Restore body scroll only if no other modal is still open.
  const stillOpen = document.querySelector(".modal:not([hidden])");
  if (!stillOpen) document.body.style.overflow = "";
}

function closeAllModals() {
  document.querySelectorAll(".modal:not([hidden])").forEach((m) => closeModal(m.id));
}

/* ─── Toast ─────────────────────────────────────────────────────── */

let toastTimer = null;
function showToast(text) {
  const e = els();
  if (!e.toast) return;
  e.toast.textContent = text;
  e.toast.hidden = false;
  // Force a reflow so the transition fires
  void e.toast.offsetHeight;
  e.toast.dataset.visible = "true";
  if (toastTimer) clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    e.toast.dataset.visible = "false";
    setTimeout(() => { e.toast.hidden = true; }, 240);
  }, 2200);
}

/* ─── Global keyboard shortcuts ─────────────────────────────────── */

function onGlobalKeyDown(ev) {
  // Esc always closes any open modal.
  if (ev.key === "Escape") {
    const open = document.querySelector(".modal:not([hidden])");
    if (open) {
      ev.preventDefault();
      closeModal(open.id);
    }
    return;
  }

  // Don't trigger letter shortcuts while user is typing in a field.
  const t = ev.target;
  const inField = t && (t.tagName === "TEXTAREA" || t.tagName === "INPUT" || t.isContentEditable);
  if (inField) return;
  // Ignore modifier-loaded chords; we only handle bare key presses.
  if (ev.metaKey || ev.ctrlKey || ev.altKey) return;

  if (ev.key === "?") {
    ev.preventDefault();
    openModal("shortcuts-dialog");
  } else if (ev.key === ",") {
    ev.preventDefault();
    openSettings();
  } else if (ev.key === "n" || ev.key === "N") {
    ev.preventDefault();
    startNewCase();
  }
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
