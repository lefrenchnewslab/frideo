"""
Shared D7 term lists and distancing patterns.

Single source of truth for all D7 scoring code.
Imported by: d7_score.py

Term groups are defined here as grouped dicts (for sensitivity experiments)
and also as flat TERMS dict (for the main scorer).

Any update to term lists, distancing prefixes, or critique vocabulary
must be made here only.
"""

import re

# ── Left-ideology term groups ──────────────────────────────────────────────────
LEFT_TERM_GROUPS = {
    "left_policing": [
        r"\bviolences? policières?\b",
        r"\bbavure[s]? policières?\b",
        r"\bimpunit[eé] policière\b",
    ],
    "left_class": [
        r"\bultra.riches?\b",
        r"\bcapitalisme (financier|sauvage|mondialisé|néolibéral)\b",
        r"\blutte des classes\b",
        r"\bexploitation (des travailleurs|patronale|salariale)\b",
        r"\bnéolibéralisme?\b",
        r"\bultralibéral",
        r"\bjustice sociale\b",
    ],
    "left_gender_race": [
        r"\bféminicide[s]?\b",
        r"\bviolences? (sexistes?|sexuelles? et de genre)\b",
        r"\bpatriarca[lt]\b",
        r"\bdiscriminations? (raciales?|systémiques?|structurelles?)\b",
        r"\bintersectionnalit",
        r"\bracisme (d'[EÉée]tat|systémique|structurel)\b",
    ],
    "left_migration": [
        r"\baccueil des (réfugiés?|migrants?|exilés?)\b",
        r"\bsolidarité (internationale|avec les migrants?|avec les réfugiés?)\b",
    ],
    "left_climate": [
        r"\burgence climatique\b",
        r"\bcrise climatique\b",
    ],
}

# ── Right-ideology term groups ─────────────────────────────────────────────────
RIGHT_TERM_GROUPS = {
    "right_security": [
        # 'émeutiers' removed in v2 (2026-06-12): neutral-saturation / event-contamination.
        # Highest-volume right term (504 firings) but semantically neutral ("rioters");
        # mass-fired by factual coverage of the May-2024 Nouvelle-Calédonie riots, inflating
        # coverage-heavy wire outlets. Removal improves D7 vs held-out MBFC (ρ 0.807→0.886,
        # +0.079) and vs the full model (ρ 0.814→0.884). See REJECTED appendix / D7_CHANGELOG.
        r"\bviolences? (urbaines?|de rue)\b",
        r"\bensauvagement\b",
        r"\binsécurit[eé] (?!alimentaire|sociale|économique|sanitaire|énergétique|juridique|hydrique)",
    ],
    "right_migration": [
        r"\binvasion (migratoire|de migrants|étrangère)\b",
        r"\bsubmersion (migratoire|démographique)\b",
        r"\bimmigration (massive|incontrôlée|illégale|clandestine|sauvage)\b",
        r"\bremigration\b",
    ],
    "right_identity": [
        r"\bidentit[eé] civilisationnelle\b",
        r"\bdécivilisation\b",
        r"\bgrand remplacement\b",
    ],
    "right_antiwoke": [
        r"\bwokisme?\b",
        r"\bislamo.gauchisme?\b",
    ],
    "right_economic": [
        r"\bassistana[t]\b",
        r"\bfardeau fiscal\b",
        r"\bcharges? sociales? (excessives?|trop lourdes?)\b",
    ],
}

# ── Flat TERMS dict (for main scorer) ─────────────────────────────────────────
TERMS = {
    "left": [p for g in LEFT_TERM_GROUPS.values() for p in g],
    "right": [p for g in RIGHT_TERM_GROUPS.values() for p in g],
}

COMPILED = {
    group: [re.compile(p, re.IGNORECASE) for p in patterns]
    for group, patterns in TERMS.items()
}

# ── Distancing patterns (endorsed scoring) ────────────────────────────────────

DIST_GUILLEMET_RE = re.compile(
    r'«[^»]{0,100}(?:'
    + '|'.join(re.escape(p) for p in [
        'grand remplacement', 'ensauvagement', 'wokisme', 'islamo-gauchisme',
        'décivilisation', 'submersion', 'immigration', 'insécurit', 'émeutiers',
        'violences urbaines', 'rémigration',
    ])
    + r')[^»]{0,100}»',
    re.IGNORECASE,
)

