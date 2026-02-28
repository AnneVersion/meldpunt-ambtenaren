"""
Meldpunt Ambtenaren — Database Modellen (SQLAlchemy)
"""
from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Melding(db.Model):
    __tablename__ = 'meldingen'

    id = db.Column(db.String(100), primary_key=True)
    claim_code = db.Column(db.String(20), unique=True, nullable=False, index=True)
    titel = db.Column(db.Text, nullable=False, default='')
    verhaal = db.Column(db.Text, default='')
    instantie = db.Column(db.String(200), default='')
    namen = db.Column(db.JSON, default=list)       # [{naam, functie, foto}]
    bronnen = db.Column(db.JSON, default=list)      # [{t, u}]
    anoniem = db.Column(db.Boolean, default=True)
    melder_naam = db.Column(db.String(200), nullable=True)
    melder_email = db.Column(db.String(200), nullable=True)
    klokkenluider = db.Column(db.Boolean, default=False)
    status = db.Column(db.String(20), default='review', index=True)  # review | live | rejected
    views = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))

    reacties = db.relationship('Reactie', backref='melding', lazy='dynamic',
                               cascade='all, delete-orphan')

    def to_dict(self, include_private=False):
        """Serialiseer naar dict. include_private=True voor admin/claim."""
        d = {
            'id': self.id,
            'titel': self.titel,
            'verhaal': self.verhaal,
            'instantie': self.instantie,
            'namen': self.namen or [],
            'bronnen': self.bronnen or [],
            'anoniem': self.anoniem,
            'klokkenluider': self.klokkenluider,
            'status': self.status,
            'views': self.views,
            'ts': int(self.created_at.timestamp() * 1000) if self.created_at else 0,
            'reacties_count': self.reacties.count()
        }
        if include_private:
            d['claimCode'] = self.claim_code
            d['melder_naam'] = self.melder_naam
            d['melder_email'] = self.melder_email
            d['updated_at'] = self.updated_at.isoformat() if self.updated_at else None
        if not self.anoniem:
            d['melder_naam'] = self.melder_naam
        return d


class Reactie(db.Model):
    __tablename__ = 'reacties'

    id = db.Column(db.String(100), primary_key=True)
    melding_id = db.Column(db.String(100), db.ForeignKey('meldingen.id', ondelete='CASCADE'),
                           nullable=False, index=True)
    naam = db.Column(db.String(200), default='Anoniem')
    tekst = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            'id': self.id,
            'mid': self.melding_id,
            'naam': self.naam,
            'tekst': self.tekst,
            'ts': int(self.created_at.timestamp() * 1000) if self.created_at else 0
        }


class Ambtenaar(db.Model):
    __tablename__ = 'ambtenaren'

    id = db.Column(db.String(100), primary_key=True)
    email = db.Column(db.String(200))
    naam = db.Column(db.String(200))
    organisatie = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            'id': self.id,
            'email': self.email,
            'naam': self.naam,
            'organisatie': self.organisatie,
            'ts': int(self.created_at.timestamp() * 1000) if self.created_at else 0
        }


class AdminUser(db.Model):
    __tablename__ = 'admin_users'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))


class PageView(db.Model):
    __tablename__ = 'pageviews'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    page = db.Column(db.String(100), nullable=False, index=True)
    referrer = db.Column(db.String(500), default='')
    session_id = db.Column(db.String(50), default='', index=True)
    screen_w = db.Column(db.Integer)
    screen_h = db.Column(db.Integer)
    is_mobile = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
