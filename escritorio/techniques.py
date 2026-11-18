"""Laboratory methods supplied by the company; document text, never filename inference."""
from functools import lru_cache
from pathlib import Path
import json

@lru_cache(maxsize=1)
def technique_context():
    path = Path(__file__).with_name('tecnicas.json')
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else []


def analysis_context(fields):
    """Full active-method detail plus concise objectives for alternative methods."""
    import re
    codes = set(re.findall(r'CC-FQ-TEC-\d+', ' '.join(f.value for f in fields.values())))
    result=[]
    for t in technique_context():
        text=t['texto']
        objective=re.search(r'OBJETIVO[:.\s]*(.*?)(?:\n\s*2[.)]|DEFINICIONES|DOCUMENTOS A CONSULTAR)',text,re.S|re.I)
        excerpt=(objective.group(1).strip() if objective else text)[:900]
        result.append({'codigo':t['codigo'],'documento':t['archivo'],
            'detalle':text[:5500] if t['codigo'] in codes else excerpt,
            'lectura':t.get('lectura','Texto extraído del PDF')})
    return result


def validate_section_a(field, value):
    """Reject invented internal method codes; uncertain capacity stays with the reviewer."""
    import re
    known = {t['codigo'] for t in technique_context()}
    codes = re.findall(r'CC-FQ-TEC-\d+', value)
    if any(code not in known for code in codes):
        raise ValueError('La técnica propuesta no está en el catálogo del laboratorio. Revisa su código o registra el parámetro en B.')
    if field.kind == 'add' and codes and not any(parameter_matches(value.split(' | ')[0], code) for code in codes):
        raise ValueError('El parámetro no se reconoce en el alcance de esa técnica. Revisa el catálogo o incorpóralo en B bajo su fabricante.')
    if field.kind == 'add' and not codes:
        raise ValueError('Para agregar un parámetro a A indica su técnica interna. Los parámetros sin técnica corresponden a B.')


def parameter_matches(parameter, code):
    """Conservative lexical guard; semantic applicability still requires review."""
    import re
    from office import norm
    text = next((norm(t['texto']) for t in technique_context() if t['codigo'] == code), '')
    words = re.findall(r'[a-z]{4,}', norm(parameter))
    ignored = {'solucion','acuosa','minimo','maximo','porcentaje','contenido','determinacion','analisis'}
    words = [w for w in words if w not in ignored]
    if code == 'CC-FQ-TEC-131':
        return bool(set(words) & {'aspecto','apariencia','color','olor','sabor','textura','descripcion'})
    return any(w in text for w in words)


def catalog_entries(used_text=''):
    """Técnicas para mostrar: título limpio, versión, objetivo, categoría y si el Word las usa."""
    import re
    from office import norm
    used = set(re.findall(r'CC-FQ-TEC-\d+', used_text))
    items = []
    for t in technique_context():
        name = re.sub(r'\.pdf$', '', t['archivo'], flags=re.I)
        name = name.replace(t['codigo'], '').strip(' -·')
        version = re.search(r'\(V(\d+)\)', name)
        name = re.sub(r'\(V\d+\)\s*(\d{4})?', '', name).strip(' -·')
        # Mayúscula inicial y el resto en minúsculas; se respetan palabras con mayúsculas y minúsculas (pH).
        words = [w if (w != w.upper() and w != w.lower()) else w.lower() for w in name.split()]
        title = ' '.join(words)
        title = title[:1].upper() + title[1:]
        text = t['texto']
        objective = re.search(r'OBJETIVO[:.\s]*(.*?)(?:\n\s*2\s*[.)]|DEFINICIONES|DOCUMENTOS A CONSULTAR|ALCANCE)', text, re.S | re.I)
        objective = ' '.join((objective.group(1) if objective else '').split())[:600]
        key = norm(name)
        category = ('Preparación de soluciones' if 'preparacion' in key else
                    'Evaluación sensorial' if 'sensorial' in key else
                    'Envases y empaques' if re.search(r'prueba|calibre|gramaje|capacidad|volumen dosificado|medidas dimensionales|hermeticidad|torque', key) else
                    'Análisis fisicoquímico')
        items.append({'codigo': t['codigo'], 'titulo': title, 'version': version.group(1) if version else '',
                      'objetivo': objective, 'categoria': category, 'en_uso': t['codigo'] in used,
                      'ocr': bool(t.get('lectura')), 'texto': text})
    return sorted(items, key=lambda i: (not i['en_uso'], i['codigo']))