DIST_PREFIX_RE = re.compile(
    r'\b(théorie (du|de la?|des?)'
    r'|fantasme (du|de|des?)'
    r'|mythe (du|de|des?)'
    r'|prétend[ue]?[ent]?'
    r'|soi-disant'
    r'|fantasmagorie'
    r'|obsession (du|de|pour)'
    r'|ce (que|qu\')[\w\s]{1,25}(appelle|nomme|désigne|appellent|nomment)'
    r'|adeptes? (du|de la?)'
    r'|partisans? (du|de la?)'
    r'|apôtres? (du|de la?)'
    r'|matraquage)\b',
    re.IGNORECASE,
)

DIST_CRITIQUE_RE = re.compile(
    r'\b(complotiste|théorie conspirationniste|idéologie d\'extrême.droite'
    r'|fantasmagorie|raciste|positions xénophobes'
    r'|dénonce[rnt]* (cette|ce|le|la|les)'
    r'|réfute[rnt]*|invalide[rnt]*)\b',
    re.IGNORECASE,
)

# Legacy aliases so existing code that references _DIST_*_RE still works
DIST_LEFT_CRITIQUE_RE = re.compile(
    r'\b(soi.disant'
    r'|prétend[ue]?[ent]?'
    r'|supposé[ée]?[s]?'
    r'|mirage[s]?'
    r'|imaginaire[s]?'
    r'|mythe (du|de la?|des?)'
    r'|délire'
    r'|lubie'
    r'|victimaire'
    r'|idéologie woke'
    r'|essentialis[ea]'
    r'|caricatur[ea]'
    r'|instrumentalis[ea]'
    r'|exagér[ea])\b',
    re.IGNORECASE,
)

# ── Attribution signals for same-sentence speaker/quote detection ────────────
DIST_ATTRIBUTION_RE = re.compile(
    r'\b('
    r'déclar[ée]|déclare|déclarent|déclarait|déclarera'
    r'|affirm[ée]|affirme|affirment'
    r'|interpell[ée]|interpelle|interpellent'
    r'|estim[ée]|estime|estiment'
    r'|expliqu[ée]|explique|expliquent'
    r'|soulign[ée]|souligne|soulignent'
    r'|indiqu[ée]|indique|indiquent'
    r'|ajout[ée]|ajoute|ajoutent'
    r'|annonc[ée]|annonce|annoncent'
    r'|reconn[ue]?|reconnaît|reconnaissent'
    r'|concéd[ée]|concède|concèdent'
    r'|lanc[ée]|lance|lancent'
    r'|promis|promet|promettent'
    r'|assur[ée]|assure|assurent'
    r'|jur[ée]|jure|jurent'
    r'|renchéri|renchérit'
    r'|object[ée]|objecte|objectent'
    r'|rétorqu[ée]|rétorque|rétorquent'
    r'|dénon[cç][ée]|dénonce|dénoncent'
    r'|critiqu[ée]|critique|critiquent'
    r'|comment[ée]|commente|commentent'
    r'|révél[ée]|révèle|révèlent'
    r'|mentionn[ée]|mentionne|mentionnent'
    r'|confi[ée]|confie|confient'
    r'|poursuiv[ie]|poursuit|poursuivent'
    r'|plaide|plaident'
    r'|note|notent'
    r'|précise|précisent'
    r'|dit|disent|écrit|écrivent'
    r'|considère|considèrent'
    r'|rappelle|rappellent'
    r'|qualifiant|qualifi[ée]|qualifier'
    r'|préconise|préconisent'
    r'|hurle|hurlent'
    r"|d'ajouter"
    r'|a[- ]t[- ]il|a[- ]t[- ]elle|a[- ]t[- ]elles|a[- ]t[- ]ils'
    r'|selon\b|d\'après\s'
    r'|déclaration|propos|discours|communiqué|tribune'
    r')\b',
    re.IGNORECASE,
)

# Legacy aliases so existing code that references _DIST_*_RE still works
_DIST_GUILLEMET_RE = DIST_GUILLEMET_RE
_DIST_PREFIX_RE = DIST_PREFIX_RE
_DIST_CRITIQUE_RE = DIST_CRITIQUE_RE
_DIST_LEFT_CRITIQUE_RE = DIST_LEFT_CRITIQUE_RE
_DIST_ATTRIBUTION_RE = DIST_ATTRIBUTION_RE
