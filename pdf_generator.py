from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_RIGHT, TA_LEFT, TA_CENTER
import io

W, H = A4

C_BLACK  = colors.HexColor('#111111')
C_DARK   = colors.HexColor('#222222')
C_MUTED  = colors.HexColor('#666666')
C_LIGHT  = colors.HexColor('#f7f6f3')
C_LINE   = colors.HexColor('#dddddd')
C_WHITE  = colors.white

def _s(name, **kw):
    defaults = dict(fontName='Helvetica', fontSize=10, leading=14, textColor=C_BLACK)
    defaults.update(kw)
    return ParagraphStyle(name, **defaults)

S_NORMAL    = _s('n')
S_SMALL     = _s('sm',  fontSize=9,  leading=13, textColor=C_MUTED)
S_BOLD      = _s('b',   fontName='Helvetica-Bold')
S_RIGHT     = _s('r',   alignment=TA_RIGHT)
S_RIGHT_B   = _s('rb',  fontName='Helvetica-Bold', alignment=TA_RIGHT)
S_CENTER    = _s('c',   alignment=TA_CENTER, textColor=C_MUTED)
S_LABEL     = _s('lbl', fontSize=8, leading=11, fontName='Helvetica-Bold',
                         textColor=C_MUTED, spaceAfter=2)
S_META_VAL  = _s('mv',  fontSize=12, fontName='Helvetica-Bold')
S_TITLE     = _s('t',   fontSize=30, fontName='Helvetica-Bold',
                         alignment=TA_RIGHT, leading=34)
S_CO_NAME   = _s('cn',  fontSize=12, fontName='Helvetica-Bold', alignment=TA_RIGHT)
S_CO_DETAIL = _s('cd',  fontSize=9,  leading=15, alignment=TA_RIGHT, textColor=C_MUTED)
S_BILL_NAME = _s('bn',  fontSize=12, fontName='Helvetica-Bold')
S_BILL_DET  = _s('bd',  fontSize=9,  leading=15, textColor=C_MUTED)
S_TH        = _s('th',  fontSize=9,  fontName='Helvetica-Bold',
                         textColor=C_WHITE, leading=12)
S_TH_R      = _s('thr', fontSize=9,  fontName='Helvetica-Bold',
                         textColor=C_WHITE, leading=12, alignment=TA_RIGHT)
S_TD        = _s('td',  fontSize=10, leading=14)
S_TD_R      = _s('tdr', fontSize=10, leading=14, alignment=TA_RIGHT,
                         fontName='Helvetica')
S_TD_C      = _s('tdc', fontSize=10, leading=14, alignment=TA_CENTER, textColor=C_MUTED)
S_TOTAL_L   = _s('tl',  fontSize=10, fontName='Helvetica-Bold',
                         textColor=colors.HexColor('#444444'))
S_TOTAL_V   = _s('tv',  fontSize=14, fontName='Helvetica-Bold',
                         alignment=TA_RIGHT)
S_NOTES     = _s('nt',  fontSize=9,  leading=14, textColor=C_MUTED)


