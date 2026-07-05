# Skills Companion — Design Spec

- **Date:** 2026-07-06
- **Status:** Approved design (pre-implementation)
- **Working name:** Skills Companion
- **Home:** `~/Desktop/Work_with_Claude_Mac/skills-companion/`

---

## 1. Context & Motivation

A prior session reduced Claude Code session-startup context by silencing personal
skills (`skillOverrides: user-invocable-only`), disabling unused plugins
(`enabledPlugins`), and shipping a **static HTML cheat sheet** opened by a
`SessionStart` hook + `/myskills`. See memory `claude-startup-context-tuning`.

That static cheat sheet has three shortcomings the user wants fixed:

1. **Wrong surface.** It opens as a plain browser tab, tangled with work tabs / an
   arbitrary window — not a dedicated app.
2. **Flat listing.** A single search + fixed categories does not organize 150+
   skills/commands by multiple, switchable criteria.
3. **No context awareness.** It cannot suggest what is relevant to what the user is
   currently doing.

**This project replaces the static cheat sheet with a resident, cross-platform
tray application** that lists skills/plugins dynamically and recommends relevant
ones based on the active session's content — with **no AI**, using deterministic
keyword matching — and can **(re)activate a disabled plugin** on one click, with a
**session-scoped revert** lifecycle.

---

## 2. Ubiquitous Language (glossary)

- **Catalog** — the scanned inventory of everything invocable: personal skills,
  plugin skills, plugin commands, and the enabled/disabled state of plugins.
- **Silenced skill** — a personal skill set to `user-invocable-only`: hidden from
  Claude's context but still callable via `/name`. (This is the baseline for all
  personal skills except `domain-modeling`.)
- **Activation** — the app enabling a **disabled plugin** (`enabledPlugins → true`)
  in response to a user-accepted recommendation. **Applies to plugins only.**
- **Recommendation** — a ranked catalog item the app surfaces for the active
  session. Two kinds:
  - *Actionable* — a disabled plugin; accepting it performs an Activation.
  - *Informational* — a callable skill; accepting it just tells the user the
    `/command` to run (no state change).
- **Session-scoped activation** — an Activation tagged to the session that
  requested it; eligible for Revert when that session ends.
- **Persistent activation** — an activation the user chose to keep; removed from the
  Ledger, left enabled.
- **Revert** — undoing a session-scoped activation (`enabledPlugins → false`).
- **Revert Policy** — configurable behavior on session end: `ask` (default) /
  `auto-revert` / `keep`, with **per-plugin overrides** ("remember for this plugin").
- **Ledger** — persisted map `session_id → [activated plugin@marketplace, …]` with
  timestamps; the source of truth for what to revert.
- **Leak** — a session-scoped activation whose session ended without the SessionEnd
  hook firing (e.g. Ctrl+C, terminal close, crash); caught by the Leak Sweep.

> Personal skills are **never** activated/reverted — they are only recommended for
> manual invocation. The entire activation/revert lifecycle concerns **plugins**.

---

## 3. Verified Platform Constraints (doc-grounded)

