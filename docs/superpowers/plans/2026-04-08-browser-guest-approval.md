# Browser Guest Approval Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Allow an Android browser session to appear as a pending approval on the desktop client, then let the user approve it so the phone can upload files to the computer.

**Architecture:** Extend the local web gateway to create and persist pending guest browser sessions when an unknown browser opens the LAN URL. Expose those pending sessions through `CoreService` and desktop state, then add a small desktop UI section that lists and approves pending browser sessions.

**Tech Stack:** Python, Tkinter, unittest, local HTTP server

---

### Task 1: Add failing tests for browser pending-session creation and approval

**Files:**
- Modify: `tests/test_hybrid_transfer.py`

- [ ] Add a test that requests the mobile browser endpoint without a guest token and expects a pending session token plus pending state.
- [ ] Run `python3 -m unittest tests.test_hybrid_transfer.WebAccessTests -q` and confirm the new test fails for the missing pending-session behavior.
- [ ] Add a desktop-facing test that verifies pending guest sessions become visible through `CoreService`.
- [ ] Run `python3 -m unittest tests.test_hybrid_transfer.CoreServiceNetworkTests -q` and confirm the new test fails for the missing pending-session exposure.

### Task 2: Implement pending browser-session tracking in the web and core layers

**Files:**
- Modify: `hybrid_transfer/web.py`
- Modify: `hybrid_transfer/core.py`

- [ ] Extend `GuestAccessController` so it can create idempotent pending sessions for browser requests and list pending guest sessions.
- [ ] Update `LocalWebGatewayServer` so mobile requests without a token create a pending guest session and return that token in the response payload.
- [ ] Expose pending guest sessions and approval operations from `CoreService`.
- [ ] Run the targeted unittest commands and confirm they pass.

### Task 3: Surface pending browser approvals in the desktop UI

**Files:**
- Modify: `hybrid_transfer/desktop_state.py`
- Modify: `hybrid_transfer/desktop.py`

- [ ] Extend desktop state snapshots with pending guest browser sessions.
- [ ] Add a small Tkinter section that lists pending browser sessions and includes an `Approve Selected Browser` action.
- [ ] Wire the approval button to the new `CoreService` approval method and refresh the UI after approval.
- [ ] Run targeted unittest commands and a source-entrypoint smoke check to confirm the flow still starts cleanly.