def generate_invoice_pdf(context: dict) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        topMargin=18*mm, bottomMargin=18*mm,
        leftMargin=20*mm, rightMargin=20*mm,
        title=f"Invoice {context['invoice_number']}",
    )

    cur = context['currency']
    co  = context
    elems = []

    # ── ШАПКА ────────────────────────────────────────────────────────────────
    left = [
        Paragraph('INVOICE', S_LABEL),
        Paragraph(co['invoice_number'], S_META_VAL),
        Spacer(1, 6*mm),
        Paragraph('DATE', S_LABEL),
        Paragraph(co['invoice_date'], S_META_VAL),
    ]

    right = [
        Paragraph('INVOICE', S_TITLE),
        Spacer(1, 2*mm),
        Paragraph(co['company_name'], S_CO_NAME),
    ]
    if co.get('company_address'): right.append(Paragraph(co['company_address'], S_CO_DETAIL))
    if co.get('company_country'): right.append(Paragraph(co['company_country'], S_CO_DETAIL))
    if co.get('company_number'): right.append(Paragraph(f"Reg: {co['company_number']}", S_CO_DETAIL))
    if co.get('company_vat'):    right.append(Paragraph(f"VAT: {co['company_vat']}", S_CO_DETAIL))
    if co.get('company_iban'):   right.append(Paragraph(f"IBAN: {co['company_iban']}", S_CO_DETAIL))
    if co.get('company_swift'):  right.append(Paragraph(f"SWIFT: {co['company_swift']}", S_CO_DETAIL))

    header = Table([[left, right]], colWidths=[90*mm, 80*mm])
    header.setStyle(TableStyle([
        ('VALIGN',        (0,0), (-1,-1), 'TOP'),
        ('LEFTPADDING',   (0,0), (-1,-1), 0),
        ('RIGHTPADDING',  (0,0), (-1,-1), 0),
        ('TOPPADDING',    (0,0), (-1,-1), 0),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
    ]))
    elems.append(header)
    elems.append(Spacer(1, 5*mm))
    elems.append(HRFlowable(width='100%', thickness=0.5, color=C_LINE))
    elems.append(Spacer(1, 6*mm))

    # ── BILL TO ───────────────────────────────────────────────────────────────
    elems.append(Paragraph('BILL TO', S_LABEL))
    elems.append(Spacer(1, 1.5*mm))
    elems.append(Paragraph(context['cp_name'], S_BILL_NAME))
    elems.append(Spacer(1, 0.5*mm))
    if context.get('cp_address'):
        elems.append(Paragraph(context['cp_address'], S_BILL_DET))
    if context.get('cp_old_address'):
        elems.append(Paragraph(f"prev: {context['cp_old_address']}", S_BILL_DET))
    ids = []
    if context.get('cp_company_number'): ids.append(f"Reg: {context['cp_company_number']}")
    if context.get('cp_eu_vat'):         ids.append(f"EU VAT: {context['cp_eu_vat']}")
    if ids:
        elems.append(Paragraph('  ·  '.join(ids), S_BILL_DET))
    elems.append(Spacer(1, 8*mm))

    # ── ТАБЛИЦА ───────────────────────────────────────────────────────────────
    # Content width = 210mm - 20mm L - 20mm R = 170mm. All tables match this width.
    # Columns: # | Description | Unit | Rate | Hours | Amount
    COL_W = [8*mm, 64*mm, 18*mm, 24*mm, 20*mm, 36*mm]

    thead = [
        Paragraph('#',              S_TH),
        Paragraph('Description',    S_TH),
        Paragraph('Unit',           S_TH),
        Paragraph(f'Rate, {cur}',   S_TH_R),
        Paragraph('Hours',          S_TH_R),
        Paragraph(f'Amount, {cur}', S_TH_R),
    ]
    rows = [thead]

    for i, item in enumerate(context['items']):
        rows.append([
            Paragraph(str(i+1),                  S_TD_C),
            Paragraph(item['description'],        S_TD),
            Paragraph(item['unit'],               S_TD),
            Paragraph(str(int(item['rate'])),     S_TD_R),
            Paragraph(item['time_formatted'],     S_TD_R),
            Paragraph(f"{item['amount']:,.2f}",   S_TD_R),
        ])

    n = len(rows)
    tbl = Table(rows, colWidths=COL_W, repeatRows=1)
    tbl.setStyle(TableStyle([
        ('BACKGROUND',    (0,0),  (-1,0),   C_DARK),
        ('ROWBACKGROUNDS',(0,1),  (-1,-1),  [C_WHITE, C_LIGHT]),
        ('LINEBELOW',     (0,1),  (-1,-1),  0.5, C_LINE),
        ('LEFTPADDING',   (0,0),  (-1,-1),  7),
        ('RIGHTPADDING',  (0,0),  (-1,-1),  7),
        ('TOPPADDING',    (0,0),  (-1,-1),  7),
        ('BOTTOMPADDING', (0,0),  (-1,-1),  7),
        ('VALIGN',        (0,0),  (-1,-1),  'MIDDLE'),
    ]))
    elems.append(tbl)

    # ── TOTAL вплотную к таблице ──────────────────────────────────────────────
    total_data = [[
        Paragraph('', S_NORMAL),
        Paragraph(f'Total, {cur}', S_TOTAL_L),
        Paragraph(f"{context['total_amount']:,.2f}", S_TOTAL_V),
    ]]
    # Total table: last col (36mm) aligns with items Amount column → LINEABOVE
    # spans the rightmost 80mm and ends exactly at the items table right edge.
    total_tbl = Table(total_data, colWidths=[90*mm, 44*mm, 36*mm])
    total_tbl.setStyle(TableStyle([
        ('LINEABOVE',     (1,0), (2,0),  1.5, C_BLACK),
        ('TOPPADDING',    (0,0), (-1,-1), 8),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING',   (0,0), (-1,-1), 7),
        ('RIGHTPADDING',  (0,0), (-1,-1), 7),
        ('VALIGN',        (0,0), (-1,-1), 'MIDDLE'),
    ]))
    elems.append(total_tbl)

    # ── NOTES ─────────────────────────────────────────────────────────────────
    if context.get('notes'):
        elems.append(Spacer(1, 6*mm))
        elems.append(HRFlowable(width='100%', thickness=0.5, color=C_LINE))
        elems.append(Spacer(1, 3*mm))
        elems.append(Paragraph(context['notes'], S_NOTES))

    doc.build(elems)
    return buf.getvalue()
