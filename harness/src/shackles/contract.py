"""The words and lines the runner emits into prompts and parses back."""
import re

STATUSES = ("DONE", "NEEDS-OWNER", "UPSTREAM", "BLOCKED")
VERDICTS = ("PASS", "FAIL")
RESOLUTIONS = ("fixed", "disputed", "deferred")
RULINGS = ("upheld", "withdrawn")
KEYS = ("STEP", "KIND", "ROUND", "ATTEMPT", "WORKTREE", "HARNESS", "ARTIFACT", "RESULT_FILE", "DIFF_FILE",
        "WRITE_PATHS", "FROZEN_PATHS", "MERGE_IN_PROGRESS")
WRAPPER = ("Your instructions are the entire content of {prompt_file}. Read it now and follow it exactly; "
           "your final message must be exactly the JSON object it specifies and nothing else.")


def parse(text):
    """The last occurrence of each KEY: line, as a dict of the raw values."""
    found = {}
    for key in KEYS:
        matches = re.findall(rf"^{key}:[ \t]*(.*?)[ \t]*$", text, re.M)
        if matches:
            found[key] = matches[-1]
    return found
