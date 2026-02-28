"""
Meldpunt Ambtenaren — Flask API
"""
import os
import re
import uuid
import random
import string
import json
import functools
from datetime import datetime, timezone

from flask import Flask, request, jsonify, session, send_from_directory, abort
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import bcrypt

from config import Config
from models import db, Melding, Reactie, Ambtenaar, AdminUser, PageView

# ============ APP SETUP ============

app = Flask(__name__, static_folder=None)
app.config.from_object(Config)

db.init_app(app)
CORS(app, supports_credentials=True, origins=['*'])

limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    default_limits=[Config.RATELIMIT_DEFAULT],
    storage_uri="memory://"
)

# Pad naar de frontend (index.html zit een map hoger)
FRONTEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))


# ============ HELPERS ============

def maak_claim_code():
    """Genereer een unieke MLD-XXXXXX code."""
    chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
    for _ in range(100):  # max pogingen
        code = 'MLD-' + ''.join(random.choices(chars, k=6))
        if not Melding.query.filter_by(claim_code=code).first():
            return code
    raise RuntimeError('Kan geen unieke claim code genereren')


def maak_id():
    """Genereer een uniek ID."""
    return f'id_{int(datetime.now(timezone.utc).timestamp()*1000)}_{uuid.uuid4().hex[:8]}'


def sanitize_text(text, max_length=50000):
    """Basis input sanitatie."""
    if not text:
        return ''
    text = str(text).strip()
    if len(text) > max_length:
        text = text[:max_length]
    return text


def sanitize_namen(namen_list):
    """Valideer en sanitize namen array."""
    if not isinstance(namen_list, list):
        return []
    result = []
    for n in namen_list[:20]:  # max 20 namen
        if isinstance(n, dict) and n.get('naam', '').strip():
            result.append({
                'naam': sanitize_text(n.get('naam', ''), 200),
                'functie': sanitize_text(n.get('functie', ''), 200),
                'foto': sanitize_text(n.get('foto', ''), 2000)  # data: URI of URL
            })
    return result


def sanitize_bronnen(bronnen_list):
    """Valideer en sanitize bronnen array."""
    if not isinstance(bronnen_list, list):
        return []
    result = []
    for b in bronnen_list[:50]:  # max 50 bronnen
        if isinstance(b, dict):
            result.append({
                't': sanitize_text(b.get('t', ''), 500),
                'u': sanitize_text(b.get('u', ''), 2000)
            })
    return result


def admin_required(f):
    """Decorator: vereist admin-sessie."""
    @functools.wraps(f)
    def wrapped(*args, **kwargs):
        if not session.get('admin_id'):
            return jsonify({'error': 'Niet ingelogd'}), 401
        return f(*args, **kwargs)
    return wrapped


# ============ STATIC FILES ============

@app.route('/')
def serve_index():
    return send_from_directory(FRONTEND_DIR, 'index.html')


@app.route('/<path:filename>')
def serve_static(filename):
    """Serveer statische bestanden uit de frontend map."""
    filepath = os.path.join(FRONTEND_DIR, filename)
    if os.path.isfile(filepath):
        return send_from_directory(FRONTEND_DIR, filename)
    # SPA fallback: stuur altijd index.html voor onbekende routes
    return send_from_directory(FRONTEND_DIR, 'index.html')


# ============ PUBLIEKE API ============

@app.route('/api/meldingen', methods=['GET'])
def get_meldingen():
    """Haal alle gepubliceerde meldingen op."""
    meldingen = Melding.query.filter_by(status='live') \
        .order_by(Melding.created_at.desc()).all()
    return jsonify([m.to_dict() for m in meldingen])


@app.route('/api/meldingen/<melding_id>', methods=['GET'])
def get_melding(melding_id):
    """Haal een specifieke melding op (alleen als live)."""
    m = Melding.query.get(melding_id)
    if not m or m.status != 'live':
        return jsonify({'error': 'Niet gevonden'}), 404
    # Views teller ophogen
    m.views = (m.views or 0) + 1
    db.session.commit()
    return jsonify(m.to_dict())


