# CLARIFICATIONS: questions for the owner, one section per round, appended by POSTMORTEM and read verbatim by the next round's planner.

## bootstrap
- maxFailuresBeforeStop is read per producer step and maxRoundAttempts as the number of re-entries; confirm.
- ownerHourlyRate is priced with ownerMinutesPerCheckpoint (10 by default); set it in project.yaml if another estimate fits.
- Gates are read-only, so their judgment calls come back in the verdict and the runner appends them to the round files.
- With CHAT-TO-PLAN-GATE disabled no owner word is required at start; the round runs with review checkpoints unless delegated.
