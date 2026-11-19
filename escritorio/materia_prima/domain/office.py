"""Ediciones localizadas en los paquetes Open XML de Smasac."""
from copy import deepcopy
from dataclasses import dataclass
from io import BytesIO
import posixpath
import re
from textwrap import wrap
import unicodedata
from zipfile import ZipFile

from lxml import etree as ET

W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
S = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
REL = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
ENTITY = r'(fabricante|proveedor|nombre comercial|tiempo de vida util|almacenamiento)'
SPACE = '{http://www.w3.org/XML/1998/namespace}space'
# Colores de resaltado de la vista previa (uno por cambio). Deben coincidir con .chg-N de style.css.
PALETTE = ('FFE08A', 'A8E6CF', 'FFB3C1', 'A9D3FF', 'D9C2FF', 'FFC999', 'C5E99B', '9EE6E6', 'F5B8E8', 'E6CFA3')


def norm(value):
    return ''.join(c for c in unicodedata.normalize('NFD', value.lower())
                   if not unicodedata.combining(c)).strip()


def paragraph_text(p):
    return ''.join({W+'tab': '\t', W+'br': '\n'}.get(n.tag, n.text or '')
                   for n in p.iter(W+'t', W+'tab', W+'br'))


def word_text(node):
    return '\n'.join(paragraph_text(p) for p in node.iter(W+'p'))


def write_paragraph(p, value):
    if paragraph_text(p) == value:
        return
    if any(n.tag in {W+'fldChar', W+'instrText', W+'drawing', W+'object',
                     W+'pict', W+'fldSimple', W+'del', W+'ins'} for n in p.iter()):
        raise ValueError('El campo contiene elementos de Word que requieren edición directa.')
    runs = list(p.iter(W+'r'))
    run = next((r for r in runs if r.find(W+'t') is not None), None)
    if run is None:
        run = ET.SubElement(p, W+'r')
    old = list(p.iter(W+'t', W+'tab', W+'br'))
    offset = run.index(old[0]) if old and old[0].getparent() is run else len(run)
    for n in old:
        n.getparent().remove(n)
    for part in re.split(r'(\n|\t)', value):
        n = ET.Element(W+{'\n': 'br', '\t': 'tab'}.get(part, 't'))
        if n.tag == W+'t':
            n.text = part
            n.set(SPACE, 'preserve')
        run.insert(offset, n)
        offset += 1


def write_word(node, value):
    if node.tag == W+'p':
        write_paragraph(node, value)
        return
    paragraphs = list(node.iter(W+'p'))
    lines = value.split('\n', len(paragraphs)-1)
    for index, p in enumerate(paragraphs):
        write_paragraph(p, lines[index] if index < len(lines) else '')


def root(z, name):
    return ET.fromstring(z.read(name), ET.XMLParser(resolve_entities=False, no_network=True))


def replace_parts(data, output, parts):
    with ZipFile(BytesIO(data)) as source, ZipFile(output, 'w') as dest:
        for info in source.infolist():
            payload = (ET.tostring(parts[info.filename], encoding='UTF-8', xml_declaration=True)
                       if info.filename in parts else source.read(info))
            dest.writestr(info, payload)



def format_new_table(table, widths, borders=True):
    props=table.find(W+'tblPr')
    if props is None:props=ET.SubElement(table,W+'tblPr')
    ET.SubElement(props,W+'tblW',{W+'w':str(sum(widths)),W+'type':'dxa'})
    ET.SubElement(props,W+'tblLayout',{W+'type':'fixed'})
    grid=ET.Element(W+'tblGrid');table.insert(table.index(props)+1,grid)
    for width in widths:ET.SubElement(grid,W+'gridCol',{W+'w':str(width)})
    for row in table.findall(W+'tr'):
        rowprops=ET.SubElement(row,W+'trPr');ET.SubElement(rowprops,W+'cantSplit')
        for cell,width in zip(row.findall(W+'tc'),widths):
            cellprops=ET.SubElement(cell,W+'tcPr');cell.insert(0,cellprops)
            ET.SubElement(cellprops,W+'tcW',{W+'w':str(width),W+'type':'dxa'})
            for run in cell.iter(W+'r'):
                rprops=run.find(W+'rPr')
                if rprops is None:rprops=ET.Element(W+'rPr');run.insert(0,rprops)
                ET.SubElement(rprops,W+'rFonts',{W+'ascii':'Arial',W+'hAnsi':'Arial'})
                ET.SubElement(rprops,W+'sz',{W+'val':'20'})
    if not borders:
        bd=props.find(W+'tblBorders')
        if bd is not None:
            for edge in bd:edge.set(W+'val','nil')


W14 = '{http://schemas.microsoft.com/office/word/2010/wordml}'


def fresh_copy(node):
    """Copia de un nodo de Word sin identificadores de párrafo duplicados."""
    copy = deepcopy(node)
    for element in copy.iter():
        for attribute in (W14+'paraId', W14+'textId'):
            element.attrib.pop(attribute, None)
    return copy


