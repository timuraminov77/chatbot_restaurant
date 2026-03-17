import re
from pathlib import Path


def parse_md_chunks(filepath: str) -> list[dict]:
    text = Path(filepath).read_text(encoding="utf-8")
    lines = text.split("\n")

    chunks = []
    current_section = None
    current_subsection = None
    current_lines = []

    def flush(section, subsection, lines):
        content = "\n".join(lines).strip()
        if content:
            chunks.append({
                "content": content,
                "metadata": {
                    "source": filepath,
                    "section": section,
                    "subsection": subsection,
                }
            })

    for line in lines:
        if line.startswith("## "):
            flush(current_section, current_subsection, current_lines)
            current_section = line.lstrip("# ").strip()
            current_subsection = None
            current_lines = [line]

        elif line.startswith("### "):
            if current_section:
                flush(current_section, current_subsection, current_lines)
                current_subsection = line.lstrip("# ").strip()
                current_lines = [line]
            else:
                current_lines.append(line)

        else:
            current_lines.append(line)

    flush(current_section, current_subsection, current_lines)

    result = []
    for chunk in chunks:
        if chunk["metadata"]["section"] and "FAQ" in chunk["metadata"]["section"]:
            result.extend(split_faq(chunk))
        else:
            result.append(chunk)

    return result


def split_faq(faq_chunk: dict) -> list[dict]:
    """Разбивает FAQ на отдельные Q&A пары"""
    pairs = []
    content = faq_chunk["content"]

    pattern = r'\*\*(.+?\?)\*\*\s*\n(.*?)(?=\n\*\*|\Z)'
    matches = re.findall(pattern, content, re.DOTALL)

    for question, answer in matches:
        pairs.append({
            "content": f"Вопрос: {question.strip()}\nОтвет: {answer.strip()}",
            "metadata": {
                "source": faq_chunk["metadata"]["source"],
                "section": "FAQ",
                "subsection": question.strip(),
            }
        })

    return pairs if pairs else [faq_chunk]