@app.route('/api/meldingen', methods=['POST'])
@limiter.limit(Config.RATELIMIT_SUBMIT)
def submit_melding():
    """Dien een nieuwe melding in."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Geen data'}), 400

    namen = sanitize_namen(data.get('namen', []))
    if len(namen) == 0:
        return jsonify({'error': 'Vul minstens een naam in'}), 400

    anoniem = data.get('anoniem', True)
    titel = sanitize_text(data.get('titel', ''), 500)
    if not titel:
        titel = ', '.join(n['naam'] for n in namen)

    melding = Melding(
        id=maak_id(),
        claim_code=maak_claim_code(),
        titel=titel,
        verhaal=sanitize_text(data.get('verhaal', '')),
        instantie=sanitize_text(data.get('instantie', ''), 200),
        namen=namen,
        bronnen=sanitize_bronnen(data.get('bronnen', [])),
        anoniem=anoniem,
        melder_naam=sanitize_text(data.get('melder_naam', ''), 200) if not anoniem else None,
        melder_email=sanitize_text(data.get('melder_email', ''), 200) if not anoniem else None,
        klokkenluider=bool(data.get('klokkenluider', False)),
        # Anoniem → review nodig; met naam → direct live
        status='review' if anoniem else 'live',
        views=0
    )

    db.session.add(melding)
    db.session.commit()

    return jsonify({
        'id': melding.id,
        'claimCode': melding.claim_code,
        'status': melding.status
    }), 201


# ============ AMBTENAREN API ============

@app.route('/api/ambtenaren', methods=['POST'])
@limiter.limit("10/hour")
def submit_ambtenaar():
    """Registreer een ambtenaar voor meldingen."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Geen data'}), 400

    email = sanitize_text(data.get('email', ''), 200)
    naam = sanitize_text(data.get('naam', ''), 200)
    if not email or '@' not in email:
        return jsonify({'error': 'Ongeldig e-mailadres'}), 400
    if not naam:
        return jsonify({'error': 'Vul een naam in'}), 400

    ambtenaar = Ambtenaar(
        id=maak_id(),
        email=email,
        naam=naam,
        organisatie=sanitize_text(data.get('organisatie', ''), 200)
    )
    db.session.add(ambtenaar)
    db.session.commit()
    return jsonify(ambtenaar.to_dict()), 201


# ============ CLAIM API ============

@app.route('/api/claim/<code>', methods=['GET'])
def get_claim(code):
    """Zoek een melding op via claim-code (elke status)."""
    code = code.strip().upper()
    m = Melding.query.filter_by(claim_code=code).first()
    if not m:
        return jsonify({'error': 'Niet gevonden'}), 404
    return jsonify(m.to_dict(include_private=True))


@app.route('/api/claim/<code>', methods=['PUT'])
@limiter.limit("10/hour")
def update_claim(code):
    """Werk een melding bij via claim-code."""
    code = code.strip().upper()
    m = Melding.query.filter_by(claim_code=code).first()
    if not m:
        return jsonify({'error': 'Niet gevonden'}), 404

    data = request.get_json()
    if not data:
        return jsonify({'error': 'Geen data'}), 400

    if 'namen' in data:
        m.namen = sanitize_namen(data['namen'])
    if 'titel' in data:
        m.titel = sanitize_text(data['titel'], 500)
    if 'verhaal' in data:
        m.verhaal = sanitize_text(data['verhaal'])
    if 'instantie' in data:
        m.instantie = sanitize_text(data['instantie'], 200)
    if 'bronnen' in data:
        m.bronnen = sanitize_bronnen(data['bronnen'])

    m.updated_at = datetime.now(timezone.utc)
    db.session.commit()

    return jsonify({'ok': True, 'status': m.status})


# ============ REACTIES API ============

@app.route('/api/reacties/<melding_id>', methods=['GET'])
def get_reacties(melding_id):
    """Haal reacties op voor een melding."""
    m = Melding.query.get(melding_id)
    if not m or m.status != 'live':
        return jsonify({'error': 'Niet gevonden'}), 404
    reacties = Reactie.query.filter_by(melding_id=melding_id) \
        .order_by(Reactie.created_at.asc()).all()
    return jsonify([r.to_dict() for r in reacties])