def clone_row(template, values):
    row = fresh_copy(template)
    for cell, value in zip(row.findall(W+'tc'), values):
        write_word(cell, value)
    return row


def section_b_nodes(body):
    nodes, section = [], False
    for node in body:
        if node.tag == W+'p':
            title = re.sub(r'^[a-d]\s*[.)-]\s*', '', norm(word_text(node)))
            if re.match(r'informacion tecnico', title):
                section = True
            elif re.match(r'(observaciones|revision historica)', title):
                section = False
        if section:
            nodes.append(node)
    return nodes


def block_template(body):
    """Tabla del primer fabricante vigente: los bloques nuevos copian su formato e interlineado."""
    blocks = manufacturer_blocks(body)
    if not blocks:
        return None
    rows = blocks[0]['table'].findall(W+'tr')
    first = next((r for r in rows if any(norm(word_text(c).strip()) == 'fabricante' for c in r.findall(W+'tc'))), None)
    if first is None or len(rows) < 2 or len(first.findall(W+'tc')) < 3:
        return None
    other = rows[rows.index(first)+1] if rows.index(first)+1 < len(rows) else first
    if len(other.findall(W+'tc')) != len(first.findall(W+'tc')):
        return None
    role = next(i for i, c in enumerate(first.findall(W+'tc')) if norm(word_text(c).strip()) == 'fabricante')
    return {'table': blocks[0]['table'], 'first': first, 'other': other, 'role': role}


def additional_template(body):
    """Encabezado «Información adicional» y su tabla PARÁMETRO/RANGO/TÉCNICA vigentes en B."""
    nodes = section_b_nodes(body)
    for i, node in enumerate(nodes):
        if node.tag != W+'p' or not norm(word_text(node)).startswith('informacion adicional'):
            continue
        table = next((n for n in nodes[i+1:i+4] if n.tag == W+'tbl'), None)
        rows = table.findall(W+'tr') if table is not None else []
        if len(rows) >= 2 and len(rows[0].findall(W+'tc')) == 3 == len(rows[1].findall(W+'tc')):
            gap = nodes[i+1:nodes.index(table)]  # Párrafos vacíos entre el título y la tabla.
            return {'heading': node, 'table': table, 'header': rows[0], 'row': rows[1], 'gap': gap}
    return None


def manufacturer_blocks(body):
    blocks = []
    section = False
    for node in body:
        if node.tag == W+'p':
            title = re.sub(r'^[a-d]\s*[.)-]\s*', '', norm(word_text(node)))
            if re.match(r'informacion tecnico', title):
                section = True
            elif re.match(r'(observaciones|revision historica)', title):
                section = False
        if not section or node.tag != W+'tbl':
            continue
        for row in node.findall(W+'tr'):
            cells = row.findall(W+'tc')
            values = [word_text(c).strip() for c in cells]
            idx = next((i for i,v in enumerate(values[:-1]) if norm(v) == 'fabricante'), None)
            if idx is not None:
                number = re.fullmatch(r'\(?([0-9]+)\)?[.)]?', values[0]) if idx else None
                blocks.append({'number': int(number[1]) if number else len(blocks)+1,
                               'name': values[idx+1].lstrip(': ').strip(), 'table':node})
                break
    return blocks


def range_entries(value):
    matches = list(re.finditer(r'(?m)^\s*\((\d+)\)\s*', value))
    return [(int(m[1]), value[m.end(): matches[i+1].start() if i+1<len(matches) else len(value)].strip())
            for i,m in enumerate(matches)]


def manufacturer_key(name):
    return re.sub(r'[^a-z0-9]', '', norm(name))


