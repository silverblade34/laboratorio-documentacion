"""Historial local de análisis: permite reabrir una revisión sin volver a consultar a la IA.

Cada análisis se guarda en su carpeta con copias del Word y los PDF, las propuestas, las
observaciones y las aprobaciones. No sale del equipo.
"""
from datetime import datetime
from pathlib import Path
import json
import re
import secrets
import shutil

LIMIT = 200


class History:
    def __init__(self, directory):
        self.root = Path(directory)
        self.root.mkdir(parents=True, exist_ok=True)

    def folder(self, entry_id):
        if not re.fullmatch(r'[0-9]{8}-[0-9]{6}-[0-9a-f]{6}', entry_id or ''):
            raise ValueError('Registro de historial no válido.')
        return self.root / entry_id

    @staticmethod
    def new_id():
        return datetime.now().strftime('%Y%m%d-%H%M%S-') + secrets.token_hex(3)

    def save(self, entry_id, word, pdfs, record):
        """Crea o actualiza un registro. Los archivos se copian solo la primera vez."""
        folder = self.folder(entry_id)
        (folder / 'pdf').mkdir(parents=True, exist_ok=True)
        if not (folder / 'word' / word.name).exists():
            (folder / 'word').mkdir(exist_ok=True)
            shutil.copy2(word, folder / 'word' / word.name)
        for pdf in pdfs:
            if not (folder / 'pdf' / pdf.name).exists():
                shutil.copy2(pdf, folder / 'pdf' / pdf.name)
        path = folder / 'analisis.json'
        previous = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
        data = {**previous, **record, 'id': entry_id, 'word': word.name, 'pdfs': [p.name for p in pdfs],
                'creado': previous.get('creado') or datetime.now().isoformat(timespec='seconds'),
                'actualizado': datetime.now().isoformat(timespec='seconds')}
        temp = path.with_suffix('.tmp')
        temp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding='utf-8')
        temp.replace(path)
        self.prune()

    def load(self, entry_id):
        folder = self.folder(entry_id)
        data = json.loads((folder / 'analisis.json').read_text(encoding='utf-8'))
        word = folder / 'word' / data['word']
        pdfs = [folder / 'pdf' / name for name in data['pdfs']]
        if not word.is_file() or not all(p.is_file() for p in pdfs):
            raise ValueError('Faltan archivos de este análisis en el historial.')
        return data, word, pdfs

    def entries(self):
        items = []
        for path in self.root.glob('*/analisis.json'):
            try:
                data = json.loads(path.read_text(encoding='utf-8'))
            except (OSError, ValueError):
                continue
            proposals = data.get('proposals', {})
            items.append({
                'id': data['id'], 'sap': data.get('sap', ''), 'version': data.get('version'),
                'word': data.get('word', ''), 'pdfs': data.get('pdfs', []),
                'creado': data.get('creado', ''), 'actualizado': data.get('actualizado', ''),
                'secciones': data.get('sections', []),
                'propuestas': sum(1 for v in proposals.values() if v),
                'aprobados': len(data.get('approved', {})),
                'errores': sum(1 for n in data.get('notes', []) if n.get('type') == 'error'),
                'exportado': data.get('exportado', ''),
            })
        return sorted(items, key=lambda i: i['actualizado'], reverse=True)

    def delete(self, entry_id):
        folder = self.folder(entry_id)
        if folder.is_dir():
            shutil.rmtree(folder)

    def prune(self):
        for item in self.entries()[LIMIT:]:
            self.delete(item['id'])
