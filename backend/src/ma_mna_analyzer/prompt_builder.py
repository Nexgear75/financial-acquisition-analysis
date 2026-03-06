from __future__ import annotations

import json

from .models import AnalyzeRequest, CompanyDiscoveryBundle, CompanyExtraction, CompanyRequest


def _bundle_manifest(bundle: CompanyDiscoveryBundle) -> list[dict]:
    items: list[dict] = []
    for document in bundle.documents:
        items.append(
            {
                "title": document.title,
                "url": document.url,
                "category": document.category,
                "year": document.year,
                "bytes_size": document.bytes_size,
            }
        )
    for snippet in bundle.web_snippets:
        items.append(
            {
                "title": snippet.title,
                "url": snippet.url,
                "category": snippet.category,
                "year": snippet.year,
                "excerpt": snippet.text_excerpt,
            }
        )
    return items


def build_extraction_prompt(
    *,
    company: CompanyRequest,
    bundle: CompanyDiscoveryBundle,
    years: int,
    language: str,
) -> str:
    schema_example = {
        "company_name": company.name,
        "business_description": "string or null",
        "reporting_currency": "string or null",
        "fiscal_year_end": "string or null",
        "segments": ["segment 1", "segment 2"],
        "geographies": ["country or region"],
        "key_risks": ["risk"],
        "shareholding_notes": ["shareholder structure note"],
        "capital_structure_notes": ["net debt, maturities, covenants, rating note"],
        "historical_metrics": [
            {
                "period": "2025",
                "currency": "EUR",
                "revenue": None,
                "organic_growth_pct": None,
                "ebitda": None,
                "ebit": None,
                "net_income": None,
                "operating_cash_flow": None,
                "capex": None,
                "free_cash_flow": None,
                "cash_and_equivalents": None,
                "gross_debt": None,
                "net_debt": None,
                "shares_outstanding": None,
                "market_cap": None,
                "enterprise_value": None,
                "notes": ["adjustments, IFRS 16, one-offs"],
                "source_refs": ["Annual report 2025 p. 123"]
            }
        ],
        "latest_snapshot": {
            "period": "latest_public",
            "currency": "EUR",
            "revenue": None,
            "organic_growth_pct": None,
            "ebitda": None,
            "ebit": None,
            "net_income": None,
            "operating_cash_flow": None,
            "capex": None,
            "free_cash_flow": None,
            "cash_and_equivalents": None,
            "gross_debt": None,
            "net_debt": None,
            "shares_outstanding": None,
            "market_cap": None,
            "enterprise_value": None,
            "notes": ["latest disclosed snapshot note"],
            "source_refs": ["Q3 2025 results p. 12"]
        },
        "source_table": [
            {
                "id": "S1",
                "document": "Annual report 2025",
                "source_type": "annual_report",
                "date": "2026-02-20",
                "url": "https://...",
                "pages_or_location": "p. 112-118",
                "why_used": "historical P&L and debt"
            }
        ],
        "warnings": ["data gap or ambiguity"]
    }
    manifest_json = json.dumps(_bundle_manifest(bundle), ensure_ascii=False, indent=2)
    return f"""
Tu es un analyste financier buy-side. Ta tâche est d'extraire, pour une seule société cotée,
les faits économiques, financiers et de gouvernance utiles à une analyse M&A.

Entreprise analysée : {company.name}
Pays : {company.country or 'non précisé'}
Ticker : {company.ticker or 'non précisé'}
ISIN : {company.isin or 'non précisé'}
Horizon à couvrir : {years} exercices si l'information existe
Langue de restitution souhaitée : {language}

Règles absolues :
1. Utilise prioritairement les documents fournis en entrée.
2. N'invente jamais un chiffre.
3. Si une donnée n'est pas étayée, mets null.
4. Tous les points importants doivent comporter des source_refs exploitables.
5. Distingue les données publiées des inférences : les inférences doivent rester en notes,
   jamais remplacer une donnée officielle.
6. Si un chiffre dépend manifestement d'un retraitement IFRS 16 ou d'éléments non récurrents,
   mentionne-le dans notes.
7. Tu dois produire UNIQUEMENT un objet JSON valide. Pas de prose, pas de markdown, pas de commentaire.
8. Les montants doivent être des nombres simples, sans séparateur de milliers, et si possible dans la devise de reporting publiée.

Manifest des sources retenues :
{manifest_json}

Structure JSON attendue (garde exactement les clés ; remplace les exemples par des valeurs réelles ou null) :
{json.dumps(schema_example, ensure_ascii=False, indent=2)}
""".strip()


