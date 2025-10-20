import tempfile
import unittest
from pathlib import Path

from parse.xml_parser import parse_xml_chunks


class XmlParserTests(unittest.TestCase):
    def test_parse_xml_chunks(self):
        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
        <report>
            <section>
                <title>Test Filing</title>
                <paragraph>이것은 테스트 문단입니다. 공시 본문을 시뮬레이션합니다. 충분한 길이를 확보합니다.</paragraph>
                <paragraph>두 번째 문단은 충분히 길게 작성되어 Chunk로 추출되어야 합니다.</paragraph>
            </section>
        </report>
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            xml_path = Path(tmpdir) / "sample.xml"
            xml_path.write_text(xml_content, encoding="utf-8")

            chunks = parse_xml_chunks([str(xml_path)])

            self.assertGreaterEqual(len(chunks), 1)
            self.assertTrue(all("metadata" in chunk for chunk in chunks))
            self.assertTrue(any(chunk["type"] == "text" for chunk in chunks))
            self.assertTrue(any("paragraph" in chunk["section"] for chunk in chunks if chunk["type"] == "text"))


if __name__ == "__main__":
    unittest.main()
