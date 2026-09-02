# Project SRT — Contract Agreement

## Contract Version

**Contract Version:** v1.0  
**Status:** FROZEN  
**Project:** Project SRT — Smart Recognition and Tracking  
**SIH Problem Statement:** SIH26187

---

## 1. Purpose

The contracts in the `/contracts` directory define the agreed interfaces
between the AI, Computer Vision, Video/Realtime, Backend, Frontend,
Security, DevOps and QA modules of Project SRT.

They ensure that different team members and AI coding agents can work
independently without breaking communication between modules.

---

## 2. Frozen Contract Rule

The 23 contracts in `/contracts` are FROZEN as Contract v1.0.

No team member may:

- rename a contract
- delete a contract
- add a new contract
- change an existing contract
- change required fields
- change field types
- change enum values
- change the meaning of an existing field

without an explicit team-approved contract change.

---

## 3. The 23 Frozen Contracts

1. common.schema.json
2. detection.schema.json
3. tracking.schema.json
4. activity.schema.json
5. behavior_observation.schema.json
6. context.schema.json
7. baseline.schema.json
8. anomaly.schema.json
9. crowd.schema.json
10. zone_event.schema.json
11. risk.schema.json
12. event.schema.json
13. incident.schema.json
14. evidence.schema.json
15. alert.schema.json
16. vehicle.schema.json
17. anpr.schema.json
18. face.schema.json
19. reid.schema.json
20. camera_health.schema.json
21. operator_feedback.schema.json
22. api_response.schema.json
23. model_metadata.schema.json

---

## 4. Contract Ownership

The contracts are a shared project-level agreement.

Individual module owners may implement their modules independently,
but implementation must follow the frozen contracts.

No module may silently change a contract to make its own implementation
easier.

---

## 5. Implementation Rule

If a module produces data:

    Producer → Frozen Contract → Consumer

The producer must generate data matching the contract.

The consumer must expect data matching the contract.

Internal implementation can change without changing the contract.

---

## 6. AI Coding Agent Rule

Before modifying any Project SRT module, AI coding agents must:

1. Read this document.
2. Read the relevant contract.
3. Preserve the contract.
4. Never silently modify a contract.
5. Report any apparent contract conflict instead of changing it automatically.

---

## 7. Contract Changes

Contract changes are NOT normal implementation changes.

If a genuine contract change becomes necessary, the team must first document:

- Why the change is necessary
- Which modules are affected
- Current behavior
- Proposed behavior
- Compatibility impact
- Tests required
- Migration impact

No contract change is considered approved until the team explicitly agrees.

---

## 8. Versioning

Contract v1.0 is the current frozen baseline.

Future contract versions must be explicitly approved.

Non-breaking changes may use a minor version.

Breaking changes require a major version.

---

## 9. Important Distinction

Contracts are NOT database schemas.

Contracts define communication between modules and services.

Database models may contain additional internal fields that do not
need to appear in the public module contract.

---

## 10. Team Agreement

By approving this document, each team member agrees to follow the
Project SRT Contract v1.0 rules.

Team members:

- Member 1 — AI/ML
- Member 2 — Computer Vision
- Member 3 — Video/Realtime/Edge
- Member 4 — Backend/Data/Security
- Member 5 — Frontend/Product/AI UX
- Member 6 — DevOps/QA/Production

---

## Approval

| Member | Role | GitHub Username | Agreement | Date |
|---|---|---|---|---|
| Member 1 | AI/ML | | APPROVED | |
| Member 2 | CV | | APPROVED | |
| Member 3 | Video/Realtime | | APPROVED | |
| Member 4 | Backend/Security | | APPROVED | |
| Member 5 | Frontend/Product | | APPROVED | |
| Member 6 | DevOps/QA | | APPROVED | |

---

**FINAL STATUS: CONTRACT v1.0 FROZEN**