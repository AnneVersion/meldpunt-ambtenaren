"""
Meldpunt Ambtenaren — Database Migratie & Setup

Gebruik:
    python migrate.py                    # Maak tabellen aan + admin user
    python migrate.py --seed             # + importeer seed data uit index.html localStorage export
    python migrate.py --import data.json # Importeer een JSON export bestand
    python migrate.py --reset            # DROP alles en begin opnieuw (DESTRUCTIEF!)
"""
import os
import sys
import json
import getpass
import bcrypt

# Voeg parent dir toe voor imports
sys.path.insert(0, os.path.dirname(__file__))

from app import app
from models import db, Melding, Reactie, Ambtenaar, AdminUser
from config import Config


def create_tables():
    """Maak alle tabellen aan."""
    print("  Tabellen aanmaken...")
    db.create_all()
    print("  OK — alle tabellen bestaan nu")


def create_admin(username=None, password=None):
    """Maak een admin-gebruiker aan."""
    existing = AdminUser.query.filter_by(username=username or Config.ADMIN_DEFAULT_USER).first()
    if existing:
        print(f"  Admin '{existing.username}' bestaat al — overslaan")
        return

    if not username:
        username = Config.ADMIN_DEFAULT_USER or input("  Admin gebruikersnaam: ").strip()
    if not password:
        password = Config.ADMIN_DEFAULT_PASS
        if not password:
            password = getpass.getpass("  Admin wachtwoord: ").strip()
            if not password:
                print("  FOUT: Wachtwoord mag niet leeg zijn")
                return

    pw_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    user = AdminUser(username=username, password_hash=pw_hash)
    db.session.add(user)
    db.session.commit()
    print(f"  Admin '{username}' aangemaakt!")


def import_json(filepath):
    """Importeer een JSON export bestand."""
    print(f"  Bestand laden: {filepath}")
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    counts = {'meldingen': 0, 'reacties': 0, 'ambtenaren': 0}

    # Als het een array is, probeer te raden welke collectie
    if isinstance(data, list):
        if len(data) > 0 and 'titel' in data[0]:
            data = {'meldingen': data}
        elif len(data) > 0 and 'tekst' in data[0]:
            data = {'reacties': data}
        else:
            data = {'meldingen': data}

    from app import sanitize_text, sanitize_namen, sanitize_bronnen, maak_claim_code

    for item in data.get('meldingen', []):
        if not item.get('id'):
            continue
        if Melding.query.get(item['id']):
            continue

        from datetime import datetime, timezone
        m = Melding(
            id=item['id'],
            claim_code=item.get('claimCode') or maak_claim_code(),
            titel=sanitize_text(item.get('titel', '')),
            verhaal=sanitize_text(item.get('verhaal', '')),
            instantie=sanitize_text(item.get('instantie', ''), 200),
            namen=sanitize_namen(item.get('namen', [])),
            bronnen=sanitize_bronnen(item.get('bronnen', [])),
            anoniem=item.get('anoniem', True),
            melder_naam=item.get('melder_naam'),
            melder_email=item.get('melder_email'),
            klokkenluider=item.get('klokkenluider', False),
            status=item.get('status', 'live'),
            views=item.get('views', 0)
        )
        if item.get('ts'):
            m.created_at = datetime.fromtimestamp(item['ts'] / 1000, tz=timezone.utc)
        db.session.add(m)
        counts['meldingen'] += 1

    for item in data.get('reacties', []):
        if not item.get('id'):
            continue
        if Reactie.query.get(item['id']):
            continue

        from datetime import datetime, timezone
        r = Reactie(
            id=item['id'],
            melding_id=item.get('mid', ''),
            naam=sanitize_text(item.get('naam', 'Anoniem'), 200),
            tekst=sanitize_text(item.get('tekst', ''))
        )
        if item.get('ts'):
            r.created_at = datetime.fromtimestamp(item['ts'] / 1000, tz=timezone.utc)
        db.session.add(r)
        counts['reacties'] += 1

    for item in data.get('ambtenaren', []):
        if not item.get('id'):
            continue
        if Ambtenaar.query.get(item['id']):
            continue

        a = Ambtenaar(
            id=item['id'],
            email=item.get('email', ''),
            naam=item.get('naam', ''),
            organisatie=item.get('organisatie', '')
        )
        db.session.add(a)
        counts['ambtenaren'] += 1

    db.session.commit()
    print(f"  Geimporteerd: {counts}")


def reset_database():
    """DROP alle tabellen en maak opnieuw aan. DESTRUCTIEF!"""
    confirm = input("  WAARSCHUWING: Dit verwijdert ALLE data! Type 'ja' om door te gaan: ")
    if confirm.strip().lower() != 'ja':
        print("  Geannuleerd.")
        return
    print("  Tabellen verwijderen...")
    db.drop_all()
    print("  Tabellen opnieuw aanmaken...")
    db.create_all()
    print("  Database gereset!")


def main():
    with app.app_context():
        print("=" * 50)
        print("  Meldpunt Ambtenaren — Database Setup")
        print("=" * 50)

        if '--reset' in sys.argv:
            reset_database()
            create_admin()
            return

        create_tables()
        create_admin()

        if '--import' in sys.argv:
            idx = sys.argv.index('--import')
            if idx + 1 < len(sys.argv):
                import_json(sys.argv[idx + 1])
            else:
                print("  FOUT: Geef een JSON bestandspad op na --import")

        if '--seed' in sys.argv:
            # Zoek naar data/ map met JSON bestanden
            data_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
            if os.path.exists(data_dir):
                for fn in os.listdir(data_dir):
                    if fn.endswith('.json'):
                        import_json(os.path.join(data_dir, fn))
            else:
                print("  Geen data/ map gevonden voor seed")

        print("\n  Klaar!")
        print(f"  Database: {Config.SQLALCHEMY_DATABASE_URI}")
        print(f"  Meldingen: {Melding.query.count()}")
        print(f"  Reacties: {Reactie.query.count()}")
        print(f"  Admins: {AdminUser.query.count()}")


if __name__ == '__main__':
    main()
