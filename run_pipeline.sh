#!/bin/bash

# --- CONFIGURATION VISUELLE ---
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Arrêter le script dès qu'une commande échoue
set -e

echo -e "${BLUE}==============================================${NC}"
echo -e "${BLUE}   PIPELINE IDM : EXTRACTION - RCA - GENAI    ${NC}"
echo -e "${BLUE}==============================================${NC}"

# --- 1. GESTION DE LA CLÉ API (Optionnel) ---
# Si la variable n'est pas déjà dans l'environnement, on la demande
if [ -z "$GOOGLE_API_KEY" ]; then
    echo -e "${YELLOW}[CONFIG] La variable GOOGLE_API_KEY n'est pas définie.${NC}"
    read -s -p "Entrez votre clé API Google (ou appuyez sur Entrée pour le mode SIMULATION) : " USER_KEY
    echo "" # Saut de ligne après la saisie masquée

    if [ ! -z "$USER_KEY" ]; then
        export GOOGLE_API_KEY="$USER_KEY"
        echo -e "${GREEN}   -> Clé API configurée pour cette session.${NC}"
    else
        echo -e "${YELLOW}   -> Aucune clé fournie. Le pipeline utilisera le mode SIMULATION (Fallback).${NC}"
    fi
else
    echo -e "${GREEN}[CONFIG] Clé API détectée dans l'environnement.${NC}"
fi

echo ""

# --- 2. CHOIX DU FICHIER ---
FILE_INPUT=$1

# Si aucun argument, liste les fichiers dispos
if [ -z "$FILE_INPUT" ]; then
    echo -e "${BLUE}[INFO] Fichiers Ecore disponibles :${NC}"
    # On liste uniquement les noms de fichiers dans resources
    ls src/main/resources/*.ecore | xargs -n 1 basename
    echo ""
    read -p "Nom du fichier cible (ex: transport.ecore) : " FILE_INPUT

    # Valeur par défaut
    if [ -z "$FILE_INPUT" ]; then
        FILE_INPUT="transport.ecore"
        echo -e "${YELLOW}   -> Utilisation par défaut : $FILE_INPUT${NC}"
    fi
fi

# Vérification physique du fichier
if [ ! -f "src/main/resources/$FILE_INPUT" ]; then
    echo -e "${RED}[ERREUR] Le fichier 'src/main/resources/$FILE_INPUT' n'existe pas.${NC}"
    exit 1
fi

echo -e "\n${GREEN}[STEP 1] Compilation du projet Java...${NC}"
# On compile (sans le -q pour voir les erreurs de compilation si ça plante)
mvn clean compile

echo -e "\n${GREEN}[STEP 2] Exécution du Workflow...${NC}"
echo -e "${BLUE}-----------------------------------------------------${NC}"

# Exécution avec exec:java
# Note : On passe la clé API à la JVM via l'environnement du shell courant (export fait plus haut)
mvn -q exec:java \
    -Dexec.mainClass="org.example.MainWorkflow" \
    -Dexec.args="$FILE_INPUT"

# Le code de retour est géré par 'set -e', mais on affiche un message de fin
echo -e "${BLUE}-----------------------------------------------------${NC}"
echo -e "${GREEN}   SUCCÈS : Pipeline terminé.${NC}"
echo -e "${BLUE}==============================================${NC}"