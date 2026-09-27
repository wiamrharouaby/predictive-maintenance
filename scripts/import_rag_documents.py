"""Extract local PDF/PPTX sources into retrieval-sized JSON passages."""

from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree

from PyPDF2 import PdfReader


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "knowledge_documents"
OUTPUT_FILE = SOURCE_DIR / "rag_documents.json"
MAX_CHARS = 1400
OVERLAP_CHARS = 180


def clean_text(value: str) -> str:
    value = value.replace("\x00", " ").replace("\u00ad", "")
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def chunk_text(text: str) -> list[str]:
    """Split text on paragraph boundaries with a small contextual overlap."""
    paragraphs = [clean_text(item) for item in re.split(r"\n\s*\n", text)]
    paragraphs = [item for item in paragraphs if item]
    chunks: list[str] = []
    current = ""

    for paragraph in paragraphs:
        if len(paragraph) > MAX_CHARS:
            sentences = re.split(r"(?<=[.!?;:])\s+", paragraph)
        else:
            sentences = [paragraph]
        for sentence in sentences:
            candidate = f"{current}\n\n{sentence}".strip()
            if current and len(candidate) > MAX_CHARS:
                chunks.append(current)
                current = f"{current[-OVERLAP_CHARS:]} {sentence}".strip()
            else:
                current = candidate
    if current:
        chunks.append(current)
    return chunks


def extract_pdf(path: Path) -> list[dict[str, str]]:
    passages: list[dict[str, str]] = []
    reader = PdfReader(str(path))
    for page_number, page in enumerate(reader.pages, start=1):
        text = clean_text(page.extract_text() or "")
        for chunk_number, content in enumerate(chunk_text(text), start=1):
            passages.append({
                "id": f"rapport-dxm-p{page_number}-c{chunk_number}",
                "document_title": f"Rapport DXM — page {page_number}",
                "document_type": "rapport technique PDF",
                "equipment_type": "DXM",
                "tags": "DXM,rapport technique,maintenance,circuit,procédure",
                "source": path.name,
                "location": f"page {page_number}",
                "content": content,
            })
    return passages


def extract_pptx(path: Path) -> list[dict[str, str]]:
    passages: list[dict[str, str]] = []
    namespace = {"a": "http://schemas.openxmlformats.org/drawingml/2006/main"}
    with zipfile.ZipFile(path) as archive:
        slide_names = sorted(
            (
                name for name in archive.namelist()
                if re.fullmatch(r"ppt/slides/slide\d+\.xml", name)
            ),
            key=lambda name: int(re.search(r"\d+", Path(name).stem).group()),
        )
        for slide_number, slide_name in enumerate(slide_names, start=1):
            root = ElementTree.fromstring(archive.read(slide_name))
            text = clean_text("\n".join(
                node.text.strip()
                for node in root.findall(".//a:t", namespace)
                if node.text and node.text.strip()
            ))
            for chunk_number, content in enumerate(chunk_text(text), start=1):
                passages.append({
                    "id": f"circuits-dxm-s{slide_number}-c{chunk_number}",
                    "document_title": f"Circuits DXM animés — diapositive {slide_number}",
                    "document_type": "présentation technique PowerPoint",
                    "equipment_type": "DXM",
                    "tags": "DXM,circuits,schéma,fonctionnement,maintenance",
                    "source": path.name,
                    "location": f"diapositive {slide_number}",
                    "content": content,
                })
    return passages


def main() -> None:
    documents = []
    documents.extend(extract_pdf(SOURCE_DIR / "rapport_dxm.pdf"))
    documents.extend(extract_pptx(SOURCE_DIR / "circuits_dxm_anime.pptx"))
    OUTPUT_FILE.write_text(
        json.dumps(documents, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"{len(documents)} passages écrits dans {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
