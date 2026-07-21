from __future__ import annotations

import html
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE = PROJECT_ROOT / "docs" / "USER_GUIDE.md"
OUTPUT = PROJECT_ROOT / "output" / "pdf" / "使用说明.pdf"


def _register_fonts() -> tuple[str, str]:
    candidates = [
        (Path("C:/Windows/Fonts/msyh.ttc"), Path("C:/Windows/Fonts/msyhbd.ttc")),
        (Path("C:/Windows/Fonts/simsun.ttc"), Path("C:/Windows/Fonts/simhei.ttf")),
    ]
    for regular_path, bold_path in candidates:
        if regular_path.exists() and bold_path.exists():
            pdfmetrics.registerFont(TTFont("GuideRegular", str(regular_path), subfontIndex=0))
            pdfmetrics.registerFont(TTFont("GuideBold", str(bold_path), subfontIndex=0))
            return "GuideRegular", "GuideBold"
    raise RuntimeError("未找到可用于中文 PDF 的微软雅黑或宋体字体。")


def _page_decorations(canvas, document) -> None:
    regular, _bold = document.guide_fonts
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#D9E2EC"))
    canvas.line(18 * mm, 282 * mm, 192 * mm, 282 * mm)
    canvas.setFont(regular, 8)
    canvas.setFillColor(colors.HexColor("#52606D"))
    canvas.drawString(18 * mm, 286 * mm, "非线路运距计算工具 V1.0")
    canvas.drawRightString(192 * mm, 12 * mm, f"第 {document.page} 页")
    canvas.setFillColor(colors.HexColor("#7A5200"))
    canvas.drawString(18 * mm, 12 * mm, "普通驾车参考距离，不代表货车实际可通行路线")
    canvas.restoreState()


def _paragraph_text(value: str) -> str:
    escaped = html.escape(value.strip())
    if escaped.startswith("`") and escaped.endswith("`"):
        escaped = escaped[1:-1]
    escaped = escaped.replace("`", "")
    return escaped


def build() -> Path:
    regular, bold = _register_fonts()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    document = SimpleDocTemplate(
        str(OUTPUT),
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
        title="非线路运距计算工具 V1.0 使用说明",
        author="非线路运距计算工具项目",
        subject="Windows 便携版用户手册",
    )
    document.guide_fonts = (regular, bold)
    styles = getSampleStyleSheet()
    title = ParagraphStyle(
        "GuideTitle", parent=styles["Title"], fontName=bold, fontSize=22,
        leading=30, textColor=colors.HexColor("#173F5F"), alignment=TA_CENTER,
        spaceAfter=10 * mm,
    )
    h1 = ParagraphStyle(
        "GuideH1", parent=styles["Heading1"], fontName=bold, fontSize=15,
        leading=22, textColor=colors.HexColor("#173F5F"), spaceBefore=5 * mm,
        spaceAfter=2.5 * mm, keepWithNext=True,
    )
    h2 = ParagraphStyle(
        "GuideH2", parent=styles["Heading2"], fontName=bold, fontSize=11.5,
        leading=18, textColor=colors.HexColor("#20639B"), spaceBefore=3 * mm,
        spaceAfter=1.5 * mm, keepWithNext=True,
    )
    body = ParagraphStyle(
        "GuideBody", parent=styles["BodyText"], fontName=regular, fontSize=9.5,
        leading=16, textColor=colors.HexColor("#243B53"), spaceAfter=2 * mm,
        wordWrap="CJK",
    )
    bullet = ParagraphStyle(
        "GuideBullet", parent=body, leftIndent=5 * mm, firstLineIndent=-3.5 * mm,
        bulletIndent=0, spaceAfter=1.2 * mm,
    )
    quote = ParagraphStyle(
        "GuideQuote", parent=body, leftIndent=5 * mm, rightIndent=5 * mm,
        borderColor=colors.HexColor("#D6A100"), borderWidth=1,
        borderPadding=7, backColor=colors.HexColor("#FFF7D6"),
        textColor=colors.HexColor("#5F4500"), spaceBefore=2 * mm, spaceAfter=4 * mm,
    )

    story = []
    first_title = True
    for raw in SOURCE.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("# "):
            if not first_title:
                story.append(PageBreak())
            story.append(Spacer(1, 28 * mm))
            story.append(Paragraph(_paragraph_text(line[2:]), title))
            story.append(Paragraph("Windows onedir 便携正式版", ParagraphStyle(
                "Subtitle", parent=body, fontName=regular, fontSize=11,
                alignment=TA_CENTER, textColor=colors.HexColor("#52606D"),
            )))
            story.append(Spacer(1, 18 * mm))
            first_title = False
        elif line.startswith("## "):
            story.append(Paragraph(_paragraph_text(line[3:]), h1))
        elif line.startswith("### "):
            if line == "### 导入":
                story.append(PageBreak())
            story.append(Paragraph(_paragraph_text(line[4:]), h2))
        elif line.startswith("> "):
            story.append(Paragraph(_paragraph_text(line[2:]), quote))
        elif line.startswith("- "):
            story.append(Paragraph("• " + _paragraph_text(line[2:]), bullet))
        elif len(line) > 2 and line[0].isdigit() and ". " in line[:4]:
            story.append(Paragraph(_paragraph_text(line), bullet))
        else:
            story.append(Paragraph(_paragraph_text(line), body))

    document.build(story, onFirstPage=_page_decorations, onLaterPages=_page_decorations)
    return OUTPUT


if __name__ == "__main__":
    print(build())
