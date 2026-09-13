# CLARIFICATIONS: questions for the owner, one section per round, appended by POSTMORTEM and read verbatim by the next round's planner.

## bootstrap
- maxFailuresBeforeStop is read per producer step and maxRoundAttempts as the number of re-entries; confirm.
- ownerHourlyRate is priced with ownerMinutesPerCheckpoint (10 by default); set it in project.yaml if another estimate fits.
- Gates are read-only, so their judgment calls come back in the verdict and the runner appends them to the round files.
- With CHAT-TO-PLAN-GATE disabled no owner word is required at start; the round runs with review checkpoints unless delegated.

## test-A (sandbox round 0001, bootstrap/tests/test-A.md)
- A round starts and lands on unverified owner words whenever no owner log exists (a session started outside this repository has no hook); PROCESS.md permits that with a FLAG. Should a missing log stop `start` instead?
- `specCostPerWord` is charged at PLAN-TO-SPEC's acceptance whether or not the round is delegated past its review, and PLAN-TO-SPEC sized SPEC.md against it: is it the owner's reading time (skip it when delegated) or the standing weight of a contract (charge always)?
