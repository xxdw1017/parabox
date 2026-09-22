"""把《个人文档》Markdown 生成为 A4 PDF（5 页）。

用法：.venv/bin/python 提交材料/生成个人文档PDF.py
输出：提交材料/递归之箱_个人文档_董长坤.pdf

为什么用脚本而不是手工排版：文档有分页上限（≤5 页），用 PageBreak 固定分页最稳，
改内容后重跑一次即可，不必手工调格式。
"""

from __future__ import annotations

import re
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (HRFlowable, Image, PageBreak, Paragraph, Preformatted,
                                SimpleDocTemplate, Spacer, Table, TableStyle)

HERE = Path(__file__).resolve().parent
SRC = HERE / "个人文档_董长坤.md"
DST = HERE / "递归之箱_个人文档_董长坤.pdf"

# ── 中文字体（按可用性依次尝试；.ttc 需要 subfontIndex）──
CANDIDATES = [("/System/Library/Fonts/Hiragino Sans GB.ttc", "Hiragino Sans GB"),
              ("/System/Library/Fonts/STHeiti Medium.ttc", "STHeiti Medium"),
              ("/System/Library/Fonts/Supplemental/Songti.ttc", "Songti"),
              ("C:/Windows/Fonts/msyh.ttc", "Microsoft YaHei")]
BODY, BOLD = None, None
for path, name in CANDIDATES:
    if not Path(path).exists():
        continue
    try:
        pdfmetrics.registerFont(TTFont("CJK", path, subfontIndex=0))
        BODY = "CJK"
        try:
            pdfmetrics.registerFont(TTFont("CJK-Bold", path, subfontIndex=1))
            BOLD = "CJK-Bold"
        except Exception:
            BOLD = "CJK"
        break
    except Exception:
        continue
if BODY is None:
    raise SystemExit("找不到可用的中文字体，无法生成 PDF")
pdfmetrics.registerFontFamily("CJK", normal=BODY, bold=BOLD, italic=BODY, boldItalic=BOLD)

S = dict(
    title=ParagraphStyle("t", fontName=BOLD, fontSize=17, leading=22, spaceAfter=2 * mm),
    sub=ParagraphStyle("s", fontName=BODY, fontSize=9.5, leading=14, textColor=colors.HexColor("#444444")),
    h2=ParagraphStyle("h2", fontName=BOLD, fontSize=12.5, leading=16, spaceBefore=3 * mm, spaceAfter=1.2 * mm),
    h3=ParagraphStyle("h3", fontName=BOLD, fontSize=11.5, leading=15, spaceBefore=2.2 * mm, spaceAfter=0.6 * mm),
    body=ParagraphStyle("b", fontName=BODY, fontSize=10.5, leading=15, alignment=TA_JUSTIFY, spaceAfter=1.1 * mm),
    bullet=ParagraphStyle("bu", fontName=BODY, fontSize=10.5, leading=15, leftIndent=5 * mm,
                          bulletIndent=1.5 * mm, spaceAfter=0.5 * mm),
    quote=ParagraphStyle("q", fontName=BODY, fontSize=9.8, leading=14, leftIndent=3 * mm,
                         textColor=colors.HexColor("#333333"), spaceAfter=2 * mm),
    cell=ParagraphStyle("c", fontName=BODY, fontSize=9.5, leading=13),
    cellh=ParagraphStyle("ch", fontName=BOLD, fontSize=9.5, leading=13),
    code=ParagraphStyle("code", fontName=BODY, fontSize=8, leading=10.5),
)
SUBST = {"✅": "√", "⭐": "★", "❌": "×", "⚠️": "!", "⚠": "!"}


def escape(t: str) -> str:
    for k, v in SUBST.items():
        t = t.replace(k, v)
    t = t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    t = re.sub(r"&lt;(https?://[^\s]+)&gt;", r'<link href="\1" color="#0b5cad">\1</link>', t)
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"`(.+?)`", r'<font color="#0b5cad">\1</font>', t)
    return t


def image_flow(path: Path, caption: str):
    from reportlab.lib.utils import ImageReader          # 不额外依赖 PIL
    w, h = ImageReader(str(path)).getSize()
    max_w, max_h = 150 * mm, 46 * mm
    scale = min(max_w / w, max_h / h)
    pic = Image(str(path), width=w * scale, height=h * scale)
    pic.hAlign = "CENTER"
    cap = Paragraph(f'<font size="8.6" color="#666666">{escape(caption)}</font>',
                    ParagraphStyle("cap", fontName=BODY, alignment=1, spaceBefore=0.4 * mm))
    return [pic, cap, Spacer(1, 1.5 * mm)]


