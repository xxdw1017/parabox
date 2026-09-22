"""把《个人文档》Markdown 生成为 A4 打印版 HTML（浏览器「打印为 PDF」即成品）。

用法：.venv/bin/python 提交材料/生成个人文档HTML.py
输出：提交材料/个人文档_董长坤.html

与 `生成个人文档PDF.py` 同源（同一份 Markdown）：改内容后两个脚本都重跑一次即可。
HTML 用 `<!--pagebreak-->` 固定 5 页；打印时纸张请选 **A4**（选 Letter 会挤成 6 页）。
"""

from __future__ import annotations

import html
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "个人文档_董长坤.md"
DST = HERE / "个人文档_董长坤.html"

CSS = """
@page { size: A4; margin: 14mm; }
body { font-family: "Songti SC","PingFang SC","Microsoft YaHei",serif; font-size: 10.5pt;
       line-height: 1.55; color: #1a1a1a; margin: 0; }
h1 { font-size: 17pt; margin: 0 0 2mm; }
h2 { font-size: 12.5pt; margin: 5mm 0 2mm; padding-bottom: 1mm; border-bottom: 1px solid #999; }
h3 { font-size: 11.5pt; margin: 3.5mm 0 1.5mm; }
p { margin: 0 0 1.6mm; text-align: justify; }
ul { margin: 0 0 2mm; padding-left: 5.5mm; }
li { margin-bottom: 0.8mm; }
blockquote { margin: 0 0 2mm; padding: 1.5mm 3mm; background: #f4f5f7; border-left: 3px solid #888;
             color: #333; font-size: 9.8pt; }
table { border-collapse: collapse; width: 100%; margin: 0 0 2.5mm; font-size: 9.8pt; }
th, td { border: 1px solid #bbb; padding: 1.1mm 1.8mm; text-align: left; vertical-align: top; }
th { background: #eef0f3; }
code { font-family: "SF Mono",Menlo,Consolas,monospace; font-size: 9pt; background: #f2f2f4; padding: 0 0.6mm; }
pre { background: #f6f6f8; border: 1px solid #ddd; border-radius: 2px; padding: 2mm 2.5mm;
      margin: 0 0 2.5mm; white-space: pre-wrap; page-break-inside: avoid; }
pre code { background: none; font-size: 8.4pt; line-height: 1.4; }
figure { margin: 0 0 2.5mm; text-align: center; page-break-inside: avoid; }
figure img { max-width: 100%; max-height: 78mm; }
figcaption { font-size: 8.6pt; color: #666; margin-top: 0.8mm; }
hr { border: none; border-top: 1px dashed #bbb; margin: 3mm 0; }
a { color: #0b5cad; text-decoration: none; word-break: break-all; }
.pagebreak { page-break-after: always; }
h2, h3 { page-break-after: avoid; }
"""


def inline(text: str) -> str:
    text = html.escape(text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"`(.+?)`", r"<code>\1</code>", text)
    return re.sub(r"&lt;(https?://[^&\s]+)&gt;", r'<a href="\1">\1</a>', text)


def render(md: str) -> str:
    out, in_code, in_table, in_list, first_row = [], False, False, False, True
    close = lambda: None

    def close_blocks():
        nonlocal in_table, in_list
        if in_table:
            out.append("</table>")
            in_table = False
        if in_list:
            out.append("</ul>")
            in_list = False

    for raw in md.split("\n"):
        line = raw.rstrip()
        if line.startswith("```"):
            close_blocks()
            out.append("<pre><code>" if not in_code else "</code></pre>")
            in_code = not in_code
            continue
        if in_code:
            out.append(html.escape(line))
            continue
        if line.strip() == "<!--pagebreak-->":
            close_blocks()
            out.append('<div class="pagebreak"></div>')
            continue
        if not line.strip():
            close_blocks()
            continue
        img = re.match(r"!\[(.*?)\]\((.*?)\)", line.strip())
        if img:
            close_blocks()
            src = img.group(2).replace("screenshots/", "../screenshots/")
            out.append(f'<figure><img src="{src}" alt="{html.escape(img.group(1))}">'
                       f'<figcaption>{html.escape(img.group(1))}</figcaption></figure>')
            continue
        if re.match(r"^#{1,3} ", line):
            close_blocks()
            lvl = len(line) - len(line.lstrip("#"))
            out.append(f"<h{lvl}>{inline(line[lvl + 1:])}</h{lvl}>")
            continue
        if line.startswith("|"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if set("".join(cells)) <= set("-: "):
                continue
            if not in_table:
                close_blocks()
                out.append("<table>")
                in_table, first_row = True, True
            tag = "th" if first_row else "td"
            first_row = False
            out.append("<tr>" + "".join(f"<{tag}>{inline(c)}</{tag}>" for c in cells) + "</tr>")
            continue
        if line.strip() == "---":
            close_blocks()
            out.append("<hr>")
            continue
        if line.startswith("> "):
            close_blocks()
            out.append(f"<blockquote>{inline(line[2:])}</blockquote>")
            continue
        if re.match(r"^\s*[-*] ", line) or re.match(r"^\s*\d+\. ", line):
            if not in_list:
                close_blocks()
                out.append("<ul>")
                in_list = True
            out.append(f"<li>{inline(re.sub(r'^\s*(?:[-*]|\d+\.) ', '', line))}</li>")
            continue
        close_blocks()
        out.append(f"<p>{inline(line)}</p>")
    close_blocks()
    return "\n".join(out)


def main() -> None:
    body = render(SRC.read_text(encoding="utf-8"))
    DST.write_text('<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">'
                   "<title>递归之箱 · 个人文档 · 董长坤</title><style>" + CSS + "</style></head><body>"
                   + body + "</body></html>", encoding="utf-8")
    pages = SRC.read_text(encoding="utf-8").count("<!--pagebreak-->") + 1
    missing = [m for m in re.findall(r"!\[.*?\]\((.*?)\)", SRC.read_text(encoding="utf-8"))
               if not (HERE.parent / m).exists()]   # 图片路径相对仓库根
    print(f"已生成：{DST.name}｜分页标记 {pages - 1} 处 → 固定 {pages} 页")
    print("图片引用：", "全部存在 ✅" if not missing else f"缺失 {missing} ❌")
    print("提醒：浏览器打印时纸张必须选 A4（选 Letter 会变成 6 页）")


if __name__ == "__main__":
    main()
