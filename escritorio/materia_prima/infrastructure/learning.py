"""Memoria versionada de decisiones finales; nunca aplica valores al documento."""
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3

from materia_prima.domain.office import norm


class LearningMemory:
    def __init__(self, directory):
        self.path = Path(directory) / 'aprendizajes.sqlite3'
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute('''CREATE TABLE IF NOT EXISTS decision_v1 (
                id TEXT PRIMARY KEY, sap TEXT NOT NULL, campo TEXT NOT NULL,
                creado TEXT NOT NULL, datos TEXT NOT NULL)''')
            db.execute('CREATE INDEX IF NOT EXISTS decision_material ON decision_v1(sap, campo)')

    @staticmethod
    def field_key(field):
        # Los identificadores de filas y números de fabricante pueden cambiar entre Word.
        return json.dumps([field.section, norm(field.label), field.kind,
                           norm(field.manufacturer_name or '')], ensure_ascii=False)

    def record_export(self, spec, approved, proposals, export_id, app_version, model):
        if not str(spec.sap or '').strip():
            return 0
        rows = []
        for field_id, final in approved.items():
            field = spec.fields[field_id]
            candidates = proposals.get(field_id, [])
            values = [str(p.get('value', '')) for p in candidates]
            decision = 'aceptada' if final in values else ('corregida' if values else 'manual')
            data = {'schema': 1, 'exportacion': str(export_id), 'sap': spec.sap,
                    'seccion': field.section, 'campo': field.label,
                    'fabricante': field.manufacturer_name or '', 'tipo': field.kind,
                    'antes': field.value, 'propuestas': candidates, 'final': final,
                    'decision': decision, 'aplicacion': app_version, 'modelo_configurado': model}
            encoded = json.dumps(data, ensure_ascii=False, sort_keys=True)
            identity = hashlib.sha256(encoded.encode('utf-8')).hexdigest()
            rows.append((identity, str(spec.sap), self.field_key(field),
                         datetime.now(timezone.utc).isoformat(), encoded))
        with closing(sqlite3.connect(self.path)) as db, db:
            before = db.total_changes
            db.executemany('INSERT OR IGNORE INTO decision_v1 VALUES (?,?,?,?,?)', rows)
            return db.total_changes - before

    def examples(self, sap, fields, limit=12):
        """Solo el ejemplo más reciente por campo compatible, acotado para el prompt."""
        if not str(sap or '').strip():
            return []
        keys = {self.field_key(f) for f in fields.values()}
        found, seen = [], set()
        with closing(sqlite3.connect(self.path)) as db:
            for key, encoded in db.execute(
                    'SELECT campo, datos FROM decision_v1 WHERE sap=? ORDER BY creado DESC, rowid DESC',
                    (str(sap),)):
                if key not in keys or key in seen:
                    continue
                seen.add(key)
                data = json.loads(encoded)
                found.append({k: str(data[k])[:1000] for k in
                              ('seccion', 'campo', 'fabricante', 'antes', 'final', 'decision')})
                if len(found) >= limit:
                    break
        return found
