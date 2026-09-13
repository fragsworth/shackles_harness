import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "src"))
from toy import text  # noqa: E402


class ScratchTest(unittest.TestCase):
    def test_shout_scratch(self):  # redundant with test_text.py's test_shout: a real test, worth archiving rather than keeping
        self.assertEqual(text.shout("scratch"), "SCRATCH")
