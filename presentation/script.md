# Presentation Script

**Total time:** ~20 minutes  
**Breakdown:** ~4 min slides, ~16 min demo  
**Format:** Keep spoken parts brief — the demo carries the presentation.

---

## Slide 1 — Title Page (~20 sec)

**Speaker: Ben Blake**

"Hi everyone. I'm Ben Blake, and with me are Rasagyna, Bhavya, and Mukunda. We'll do a quick overview of what we built and then jump straight into the demo."

---

## Slide 2 — What We Built (~30 sec)

**Speaker: Ben Blake**

"The app is a browser-based interface for managing Network Attached Storage. It has four modules: user management, file browsing and upload, live system monitoring, and backup scheduling with restore. We're running Flask on an Ubuntu VM with SQLite, and using ngrok to tunnel out of the VM so we can reach it remotely over HTTPS."

---

## Slide 3 — Key Design Decisions (~30 sec)

**Speaker: Ben Blake**

"We used Flask Blueprints so each person owned one module with no merge conflicts. SQLite keeps it simple — no separate DB server. ngrok gets us HTTPS out of a NAT'd VM with zero configuration. And access control is split into role — admin or user — which controls what pages you can reach, and permissions — read, write, edit — which control what you can do with files."

---

## Slide 4 — User Management (~20 sec)

**Speaker: Ben Blake**

"My module handles login, user accounts, roles, and permissions. And I'll demo that for you now."

---

## Slide 5 — DEMO: User Management (~4 min)

**Speaker: Ben Blake**

*(Switch to browser — run demo-script.md Section 1)*

---

## Slide 6 — File Management (~20 sec)

**Speaker: Rasagyna Peddapalli**

"My module is the file browser — upload, download, create folders, rename, and delete. Every path is validated server-side to block traversal attacks. Here's the demo."

---

## Slide 7 — DEMO: File Management (~4 min)

**Speaker: Rasagyna Peddapalli**

*(Switch to browser — run demo-script.md Section 2)*

---

## Slide 8 — System Monitoring (~20 sec)

**Speaker: Bhavya Harshitha Chennu**

"My module shows live CPU, memory, and disk stats plus a system log viewer. Stats update every 10 seconds via a javascript fetch call — so it doesn't have to do a full page reload. Logs are read-only from the UI. Here's the monitor."

---

## Slide 9 — DEMO: System Monitoring (~4 min)

**Speaker: Bhavya Harshitha Chennu**

*(Switch to browser — run demo-script.md Section 3)*

---

## Slide 10 — Backup & Restore (~20 sec)

**Speaker: Mukunda Chakravartula**

"My module handles backups — manual snapshots, a configurable automatic schedule, and restore. Let me show it."

---

## Slide 11 — DEMO: Backup & Restore (~4 min)

**Speaker: Mukunda Chakravartula**

*(Switch to browser — run demo-script.md Section 4)*

---

## Slide 12 — Summary (~20 sec)

**Speaker: Ben Blake**

"To wrap up: four modules, one integrated app, role-based access control throughout, 142 automated tests all passing, deployed on Ubuntu and accessible via ngrok. We're happy to take any questions."

---

## Slide 13 — Questions

*(Field questions as a team — each person owns their module.)*

---

## Timing Guide

| Section | Target Time |
|---|---|
| Slides 1–3 (intro + overview) | ~1 min |
| Slide 4 + Demo (User Management) | ~4.5 min |
| Slide 6 + Demo (File Management) | ~4.5 min |
| Slide 8 + Demo (System Monitoring) | ~4.5 min |
| Slide 10 + Demo (Backup & Restore) | ~4.5 min |
| Slide 12–13 (summary + Q&A) | ~1 min |
| **Total** | **~20 min** |
