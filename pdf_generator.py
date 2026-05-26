from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_RIGHT, TA_LEFT, TA_CENTER
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import io

W, H = A4

# Цвета
C_DARK    = colors.HexColor('#0f0f0e')
C_ACCENT  = colors.HexColor('#1a1a18')
C_MUTED   = colors.HexColor('#6b6b65')
C_LIGHT   = colors.HexColor('#f7f6f3')
C_BORDER  = colors.HexColor('#e0dfd9')
C_WHITE   = colors.white
C_BLUE    = colors.HexColor('#2563eb')


def _s(name, **kw):
    defaults = dict(fontName='Helvetica', fontSize=9, leading=14, textColor=C_DARK)
    defaults.update(kw)
    return ParagraphStyle(name, **defaults)


S_NORMAL     = _s('normal')
S_SMALL      = _s('small',  fontSize=8, leading=12, textColor=C_MUTED)
S_BOLD       = _s('bold',   fontName='Helvetica-Bold')
S_RIGHT      = _s('right',  alignment=TA_RIGHT)
S_RIGHT_BOLD = _s('rb',     fontName='Helvetica-Bold', alignment=TA_RIGHT)
S_RIGHT_SM   = _s('rsm',    fontSize=8, leading=12, alignment=TA_RIGHT, textColor=C_MUTED)
S_CENTER     = _s('center', alignment=TA_CENTER)
S_CENTER_SM  = _s('csm',    fontSize=8, alignment=TA_CENTER, textColor=C_MUTED)
S_TITLE      = _s('title',  fontName='Helvetica-Bold', fontSize=28, leading=32,
                             alignment=TA_RIGHT, textColor=C_ACCENT)
S_CO_NAME    = _s('coname', fontName='Helvetica-Bold', fontSize=11, leading=16,
                             alignment=TA_RIGHT)
S_LABEL      = _s('label',  fontSize=7, leading=10, textColor=C_MUTED,
                             fontName='Helvetica-Bold', spaceAfter=1)
S_FOOTER     = _s('footer', fontSize=8, leading=12, textColor=C_MUTED, alignment=TA_CENTER)
S_H_TH       = _s('th',     fontName='Helvetica-Bold', fontSize=8, leading=12,
                             textColor=C_MUTED)
S_H_TH_R     = _s('thr',    fontName='Helvetica-Bold', fontSize=8, leading=12,
                             textColor=C_MUTED, alignment=TA_RIGHT)
S_TOTAL_LBL  = _s('tlbl',   fontName='Helvetica-Bold', fontSize=10, leading=14,
                             alignment=TA_RIGHT)
S_TOTAL_VAL  = _s('tval',   fontName='Helvetica-Bold', fontSize=11, leading=16,
                             alignment=TA_RIGHT, textColor=C_BLUE)