@dataclass
class Field:
    section: str
    label: str
    value: str
    node: object
    kind: str = 'text'
    manufacturer_number: int | None = None
    manufacturer_name: str = ''

    def write(self, value):
        if self.kind == 'range':
            supplied = range_entries(value)
            if supplied:
                if len(supplied) != 1 or supplied[0][0] != self.manufacturer_number:
                    raise ValueError('Edita solo el rango del fabricante indicado en este campo.')
                value = supplied[0][1]
            entries = range_entries(word_text(self.node))
            if self.manufacturer_number not in {n for n,_ in entries}:
                raise ValueError('No se encontró la referencia del fabricante en el rango.')
            write_word(self.node, '\n'.join(f'({n}) {value.strip() if n == self.manufacturer_number else text}' for n,text in entries))
            return
        if self.kind == 'range_add':
            lines=[line.strip() for line in value.splitlines() if line.strip()]
            if len(lines)>1:
                for line in lines:
                    Field(self.section,self.label,'',self.node,'range_add').write(line)
                return
            maker, separator, text = value.partition(' | ')
            if not separator or not text.strip() or not maker.lower().startswith('fabricante:'):
                raise ValueError('Indica Fabricante: nombre completo | rango.')
            text = re.sub(r'^\s*\(\d+\)\s*', '', text)
            name = maker.partition(':')[2].strip()
            body = self.node.getroottree().getroot().find(W+'body')
            groups = manufacturer_blocks(body) if body is not None else []
            match = next((g for g in groups if manufacturer_key(g['name']) == manufacturer_key(name)), None)
            if match is None:
                raise ValueError('Aprueba primero la incorporación de ese fabricante o revisa su nombre exacto.')
            current = word_text(self.node).strip()
            entries = range_entries(current)
            if not entries and current:
                # A value without indices was common to the manufacturers already present.
                entries = [(g['number'], current) for g in groups if g['number'] != match['number']]
            entries = [(n,t) for n,t in entries if n != match['number']] + [(match['number'],text.strip())]
            write_word(self.node, '\n'.join(f'({n}) {t}' for n,t in entries))
            return
        if self.kind == 'text':
            write_word(self.node, value)
            return
        if self.kind == 'additional':
            lines = [re.sub(r'^par[aá]metro adicional\s*:\s*', '', line, flags=re.I) for line in value.splitlines() if line.strip()]
            if any(len(line.split(' | ')) != 3 for line in lines):
                raise ValueError('Cada parámetro adicional debe tener: Parámetro | Rango | Referencia.')
            body = self.node.getroottree().getroot().find(W+'body')
            template = additional_template(body) if body is not None else None
            if template is not None:
                table = fresh_copy(template['table'])
                for row in table.findall(W+'tr'):
                    table.remove(row)
                table.append(fresh_copy(template['header']))
                for line in lines:
                    table.append(clone_row(template['row'], line.split(' | ')))
                heading = fresh_copy(template['heading'])
                self.node.addnext(heading)
                anchor = heading
                for node in template['gap']:
                    copy = fresh_copy(node); anchor.addnext(copy); anchor = copy
                anchor.addnext(table)
                table.addnext(ET.Element(W+'p'))
                return
            table = ET.Element(W+'tbl')
            props = ET.SubElement(table, W+'tblPr')
            borders = ET.SubElement(props, W+'tblBorders')
            for edge in ('top','left','bottom','right','insideH','insideV'):
                ET.SubElement(borders, W+edge, {W+'val':'single', W+'sz':'4'})
            for line in ['Parámetro | Rango | Referencia'] + value.splitlines():
                line=re.sub(r'^par[aá]metro adicional\s*:\s*','',line,flags=re.I)
                values = line.split(' | ')
                if len(values) != 3:
                    raise ValueError('Cada parámetro adicional debe tener: Parámetro | Rango | Referencia.')
                row = ET.SubElement(table, W+'tr')
                for text in values:
                    cell = ET.SubElement(row, W+'tc')
                    write_paragraph(ET.SubElement(cell, W+'p'), text)
            # Keep the inserted heading and column labels with the first data row.
            # Otherwise the labels can be stranded at the bottom of the prior page.
            rows=table.findall(W+'tr')
            for cell in rows[0].findall(W+'tc'):
                for paragraph in cell.iter(W+'p'):
                    props=paragraph.find(W+'pPr')
                    if props is None:props=ET.Element(W+'pPr');paragraph.insert(0,props)
                    if props.find(W+'keepNext') is None:ET.SubElement(props,W+'keepNext')
                    props.find(W+'keepNext').set(W+'val','1')
            format_new_table(table,[4300,2300,2200])
            heading=ET.Element(W+'p')
            pp=ET.SubElement(heading,W+'pPr');ET.SubElement(pp,W+'keepNext')
            write_paragraph(heading,'Información adicional:')
            self.node.addnext(heading);heading.addnext(table)
            return
        if self.kind == 'manufacturer':
            blocks = [b.strip() for b in re.split(r'(?im)(?=^fabricante\s*:)', value) if b.strip()]
            if len(blocks) > 1:
                for block in blocks:
                    Field(self.section, self.label, '', self.node, 'manufacturer').write(block)
                return
            if not re.match(r'^fabricante\s*:\s*\S', norm(value)):
                raise ValueError('El nuevo bloque debe comenzar con «Fabricante: nombre».')
            root_node = self.node.getroottree().getroot()
            body = root_node.find(W+'body')
            groups = manufacturer_blocks(body) if body is not None else []
            number = max((g['number'] for g in groups), default=0)+1
            template = block_template(body) if body is not None else None
            if template is not None:
                lines, additional = [], []
                for line in value.splitlines():
                    if not line.strip():
                        continue
                    role, separator, text = line.partition(':')
                    if not separator or not text.strip():
                        raise ValueError('Usa una línea por dato: Etiqueta: valor.')
                    if norm(role) == 'parametro adicional':
                        additional.append(text.strip())
                    else:
                        lines.append((role.strip(), text.strip()))
                table = fresh_copy(template['table'])
                for row in table.findall(W+'tr'):
                    table.remove(row)
                width = len(template['first'].findall(W+'tc'))
                for index, (role, text) in enumerate(lines):
                    values = [''] * width
                    if template['role'] > 0:
                        values[0] = f'{number})' if index == 0 else ''
                    values[template['role']] = role
                    values[template['role']+1] = ': ' + text
                    table.append(clone_row(template['first'] if index == 0 else template['other'], values))
                spacer = ET.Element(W+'p')
                self.node.addprevious(spacer)
                self.node.addprevious(table)
                if additional:
                    Field('B', 'Parámetros del fabricante nuevo', '', table, 'additional').write('\n'.join(additional))
                return
            table = ET.Element(W+'tbl')
            props = ET.SubElement(table, W+'tblPr')
            borders = ET.SubElement(props, W+'tblBorders')
            for edge in ('top','left','bottom','right','insideH','insideV'):
                ET.SubElement(borders, W+edge, {W+'val':'single', W+'sz':'4'})
            additional = []
            first_row = True
            for line in value.splitlines():
                if not line.strip():
                    continue
                role, separator, text = line.partition(':')
                if not separator or not text.strip():
                    raise ValueError('Usa una línea por dato: Etiqueta: valor.')
                if norm(role) == 'parametro adicional':
                    additional.append(text.strip())
                    continue
                row = ET.SubElement(table, W+'tr')
                for content in (str(number)+')' if first_row else '', role.strip(), text.strip()):
                    cell = ET.SubElement(row, W+'tc')
                    write_paragraph(ET.SubElement(cell, W+'p'), content)
                first_row = False
            format_new_table(table,[450,2300,6050],borders=False)
            self.node.addprevious(table)
            if additional:
                Field('B', 'Parámetros del fabricante nuevo', '', table, 'additional').write('\n'.join(additional))
            return
        row = deepcopy(self.node)
        self.node.addnext(row)
        cells = row.findall(W+'tc')
        values = value.split(' | ')
        if len(values) != len(cells) or not all(v.strip() for v in values):
            raise ValueError(f'{self.label}: separa los {len(cells)} valores con " | ".')
        for cell, text in zip(cells, values):
            write_word(cell, text)