@app.route('/api/reacties', methods=['POST'])
@limiter.limit("20/hour")
def submit_reactie():
    """Plaats een reactie op een melding."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Geen data'}), 400

    melding_id = data.get('mid', '')
    tekst = sanitize_text(data.get('tekst', ''), 5000)
    if not tekst:
        return jsonify({'error': 'Reactie mag niet leeg zijn'}), 400

    m = Melding.query.get(melding_id)
    if not m or m.status != 'live':
        return jsonify({'error': 'Melding niet gevonden'}), 404

    reactie = Reactie(
        id=maak_id(),
        melding_id=melding_id,
        naam=sanitize_text(data.get('naam', 'Anoniem'), 200) or 'Anoniem',
        tekst=tekst
    )
    db.session.add(reactie)
    db.session.commit()

    return jsonify(reactie.to_dict()), 201


# ============ ADMIN API ============

@app.route('/api/admin/login', methods=['POST'])
@limiter.limit("10/minute")
def admin_login():
    """Admin inloggen."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Geen data'}), 400

    username = (data.get('username') or '').strip()
    password = (data.get('password') or '').strip()

    if not username or not password:
        return jsonify({'error': 'Vul gebruikersnaam en wachtwoord in'}), 400

    user = AdminUser.query.filter_by(username=username).first()
    if not user or not bcrypt.checkpw(password.encode('utf-8'), user.password_hash.encode('utf-8')):
        return jsonify({'error': 'Ongeldige inloggegevens'}), 401

    session.permanent = True
    session['admin_id'] = user.id
    session['admin_user'] = user.username
    return jsonify({'ok': True, 'username': user.username})


@app.route('/api/admin/logout', methods=['POST'])
def admin_logout():
    """Admin uitloggen."""
    session.clear()
    return jsonify({'ok': True})


@app.route('/api/admin/check', methods=['GET'])
def admin_check():
    """Check of admin is ingelogd."""
    if session.get('admin_id'):
        return jsonify({'loggedIn': True, 'username': session.get('admin_user')})
    return jsonify({'loggedIn': False}), 401


@app.route('/api/admin/meldingen', methods=['GET'])
@admin_required
def admin_meldingen():
    """Alle meldingen (inclusief review/rejected) voor admin."""
    status_filter = request.args.get('status', '')
    q = Melding.query.order_by(Melding.created_at.desc())
    if status_filter:
        q = q.filter_by(status=status_filter)
    meldingen = q.all()
    return jsonify([m.to_dict(include_private=True) for m in meldingen])


@app.route('/api/admin/meldingen/<melding_id>/approve', methods=['PUT'])
@admin_required
def admin_approve(melding_id):
    """Keur een melding goed (status → live)."""
    m = Melding.query.get(melding_id)
    if not m:
        return jsonify({'error': 'Niet gevonden'}), 404
    m.status = 'live'
    m.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    return jsonify({'ok': True, 'id': m.id, 'status': 'live'})


@app.route('/api/admin/meldingen/<melding_id>/reject', methods=['PUT'])
@admin_required
def admin_reject(melding_id):
    """Wijs een melding af (status → rejected)."""
    m = Melding.query.get(melding_id)
    if not m:
        return jsonify({'error': 'Niet gevonden'}), 404
    m.status = 'rejected'
    m.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    return jsonify({'ok': True, 'id': m.id, 'status': 'rejected'})


@app.route('/api/admin/meldingen/<melding_id>', methods=['DELETE'])
@admin_required
def admin_delete(melding_id):
    """Verwijder een melding permanent."""
    m = Melding.query.get(melding_id)
    if not m:
        return jsonify({'error': 'Niet gevonden'}), 404
    db.session.delete(m)
    db.session.commit()
    return jsonify({'ok': True})


@app.route('/api/admin/export', methods=['GET'])
@admin_required
def admin_export():
    """Exporteer alle data als JSON."""
    data = {
        'meldingen': [m.to_dict(include_private=True) for m in Melding.query.all()],
        'reacties': [r.to_dict() for r in Reactie.query.all()],
        'ambtenaren': [a.to_dict() for a in Ambtenaar.query.all()]
    }
    return jsonify(data)


