"""Build the Word progress report from PROGRESS_TRACKER.md.

Usage: python docs/progress/build_report.py
Needs pandoc on PATH. Output: Progress_Report_<date>.docx at the repository root (git-ignored)
Formatting: Times New Roman 12, 1.5 line spacing, justified body, per the faculty guide.
"""

import datetime as dt
import re
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "PROGRESS_TRACKER.md"

FONT = '<w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:eastAsia="Times New Roman" w:cs="Times New Roman"/>'


def patch_styles(xml: str) -> str:
    xml = re.sub(r"<w:rFonts [^>]*/>", FONT, xml)
    xml = re.sub(r"<w:rFonts [^>]*>.*?</w:rFonts>", FONT, xml, flags=re.S)
    xml = re.sub(r'<w:sz w:val="\d+"\s*/>', '<w:sz w:val="24"/>', xml)
    xml = re.sub(r'<w:szCs w:val="\d+"\s*/>', '<w:szCs w:val="24"/>', xml)
    xml = re.sub(r"<w:color [^>]*/>", '<w:color w:val="000000"/>', xml)

    def set_para(block: str, extra: str) -> str:
        block = re.sub(r"<w:spacing [^>]*/>", "", block)
        block = re.sub(r"<w:jc [^>]*/>", "", block)
        if "<w:pPr>" in block:
            return block.replace("<w:pPr>", "<w:pPr>" + extra, 1)
        # OOXML requires pPr before rPr inside a style element.
        anchor = "<w:rPr>" if "<w:rPr>" in block else "</w:style>"
        return block.replace(anchor, "<w:pPr>" + extra + "</w:pPr>" + anchor, 1)

    body = '<w:spacing w:line="360" w:lineRule="auto" w:after="120"/><w:jc w:val="both"/>'
    table_cell = '<w:spacing w:line="240" w:lineRule="auto" w:before="40" w:after="40"/><w:jc w:val="left"/>'
    for style_id, extra in (("Normal", body), ("BodyText", body), ("FirstParagraph", body), ("Compact", table_cell)):
        pattern = rf'<w:style [^>]*w:styleId="{style_id}".*?</w:style>'
        xml = re.sub(pattern, lambda m, e=extra: set_para(m.group(0), e), xml, flags=re.S)
    return xml


def build_reference(tmp: Path) -> Path:
    ref = tmp / "reference.docx"
    subprocess.run(["pandoc", "-o", str(ref), "--print-default-data-file", "reference.docx"], check=True)
    patched = tmp / "reference_patched.docx"
    with zipfile.ZipFile(ref) as zin, zipfile.ZipFile(patched, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename == "word/styles.xml":
                data = patch_styles(data.decode("utf-8")).encode("utf-8")
            zout.writestr(item, data)
    return patched


def main() -> None:
    if shutil.which("pandoc") is None:
        raise SystemExit("pandoc is required: sudo apt install pandoc")
    out = HERE.parents[1] / f"Progress_Report_{dt.date.today().isoformat()}.docx"
    with tempfile.TemporaryDirectory() as tmp:
        ref = build_reference(Path(tmp))
        subprocess.run(
            ["pandoc", str(SOURCE), "-o", str(out), f"--reference-doc={ref}"],
            check=True,
        )
    print(out)


if __name__ == "__main__":
    main()