class Specification:
    def __init__(self, data):
        self.data = data
        self.fields = {}
        self.headers = []
        self.history = None
        with ZipFile(BytesIO(data)) as z:
            self.parts = {'word/document.xml': root(z, 'word/document.xml')}
            for name in z.namelist():
                if not re.fullmatch(r'word/header\d+\.xml', name):
                    continue
                header = root(z, name)
                for row in header.iter(W+'tr'):
                    cells = row.findall(W+'tc')
                    labels = [norm(word_text(c)) for c in cells]
                    if len(cells) >= 4 and labels[0] == 'emision' and labels[2] == 'version':
                        self.parts[name] = header
                        self.headers.append((cells[1], cells[3]))
        versions = {word_text(version).strip() for _, version in self.headers}
        if len(versions) != 1 or not next(iter(versions), '').isdigit():
            raise ValueError('No se pudo identificar una versión vigente única en la cabecera.')
        self.version = int(versions.pop())
        self.materialize_range_numbers()
        self.read_fields()
        self.manufacturers = manufacturer_blocks(self.parts['word/document.xml'].find(W+'body'))
        for f in self.fields.values():
            if f.section == 'B':
                group = next((g for g in self.manufacturers if g['name'] and g['name'] in f.label), None)
                f.manufacturer_number = group['number'] if group else None
            if f.manufacturer_number is not None:
                group = next((g for g in self.manufacturers if g['number']==f.manufacturer_number),None)
                f.manufacturer_name = group['name'] if group else ''

    def materialize_range_numbers(self):
        """Resolve Word automatic (1)/(2) list labels in A range cells only."""
        with ZipFile(BytesIO(self.data)) as z:
            if 'word/numbering.xml' not in z.namelist():
                return
            numbering = root(z, 'word/numbering.xml')
        abstracts = {n.get(W+'abstractNumId'): n for n in numbering.findall(W+'abstractNum')}
        nums = {n.get(W+'numId'): n for n in numbering.findall(W+'num')}
        cells = set()
        body = self.parts['word/document.xml'].find(W+'body')
        in_a = False
        for node in body:
            if node.tag == W+'p':
                title = re.sub(r'^[a-d]\s*[.)-]\s*', '', norm(word_text(node)))
                if re.match(r'especificacion tecnica',title):in_a=True
                elif re.match(r'informacion tecnico',title):in_a=False
            if in_a and node.tag == W+'tbl':
                rows=node.findall(W+'tr')
                if not rows:continue
                labels=[norm(word_text(c)) for c in rows[0].findall(W+'tc')]
                if 'rango' not in labels:continue
                index=labels.index('rango')
                cells.update(row.findall(W+'tc')[index] for row in rows[1:] if len(row.findall(W+'tc'))>index)
        counters={}
        for paragraph in body.iter(W+'p'):
            props=paragraph.find(W+'pPr')
            numpr=props.find(W+'numPr') if props is not None else None
            if numpr is None:continue
            numid=numpr.find(W+'numId');level=numpr.find(W+'ilvl')
            if numid is None:continue
            nid=numid.get(W+'val');lev=int(level.get(W+'val','0')) if level is not None else 0
            num=nums.get(nid)
            if num is None:continue
            aid=num.find(W+'abstractNumId');abstract=abstracts.get(aid.get(W+'val')) if aid is not None else None
            if abstract is None:continue
            definition=next((l for l in abstract.findall(W+'lvl') if int(l.get(W+'ilvl'))==lev),None)
            if definition is None:continue
            for key in list(counters):
                if key[0]==nid and key[1]>lev:del counters[key]
            start=definition.find(W+'start');initial=int(start.get(W+'val','1')) if start is not None else 1
            override=next((o for o in num.findall(W+'lvlOverride') if int(o.get(W+'ilvl'))==lev),None)
            if override is not None:
                st=override.find(W+'startOverride')
                if st is not None:initial=int(st.get(W+'val'))
            key=(nid,lev);counters[key]=counters.get(key,initial-1)+1
            fmt=definition.find(W+'numFmt');label=definition.find(W+'lvlText')
            if (paragraph.getparent() in cells and fmt is not None and fmt.get(W+'val')=='decimal'
                    and label is not None and re.fullmatch(r'\(%\d\)',label.get(W+'val',''))):
                text=paragraph_text(paragraph)
                props.remove(numpr)
                write_paragraph(paragraph,f'({counters[key]}) '+text)

    def add(self, section, label, node, value=None, kind='text'):
        actual = word_text(node) if value is None else value
        if section == 'A' and label.rstrip().endswith('· RANGO'):
            entries = range_entries(actual)
            if entries:
                for number, text in entries:
                    self.fields[str(len(self.fields)+1)] = Field(section, label+f' · Fabricante ({number})', text, node, 'range', number)
            else:
                self.fields[str(len(self.fields)+1)] = Field(section, label, actual, node, kind)
            self.fields[str(len(self.fields)+1)] = Field(section, label+' · agregar rango por fabricante', '', node, 'range_add')
            return
        self.fields[str(len(self.fields)+1)] = Field(section, label, actual, node, kind)

    def read_fields(self):
        body = self.parts['word/document.xml'].find(W+'body')
        sap = re.search(r'c[oó]digo(?:\s+SAP)?\s*:?\s*(\d{8,})', word_text(body), re.I)
        if not sap:
            raise ValueError('No se encontró el código SAP en el Word.')
        self.sap = sap.group(1)
        section, heading, pending = 'ID', '', ''
        manufacturer = ''
        for node in body:
            if node.tag == W+'p':
                value = word_text(node).strip()
                title = re.sub(r'^[a-d]\s*[.)-]\s*', '', norm(value))
                if section == 'B' and re.match(r'(observaciones|revision historica)\b', title):
                    self.add('B', 'Agregar fabricante y su bloque comercial', node, '', 'manufacturer')
                if re.match(r'revision historica\b', title):
                    section = 'D'
                elif re.match(r'especificacion tecnica\b', title):
                    section, heading = 'A', value
                elif re.match(r'informacion tecnico\b', title):
                    section, heading = 'B', value
                elif re.match(r'observaciones\b', title):
                    section, heading = 'C', value
                elif re.match(r'(analisis |informacion adicional)', title):
                    heading = value
                elif section == 'ID' and re.match(r'(inci|cas|nombre inci)', title):
                    self.add(section, value.split(':')[0], node)
                elif value and section in {'A', 'B', 'C'}:
                    entity = re.match(r'^(?:\(?\d+\)\s*)?' + ENTITY + r'\s*:', title)
                    if section == 'B' and entity:
                        role = entity.group(1).capitalize()
                        if role == 'Fabricante':
                            manufacturer = value.split(':', 1)[1].strip()
                        self.add(section, f'{role} · {manufacturer}', node)
                    elif not re.fullmatch(r'\(?\d+\)', value):
                        self.add(section, heading or section, node)
                continue
            if node.tag != W+'tbl':
                continue
            rows = node.findall(W+'tr')
            if not rows:
                continue
            first = [norm(word_text(c)) for c in rows[0].findall(W+'tc')]
            if len(first) == 3 and 'cambio' in first[0] and first[2] == 'version':
                self.history = node
                continue
            if section == 'D':
                continue
            last = None
            columns = [word_text(c).strip() for c in rows[0].findall(W+'tc')]
            if 'rango' not in first:
                columns = []
            for row in rows:
                cells = row.findall(W+'tc')
                values = [word_text(c) for c in cells]
                if not cells:
                    continue
                label = values[0].strip()
                normalized = norm(label)
                if normalized in {'parametro', 'alergeno', 'nombre del alergeno'}:
                    continue
                if section == 'ID':
                    if re.match(r'(inci|cas|nombre inci)', normalized):
                        self.add(section, label, cells[-1])
                    continue
                indexes = [i for i, value in enumerate(values[:-1])
                           if re.fullmatch(ENTITY, norm(value))]
                if section == 'B' and indexes:
                    index = indexes[0]
                    pending = values[index].strip()
                    if norm(pending) == 'fabricante':
                        manufacturer = values[index+1].lstrip(': ').strip()
                    self.add(section, f'{pending} · {manufacturer}', cells[index+1])
                elif section == 'A' and not any(v.strip() for v in values) and len(cells) == 3:
                    last = row
                    for index, cell in enumerate(cells):
                        self.add(section, f'{heading} · fila vacía · columna {index+1}', cell)
                elif not any(v.strip() for v in values):
                    continue
                elif len(cells) >= 2:
                    for index, cell in enumerate(cells):
                        column = columns[index] if len(columns) == len(cells) else f'columna {index+1}'
                        detail = f'{heading}' + (f' · Fabricante {manufacturer}' if section == 'B' and manufacturer else '') + f' · {label} · {column}'
                        self.add(section, detail, cell)
                    if len(cells) == 3 and section in {'A', 'B', 'C'}:
                        last = row
                elif values[0].strip():
                    self.add(section, pending or heading, cells[0])
            if section == 'B' and manufacturer and any(
                    re.fullmatch(ENTITY, norm(word_text(c)))
                    for row in rows for c in row.findall(W+'tc')[:-1]):
                self.add('B', f'Agregar parámetros adicionales · {manufacturer}', node, '', 'additional')
            if last is not None:
                self.add(section, f'{heading}'+(f' · Fabricante {manufacturer}' if section=='B' and manufacturer else '')+' · agregar fila (3 columnas)', last, '', 'add')
        if self.history is None or len(self.history.findall(W+'tr')) < 2:
            raise ValueError('No se encontró una tabla de Revisión Histórica compatible.')

    def history_summary(self, approved):
        groups = {}
        makers = {manufacturer_key(g['name']):g['number'] for g in self.manufacturers}
        for key,value in approved.items():
            if self.fields[key].kind=='manufacturer':
                for maker in re.findall(r'(?im)^fabricante\s*:\s*(.+)$',value):
                    makers.setdefault(manufacturer_key(maker),max(makers.values(),default=0)+1)
        for key, value in approved.items():
            f = self.fields[key]
            parts = [p.strip().rstrip(':') for p in f.label.split(' · ')]
            name = parts[-2] if len(parts) >= 3 else parts[0]
            if f.kind in {'range', 'range_add'}:
                name = parts[-3] if len(parts)>=3 else parts[0]
            if f.kind == 'range_add':
                sentences=[]
                for line in value.splitlines():
                    maker, _, new_range = line.partition(' | ')
                    number=makers.get(manufacturer_key(maker.partition(":")[2].strip()))
                    reference=f"({number})" if number else maker.partition(":")[2].strip()
                    sentences.append(f'Se incorpora el rango de {name} del fabricante {reference}: «{new_range.strip()}».')
                sentence=' '.join(sentences)
            elif f.kind == 'manufacturer':
                descriptions = []
                for block in re.split(r'(?im)(?=^fabricante\s*:)', value):
                    roles = {norm(line.partition(':')[0]): line.partition(':')[2].strip()
                             for line in block.splitlines() if ':' in line}
                    if not roles.get('fabricante'):
                        continue
                    description = f'Se incorpora al fabricante «{roles["fabricante"]}»'
                    if roles.get('proveedor') and manufacturer_key(roles['proveedor'])!=manufacturer_key(roles['fabricante']):
                        description += f', con el proveedor «{roles["proveedor"]}»'
                    description += ', junto con la información comercial respaldada'
                    if 'parametro adicional' in roles:
                        description += ' y sus parámetros adicionales'
                    descriptions.append(description + '.')
                sentence = ' '.join(descriptions)
            elif f.kind == 'add':
                sentence = 'Se incorpora la información de ' + value.replace(' | ', ', ').rstrip('.') + '.'
            elif not f.value.strip():
                sentence = f'Se incorpora {name}: «{value.strip()}».'
            else:
                sentence = f'Se actualiza {name} de «{f.value.strip().lstrip(": ")}» a «{value.strip().lstrip(": ")}».'
            groups.setdefault(f.section, []).append(sentence)
        return ' '.join(('En la identificación, ' if section == 'ID' else f'En el ítem {section}, ') +
                        ' '.join(lines)[0].lower() + ' '.join(lines)[1:]
                        for section, lines in groups.items())

    def apply_changes(self, approved):
        """Aplica los cambios en el orden de exportación y devuelve {nodo: id del campo}.

        El mapa permite resaltar cada cambio con su propio color en la vista previa.
        """
        document = self.parts['word/document.xml']
        owners = {}
        order = {'manufacturer': 0, 'range_add': 2}
        for field_id, value in sorted(approved.items(), key=lambda item: order.get(self.fields[item[0]].kind, 1)):
            field = self.fields[field_id]
            before = set(document.iter())
            field.write(value)
            if field.kind in {'text', 'range', 'range_add'}:
                owners.setdefault(field.node, field_id)
            for node in document.iter(W+'tc', W+'p'):
                if node not in before:
                    owners.setdefault(node, field_id)
        return owners

    def preview_html(self, approved, effective, add_history=True, history_text=None, colors=None):
        from html import escape
        from tempfile import TemporaryDirectory
        from pathlib import Path
        # Apply exactly the same document mutations used by export, to an isolated copy.
        draft = Specification(self.data)
        owners = draft.apply_changes(approved)
        with TemporaryDirectory() as folder:
            output = Path(folder) / 'materia_prima.infrastructure.preview.docx'
            if approved:
                summary = history_text if history_text is not None else self.history_summary(approved)
                draft.export(output, approved, effective, add_history and bool(summary.strip()), history_text, applied=True)
        colors = colors or {}
        def mark(node):
            field_id = owners.get(node)
            if field_id is None:
                return ''
            return f' class="modified chg-{int(colors.get(field_id, 0)) % len(PALETTE)}" data-change="{escape(field_id)}"'
        def render(node):
            tag = node.tag
            if tag == W+'p':
                return '<p' + mark(node) + '>' + escape(paragraph_text(node)).replace('\n', '<br>') + '</p>'
            if tag == W+'tbl':
                return '<table>' + ''.join(render(c) for c in node if c.tag == W+'tr') + '</table>'
            if tag == W+'tr':
                return '<tr>' + ''.join(render(c) for c in node if c.tag == W+'tc') + '</tr>'
            if tag == W+'tc':
                return '<td' + mark(node) + '>' + ''.join(render(c) for c in node if c.tag in {W+'p', W+'tbl'}) + '</td>'
            return ''
        return '<p><strong>Especificación técnica · ' + escape(self.sap) + ' · Versión ' + str(self.version + bool(approved)) + '</strong></p>' + ''.join(render(n) for n in draft.parts['word/document.xml'].find(W+'body'))

    def export(self, output, approved, date, add_history=True, history_text=None, applied=False):
        if not applied:
            self.apply_changes(approved)
        body = self.parts['word/document.xml'].find(W+'body')
        groups = manufacturer_blocks(body)
        numbers = {g['number'] for g in groups}
        if not groups:
            raise ValueError('La especificación debe conservar al menos un fabricante en B.')
        if len(numbers) != len(groups):
            raise ValueError('Hay números de fabricante duplicados en B. Corrígelos antes de exportar.')
        for f in self.fields.values():
            if f.section == 'A' and f.kind in {'range', 'range_add'}:
                unknown = {n for n,_ in range_entries(word_text(f.node))} - numbers
                if unknown:
                    raise ValueError('El rango referencia fabricantes inexistentes: '+', '.join(map(str,sorted(unknown))))
        for emission, version in self.headers:
            write_word(emission, date.strftime('%d/%m/%Y'))
            write_word(version, str(self.version+1))
        for part_name, header in self.parts.items():
            if not part_name.startswith('word/header'):continue
            for cell in header.iter(W+'tc'):
                if not re.fullmatch(r'\d+\s+de\s+\d+',word_text(cell).strip()):continue
                write_word(cell,'')
                paragraph=next(cell.iter(W+'p'))
                for instruction,fallback in [('PAGE','1'),(None,' de '),('NUMPAGES','1')]:
                    if instruction is None:
                        ET.SubElement(ET.SubElement(paragraph,W+'r'),W+'t').text=fallback
                    else:
                        field=ET.SubElement(paragraph,W+'fldSimple',{W+'instr':instruction})
                        ET.SubElement(ET.SubElement(field,W+'r'),W+'t').text=fallback
        rows = self.history.findall(W+'tr')
        new = deepcopy(rows[-1])
        summary = self.history_summary(approved) if history_text is None else history_text.strip()
        if add_history and not summary:
            raise ValueError('Redacta la revisión histórica o desactiva su registro.')
        for cell, value in zip(new.findall(W+'tc'),
                               [date.strftime('%d/%m/%Y'), summary, str(self.version+1)], strict=True):
            write_word(cell, value)
        if add_history:
            rowprops=new.find(W+'trPr')
            if rowprops is None:rowprops=ET.SubElement(new,W+'trPr')
            if rowprops.find(W+'cantSplit') is None:ET.SubElement(rowprops,W+'cantSplit')
            self.history.append(new)
        # Keep section headings and history table headers with their first content row.
        for node in body:
            if node.tag == W+'p' and re.search(r'(observaciones|revisi[oó]n hist[oó]rica)', word_text(node), re.I):
                props=node.find(W+'pPr')
                if props is None:props=ET.Element(W+'pPr');node.insert(0,props)
                if props.find(W+'keepNext') is None:ET.SubElement(props,W+'keepNext')
                props.find(W+'keepNext').set(W+'val','1')
        for paragraph in self.history.findall(W+'tr')[0].iter(W+'p'):
            props=paragraph.find(W+'pPr')
            if props is None:props=ET.Element(W+'pPr');paragraph.insert(0,props)
            if props.find(W+'keepNext') is None:ET.SubElement(props,W+'keepNext')
            props.find(W+'keepNext').set(W+'val','1')
        replace_parts(self.data, output, self.parts)


