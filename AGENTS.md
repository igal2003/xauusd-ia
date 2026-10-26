# Conventions du projet XAUUSD IA

- Réponses, interface et documentation en français ; Python 3.12+.
- Préserver les modifications existantes ; travailler sur une branche dédiée ; ne pas fusionner automatiquement.
- Paper trading seulement : aucun adaptateur d'ordres réels ni accès courtier.
- Toujours distinguer données synthétiques et données de marché ; aucune actualité ou capacité IA inventée.
- Prix USD/once troy, quantité onces troy, dates UTC ; coûts explicites à l'entrée et à la sortie.
- Le moteur impose les limites ; les futures analyses IA ne reçoivent aucun accès aux commandes ou aux paramètres de risque.
- Conserver l'idempotence par identifiant de cours, les transactions et la reprise SQLite. Documenter toute migration de schéma avant changement d'une base existante.
- Aucun secret dans Git. Ne pas ajouter les bases ou sauvegardes. Ne pas exposer cette V1 sans authentification à Internet.
- Ne pas ajuster automatiquement une stratégie sur suggestion de modèle : séparer calibration, validation et test final ; versionner données, paramètres et résultats.
- Un seul worker serveur par base. Le fournisseur doit rendre des identifiants stables et des horodatages UTC vérifiables.

Vérifications après changement du moteur ou de l'API :

```bash
python -m unittest discover -s tests -v
python -m compileall -q app tests
```

Lancement : `python -m uvicorn app.main:app --host 127.0.0.1 --port 8000`.

Mettre PROJECT_STATUS.md à jour avec les résultats réels, limites et vérifications impossibles. Un test ignoré n'est pas un test réussi.
