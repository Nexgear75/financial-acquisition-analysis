# ma-mna-analyzer

Backend Python pour automatiser une analyse d'opportunité d'acquisition entre deux sociétés cotées en Europe à partir de documents publics, avec FastAPI et l'API OpenAI.

## Ce que fait le module

Le pipeline exécute cinq étapes :

1. **Découverte des sources publiques**
   - recherche du site officiel et de la page Investor Relations,
   - collecte heuristique de PDF et de pages HTML utiles,
   - priorité donnée aux documents officiels.

2. **Téléchargement des documents**
   - cache local des PDF,
   - récupération d'extraits textuels sur les pages HTML pertinentes.

3. **Upload vers l'API OpenAI**
   - envoi des PDF via `files.create(..., purpose="user_data")`.

4. **Extraction structurée des faits par société**
   - chiffre d'affaires,
   - EBITDA,
   - EBIT,
   - dette,
   - trésorerie,
   - FCF,
   - segments,
   - géographies,
   - risques,
   - structure actionnariale,
   - table des sources.

5. **Génération du rapport M&A final**
   - thèse stratégique,
   - valorisation,
   - synergies,
   - deal math,
   - contraintes réglementaires,
   - red flags,
   - verdict final.

## Pourquoi cette architecture

### 1. Source de données choisie

Le module prend pour **source primaire** :
- rapports annuels,
- documents d'enregistrement universel,
- communiqués de résultats,
- présentations investisseurs,
- autres publications publiques disponibles sur les sites IR officiels.

Le choix est volontaire : ce sont les sources les plus auditables, les plus stables juridiquement, et les moins contaminées par les reformulations de tiers.

### 2. Modélisation du rapport de compte

Le module extrait une structure normalisée comprenant notamment :
- `historical_metrics[]`
- `latest_snapshot`
- `segments`
- `geographies`
- `key_risks`
- `shareholding_notes`
- `capital_structure_notes`
- `source_table`

### 3. Prompt à trous

Le prompt final est généré dynamiquement à partir :
- des deux sociétés,
- du manifeste des sources,
- des extractions structurées intermédiaires,
- de paramètres d'analyse (`years`, `language`, `perspective`, `prudence_level`).

## Limites importantes

Ce module est un **MVP sérieux**, pas un système institutionnel définitif.

Les principaux points à connaître :
- la découverte automatique des sites IR reste heuristique ;
- certains PDF scannés ou protégés peuvent être mal exploités ;
- les sociétés avec sites multi-domaines ou archives IR externalisées peuvent nécessiter `official_website`, `investor_relations_url` ou `extra_document_urls` ;
- pour un usage production, il faut ajouter une vraie couche d'observabilité, une file de jobs, une politique de retry plus fine, des garde-fous SSRF renforcés et idéalement des adaptateurs par place de cotation / régulateur.

## Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

Variables d'environnement minimales :

```bash
export OPENAI_API_KEY="..."
export OPENAI_MODEL="gpt-5"
# optionnel
export OPENAI_EXTRACTION_MODEL="gpt-5"
```

## Deploiement production (secret management)

En production, la cle API OpenAI doit etre injectee au runtime via un gestionnaire de secrets.
Ne stocke jamais de secret dans le repo ni dans l'image Docker.

Variables runtime recommandees :

```bash
export APP_ENV="production"
export OPENAI_API_KEY="..."
export OPENAI_MODEL="gpt-5"
export OPENAI_EXTRACTION_MODEL="gpt-5"
```

Comportement du backend :
- en `APP_ENV=production`, le backend ne charge pas de fichier `.env` local ;
- si `OPENAI_API_KEY` est absent, l'application echoue au demarrage (fail-fast).

Exemple Docker (sans secret dans l'image) :

```bash
docker run --rm -p 8000:8000 \
   -e APP_ENV=production \
   -e OPENAI_API_KEY="$OPENAI_API_KEY" \
   -e OPENAI_MODEL=gpt-5 \
   your-backend-image
```

Templates prets a copier :
- `deploy/systemd/ma-mna-analyzer.service`
- `deploy/compose/docker-compose.prod.yml`
- `deploy/k8s/deployment.yaml`
- guide d'usage: `deploy/README.md`

## Lancer l'API

```bash
uvicorn ma_mna_analyzer.api:app --reload
```

Health check :

```bash
curl http://localhost:8000/healthz
```

## Endpoint principal

### `POST /analyze`

Exemple de payload :

```json
{
  "acquirer": {
    "name": "Schneider Electric",
    "country": "France",
    "ticker": "SU",
    "official_website": "https://www.se.com",
    "investor_relations_url": "https://www.se.com/ww/en/about-us/investor-relations/"
  },
  "target": {
    "name": "Legrand",
    "country": "France",
    "ticker": "LR",
    "official_website": "https://www.legrandgroup.com",
    "investor_relations_url": "https://www.legrandgroup.com/en/investors"
  },
  "language": "fr",
  "years": 5,
  "allow_openai_web_search": true,
  "strict_official_sources_only": true,
  "perspective": "comité d'investissement",
  "prudence_level": "conservateur"
}
```

Exemple cURL :

```bash
curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d @payload.json
```

## Champs utiles du payload

- `official_website` : très utile pour éviter une mauvaise autodétection.
- `investor_relations_url` : recommandé en production.
- `extra_document_urls` : permet d'injecter des PDF déjà identifiés.
- `extra_page_urls` : permet d'ajouter des communiqués HTML récents.
- `manual_sources_only` : force l'utilisation exclusive des URLs fournies.
- `strict_official_sources_only` : limite les résultats aux domaines officiels détectés.
- `allow_openai_web_search` : permet au modèle de compléter les éléments très récents comme la capitalisation, les dernières publications, ou certains points réglementaires.

## Structure du code

```text
src/ma_mna_analyzer/
├── api.py                # FastAPI app
├── config.py             # paramètres et variables d'environnement
├── discovery.py          # découverte des sources publiques
├── document_fetcher.py   # téléchargement PDF + snippets HTML
├── models.py             # schémas Pydantic
├── openai_service.py     # intégration OpenAI Files + Responses API
├── orchestrator.py       # pipeline complet
├── prompt_builder.py     # prompt d'extraction + prompt d'analyse
└── utils.py              # helpers
```

## Conseils d'usage

Pour un vrai usage analyste / comité :
- passe toujours `official_website` et `investor_relations_url`,
- ajoute les PDF stratégiques via `extra_document_urls`,
- active `strict_official_sources_only`,
- conserve le rapport final mais aussi `acquirer_extraction` et `target_extraction` pour auditabilité.

## Évolutions recommandées

1. **Vector stores / file search** pour portefeuilles documentaires plus volumineux.
2. **Streaming** côté endpoint pour suivre les longues analyses.
3. **Persistence** des `file_id` OpenAI dans une base locale.
4. **Adapters par marché** : Euronext, LSE, Deutsche Börse, SIX, BME, etc.
5. **Quant layer** séparée pour les calculs de multiple, DCF et sensitivities.
6. **Evaluation harness** pour comparer la stabilité des sorties.

