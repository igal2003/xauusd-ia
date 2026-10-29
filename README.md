# xauusd-ia

Première version autonome de laboratoire XAUUSD : Python, FastAPI, SQLite et interface web française adaptée au téléphone. **Paper trading uniquement : aucune intégration de courtier et aucun ordre réel.** Aucune clé API nécessaire.

Les prix portent la mention **« Démonstration — données simulées »**. La stratégie de référence compare deux moyennes mobiles ; ce n'est pas une IA entraînée. Ses résultats synthétiques ne constituent pas une évaluation de marché.

## Installation sur macOS

Installer Python 3.12 ou supérieur et Git, puis dans Terminal :

```bash
git clone https://github.com/igal2003/xauusd-ia.git
cd xauusd-ia
git switch feat/technical-analysis-v1
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
set -a
source .env
set +a
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Ouvrir **http://127.0.0.1:8000**. Choisir un profil, puis **Démarrer**. Après 12 cours (environ 12 secondes), la stratégie peut ouvrir une position. Les cours évoluent toutes les secondes par défaut, sans dépendance à ChatGPT. Le tableau de bord se rafraîchit toutes les 1,5 secondes. `Ctrl+C` arrête le serveur.

Pour reprendre ultérieurement :

```bash
cd xauusd-ia
source .venv/bin/activate
set -a
source .env
set +a
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Le mode, les compteurs, le profil et les positions persistent : une simulation en cours reprend automatiquement au redémarrage. Il n'y a pas de reconstruction des cours pendant l'extinction. Mettre en pause avant d'éteindre pour empêcher cette reprise automatique.

Pour accéder depuis le téléphone sur le **même Wi-Fi privé**, lancer avec `--host 0.0.0.0`, puis ouvrir `http://ADRESSE_IP_DU_MAC:8000`. Autoriser si nécessaire l'accès réseau local dans macOS. Cette V1 n'a pas d'authentification : chaque personne ayant accès au serveur peut piloter la simulation. Ne pas l'exposer directement à Internet.

## Commandes et profils

- **Démarrer** : avance les données et active la gestion des positions.
- **Mettre en pause** : suspend les données et toute gestion, stops compris ; conserve les positions.
- **Arrêter et clôturer** : demande la liquidation au prochain cours frais, puis cesse la génération. Si le fournisseur ne donne pas de cours frais, l'arrêt reste en attente.
- Changer de profil nécessite une simulation hors marche et aucune position ouverte. Arrêter d'abord, attendre la clôture, sélectionner le profil, puis démarrer.

| Profil | Risque par position | Perte quotidienne | Positions maximum | Stop USD/oz | Objectif |
|---|---:|---:|---:|---:|---:|
| Prudent | 0,25 % | 1 % | 1 | 8 | 1,5 × stop |
| Équilibré | 0,5 % | 2 % | 2 | 10 | 1,5 × stop |
| Dynamique | 1 % | 3 % | 3 | 12 | 1,5 × stop |

Paramètres visibles dans l'interface et archivés à chaque décision. Les profils sont des constantes du code ; aucune proposition de modèle ne peut les modifier.

## Modèle d'exécution et de risque

- Capital initial : **10 000 USD**. Prix en **USD par once troy**, quantités en **onces troy**, arrondies vers le bas au millième. Aucune conversion implicite en lots courtier.
- Un cours est un midpoint. Achat au midpoint + demi-spread + slippage ; vente au midpoint − demi-spread − slippage. Même convention à la sortie ; coûts appliqués une seule fois par exécution. P&L = `(sortie − entrée) × sens × onces`.
- Taille = minimum du budget de risque / (distance du stop + slippage de sortie) et du capital disponible / prix d'entrée. Notionnel agrégé limité au capital disponible sans levier. Solde = capital + P&L réalisés ; valeur totale = solde + P&L latent au prix de liquidation estimé.
- Stop et objectif définis depuis le prix exécuté, déclenchés sur le bid pour les achats et l'ask pour les ventes. Exécution au prochain cours observé avec slippage : **un saut de prix peut dépasser le risque prévu**, il n'y a pas de garantie de stop.
- Le budget quotidien se fonde sur la valeur du portefeuille au changement de date UTC (dernier cours connu avant le premier tick du jour). Les P&L latents comptent. Le risque déjà réservé aux positions réduit le budget des nouvelles entrées. Si la limite est atteinte : liquidation et verrouillage des nouvelles entrées jusqu'au jour UTC suivant, même après une reprise.
- Cours absent, non fini, futur ou âgé de plus de 15 secondes : aucun traitement de position ni ouverture. Refus conservé dans les événements. Les stops ne peuvent pas être exécutés sans cours valide.
- Identifiants de cours et de décisions uniques, transaction SQLite `BEGIN IMMEDIATE`, une position maximum par cours et verrou de processus pour une base : protection contre doublons et concurrence. Lancer **un seul worker Uvicorn**, sans `--reload`.
- Drawdown maximum calculé à chaque cours après exécution, depuis le plus haut de la valeur totale. Pas de frais de financement, swaps, commissions supplémentaires, carnet d'ordres ou liquidité dans cette V1.

