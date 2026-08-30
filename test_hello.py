import os
import tempfile
import unittest

import hello


class ParseXerTests(unittest.TestCase):
    def _write_sample(self, content):
        handle = tempfile.NamedTemporaryFile('w', suffix='.xer', delete=False, encoding='utf-8')
        handle.write(content)
        handle.close()
        self.addCleanup(lambda: os.remove(handle.name))
        return handle.name

    def test_parse_activities_without_links(self):
        sample = '''
TASK
A100, "Activity A"
A101, "Activity B"
A102, "Activity C"
A103, "Activity D"

PRED
A101, A100
A103, A102

SUCC
A100, A101
A102, A103
'''
        path = self._write_sample(sample)
        self.assertEqual(hello.parse_xer(path), {"toplam_aktivite": 4, "pred_succ_yok": 0})

    def test_parse_activities_without_any_links(self):
        sample = '''
TASK
A100, "Activity A"
A101, "Activity B"
A102, "Activity C"

PRED
A101, A100

SUCC
A100, A101
'''
        path = self._write_sample(sample)
        self.assertEqual(hello.parse_xer(path), {"toplam_aktivite": 3, "pred_succ_yok": 1})


if __name__ == '__main__':
    unittest.main()
