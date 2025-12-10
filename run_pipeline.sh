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
echo -e "${BLUE}   PIPELINE IDM : EXTRACTION - RCA - MISTRAL  ${NC}"
echo -e "${BLUE}==============================================${NC}"

# --- 1. GESTION DE LA CLÉ API (MISTRAL) ---
if [ -z "$MISTRAL_API_KEY" ]; then
    echo -e "${YELLOW}[CONFIG] La variable MISTRAL_API_KEY n'est pas définie.${NC}"
    read -s -p "Entrez votre clé API Mistral (ou appuyez sur Entrée pour le mode SIMULATION) : " USER_KEY
    echo ""

    if [ ! -z "$USER_KEY" ]; then
        export MISTRAL_API_KEY="$USER_KEY"
        echo -e "${GREEN}   -> Clé API Mistral configurée pour cette session.${NC}"
    else
        echo -e "${YELLOW}   -> Aucune clé fournie. Le pipeline utilisera le mode SIMULATION (Fallback).${NC}"
    fi
else
    echo -e "${GREEN}[CONFIG] Clé API Mistral détectée dans l'environnement.${NC}"
fi

echo ""

# --- 2. CHOIX DU FICHIER ---
FILE_INPUT=$1

if [ -z "$FILE_INPUT" ]; then
    echo -e "${BLUE}[INFO] Fichiers Ecore disponibles :${NC}"
    ls src/main/resources/*.ecore 2>/dev/null | xargs -n 1 basename
    echo ""
    read -p "Nom du fichier cible (ex: transport.ecore) : " FILE_INPUT

    if [ -z "$FILE_INPUT" ]; then
        FILE_INPUT="transport.ecore"
        echo -e "${YELLOW}   -> Utilisation par défaut : $FILE_INPUT${NC}"
    fi
fi

if [ ! -f "src/main/resources/$FILE_INPUT" ]; then
    echo -e "${RED}[ERREUR] Le fichier 'src/main/resources/$FILE_INPUT' n'existe pas.${NC}"
    exit 1
fi

echo -e "\n${GREEN}[STEP 1] Compilation du projet Java...${NC}"
mvn clean compile

echo -e "\n${GREEN}[STEP 2] Exécution du Workflow (Proposition)...${NC}"
echo -e "${BLUE}-----------------------------------------------------${NC}"

mvn -q exec:java \
    -Dexec.mainClass="org.example.MainWorkflow" \
    -Dexec.args="$FILE_INPUT"

echo -e "${BLUE}-----------------------------------------------------${NC}"

# --- 3. VALIDATION UTILISATEUR (NOUVEL AJOUT) ---
echo -e "\n${YELLOW}[STEP 3] Validation Humaine${NC}"
read -p "Voulez-vous VALIDER et APPLIQUER les modifications proposées ? (o/N) : " CONFIRM

# On vérifie si la réponse commence par o, O, y ou Y
if [[ "$CONFIRM" =~ ^[oOyY] ]]; then
    echo -e "${GREEN}   -> Modifications VALIDÉES par l'utilisateur.${NC}"

    # [OPTIONNEL] : Ajoutez ici des commandes si nécessaire
    # Exemple : mv temp_output.ecore final_output.ecore

else
    echo -e "${RED}   -> Modifications REJETÉES / ANNULÉES.${NC}"

    # [OPTIONNEL] : Ajoutez ici des commandes de nettoyage
    # Exemple : rm temp_output.ecore
    # Exemple : git checkout src/main/resources/$FILE_INPUT

    echo -e "${BLUE}==============================================${NC}"
    exit 0 # On quitte proprement, mais sans afficher le message de succès final
fi

echo -e "\n${BLUE}==============================================${NC}"
echo -e "${GREEN}   SUCCÈS : Pipeline terminé et validé.${NC}"
echo -e "${BLUE}==============================================${NC}"