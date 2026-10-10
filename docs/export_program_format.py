"""Writes docs/ProgramFormat.txt, a plain-text copy of ProgramFormat.md for users who read it in
Notepad or keep it on the USB stick with their Programs. Run it after editing ProgramFormat.md:

    python docs/export_program_format.py
"""
import os
import re
import textwrap

HERE = os.path.dirname(os.path.abspath(__file__))
WIDTH = 90


def _Inline(text):
    text = re.sub(r"\[([^\]]+)\]\(#[^)]*\)", r"\1", text)          # links within the guide
    text = re.sub(r"\[([^\]]+)\]\(([^)]*)\)", r"\1 (\2)", text)     # other links
    return text.replace("**", "").replace("`", "")


def _Wrap(text, indent="", hanging=None):
    hanging = indent if hanging is None else hanging
    return textwrap.fill(_Inline(text), WIDTH, initial_indent=indent, subsequent_indent=hanging,
                         break_long_words=False, break_on_hyphens=False)


def _Table(rows):
    # Each row becomes its first cell, then the other cells as "Header: value" lines.
    cells = [[c.strip() for c in row.strip().strip("|").split("|")] for row in rows]
    header, body = cells[0], [r for r in cells[1:] if not set("".join(r)) <= set("-: ")]
    out = []
    for row in body:
        out.append(_Wrap(row[0], "  * "))
        for name, value in zip(header[1:], row[1:]):
            if value:
                out.append(_Wrap("{}: {}".format(name, value), "      ", "        "))
    return out


def Convert(markdown):
    lines, out, i = markdown.splitlines(), [], 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("```"):
            i += 1
            while not lines[i].startswith("```"):
                out.append("    " + lines[i] if lines[i] else "")
                i += 1
        elif line.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                rows.append(lines[i])
                i += 1
            out += _Table(rows)
            continue
        elif line.startswith("#"):
            level, title = len(line) - len(line.lstrip("#")), _Inline(line.lstrip("#").strip())
            if out and out[-1]:
                out.append("")
            out += [title.upper() if level == 1 else title, {1: "=", 2: "=", 3: "-"}.get(level, "-") * len(title)]
        elif re.match(r"\s*(- |\d+\. )", line):
            indent = len(line) - len(line.lstrip())
            marker = re.match(r"\s*(- |\d+\. )", line).group(1)
            text = line.strip()[len(marker):]
            bullet = "* " if marker == "- " else marker
            out.append(_Wrap(text, " " * indent + bullet, " " * (indent + len(bullet))))
        elif line.strip():
            paragraph = [line]
            while i + 1 < len(lines) and lines[i + 1].strip() and not re.match(r"\s*([-|#]|\d+\. |```)", lines[i + 1]):
                i += 1
                paragraph.append(lines[i])
            out.append(_Wrap(" ".join(paragraph)))
        else:
            out.append("")
        i += 1
    text = "\n".join(out)
    return re.sub(r"\n{3,}", "\n\n", text).strip() + "\n"


if __name__ == "__main__":
    with open(os.path.join(HERE, "ProgramFormat.md"), encoding="utf-8") as f:
        markdown = f.read()
    # The guide's contents list only makes sense as links.
    markdown = re.sub(r"\n(- \[[^\]]+\]\(#[^)]*\)\n)+", "\n", markdown, count=1)
    with open(os.path.join(HERE, "ProgramFormat.txt"), "w", encoding="utf-8", newline="\r\n") as f:
        f.write(Convert(markdown))
    print("Wrote docs/ProgramFormat.txt")
