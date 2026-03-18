# Meldpunt Ambtenaren

Progressive Web App (PWA) voor het melden en documenteren van incidenten met ambtenaren. Bevat dossier-management, document upload met anonimisering, en een EHRM-wizard voor internationale klachtprocedures.

## Features

- Incidentmeldingen aanmaken en beheren
- Dossier-management met documentatie
- Document upload met automatische anonimisering
- EHRM wizard (Europees Hof voor de Rechten van de Mens)
- Analytics dashboard
- Offline-first (PWA met Service Worker)
- Supabase backend integratie

## Starten

### Frontend (PWA)
Open `index.html` in de browser, of gebruik een lokale server:
```bash
npx serve -p 8090
```

### Backend
```bash
cd backend
pip install -r requirements.txt
python app.py
```

## Projectstructuur

| Bestand/Map | Functie |
|-------------|---------|
| `index.html` | Hoofd PWA applicatie |
| `analytics.html` | Analytics dashboard |
| `sw.js` | Service Worker voor offline functionaliteit |
| `backend/` | Python backend (Flask + SQLite/Supabase) |
| `supabase-setup.sql` | Database schema voor Supabase |
| `deploy.sh` | Deployment script |

## Branch-strategie

| Branch | Doel |
|--------|------|
| `main` | Stabiele versie |
| `develop` | Actieve ontwikkeling |
| `feature/*` | Nieuwe functionaliteit (vanuit develop) |

Werk altijd op `develop` of een `feature/*` branch. Merge naar `main` als het stabiel is.
