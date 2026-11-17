# Printer — Impression d'étiquettes

Module d'impression d'étiquettes via le **SDK Brother b-PAC** (COM Windows).

## Structure

```
printer/
├── bpac_document.py       # Gestionnaire de documents b-PAC (contexte, ouverture, champs, impression)
├── exceptions.py          # Exceptions spécifiques
├── models/                # Modèles de données (modes d'impression)
└── services/              # Services d'impression
```

## Rôle

Ce module permet de :

- **Ouvrir un modèle d'étiquette** au format b-PAC (`.lbx`)
- **Remplir les champs texte** du modèle (désignation produit, référence, prix, code-barres)
- **Lancer l'impression** sur une imprimante Brother compatible (QL, TD, RJ)
- Gérer les erreurs (champ introuvable, modèle manquant, SDK non installé)

## Technologies

- **SDK Brother b-PAC** — bibliothèque COM Windows (`bpac.Document`)
- **win32com.client** — interopérabilité Python/COM

## Dépendances

- Windows (COM obligatoire)
- SDK Brother b-PAC installé sur la machine