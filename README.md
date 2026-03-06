# financial-acquisition-analysis

Workspace pour analyser des opportunites d'acquisition a partir de sources publiques.

## Structure

- `backend/` : API FastAPI et pipeline d'analyse (OpenAI + collecte de documents).
- `frontend/` : interface web (Vite + React + TypeScript).

## Demarrage rapide

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

Variables minimales :

```bash
export OPENAI_API_KEY="..."
export OPENAI_MODEL="gpt-5"
```

Lancer l'API :

```bash
uvicorn ma_mna_analyzer.api:app --reload
```

Documentation detaillee : `backend/README.md`

### Frontend

```bash
cd frontend
npm install
npm run dev
```

## Deploiement

Des templates prets a copier sont disponibles dans `backend/deploy/` :
- systemd
- Docker Compose (remote image, local build, dev)
- Kubernetes

Voir `backend/deploy/README.md` pour les commandes.
