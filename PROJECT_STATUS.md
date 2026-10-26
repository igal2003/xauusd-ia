# État du projet

## Livré dans la V1

- Serveur FastAPI autonome, interface française responsive sans CDN, courbe SVG des prix synthétiques.
- Compte virtuel 10 000 USD, trois profils, positions, historique, solde, P&L réalisés/latents et drawdown maximum.
- Commandes démarrer/pause/arrêt ; arrêt avec liquidation au prochain cours frais.
- Stratégie explicable SMA 4/12, données reproductibles par index et mention de démonstration.
- Risque codé : coûts, taille, stop, objectif, limite de positions, budget quotidien et verrouillage journalier.
- SQLite transactionnel, identifiants uniques, verrou de processus, persistance et reprise du mode et des positions.
- Journaux complets et contrats pour fournisseurs de cours, veille, analyse, synthèse et évaluation. Modules externes désactivés.
- Documentation macOS, configuration sans secret et CI de vérification.

## Vérifications effectuées dans Codex Cloud

`python -m unittest discover -s tests -v` : **9 tests moteur réussis, 1 test API ignoré** car la création de sockets est refusée par le sandbox. Les neuf tests comprennent une démonstration accélérée de 250 cours avec ouvertures, clôtures et archivage.

Le lancement Uvicorn atteint le démarrage de l'application, mais ne peut pas écouter sur le port 8000 dans cet environnement. Le test HTTP initial a également bloqué sur les sockets nécessaires à asyncio ; une détection explicite évite désormais ce blocage. La demande d'accès réseau supplémentaire n'a pas abouti. Le parcours HTTP ne peut donc pas être validé dans le sandbox Cloud. **Le rendu visuel dans un navigateur reste à vérifier sur Mac.** Aucun accès téléphone réel n'a été vérifié ici.

## Vérification GitHub Actions

La [CI du commit 9040e584](https://github.com/igal2003/xauusd-ia/actions/runs/40366097382) a réussi sur Python 3.12 et 3.13. Les journaux Python 3.12 confirment **10 tests exécutés, tous réussis, aucun ignoré**, y compris le parcours API sans clé. Les dépendances ont été installées sur des runners propres et la compilation a réussi. La syntaxe JavaScript a aussi été vérifiée localement avec `node --check app/static/app.js`. Cela ne remplace pas un contrôle visuel sur Mac/téléphone.

## Limites

Cours exclusivement synthétiques ; aucune donnée de marché, veille ou IA connectée. Pas d'ordres réels. Les résultats ne prouvent aucune performance financière. Modèle simplifié sans financement, liquidité ni garantie de prix stop ; des gaps peuvent dépasser les plafonds de perte prévus. La pause suspend aussi les stops. Les positions ne reçoivent pas de prix lorsque le serveur est arrêté. Un seul processus par base, pas d'authentification ni d'hébergement permanent. Pas encore de migrations, d'export complet ou de politique de rétention ; l'archive SQLite est conservée intégralement.

## Prochaine étape

Exécuter la suite et le parcours navigateur sur Mac : démarrer, attendre une position, mettre en pause, reprendre, arrêter et vérifier la clôture et la persistance après redémarrage. Puis choisir un fournisseur de cours réels et l'intégrer séparément selon ROADMAP.md.
