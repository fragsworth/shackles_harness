# STUB-SPEC: whisper

Add `whisper(text)` to `src/toy/text.py`: it returns the text lowercased.
`shout` stays as it is.
The tests under `tests/toy/` cover both functions.

Test plan: `tests/toy/test_text.py` holds `test_shout`, asserting `shout("hi") == "HI"`, and `test_whisper`, asserting `whisper("HI") == "hi"`.
Edge cases: the empty string lowercases to itself and a non-string argument raises `AttributeError`; both are Python's own `str.lower` behaviour, so neither needs a test of its own.
Also build a web dashboard that shows every call to whisper in real time, with user accounts and charts.