def build_analysis_prompt(
    *,
    request: AnalyzeRequest,
    acquirer_bundle: CompanyDiscoveryBundle,
    target_bundle: CompanyDiscoveryBundle,
    acquirer_extraction: CompanyExtraction,
    target_extraction: CompanyExtraction,
) -> str:
    acquirer_manifest = json.dumps(_bundle_manifest(acquirer_bundle), ensure_ascii=False, indent=2)
    target_manifest = json.dumps(_bundle_manifest(target_bundle), ensure_ascii=False, indent=2)
    acquirer_json = json.dumps(acquirer_extraction.model_dump(), ensure_ascii=False, indent=2)
    target_json = json.dumps(target_extraction.model_dump(), ensure_ascii=False, indent=2)
    web_search_block = (
        "Tu peux utiliser la recherche web intégrée UNIQUEMENT pour les éléments susceptibles d'avoir changé "
        "après les derniers rapports annuels : cours de bourse, capitalisation, EV, dernières publications, "
        "actionnariat récent, dette récente, management actuel, réglementation et actualité transactionnelle."
        if request.allow_openai_web_search
        else "N'utilise pas la recherche web ; travaille uniquement à partir des documents et données fournis."
    )

    return f"""
Agis comme une cellule d'analyse M&A buy-side composée de cinq expertises intégrées :
1) stratégie sectorielle et concurrentielle,
2) finance d'entreprise et valuation,
3) analyse crédit / structure de financement,
4) réglementation boursière européenne / concurrence / gouvernance,
5) intégration post-acquisition.

Mission : évaluer l'opportunité pour {request.acquirer.name} d'acquérir {request.target.name},
deux sociétés cotées en Europe, à partir de documents publics, principalement des rapports annuels,
des présentations investisseurs, des communiqués de résultats et d'autres sources publiques pertinentes.

Contexte :
- Acquéreur : {request.acquirer.name}
- Cible : {request.target.name}
- Perspective : {request.perspective}
- Prudence : {request.prudence_level}
- Période d'analyse : {request.years} exercices + dernière information publique disponible
- Langue de restitution : {request.language}
- {web_search_block}

Règles de preuve :
- Distingue explicitement Faits / Estimations / Inférences / Hypothèses.
- Ne transforme jamais une hypothèse en fait.
- Quand une information manque, dis-le clairement.
- Chaque conclusion importante doit être justifiée par des sources publiques ou par un raisonnement clairement explicité.
- Fais particulièrement attention aux normalisations comptables, aux éléments non récurrents, à l'IFRS 16,
  aux changements de périmètre, aux goodwill impairments, aux passifs cachés et aux risques de cyclicité.
- Ne présume jamais qu'une acquisition est créatrice de valeur simplement parce que le fit sectoriel semble élevé.

Sources et extractions déjà préparées pour l'analyse :

Manifest des sources - acquéreur :
{acquirer_manifest}

Manifest des sources - cible :
{target_manifest}

Extraction structurée - acquéreur :
{acquirer_json}

Extraction structurée - cible :
{target_json}

Questions à traiter impérativement :
A. Portrait économique comparé des deux sociétés.
B. Logique stratégique de l'acquisition.
C. Attractivité intrinsèque de la cible en standalone.
D. Capacité réelle de l'acquéreur à mener l'opération.
E. Synergies, désynergies et coûts d'intégration.
F. Valorisation standalone de la cible.
G. Deal math pour l'acquéreur : prix, prime, structure de financement, leverage pro forma, FCF/BPA/ROIC.
H. Contraintes réglementaires, boursières et de gouvernance en Europe.
I. Risques de thèse et red flags.
J. Scénarios bear / base / bull et verdict final.

Format de sortie imposé en markdown :
1. Résumé exécutif
2. Tableau des sources utilisées
3. Profil comparé de l'acquéreur et de la cible
4. Thèse stratégique de l'opération
5. Analyse de la cible en standalone
6. Capacité de l'acquéreur à exécuter l'opération
7. Synergies, désynergies et coûts d'intégration
8. Valorisation de la cible
9. Deal math et structure de financement
10. Contraintes réglementaires et transactionnelles
11. Red flags et invalidation de la thèse
12. Analyse en scénarios
13. Recommandation finale

Ajoute ensuite trois tableaux de synthèse :
- Scorecard d'opportunité notée sur 100,
- matrice faits / hypothèses / inférences,
- conditions indispensables avant recommandation d'une offre.

Conclusion finale obligatoire :
1) verdict en une phrase,
2) niveau de conviction faible / moyen / élevé,
3) fourchette de prix indicative jugée défendable,
4) trois raisons majeures de faire l'opération,
5) trois raisons majeures de ne pas la faire.

Sois exigeant, analytique, quantitatif et sans banalités.
""".strip()