def generate_invoice_pdf(context: dict) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        topMargin=16*mm, bottomMargin=16*mm,
        leftMargin=18*mm, rightMargin=18*mm,
        title=f"Invoice {context['invoice_number']}",
    )

    cur = context['currency']
    co  = context
    elems = []

    # ════════════════════════════════════════════════════
    # 1. ШАПКА — номер/дата слева, компания справа
    # ════════════════════════════════════════════════════
    left_col = [
        [Paragraph('DATE', S_LABEL),    Paragraph('INVOICE', S_LABEL)],
        [Paragraph(co['invoice_date'], S_BOLD), Paragraph(co['invoice_number'], S_BOLD)],
    ]
    left_tbl = Table(left_col, colWidths=[45*mm, 55*mm])
    left_tbl.setStyle(TableStyle([
        ('LEFTPADDING',   (0,0), (-1,-1), 0),
        ('RIGHTPADDING',  (0,0), (-1,-1), 0),
        ('TOPPADDING',    (0,0), (-1,-1), 1),
        ('BOTTOMPADDING', (0,0), (-1,-1), 1),
        ('VALIGN',        (0,0), (-1,-1), 'TOP'),
    ]))

    right_col = [
        Paragraph('INVOICE', S_TITLE),
        Spacer(1, 2*mm),
        Paragraph(co['company_name'], S_CO_NAME),
        Paragraph(co['company_address'], S_RIGHT_SM),
        Paragraph(co['company_country'], S_RIGHT_SM),
        Paragraph(f"Reg: {co['company_number']}", S_RIGHT_SM),
        Paragraph(f"VAT: {co['company_vat']}", S_RIGHT_SM),
        Paragraph(f"IBAN: {co['company_iban']}", S_RIGHT_SM),
        Paragraph(f"SWIFT: {co['company_swift']}", S_RIGHT_SM),
    ]

    header = Table([[left_tbl, right_col]], colWidths=[100*mm, 74*mm])
    header.setStyle(TableStyle([
        ('VALIGN',        (0,0), (-1,-1), 'TOP'),
        ('LEFTPADDING',   (0,0), (-1,-1), 0),
        ('RIGHTPADDING',  (0,0), (-1,-1), 0),
        ('TOPPADDING',    (0,0), (-1,-1), 0),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
    ]))
    elems.append(header)
    elems.append(Spacer(1, 5*mm))
    elems.append(HRFlowable(width='100%', thickness=0.5, color=C_BORDER))
    elems.append(Spacer(1, 6*mm))

    # ════════════════════════════════════════════════════
    # 2. BILL TO
    # ════════════════════════════════════════════════════
    bill_lines = [Paragraph('BILL TO', S_LABEL)]
    bill_lines.append(Paragraph(f'<b>{context["cp_name"]}</b>', S_BOLD))
    if context.get('cp_address'):
        bill_lines.append(Paragraph(context['cp_address'], S_SMALL))
    if context.get('cp_old_address'):
        bill_lines.append(Paragraph(f'prev: {context["cp_old_address"]}', S_SMALL))
    ids = []
    if context.get('cp_company_number'): ids.append(f'Reg: {context["cp_company_number"]}')
    if context.get('cp_eu_vat'):         ids.append(f'EU VAT: {context["cp_eu_vat"]}')
    if ids:
        bill_lines.append(Paragraph('  ·  '.join(ids), S_SMALL))

    elems.append(Table([[bill_lines]], colWidths=[174*mm]))
    elems.append(Spacer(1, 8*mm))

    # ════════════════════════════════════════════════════
    # 3. ТАБЛИЦА ПОЗИЦИЙ
    # ════════════════════════════════════════════════════
    COL_W = [8*mm, 68*mm, 14*mm, 26*mm, 22*mm, 26*mm]

    thead = [
        Paragraph('#',                   S_H_TH),
        Paragraph('Description',         S_H_TH),
        Paragraph('Unit',                S_H_TH),
        Paragraph(f'Rate, {cur}',        S_H_TH_R),
        Paragraph('Hours',               S_H_TH_R),
        Paragraph(f'Amount, {cur}',      S_H_TH_R),
    ]
    rows = [thead]

    for i, item in enumerate(context['items']):
        rows.append([
            Paragraph(str(i + 1),             S_CENTER_SM),
            Paragraph(item['description'],    S_NORMAL),
            Paragraph(item['unit'],           S_NORMAL),
            Paragraph(str(int(item['rate'])), S_RIGHT),
            Paragraph(item['time_formatted'], S_RIGHT),
            Paragraph(f"{item['amount']:.2f}", S_RIGHT),
        ])

    n = len(rows)
    tbl = Table(rows, colWidths=COL_W, repeatRows=1)
    tbl.setStyle(TableStyle([
        # Заголовок
        ('BACKGROUND',    (0,0), (-1,0),   C_ACCENT),
        ('TEXTCOLOR',     (0,0), (-1,0),   C_WHITE),
        ('FONTNAME',      (0,0), (-1,0),   'Helvetica-Bold'),
        # Чередование строк
        ('ROWBACKGROUNDS',(0,1), (-1,-1),  [C_WHITE, C_LIGHT]),
        # Нижняя граница каждой строки
        ('LINEBELOW',     (0,0), (-1,-1),  0.4, C_BORDER),
        ('LINEABOVE',     (0,0), (-1,0),   0,   C_WHITE),
        # Padding
        ('LEFTPADDING',   (0,0), (-1,-1),  5),
        ('RIGHTPADDING',  (0,0), (-1,-1),  5),
        ('TOPPADDING',    (0,0), (-1,-1),  6),
        ('BOTTOMPADDING', (0,0), (-1,-1),  6),
        ('VALIGN',        (0,0), (-1,-1),  'MIDDLE'),
    ]))
    elems.append(tbl)
    elems.append(Spacer(1, 4*mm))

    # ════════════════════════════════════════════════════
    # 4. ИТОГО (справа)
    # ════════════════════════════════════════════════════
    total_tbl = Table(
        [[Paragraph(f'Total, {cur}', S_TOTAL_LBL),
          Paragraph(f'{context["total_amount"]:,.2f}', S_TOTAL_VAL)]],
        colWidths=[130*mm, 44*mm]
    )
    total_tbl.setStyle(TableStyle([
        ('LEFTPADDING',   (0,0), (-1,-1), 0),
        ('RIGHTPADDING',  (0,0), (-1,-1), 0),
        ('TOPPADDING',    (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LINEABOVE',     (1,0), (1,0),   1, C_BLUE),
        ('VALIGN',        (0,0), (-1,-1), 'MIDDLE'),
    ]))
    elems.append(total_tbl)

    # ════════════════════════════════════════════════════
    # 5. ПРИМЕЧАНИЯ
    # ════════════════════════════════════════════════════
    if context.get('notes'):
        elems.append(Spacer(1, 5*mm))
        elems.append(HRFlowable(width='100%', thickness=0.4, color=C_BORDER))
        elems.append(Spacer(1, 3*mm))
        elems.append(Paragraph(f'<b>Notes:</b> {context["notes"]}', S_SMALL))

    # ════════════════════════════════════════════════════
    # 6. ФУТЕР
    # ════════════════════════════════════════════════════
    elems.append(Spacer(1, 10*mm))
    elems.append(HRFlowable(width='100%', thickness=0.4, color=C_BORDER))
    elems.append(Spacer(1, 3*mm))
    due = context.get('due_date') or 'within 30 days'
    elems.append(Paragraph(
        f'Payment due {due}  ·  IBAN: {co["company_iban"]}  ·  SWIFT: {co["company_swift"]}',
        S_FOOTER
    ))

    doc.build(elems)
    return buf.getvalue()