@app.route('/api/admin/import', methods=['POST'])
@admin_required
def admin_import():
    """Importeer JSON data (merge op ID)."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Geen data'}), 400

    counts = {'meldingen': 0, 'reacties': 0, 'ambtenaren': 0}

    # Meldingen importeren
    for item in data.get('meldingen', []):
        if not item.get('id'):
            continue
        existing = Melding.query.get(item['id'])
        if not existing:
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

    # Reacties importeren
    for item in data.get('reacties', []):
        if not item.get('id'):
            continue
        existing = Reactie.query.get(item['id'])
        if not existing:
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

    db.session.commit()
    return jsonify({'ok': True, 'imported': counts})


@app.route('/api/admin/stats', methods=['GET'])
@admin_required
def admin_stats():
    """Statistieken voor het admin dashboard."""
    return jsonify({
        'meldingen_total': Melding.query.count(),
        'meldingen_live': Melding.query.filter_by(status='live').count(),
        'meldingen_review': Melding.query.filter_by(status='review').count(),
        'meldingen_rejected': Melding.query.filter_by(status='rejected').count(),
        'reacties_total': Reactie.query.count(),
        'ambtenaren_total': Ambtenaar.query.count()
    })


# ============ ANALYTICS API ============

@app.route('/api/pv', methods=['POST'])
@limiter.limit("120/minute")
def track_pageview():
    """Registreer een pageview (privacy-vriendelijk, geen IP-opslag)."""
    data = request.get_json(silent=True)
    if not data or not data.get('p'):
        return jsonify({'ok': True}), 200  # fail silently

    pv = PageView(
        page=sanitize_text(data.get('p', ''), 100),
        referrer=sanitize_text(data.get('r', ''), 500),
        session_id=sanitize_text(data.get('s', ''), 50),
        screen_w=int(data['sw']) if str(data.get('sw', '')).isdigit() else None,
        screen_h=int(data['sh']) if str(data.get('sh', '')).isdigit() else None,
        is_mobile=bool(data.get('m', False))
    )
    db.session.add(pv)
    db.session.commit()
    return jsonify({'ok': True}), 200


@app.route('/api/admin/analytics', methods=['GET'])
@admin_required
def admin_analytics():
    """Bezoekersstatistieken voor het admin dashboard."""
    from sqlalchemy import func, cast, Date

    days = int(request.args.get('days', 30))
    cutoff = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    from datetime import timedelta
    cutoff = cutoff - timedelta(days=days)

    # Pageviews per dag
    daily = db.session.query(
        cast(PageView.created_at, Date).label('dag'),
        func.count().label('views'),
        func.count(func.distinct(PageView.session_id)).label('sessies')
    ).filter(PageView.created_at >= cutoff) \
     .group_by(cast(PageView.created_at, Date)) \
     .order_by(cast(PageView.created_at, Date)).all()

    # Top pagina's
    top_pages = db.session.query(
        PageView.page,
        func.count().label('views')
    ).filter(PageView.created_at >= cutoff) \
     .group_by(PageView.page) \
     .order_by(func.count().desc()).limit(20).all()

    # Referrers (alleen extern)
    referrers = db.session.query(
        PageView.referrer,
        func.count().label('views')
    ).filter(PageView.created_at >= cutoff, PageView.referrer != '') \
     .group_by(PageView.referrer) \
     .order_by(func.count().desc()).limit(20).all()

    # Apparaten
    total = PageView.query.filter(PageView.created_at >= cutoff).count()
    mobile = PageView.query.filter(PageView.created_at >= cutoff, PageView.is_mobile == True).count()

    # Totalen
    total_all = PageView.query.count()
    sessions_all = db.session.query(func.count(func.distinct(PageView.session_id))).scalar() or 0

    return jsonify({
        'daily': [{'dag': str(d.dag), 'views': d.views, 'sessies': d.sessies} for d in daily],
        'top_pages': [{'page': p.page, 'views': p.views} for p in top_pages],
        'referrers': [{'ref': r.referrer, 'views': r.views} for r in referrers],
        'devices': {'total': total, 'mobile': mobile, 'desktop': total - mobile},
        'totals': {'views': total_all, 'sessions': sessions_all}
    })


# ============ ERROR HANDLERS ============

@app.errorhandler(429)
def ratelimit_handler(e):
    return jsonify({'error': 'Te veel verzoeken. Probeer later opnieuw.'}), 429


@app.errorhandler(404)
def not_found(e):
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Niet gevonden'}), 404
    return send_from_directory(FRONTEND_DIR, 'index.html')


@app.errorhandler(500)
def server_error(e):
    return jsonify({'error': 'Interne serverfout'}), 500


# ============ RUN ============

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, host='0.0.0.0', port=5000)
