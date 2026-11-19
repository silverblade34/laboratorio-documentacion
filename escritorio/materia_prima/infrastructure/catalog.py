"""Repositorio SQLite de entidades comerciales verificadas en la exportación."""
from contextlib import closing
from pathlib import Path
import os
import sqlite3

from materia_prima.domain.office import norm

class Catalog:
    def __init__(self, directory=None):
        self.path = (directory or Path(os.getenv('LOCALAPPDATA') or Path.home()/'.local/share')
                     / 'MateriaPrima') / 'catalogo.sqlite3'
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute('''CREATE TABLE IF NOT EXISTS entidad (
                sap TEXT, rol TEXT, normalizado TEXT, nombre TEXT,
                PRIMARY KEY (sap, rol, normalizado))''')

    def entries(self, sap):
        with closing(sqlite3.connect(self.path)) as db:
            return db.execute('SELECT DISTINCT rol, nombre FROM entidad WHERE sap=? ORDER BY rol,nombre',
                              (sap,)).fetchall()

    def context(self, sap):
        with closing(sqlite3.connect(self.path)) as db:
            return db.execute(
                '''SELECT rol, nombre, MAX(sap = ?) AS mismo_material
                   FROM entidad GROUP BY rol, normalizado
                   ORDER BY mismo_material DESC, rol, nombre LIMIT 250''', (sap,)
            ).fetchall()

    def save(self, sap, entities):
        with closing(sqlite3.connect(self.path)) as db, db:
            db.executemany('INSERT OR IGNORE INTO entidad VALUES (?,?,?,?)',
                           ((sap, role, norm(name), name) for role, name in entities))

