"""Vista local de la página citada de un PDF, con la evidencia resaltada.

Nada sale del equipo. Para PDF digitales se usa la capa de texto; para páginas escaneadas,
si Tesseract está instalado, su OCR local. Sin texto localizable se muestra la página sin
resaltar y se informa al usuario: la ausencia de resaltado no invalida ni confirma la cita.
"""
from io import BytesIO
import base64
import re
import shutil
import subprocess
import threading
import unicodedata

PDFIUM_LOCK = threading.RLock()
SCALE = 1.6
OCR_SCALE = 3.2
MIN_PIECE = 4


def fold(char):
    base = unicodedata.normalize('NFD', char)[:1].lower()
    return base if base.isalnum() else ''


def compact(text):
    return ''.join(fold(c) for c in text)


def pieces(evidence, value=''):
    """Fragmentos a buscar: la cita completa, sus partes y el valor propuesto."""
    found = []
    def add(text):
        key = compact(text)
        if len(key) >= MIN_PIECE and key not in found:
            found.append(key)
    add(evidence)
    for part in re.split(r'[:：|;\n\r]', evidence):
        add(part)
    for part in re.split(r'[:：|;\n\r]|\s{2,}', evidence):
        add(part)
    # Columnas mezcladas en una misma cita: rótulo bilingüe, valor numérico o unidad.
    for part in re.split(r'[:：|;\n\r]|\s{2,}|\s+(?=[≤≥<>±~\d])|(?<=[\u3000-\u9fff])\s*(?=[A-Za-z])|(?<=[A-Za-z%)])\s*(?=[\u3000-\u9fff])', evidence):
        add(part)
    value = re.sub(r'^\s*fabricante\s*:[^|\n]*\|', '', value or '', flags=re.I).strip(' :|')
    if len(value) <= 80:
        add(value)
    return found


class Units:
    """Unidades de texto (caracteres o palabras) con su caja en coordenadas de imagen."""

    def __init__(self, items):
        self.boxes = []
        self.text = ''
        self.owner = []
        for text, box in items:
            key = compact(text)
            self.boxes.append(box)
            self.text += key
            self.owner.extend([len(self.boxes)-1]*len(key))

    def occurrences(self, key):
        start = self.text.find(key)
        while start >= 0:
            units = sorted(set(self.owner[start:start+len(key)]))
            yield [self.boxes[u] for u in units if self.boxes[u]]
            start = self.text.find(key, start+1)


def merge_lines(boxes):
    rects = []
    for left, top, right, bottom in boxes:
        last = rects[-1] if rects else None
        if last and abs(last[1]-top) < (bottom-top)*0.6 and left-last[2] < (bottom-top)*3:
            rects[-1] = [min(last[0], left), min(last[1], top), max(last[2], right), max(last[3], bottom)]
        else:
            rects.append([left, top, right, bottom])
    return rects


def center(rects):
    return sum((r[1]+r[3])/2 for r in rects)/len(rects), sum((r[0]+r[2])/2 for r in rects)/len(rects)


def locate(units, evidence, value):
    keys = pieces(evidence, value)
    if not keys:
        return []
    whole = next(units.occurrences(keys[0]), None)
    if whole:
        return merge_lines(whole)
    # Las tablas separan rótulo y valor en el orden de lectura: se busca cada parte y,
    # entre varias apariciones, la más próxima al fragmento más distintivo.
    rest = sorted(keys[1:], key=len, reverse=True)
    chosen, anchor = [], None
    covered = ''
    for key in rest:
        if key in covered:
            continue
        options = [merge_lines(o) for o in units.occurrences(key)]
        if not options:
            continue
        if anchor is None:
            best = options[0]
            anchor = center(best)
        else:
            best = min(options, key=lambda r: abs(center(r)[0]-anchor[0])*4 + abs(center(r)[1]-anchor[1]))
        chosen.extend(best)
        covered += key
    return chosen[:40]


def text_units(page, height):
    textpage = page.get_textpage()
    try:
        count = textpage.count_chars()
        items = []
        for index in range(count):
            char = textpage.get_text_range(index, 1)
            left, bottom, right, top = textpage.get_charbox(index)
            box = None if right <= left else (left*SCALE, (height-top)*SCALE, right*SCALE, (height-bottom)*SCALE)
            items.append((char, box))
        return Units(items)
    finally:
        textpage.close()


def ocr_image(page):
    """Imagen en escala de grises a mayor resolución para el OCR (llamar con PDFIUM_LOCK)."""
    if not shutil.which('tesseract'):
        return None
    bitmap = page.render(scale=OCR_SCALE, grayscale=True)
    try:
        return bitmap.to_pil()
    finally:
        bitmap.close()


def ocr_units(image):
    """OCR local con Tesseract; se ejecuta fuera del bloqueo de PDFium."""
    tesseract = shutil.which('tesseract')
    if not tesseract or image is None:
        return None
    factor = OCR_SCALE/SCALE
    buffer = BytesIO()
    image.save(buffer, format='PNG')
    try:
        result = subprocess.run([tesseract, 'stdin', 'stdout', '--psm', '3', 'tsv'], input=buffer.getvalue(),
                                capture_output=True, timeout=25)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode:
        return None
    items = []
    for line in result.stdout.decode('utf-8', 'replace').splitlines()[1:]:
        cols = line.split('\t')
        if len(cols) == 12 and cols[11].strip():
            left, top, width, height = map(int, cols[6:10])
            items.append((cols[11], (left/factor, top/factor, (left+width)/factor, (top+height)/factor)))
    return Units(items)


def page_preview(path, page_number, evidence, value=''):
    import pypdfium2 as pdfium
    from PIL import Image, ImageDraw

    rects, method, scan = [], '', None
    # PDFium no es seguro entre hilos: toda llamada se serializa con el mismo bloqueo.
    with PDFIUM_LOCK:
        document = pdfium.PdfDocument(str(path))
        try:
            total = len(document)
            if not 1 <= page_number <= total:
                raise ValueError(f'La página {page_number} no existe en el PDF ({total} páginas).')
            page = document[page_number-1]
            try:
                height = page.get_size()[1]
                bitmap = page.render(scale=SCALE)
                try:
                    image = bitmap.to_pil().convert('RGB')
                finally:
                    bitmap.close()
                if page.get_rotation() == 0:
                    units = text_units(page, height)
                    if units.text:
                        rects, method = locate(units, evidence, value), 'texto'
                if not rects:
                    scan = ocr_image(page)
            finally:
                page.close()
        finally:
            document.close()
    if not rects and scan is not None:
        units = ocr_units(scan)
        if units and units.text:
            rects, method = locate(units, evidence, value), 'ocr'
    if rects:
        overlay = Image.new('RGBA', image.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        for left, top, right, bottom in rects:
            box = (left-3, top-2, right+3, bottom+2)
            draw.rectangle(box, fill=(255, 214, 0, 95), outline=(214, 120, 0, 255), width=2)
        image = Image.alpha_composite(image.convert('RGBA'), overlay).convert('RGB')
    buffer = BytesIO()
    image.save(buffer, format='JPEG', quality=84)
    first = min(rects, key=lambda r: r[1]) if rects else None
    return {'image': 'data:image/jpeg;base64,' + base64.b64encode(buffer.getvalue()).decode('ascii'),
            'page': page_number, 'pages': total, 'found': bool(rects),
            'method': method if rects else '', 'focus': first[1]/image.height if first else None}
