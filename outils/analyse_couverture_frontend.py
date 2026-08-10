import json
from pathlib import Path

ROOT = Path('/home/ubuntu/pharmapp_work/pharmapp/apps/poste-client')
source = ROOT / 'coverage' / 'coverage-summary.json'
out = ROOT.parent.parent / 'artifacts' / 'revision-2026-08-07' / 'COUVERTURE_FRONTEND_PRIORITES.md'

data = json.loads(source.read_text())
rows = []
for path, metrics in data.items():
    if path == 'total' or not path.endswith(('.ts', '.tsx')):
        continue
    rel = Path(path).relative_to(ROOT).as_posix()
    if '/test' in rel or rel.endswith('.test.ts') or rel.endswith('.test.tsx'):
        continue
    lines = metrics['lines']
    funcs = metrics['functions']
    branches = metrics['branches']
    uncovered_lines = lines['total'] - lines['covered']
    uncovered_funcs = funcs['total'] - funcs['covered']
    uncovered_branches = branches['total'] - branches['covered']
    score = uncovered_lines * 1.0 + uncovered_funcs * 2.0 + uncovered_branches * 0.5
    if rel.startswith('src/components/ui/'):
        family = 'primitive UI'
    elif rel.startswith('src/screens/') or rel.startswith('src/routes/'):
        family = 'écran / route métier'
    elif rel.startswith('src/lib/') or rel.startswith('src/hooks/'):
        family = 'infrastructure frontend'
    else:
        family = 'shell / composant métier'
    rows.append((score, rel, family, lines, funcs, branches, uncovered_lines, uncovered_funcs, uncovered_branches))
rows.sort(reverse=True)

business = [r for r in rows if r[2] != 'primitive UI']
ui = [r for r in rows if r[2] == 'primitive UI']
total = data.get('total', {})

lines = []
lines.append('# Priorisation technique de la couverture frontend')
lines.append('')
lines.append('Analyse générée depuis le rapport Istanbul `coverage/coverage-summary.json`, avec `coverage.all` actif et dénominateur statique.')
lines.append('')
lines.append('## Situation globale')
lines.append('')
lines.append('| Dimension | Couvert | Total | Taux |')
lines.append('|---|---:|---:|---:|')
for key, label in [('statements', 'Statements'), ('lines', 'Lignes'), ('functions', 'Fonctions'), ('branches', 'Branches')]:
    m = total[key]
    lines.append(f"| {label} | {m['covered']} | {m['total']} | {m['pct']} % |")
lines.append('')
lines.append('## Priorité immédiate : métier et infrastructure')
lines.append('')
lines.append('Le score de rendement combine les lignes non couvertes, les fonctions non couvertes et les branches non couvertes. Les fonctions et branches reçoivent un poids supérieur car elles reflètent davantage la logique métier et les chemins d’erreur.')
lines.append('')
lines.append('| Rang | Fichier | Famille | Lignes | Fonctions | Branches | Score rendement |')
lines.append('|---:|---|---|---:|---:|---:|---:|')
for i, r in enumerate(business[:20], 1):
    _, rel, family, l, f, b, ul, uf, ub = r
    lines.append(f'| {i} | `{rel}` | {family} | {ul}/{l["total"]} non couvertes | {uf}/{f["total"]} non couvertes | {ub}/{b["total"]} non couvertes | {r[0]:.1f} |')
lines.append('')
lines.append('## Tranches recommandées')
lines.append('')
lines.append('| Tranche | Cible | Justification |')
lines.append('|---|---|---|')
lines.append('| A | `src/lib/api-client.ts` et hooks associés | Point transversal : erreurs HTTP, session, cookies, retries et contrats API. Un test couvre plusieurs écrans indirectement. |')
lines.append('| B | `src/screens/ScreenAchats.tsx` et routes achats | Écran très peu couvert avec logique de commandes, réception, erreurs et états de chargement. |')
lines.append('| C | `src/screens/ScreenClients.tsx` | CRUD, recherche, crédit, assurance, anonymisation et permissions. |')
lines.append('| D | `src/screens/ScreenParametres.tsx` et `ScreenUtilisateurs.tsx` | Formulaires et branches RBAC à fort volume de fonctions non exercées. |')
lines.append('| E | `src/routes/_app.index.tsx`, `src/routes/_app.*` | Assemblage, redirections et intégration réelle des écrans. |')
lines.append('| F | Dialogues POS, ordonnance, impression et composants métier | Compléter les branches de paiement, ordonnance, reçu et avoir après les services transversaux. |')
lines.append('')
lines.append('## À traiter en dernier')
lines.append('')
lines.append('Les primitives UI générées par le kit de composants sont nombreuses mais ont un rendement métier faible. Elles doivent être testées uniquement lorsqu’elles portent une logique locale non triviale, comme pagination, select, menu, formulaire ou dialogue. Il ne faut pas remplir la couverture avec des tests superficiels de wrappers sans comportement applicatif.')
lines.append('')
lines.append('| Fichier UI | Lignes non couvertes | Fonctions non couvertes | Branches non couvertes |')
lines.append('|---|---:|---:|---:|')
for r in ui[:12]:
    _, rel, _, l, f, b, ul, uf, ub = r
    lines.append(f'| `{rel}` | {ul}/{l["total"]} | {uf}/{f["total"]} | {ub}/{b["total"]} |')
lines.append('')
lines.append('## Décision de planification')
lines.append('')
lines.append('La prochaine tranche doit commencer par `api-client.ts`, puis enchaîner sur Achats et Clients. Chaque tranche devra produire des tests d’intégration sur l’implémentation réelle, relancer Istanbul, comparer le delta absolu et conserver le rapport avant de passer à la suivante.')
lines.append('')
lines.append('## Référence locale')
lines.append('')
lines.append(f'- Rapport source : `{source}`')

out.parent.mkdir(parents=True, exist_ok=True)
out.write_text('\n'.join(lines) + '\n')
print(out)
print(f'business_files={len(business)} ui_files={len(ui)}')
print('top5=')
for r in business[:5]:
    print(r[1], round(r[0], 1))
