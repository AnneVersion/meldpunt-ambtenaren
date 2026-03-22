# Meldpunt Ambtenaren - Claude Code Instructies

## Project
PWA voor incidentmeldingen en dossier-management met Supabase backend.

- **Locatie**: `E:\scripts\webscraper\CBSbuurt\meldpunt-ambtenaren\`
- **URL**: `http://localhost:8090`
- **GitHub**: AnneVersion/meldpunt-ambtenaren
- **GitHub Pages**: anneversion.github.io/meldpunt-ambtenaren

## Startup Checklist
1. Start de static file server:
   ```bash
   python serve.py  # http://localhost:8090
   ```
2. (Optioneel) Start de Flask backend:
   ```bash
   cd backend && python app.py
   ```
3. Controleer:
   - [ ] Server start zonder errors op port 8090
   - [ ] `http://localhost:8090/` laadt index.html (PWA)
   - [ ] `http://localhost:8090/analytics.html` laadt analytics dashboard
   - [ ] Service Worker registreert correct (check console)
   - [ ] Navigatie en dossier-management werken
   - [ ] EHRM wizard laadt correct

## Branch-strategie
- **main** = stabiel/productie
- **develop** = dagelijkse ontwikkeling (standaard werkbranch)
- **feature/*** = nieuwe features, maak aan vanuit develop

Werk op `develop`. Alleen mergen naar `main` als het stabiel is.

## Architectuur
### Frontend
| Bestand | Functie |
|---------|---------|
| `index.html` | Volledige PWA frontend (~622KB, alles in 1 bestand) |
| `analytics.html` | Analytics dashboard |
| `decrypt.html` | Decryptie hulppagina |
| `sw.js` | Service Worker voor offline support |
| `manifest.json` | PWA manifest |

### Backend
| Bestand | Functie |
|---------|---------|
| `backend/app.py` | Flask backend API |
| `backend/config.py` | Backend configuratie |
| `backend/models.py` | Database modellen |
| `backend/migrate.py` | Database migraties |
| `backend/requirements.txt` | Python dependencies |
| `supabase-setup.sql` | Supabase database schema |

### Overig
| Map/Bestand | Functie |
|-------------|---------|
| `serve.py` | Simpele HTTP server op port 8090 (CORS headers) |
| `deploy.sh` | Deployment script |
| `img/` | Afbeeldingen |
| `nginx/` | Nginx configuratie |

## Features (maart 2026)
- PWA met Supabase backend
- Dossier-management met document upload en anonimisering
- EHRM wizard voor internationale klachtprocedures
- Max sanctie badges in formulier en detail pagina's
- Analytics dashboard
- Offline support via Service Worker

## Let op
- `serve.py` is een simpele static file server (geen Flask, geen Supabase)
- De volledige frontend zit in 1 bestand: `index.html` (~622KB)
- Backend database (`meldpunt.db`) staat in .gitignore
- `.gitignore`: `*.pem`, `private_key*`, `backend/__pycache__/`, `backend/meldpunt.db`, `data/`, `sync/`, `worker/`, `.claude/`
