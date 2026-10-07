from __future__ import annotations

import html
import os
from pathlib import Path
from typing import TYPE_CHECKING

from .models import OPEN_TASK_STATUSES, TaskStatus

if TYPE_CHECKING:
    from .session import SessionTaskNotebook


class NotebookPdfReport:
    def __init__(self, notebook: SessionTaskNotebook):
        self.notebook = notebook

    def create(self, path: Path) -> None:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

        regular, bold = self._register_fonts(pdfmetrics, TTFont)
        styles = getSampleStyleSheet()
        title = ParagraphStyle(
            "NotebookTitle",
            parent=styles["Title"],
            fontName=bold,
            fontSize=22,
            leading=28,
            textColor=colors.HexColor("#172554"),
            alignment=TA_CENTER,
            spaceAfter=6,
        )
        heading = ParagraphStyle(
            "NotebookHeading",
            parent=styles["Heading2"],
            fontName=bold,
            fontSize=13,
            leading=17,
            textColor=colors.HexColor("#1D4ED8"),
            spaceBefore=12,
            spaceAfter=7,
        )
        body = ParagraphStyle(
            "NotebookBody",
            parent=styles["BodyText"],
            fontName=regular,
            fontSize=9,
            leading=13,
            textColor=colors.HexColor("#1F2937"),
        )
        small = ParagraphStyle(
            "NotebookSmall",
            parent=body,
            fontSize=7.5,
            leading=10,
            textColor=colors.HexColor("#4B5563"),
        )
        document = SimpleDocTemplate(
            str(path),
            pagesize=A4,
            rightMargin=15 * mm,
            leftMargin=15 * mm,
            topMargin=18 * mm,
            bottomMargin=17 * mm,
            title="Aksh Session Task Notebook",
            author="Aksh AI Virtual Assistant",
        )
        story = [
            Paragraph("Aksh Session Task Notebook", title),
            Paragraph(
                "Live session view - automatically deleted when Aksh exits",
                ParagraphStyle("Subtitle", parent=small, alignment=TA_CENTER),
            ),
            Spacer(1, 8),
            *self._workspace_story(heading, body, small),
            *self._task_story(heading, body, small),
        ]
        document.build(
            story,
            onFirstPage=lambda canvas, doc: self._page(canvas, doc, regular),
            onLaterPages=lambda canvas, doc: self._page(canvas, doc, regular),
        )

    def _workspace_story(self, heading, body, small) -> list:
        from reportlab.lib import colors
        from reportlab.lib.units import mm
        from reportlab.platypus import Paragraph, Spacer, Table

        windows = self.notebook.workspace.windows()
        activities = self.notebook.workspace.activities()
        story = [Paragraph("Current Workspace", heading)]
        if not windows:
            story.append(Paragraph("No supported visible applications detected.", body))
        else:
            rows = [["App", "Visible page / window", "State", "Safe URL"]]
            rows.extend(
                [
                    Paragraph(self._safe(window.app), small),
                    Paragraph(self._safe(window.title), small),
                    "Foreground" if window.foreground else "Visible",
                    Paragraph(self._safe(window.safe_url or "-"), small),
                ]
                for window in windows
            )
            table = Table(
                rows,
                colWidths=[31 * mm, 76 * mm, 23 * mm, 50 * mm],
                repeatRows=1,
            )
            table.setStyle(self._table_style(colors))
            story.append(table)
        if activities:
            story.extend([Spacer(1, 7), Paragraph("Recent browser activity", heading)])
            rows = [["Time", "Browser", "Action", "Result"]]
            rows.extend(
                [
                    item.created_at.strftime("%H:%M:%S"),
                    item.browser,
                    item.action,
                    Paragraph(self._safe(item.description), small),
                ]
                for item in activities[-12:]
            )
            table = Table(
                rows,
                colWidths=[22 * mm, 28 * mm, 35 * mm, 95 * mm],
                repeatRows=1,
            )
            table.setStyle(self._table_style(colors))
            story.append(table)
        return story

    def _task_story(self, heading, body, small) -> list:
        from reportlab.lib import colors
        from reportlab.lib.units import mm
        from reportlab.platypus import KeepTogether, Paragraph, Spacer, Table

        tasks = self.notebook.snapshot()
        open_count = sum(task.status in OPEN_TASK_STATUSES for task in tasks)
        completed = sum(task.status == TaskStatus.COMPLETED for task in tasks)
        failed = sum(task.status == TaskStatus.FAILED for task in tasks)
        story = [
            Paragraph("Session Tasks", heading),
            Paragraph(
                f"Total {len(tasks)} | Open {open_count} | "
                f"Completed {completed} | Failed {failed}",
                body,
            ),
            Spacer(1, 5),
        ]
        if not tasks:
            story.append(Paragraph("No Aksh command tasks recorded yet.", body))
            return story
        for index, task in enumerate(reversed(tasks), start=1):
            meta = (
                f"Status: {task.status.value.replace('_', ' ')} | "
                f"Requested by: {task.requested_by} | Assigned to: {task.assigned_to} | "
                f"Completed by: {task.completed_by or '-'}"
            )
            rows = [["Time", "Actor", "Event", "Details"]]
            rows.extend(
                [
                    event.created_at.strftime("%H:%M:%S"),
                    event.actor,
                    event.kind.replace("_", " "),
                    Paragraph(self._safe(event.text), small),
                ]
                for event in task.events
            )
            table = Table(
                rows,
                colWidths=[22 * mm, 24 * mm, 37 * mm, 97 * mm],
                repeatRows=1,
            )
            table.setStyle(self._table_style(colors))
            story.append(
                KeepTogether(
                    [
                        Paragraph(f"{index}. {self._safe(task.title)}", heading),
                        Paragraph(self._safe(meta), small),
                        Spacer(1, 4),
                        table,
                    ]
                )
            )
        return story

    @staticmethod
    def _register_fonts(pdfmetrics, TTFont) -> tuple[str, str]:
        fonts = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
        regular_path, bold_path = fonts / "NIRMALA.TTF", fonts / "NIRMALAB.TTF"
        if regular_path.is_file() and bold_path.is_file():
            pdfmetrics.registerFont(TTFont("AkshNirmala", str(regular_path)))
            pdfmetrics.registerFont(TTFont("AkshNirmalaBold", str(bold_path)))
            return "AkshNirmala", "AkshNirmalaBold"
        return "Helvetica", "Helvetica-Bold"

    @staticmethod
    def _table_style(colors):
        from reportlab.platypus import TableStyle

        return TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E3A8A")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 7.5),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#CBD5E1")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )

    @staticmethod
    def _page(canvas, document, font_name: str) -> None:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm

        canvas.saveState()
        canvas.setFont(font_name, 7)
        canvas.setFillColorRGB(0.35, 0.39, 0.47)
        canvas.drawString(15 * mm, 9 * mm, "Aksh - private session notebook")
        canvas.drawRightString(A4[0] - 15 * mm, 9 * mm, f"Page {document.page}")
        canvas.restoreState()

    @staticmethod
    def _safe(value: object) -> str:
        return html.escape(" ".join(str(value or "").split()))
