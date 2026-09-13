import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "src"))
from toy import text  # noqa: E402


class TextTest(unittest.TestCase):
    def test_shout(self):
        self.assertEqual(text.shout("hi"), "HI")

    def test_shout_again(self):
        self.assertEqual(text.shout("yo"), "YO")