Stratégie `sma-4-12-v1` : chauffe sur 12 observations, achat si moyenne des 4 derniers cours > moyenne des 12, vente sinon ; nouvelles entrées possibles jusqu'à la limite du profil. Elle sert à vérifier la chaîne complète. L'index détermine le prix synthétique de manière reproductible ; les horodatages de réception utilisent l'heure UTC réelle. Le rythme est celui d'une démonstration accélérée.

## Configuration et mémoire

`.env` n'est pas chargé implicitement : utiliser les commandes `set -a / source / set +a` ci-dessus. Ne jamais y enregistrer un secret dans Git.

| Variable | Défaut | Usage |
|---|---|---|
| `XAU_DB_PATH` | `data/simulation.sqlite3` | Base SQLite persistante |
| `XAU_SPREAD` | `0.6` | Spread total USD/oz |
| `XAU_SLIPPAGE` | `0.1` | Slippage défavorable par exécution USD/oz |
| `XAU_INTERVAL` | `1` | Secondes entre cours (minimum 0,1) |

Pour une nouvelle expérience, arrêter le serveur et utiliser un autre `XAU_DB_PATH`. Les coûts sont figés pour chaque base ; un changement de spread/slippage exige une nouvelle base. L'index synthétique, les cours, signaux, motifs, paramètres, résultats et événements restent enregistrés sans limite de conservation. L'interface présente les 300 derniers cours, 100 décisions/trades et 50 événements ; l'archive complète reste dans SQLite.

Sauvegarder après arrêt du serveur en copiant le dossier `data/`. Ne pas copier seulement le fichier SQLite pendant l'exécution (mode WAL). Les fichiers de données sont exclus de Git. Une synchronisation Git Cloud → Mac ne transfère donc pas le portefeuille ; transférer la sauvegarde séparément si nécessaire. Une base contenant des données de marché devra rester distincte des expériences synthétiques.

## Vérification

```bash
python -m unittest discover -s tests -v
python -m compileall -q app tests
```

Les tests couvrent tailles, P&L long/short avec coûts, fraîcheur, limites, stops/objectifs, arrêt, doublons et persistance. Le test API effectue un parcours sans clé via le vrai cycle de vie FastAPI et une base temporaire. Il est explicitement ignoré si l'environnement interdit les sockets nécessaires à asyncio. La CI GitHub Actions relance la suite sur Python 3.12 et 3.13. Un résultat de CI doit être consulté ; sa présence ne garantit pas qu'elle est passée.

## Architecture et suite

`app/engine.py` : risque, portefeuille, fournisseur synthétique et mémoire SQLite. `app/main.py` : serveur, API et boucle autonome. `app/static/` : interface sans CDN ni dépendance JavaScript. `app/extensions.py` : contrats pour veille sourcée/datée, analyse textuelle, synthèses et résultats d'évaluation ; `PriceProvider` prépare les cours interchangeables. Les modules IA, veille et synthèse sont **désactivés**, aucune connexion n'est simulée.

Voir [PROJECT_STATUS.md](PROJECT_STATUS.md), [ROADMAP.md](ROADMAP.md) et [AGENTS.md](AGENTS.md). Un hébergement permanent exige un serveur dédié, un disque persistant, des sauvegardes et un superviseur ; Codex Cloud est un environnement de développement, pas l'hébergeur permanent du logiciel.


## Analyse technique descriptive

Le tableau de bord affiche une analyse déterministe après 20 cours : moyennes
mobiles 5/20, RSI simple sur 14 variations (sans lissage de Wilder), fourchette
min/max sur 20 cours et écart-type des rendements par observation, non annualisé.
Le seuil descriptif de tendance est un écart de ±0,02 % entre les moyennes.
Les fenêtres sont en **observations**, pas en minutes ou en bougies OHLC.
Les bornes min/max ne sont pas des supports/résistances validés.

Les notes françaises sont archivées avec la version de calcul, les sources et
l'identifiant du cours. L'API `/api/state` retourne `analysis` et les dix dernières
entrées de `analysis_history`. Une analyse n'est produite que pour un cours accepté,
dans la même transaction SQLite. Les doublons et cours refusés n'en produisent pas.
La dernière note reste consultable après redémarrage ou pause ; son âge est affiché
et les données sont signalées périmées après 15 secondes.

**Cette analyse est consultative.** Elle ne modifie ni les ordres, ni la stratégie
SMA 4/12, ni les limites de risque. Le LLM et la veille restent désactivés. Les cours
sont synthétiques : aucune analyse du marché réel n'est encore disponible.

### Évolution SQLite

Au démarrage, ajout idempotent de la table `analyses` (clé primaire `quote_key`,
horodatage et JSON). Aucune table existante n'est modifiée et aucune note historique
n'est reconstruite : le premier nouveau cours accepté crée la première note.
Sauvegarder la base serveur arrêté avant mise à jour. La table est additive ; un
retour à l'ancienne version peut la laisser en place sans l'utiliser.
