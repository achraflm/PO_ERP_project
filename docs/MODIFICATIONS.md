# Modifications du projet PO

Branche : `modification`. Mise à jour : 28 octobre 2026.

## Fonctionnalités raccordées

- **Stock monitoring** : réponse API complétée avec type matière, seuil et prix ; modification des seuils persistée, contrôle des droits et des valeurs ; actualisation automatique de la page.
- **BOM et unités** : lecture du type et de l’unité des BOM courants pour les écrans stock/CutMan ; rejet des métadonnées contradictoires ; classification de réception déterminée par la matière sélectionnée.
- **CutMan** : sélection de lancements existants, actualisation de l’historique et affichage des types/unités de la base ; unité déterminée par le serveur lors de la comptabilisation. Tests HTTP couvrant import, doublon, téléchargement, consommation et relecture.
- **Simulation** : sélection des lignes PO courantes par projet, stratégie d’allocation envoyée par le frontend, sélection/import PDF du PV obligatoire, sauvegarde et relecture des simulations et allocations. Un changement de paramètres impose un nouvel aperçu avant sauvegarde.
- **Navigation** : suppression de la page System information et de son entrée de menu.
- **Validation API** : sérialisation des erreurs de validation contenant des valeurs décimales.

## Sources frontend dans le dépôt

Le dépôt parent référençait `frontend` comme un gitlink sans configuration de sous-module ni dépôt associé dans le checkout. Cette branche remplace ce gitlink par les sources présentes afin que les modifications frontend soient effectivement versionnées et récupérables. Les dépendances installées, sorties de build et journaux restent exclus.

## Documentation de soutenance

- [Modules à présenter](MODULES_PRESENTATION_STAGE.md) : objectifs, démonstrations, limites et plan de soutenance.
- [Complément Adient et prompt](PROMPT_AJOUT_ADIENT_PRESENTATION.md) : réunions/PV, collaborateurs, notifications, architecture et distinctions entre archives.

Les archives Java ont été examinées comme références ; elles ne sont pas intégrées au code de cette branche. Les modifications de la présentation Canva sont conservées dans Canva.

## Vérifications et limites

Lors de la dernière validation fonctionnelle de ces changements : 102 tests backend réussis ; build frontend, lint des fichiers concernés et contrôle TypeScript réussis. Les tests utilisent notamment SQLite et ne constituent pas une recette PostgreSQL concurrente.

La sauvegarde conserve des allocations de simulation et ne garantit pas une réservation exclusive du stock. La sécurité prototypale, certaines vues utilisant des exemples et la continuité complète lancement/remise/livraison restent à traiter. Les documents métier datés du 22 octobre décrivent un état antérieur à ces raccordements ; ce récapitulatif précise les évolutions sans déclarer leurs autres limites résolues.
