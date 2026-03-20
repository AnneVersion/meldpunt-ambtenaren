# Meldpunt Ambtenaren - Claude Code Instructies

## Project
PWA voor incidentmeldingen en dossier-management met Supabase backend.
Locatie: `E:\scripts\webscraper\CBSbuurt\meldpunt-ambtenaren\`
GitHub: AnneVersion/meldpunt-ambtenaren
GitHub Pages: anneversion.github.io/meldpunt-ambtenaren

## Starten
```bash
# Frontend
npx serve -p 8090
# → http://localhost:8090

# Backend
cd backend && python app.py
```

## Branch-strategie
- **main** = stabiel/productie
- **develop** = dagelijkse ontwikkeling (standaard werkbranch)
- **feature/*** = nieuwe features, maak aan vanuit develop

Werk op `develop`. Alleen mergen naar `main` als het stabiel is.

## Architectuur
- `index.html` - Volledige PWA frontend (~622KB, alles in 1 bestand)
- `analytics.html` - Analytics dashboard
- `sw.js` - Service Worker voor offline support
- `backend/app.py` - Flask backend API
- `supabase-setup.sql` - Database schema

## Features (maart 2026)
- PWA met Supabase backend
- Dossier-management met document upload + anonimisering
- EHRM wizard voor internationale klachtprocedures
- Max sanctie badges in formulier en detail pagina's
- Analytics dashboard

## Let op
- `data/`, `sync/`, `worker/` staan in .gitignore
- `.claude/` staat in .gitignore
- Database (`meldpunt.db`) staat in .gitignore
- Private keys (*.pem) staan in .gitignore