These are hard constraints the design must respect. Each was verified against
official Claude Code docs during design (see memory `claude-startup-context-tuning`
and this session's research).

- **C1 — Plugin load timing.** Plugin skills/agents/commands/MCP load at session
  start. Flipping `enabledPlugins → true` mid-session does **not** auto-load them;
  the running session must run **`/reload-plugins`** (or be resumed via
  `claude --continue`) to pick them up.
- **C2 — No external input injection.** There is **no supported, local, scriptable**
  way for an external process to inject a prompt/command into an already-running
  interactive session. Remote Control is a web→local bridge, not a local API.
- **C3 — No session→terminal mapping.** Transcripts carry `sessionId`, `cwd`,
  `gitBranch` but **no `pid`/`tty`**. `~/.claude/session-env/<uuid>/` and
  `~/.claude/ide/` are empty for terminal sessions. The app cannot reliably find
  which terminal hosts a session → terminal auto-typing is best-effort only.
- **C4 — SessionEnd is non-interactive and cannot block.** Fire-and-forget cleanup.
  It **cannot prompt** the user. So the *asking* must be done by the resident app.
- **C5 — SessionEnd is unreliable.** Fires only on `/exit` and Ctrl+D. Does **not**
  fire on Ctrl+C, terminal close, `kill`, logout, or crash → cleanup can **leak** →
  requires the Leak Sweep fallback.
- **C6 — SessionEnd can emit a fast signal.** Writing a small marker file or POSTing
  to localhost synchronously before exit is reliable; async work is killed.
- **C7 — `skillOverrides` is personal/project only.** It does not affect plugin
  skills; plugins are managed via `enabledPlugins`. (Confirms activation = plugin
  enable, not a skillOverride edit.)
- **C8 — settings.json hot-reloads** on change, but per C1 that alone does not load
  plugin components into a running session.

**Design consequence:** the hook only *signals*; the resident app *decides, asks,
activates, reverts*; activation completion (`/reload-plugins`) is externalized to
the user via clipboard (portable) + optional macOS auto-type (best-effort).

---

## 4. Goals / Non-Goals

**Goals**
- Resident tray app (macOS first, cross-platform-ready) replacing the static sheet.
- Dynamic, multi-facet listing of the catalog.
- No-AI, session-content-driven recommendations.
- One-click plugin activation (settings write + clipboard `/reload-plugins` + toast;
  macOS best-effort auto-type).
- Session-scoped revert with configurable policy (`ask` default + per-plugin memory)
  and a leak-sweep fallback.

**Non-Goals (now)**
- Windows/Linux packaging (code stays portable; packaging is later).
- Live-updating panel mode.
- Recommending or toggling agents.
- Un-silencing personal skills (skill state changes).
- Any AI/LLM in the recommendation path.

---

## 5. Architecture

Two cooperating layers, so the recommendation logic is testable without a GUI.

- **Shell (Tauri, Rust):** system tray + menu, app window (system webview), native
  notifications, native dialogs (the revert ask), clipboard write, and the
  macOS-only best-effort terminal auto-type. Owns lifecycle; spawns the brain.
- **Brain (Python sidecar):** all logic and data. Reuses the existing
  `~/.claude/skills-cheatsheet/generate.py` **scanning logic** (ported into the
  project). Reads transcripts, computes recommendations, reads/writes
  `settings.json`, maintains the Ledger and Config. Exposes a small **CLI/JSON API**
  (stdin/stdout or localhost) so it is unit-testable standalone.

```
[Tauri shell] --invoke--> [python brain CLI] --JSON--> [Tauri shell -> webview UI]
      |  tray/menu/notify/dialog/clipboard/(mac)autotype
      |
[SessionEnd hook] --writes signal file--> [shell watches] --> revert flow
```

**Data at rest** (app data dir, e.g. `~/.claude/skills-companion/state/`):
- `ledger.json` — session_id → activated plugins (+ timestamps).
- `config.json` — global default policy + per-plugin overrides + notification opt-in.
- Signal drop dir — `session-ended/<session_id>.json` written by the hook.

---

## 6. Components (responsibility · interface · depends-on)

1. **Scanner** — *what:* build the Catalog from `~/.claude/skills/*/SKILL.md`,
   `enabledPlugins`, and plugin-cache skills/commands. *Interface:* `scan() → Catalog
   JSON` (items with invoke, name, desc, source, category, state, invocation).
   *Deps:* filesystem, settings.json. *Reuse:* ported from `generate.py`.
2. **Recommender** — *what:* rank Catalog items for the active session. *Interface:*
   `recommend(session_id?) → [Recommendation]`. *Deps:* Scanner, Transcript reader.
3. **Session Watcher** — *what:* determine the active session (newest transcript),
   detect ends (hook signal), run the Leak Sweep. *Interface:* events
   `active_changed`, `session_ended(session_id, reason)`, `leak_detected([…])`.
   *Deps:* filesystem watch on `~/.claude/projects/**/*.jsonl` + signal dir.
4. **Activation Manager** — *what:* perform an Activation. *Interface:*
   `activate(plugin) → {settings_written, clipboard_set, autotyped?}`; appends to
   Ledger. *Deps:* settings.json writer (atomic + backup), clipboard, (mac) auto-type.
5. **Revert Engine** — *what:* on session end, apply policy to that session's Ledger
   entries. *Interface:* `on_session_end(session_id, reason)`; enforces the
   **concurrency guard**; emits an ask-request when policy = `ask`. *Deps:* Ledger,
   Config, settings writer, Session Watcher (to know other live sessions).
6. **UI Shell** — *what:* tray menu (top-3 recs + open), window (faceted list),
   notifications (opt-in), the revert dialog. *Deps:* brain JSON API.
7. **Hooks Integration** — *what:* installer that (a) adds the SessionEnd
   signal-emitter hook, (b) **removes** the old HTML-open SessionStart hook, (c)
   repoints `/myskills` to focus the app window. *Deps:* settings.json.
   *Note:* the active `session_id` is derived from the newest transcript's filename
   (`<uuid>.jsonl`), so **no SessionStart signal hook is needed**.
8. **Stores** — Ledger + Config JSON with atomic writes.

---

## 7. Data Model

- **CatalogItem:** `{invoke, name, desc, source: personal|plugin, plugin?,
  category, state: enabled|disabled|silenced|loaded, invocation: auto|manual|command}`
- **Recommendation:** `{item, score, kind: actionable|informational, reasons:[matched terms]}`
- **LedgerEntry:** `{session_id, plugin, activated_at, cwd}`
- **Config:** `{default_policy: ask|auto-revert|keep, per_plugin: {plugin: ask|auto-revert|keep},
  notifications_enabled: bool, poll_seconds: 20}`

---

## 8. Recommendation Engine (no-AI)

- **Input:** last N (default ~30) messages of the active session transcript — user +
  assistant text and tool names/args.
- **Corpus per item:** `name + description + trigger phrases + category`.
- **Tokenization:** English → lowercase word tokens (stopword-filtered); Korean →
  character bigrams + known trigger substrings (handles unspaced compounds like
  "특허번역", "카톡시각화").
- **Score:** overlap of query tokens with item corpus, TF-IDF-weighted so rare,
  distinctive terms dominate. **Disabled plugins get a boost** (they are actionable
  and otherwise invisible). Threshold + top-K (default K=5).
- **Debounce:** only recompute on transcript change; only re-surface a notification
  when a *new* strong actionable rec appears (rate-limited).
- **Output:** ranked recommendations tagged actionable/informational with the matched
  terms as human-readable "why".

---

## 9. Key Flows

**Activate (accept actionable rec)**
1. User accepts (window or tray).
2. Activation Manager writes `enabledPlugins[plugin] = true` (atomic + timestamped
   backup of settings.json), appends Ledger entry `(session_id, plugin)`.
3. Copies `/reload-plugins` to clipboard; shows toast "Enabled ✓ — paste in your
   session". On macOS, best-effort types `/reload-plugins⏎` into the frontmost
   terminal (degrades to clipboard silently if it can't).

**Session end → revert**
1. SessionEnd hook writes `state/session-ended/<session_id>.json` `{reason, ts}`.
2. Shell/Watcher notices the signal; Revert Engine loads Ledger[session_id].
3. **Concurrency guard:** drop any plugin still activated by another live session.
4. Apply policy: `auto-revert` → disable now; `keep` → clear ledger, leave; `ask` →
   native dialog listing the plugins with [Revert all]/[Keep all]/per-item +
   "remember for this plugin" → updates per-plugin Config.
5. Reverted plugins: `enabledPlugins → false`; ledger entries cleared.

**Leak sweep (fallback for C5)**
- On app startup and every poll: for each Ledger entry with no matching live session
  (transcript idle beyond threshold AND no recent end-signal), surface a "lingering
  activations" prompt per policy. Nothing stays enabled silently without the user
  having seen a choice (unless policy = keep).

---

## 10. Error Handling & Edge Cases

- **settings.json writes:** always atomic + timestamped backup (reuse the prior
  session's proven pattern); validate JSON after write; never clobber unrelated keys.
- **Plugin already enabled** when accepted: no-op activation, still ledger-tracked so
  revert offers to return to the prior (disabled) state — but only if the app was the
  one that enabled it (don't revert user's manual enables).
- **Plugin renamed/removed** (per prior findings): activation/ledger keyed by
  `plugin@marketplace`; a stale ledger key that no longer resolves is dropped
  harmlessly and logged.
- **macOS auto-type** can't find/confirm the right terminal (C3): silently fall back
  to clipboard-only; never type into the wrong window aggressively.
- **Concurrent sessions** activating the same plugin: guard prevents premature
  revert; last session to end reverts it.
- **Hook missing (C5):** Leak Sweep covers it; also idempotent — reverting an
  already-disabled plugin is a no-op.
- **Reload not applied:** app copy/toast reminds; if the user never reloads, no harm
  (setting is correct; loads next session).

---

## 11. Testing Strategy

- **Brain is CLI-first → unit-testable without GUI.** Golden fixtures: a sample
  transcript → expected ranked recommendations (assert ordering & thresholds).
- Scanner: fixture skill/plugin trees → expected Catalog (incl. Korean categories).
- Activation Manager: settings write is atomic, backed up, JSON-valid, only the one
  key changed; ledger append correct.
- Revert Engine: policy matrix (ask/auto-revert/keep × per-plugin) + concurrency
  guard + leak sweep, driven by synthetic ledgers and fake session states.
- Cross-platform: path logic uses `~/.claude/...` (home-relative) — test on macOS;
  Windows path parity checked in code review.
- Shell (Tauri): thin; manual smoke test of tray/menu/dialog/clipboard/auto-type.

---

## 12. Migration (replace the static cheat sheet)

- **Remove:** the SessionStart hook entry that opens the HTML; the static
  `~/.claude/skills-cheatsheet.html`. (Keep backups.)
- **Reuse:** `generate.py` scanning logic → ported into the Scanner component.
- **Add:** SessionEnd signal-emitter hook; a LaunchAgent to auto-start the resident
  app at login. (Active `session_id` is derived from the newest transcript filename —
  no SessionStart signal needed.)
- **Repoint:** `/myskills` → focus/open the app window instead of opening HTML.
- Prior context-reduction settings (`skillOverrides`, `enabledPlugins` off) are
  **preserved**; the app reads/writes them, never bulk-reverts them.

---

## 13. Packaging & Install

- Tauri build → `.app` (macOS now). LaunchAgent `com.earendel.skills-companion` for
  resident auto-start. Windows `.exe/.msi` deferred.
- Python brain: rely on system `python3` for personal use (no bundling initially).

---

## 14. Out of Scope / Future

- Windows/Linux packaging & tray parity validation.
- Live-panel (second-monitor real-time) mode.
- Agent recommendations; un-silencing personal skills.
- Smarter matching (embeddings) — explicitly avoided to honor the no-AI requirement.

---

## 15. Open Risks

- **R1** `/reload-plugins` may not fully hot-load every plugin component in all cases
  (C1 caveat "no explicit guarantee"). Mitigation: toast also offers "restart/resume
  session" wording; document.
- **R2** macOS auto-type depends on Accessibility/Automation permission and the user
  having the terminal frontmost. Mitigation: clipboard is the reliable baseline;
  auto-type is a bonus.
- **R3** "Active session = newest transcript" can misattribute if the user rapidly
  interleaves sessions. Mitigation: recommendations are advisory; the Ledger (keyed
  by session_id from activation time) is authoritative for revert.