def flowables_from(lines):
    flow, i = [], 0
    while i < len(lines):
        line = lines[i].rstrip()
        if line.strip() == "<!--pagebreak-->":
            flow.append(PageBreak())
        elif line.startswith("```"):
            buf, i = [], i + 1
            while i < len(lines) and not lines[i].startswith("```"):
                buf.append(lines[i]); i += 1
            code = Preformatted("\n".join(buf), S["code"])
            flow.append(Table([[code]], colWidths=[168 * mm],
                              style=TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f6f6f8")),
                                                ("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor("#dddddd")),
                                                ("LEFTPADDING", (0, 0), (-1, -1), 3),
                                                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                                                ("TOPPADDING", (0, 0), (-1, -1), 3),
                                                ("BOTTOMPADDING", (0, 0), (-1, -1), 3)])))
            flow += [code, Spacer(1, 1.8 * mm)]
        elif line.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not set("".join(cells)) <= set("-: "):
                    rows.append(cells)
                i += 1
            i -= 1
            data = [[Paragraph(escape(c), S["cellh"] if r == 0 else S["cell"]) for c in row] for r, row in enumerate(rows)]
            ncol = max(len(rows[0]), 1)
            if ncol == 2:                      # 标签列窄一点，给说明列让出宽度，少折行
                widths = [30 * mm, 138 * mm]
            elif ncol == 3:
                widths = [34 * mm, 100 * mm, 34 * mm]
            else:
                widths = [168 * mm / ncol] * ncol
            t = Table(data, colWidths=widths, repeatRows=1)
            t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#bbbbbb")),
                                   ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef0f3")),
                                   ("VALIGN", (0, 0), (-1, -1), "TOP"),
                                   ("LEFTPADDING", (0, 0), (-1, -1), 3),
                                   ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                                   ("TOPPADDING", (0, 0), (-1, -1), 2),
                                   ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]))
            flow += [t, Spacer(1, 1.8 * mm)]
        elif re.match(r"!\[(.*?)\]\((.*?)\)", line.strip()):
            m = re.match(r"!\[(.*?)\]\((.*?)\)", line.strip())
            p = (HERE.parent / m.group(2)).resolve()   # 图片路径相对仓库根
            flow += image_flow(p, m.group(1)) if p.exists() else [Paragraph(f"[缺图 {m.group(2)}]", S["body"])]
        elif line.startswith("# "):
            flow.append(Paragraph(escape(line[2:]), S["title"]))
        elif line.startswith("## "):
            flow.append(Paragraph(escape(line[3:]), S["h2"]))
            flow.append(HRFlowable(width="100%", thickness=0.6, color=colors.HexColor("#999999"), spaceAfter=2 * mm))
        elif line.startswith("### "):
            flow.append(Paragraph(escape(line[4:]), S["h3"]))
        elif line.startswith("> "):
            flow.append(Paragraph(escape(line[2:]), S["quote"]))
        elif line.strip() == "---":
            flow.append(HRFlowable(width="100%", thickness=0.6, color=colors.HexColor("#bbbbbb"),
                                   dash=(2, 2), spaceBefore=2 * mm, spaceAfter=2 * mm))
        elif re.match(r"^\s*[-*] ", line):
            flow.append(Paragraph(escape(re.sub(r"^\s*[-*] ", "", line)), S["bullet"], bulletText="•"))
        elif re.match(r"^\s*\d+\. ", line):
            n = re.match(r"^\s*(\d+)\. ", line).group(1)
            flow.append(Paragraph(escape(re.sub(r"^\s*\d+\. ", "", line)), S["bullet"], bulletText=f"{n}."))
        elif line.strip():
            flow.append(Paragraph(escape(line), S["body"]))
        i += 1
    return flow


def sections(text):
    """按 <!--pagebreak--> 切成 5 节（每节应恰好占 1 页 A4）。"""
    out = [[]]
    for ln in text.split("\n"):
        if ln.strip() == "<!--pagebreak-->":
            out.append([])
        else:
            out[-1].append(ln)
    return out


def measure():
    """逐节测量排版高度，找出超过一页的那一节（可用高度 = A4 高 - 上下边距）。"""
    avail_w = A4[0] - 28 * mm
    avail_h = A4[1] - 28 * mm
    print(f"每页可用：{avail_w:.0f} × {avail_h:.0f} pt（A4，边距 14mm）")
    over = False
    for i, sec in enumerate(sections(SRC.read_text(encoding="utf-8")), 1):
        total = 0.0
        for f in flowables_from(sec):
            try:
                _, h = f.wrap(avail_w, avail_h)
                h += f.getSpaceBefore() + f.getSpaceAfter()
            except Exception:
                h = 0.0
            total += h
        flag = "✅" if total <= avail_h else f"❌ 超 {total - avail_h:.0f}pt（≈{(total-avail_h)/15.5:.0f} 行）"
        over = over or total > avail_h
        print(f"  第 {i} 节：高 {total:6.0f}pt  {flag}")
    return over


def build():
    flow = []
    for i, sec in enumerate(sections(SRC.read_text(encoding="utf-8"))):
        if i:
            flow.append(PageBreak())
        flow += flowables_from(sec)

    doc = SimpleDocTemplate(str(DST), pagesize=A4, leftMargin=14 * mm, rightMargin=14 * mm,
                            topMargin=14 * mm, bottomMargin=14 * mm, title="递归之箱 · 个人文档 · 董长坤")
    doc.build(flow)
    return doc.page


if __name__ == "__main__":
    import sys
    if "--measure" in sys.argv:
        raise SystemExit(1 if measure() else 0)
    pages = build()
    size = DST.stat().st_size / 1024
    print(f"已生成：{DST.name}｜{pages} 页｜{size:.0f} KB")
    print("页数检查：", "✅ ≤5 页" if pages <= 5 else f"❌ 超出 {pages-5} 页，需精简内容")