class ChangeForm:
    def __init__(self, data):
        self.data = data
        with ZipFile(BytesIO(data)) as z:
            workbook = root(z, 'xl/workbook.xml')
            sheet = next((n for n in workbook.iter(S+'sheet')
                          if norm(n.get('name', '')) == 'as-reg-018'), None)
            if sheet is None:
                raise ValueError('El Excel debe contener la hoja AS-REG-018.')
            rel = next(n for n in root(z, 'xl/_rels/workbook.xml.rels')
                       if n.get('Id') == sheet.get(REL+'id'))
            target = rel.get('Target')
            self.name = target.lstrip('/') if target.startswith('/') else posixpath.normpath('xl/'+target)
            self.sheet = root(z, self.name)
            self.styles = root(z, 'xl/styles.xml')
            self.xfs = self.styles.find(S+'cellXfs')
            self.wrapped = {}
            strings = []
            if 'xl/sharedStrings.xml' in z.namelist():
                strings = [self.string(n) for n in root(z, 'xl/sharedStrings.xml')]
            self.cells = {n.get('r'): n for n in self.sheet.iter(S+'c')}
            self.labels = {}
            for addr, n in self.cells.items():
                value = n.findtext(S+'v', '')
                if n.get('t') == 's':
                    value = strings[int(value)]
                elif n.get('t') == 'inlineStr':
                    value = self.string(n)
                self.labels[addr] = norm(value)
        if ('solicitante' not in self.labels.get('B7', '') or
                'especificaciones tecnicas' not in self.labels.get('C13', '')):
            raise ValueError('La cabecera de AS-REG-018 no coincide con el formato disponible.')
        self.blocks = {'de': [], 'a': []}
        limit = min((int(k[1:]) for k, v in self.labels.items()
                     if re.fullmatch(r'A\d+', k) and 'justificacion del cambio' in v), default=0)
        headings = sorted((int(addr[1:]), value[:-1]) for addr, value in self.labels.items()
                          if re.fullmatch(r'A\d+', addr) and value in ('de:', 'a:')
                          and 19 < int(addr[1:]) < limit)
        self.version_labels = []
        for (row, key), (end, _) in zip(headings, headings[1:]+[(limit, '')]):
            self.blocks[key].extend(f'A{n}' for n in range(row+1, end) if f'A{n}' in self.cells
                                    and (n == row+1 or self.labels[f'A{n}']))
            addr = f'B{row}'
            if re.fullmatch(r'version\s+\d+', self.labels.get(addr, '')):
                self.version_labels.append((addr, key))
        if not all(self.blocks.values()):
            raise ValueError('No se localizaron los bloques DE y A del formato.')

    @staticmethod
    def string(node):
        return ''.join(t.text or '' for t in node.iter(S+'t'))

    def set_cell(self, addr, value):
        cell = self.cells.get(addr)
        if cell is None or cell.find(S+'f') is not None:
            raise ValueError(f'La celda {addr} no admite escritura en esta plantilla.')
        for child in list(cell):
            if child.tag in {S+'v', S+'is'}:
                cell.remove(child)
        if isinstance(value, int):
            cell.set('t', 'n')
            ET.SubElement(cell, S+'v').text = str(value)
        else:
            if len(value) > 32767:
                raise ValueError(f'El contenido supera el máximo de Excel en {addr}.')
            cell.set('t', 'inlineStr')
            ET.SubElement(ET.SubElement(cell, S+'is'), S+'t', {SPACE: 'preserve'}).text = value

    def fit_change_text(self, addr, value):
        if not value:
            return
        cell = self.cells[addr]
        index = int(cell.get('s', '0'))
        original = self.xfs[index]
        alignment = original.find(S+'alignment')
        if alignment is None or alignment.get('wrapText') not in {'1', 'true'}:
            if index not in self.wrapped:
                style = deepcopy(original)
                alignment = style.find(S+'alignment')
                if alignment is None:
                    alignment = ET.Element(S+'alignment')
                    style.insert(0, alignment)
                alignment.set('wrapText', '1')
                style.set('applyAlignment', '1')
                self.wrapped[index] = len(self.xfs)
                self.xfs.append(style)
                self.xfs.set('count', str(len(self.xfs)))
            cell.set('s', str(self.wrapped[index]))
        row = cell.getparent()
        lines = sum(max(1, len(wrap(line, width=106))) for line in value.splitlines())
        height = min(409, 14 * lines + 5)
        if height > float(row.get('ht', '15')):
            row.set('ht', str(height))
            row.set('customHeight', '1')

    def export(self, output, spec, approved, applicant, area, date):
        from datetime import date as Date
        for addr, value in {'F7': applicant, 'D9': area, 'W9': (date-Date(1899, 12, 30)).days,
                            'B13': 'X', 'H13': spec.sap, 'L13': spec.version}.items():
            self.set_cell(addr, value)
        for key, addresses in self.blocks.items():
            values = []
            for field_id, after in approved.items():
                f = spec.fields[field_id]
                value = f.value if key == 'de' else after
                values.append(f'{f.section} · {f.label}: {value.strip() or "—"}')
            for index, addr in enumerate(addresses):
                batch = values[index:] if index == len(addresses)-1 else values[index:index+1]
                text = '\n'.join(batch)
                self.set_cell(addr, text)
                self.fit_change_text(addr, text)
        for addr, key in self.version_labels:
            self.set_cell(addr, f'Versión {spec.version + (key == "a")}')
        parts = {self.name: self.sheet}
        if self.wrapped:
            parts['xl/styles.xml'] = self.styles
        replace_parts(self.data, output, parts)
