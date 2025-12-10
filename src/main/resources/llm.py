import os
import json
import re
import google.generativeai as genai

# Import du module RCA (treillis.py)
try:
    from treillis import generate_lattice_from_rcft
except ImportError:
    print("Erreur : 'treillis.py' introuvable.")
    exit()


def json_to_xmi_simple(json_path, output_xmi_path):
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    xmi = """<?xml version="1.0" encoding="UTF-8"?>
<refactoring:Plan xmi:version="2.0" xmlns:xmi="http://www.omg.org/XMI" xmlns:refactoring="http://refactoring/1.0">
"""
    
    for action in data:
        decision = action.get('type') # ABSTRACT_CLASS ou INTERFACE
        
        if decision in ['ABSTRACT_CLASS', 'INTERFACE', 'HERITAGE']:
            name = action.get('concept_name') or action.get('new_name')
            # Classes
            classes = action.get('classes_concernees') or action.get('sub_classes')
            classes_str = " ".join(classes)
            # Attributs
            attrs = action.get('elements_remontes') or action.get('features')
            attrs_str = " ".join(attrs) if attrs else ""
            
            # Mapping du type pour le XMI
            # Si c'est INTERFACE, on met le literal 'INTERFACE', sinon 'ABSTRACT_CLASS'
            str_type = "INTERFACE" if decision == "INTERFACE" else "ABSTRACT_CLASS"

            xmi += f'  <actions xsi:type="refactoring:IntroduceAbstraction" newConceptName="{name}" targetClasses="{classes_str}" movedAttributes="{attrs_str}" structureType="{str_type}"/>\n'

    xmi += "</refactoring:Plan>"

    with open(output_xmi_path, 'w', encoding='utf-8') as f:
        f.write(xmi)
    print(f"Fichier XMI généré : {output_xmi_path}")

def construct_consultant_prompt(objects, attributes):
    """
    Prompt qui demande une expertise d'architecture, pas juste un nom.
    """
    prompt = f"""
    Tu es un Architecte Logiciel Senior expert en UML et Clean Code.
    
    SITUATION :
    Un algorithme d'analyse formelle a détecté que les classes suivantes partagent des éléments communs.
    
    - CLASSES ANALYSÉES : {", ".join(objects)}
    - ÉLÉMENTS PARTAGÉS : {", ".join(attributes)}
    
    TA MISSION :
    Détermine si ce partage justifie une amélioration du modèle UML et laquelle.
    Ne force pas l'héritage si cela n'a pas de sens sémantique ("is-a").
    
    CHOISIS LA MEILLEURE OPTION PARMI :
    1. "INTERFACE" : Si elles partagent uniquement des comportements (méthodes) mais ne sont pas de la même "nature". (Ex: 'Vole' pour Avion et Oiseau).
    2. "HERITAGE" : Si elles partagent des attributs d'état ET une nature commune. (Ex: Animal pour Chien et Chat).
    3. "RIEN" : Si le partage est anecdotique, une coïncidence, ou si modifier le modèle le rendrait plus complexe pour rien.
    
    FORMAT DE RÉPONSE ATTENDU (JSON UNIQUEMENT) :
    {{
        "decision": "INTERFACE" ou "HERITAGE" ou "RIEN",
        "nom_suggere": "LeNomDuConcept" (CamelCase, ex: 'IVolant' ou 'Animal'),
        "justification": "Explication courte de pourquoi cette amélioration est pertinente."
    }}
    """
    return prompt

def ask_gemini_architect(prompt):
    """Interroge Gemini avec une attente de JSON structuré."""
    
    # Récupération sécurisée de la clé (ou via variable d'environnement)
    api_key = os.getenv("GOOGLE_API_KEY")
        # Fallback pour vos tests rapides si la variable n'est pas mise
        # api_key = "AIzaSy..." (Déconseillé en prod)
        print("[ERREUR] Clé API manquante.")
        return None

    try:
        genai.configure(api_key=api_key)
        # Utilisation du modèle 2.0 Flash qui est excellent pour suivre des instructions JSON
        model = genai.GenerativeModel('gemini-2.0-flash')
        
        # On ajoute une instruction système implicite pour forcer le JSON
        response = model.generate_content(prompt + "\n\nRéponds uniquement avec le JSON valide.")
        
        text_response = response.text.strip()
        
        # Nettoyage des balises markdown éventuelles (```json ... ```)
        clean_json = text_response.replace("```json", "").replace("```", "").strip()
        
        return json.loads(clean_json)
        
    except Exception as e:
        print(f"Erreur Consultant IA : {e}")
        return None

def run_pipeline_improvement():
    rcft_path = 'sortie.rcft' # Vérifiez votre chemin !
    
    print("=== 1. ANALYSE STRUCTURELLE (RCA) ===")
    lattice = generate_lattice_from_rcft(rcft_path)
    
    if not lattice: return

    improvements_plan = []
    
    print("\n=== 2. CONSULTATION ARCHITECTURALE (GEMINI) ===")
    
    # Pour éviter de spammer l'IA avec des doublons, on peut utiliser un Set des groupes déjà traités
    processed_groups = set()

    for concept in lattice:
        objets = sorted(list(concept.extent)) # Trier pour la clé unique
        attributs = list(concept.intent)
        
        # On ne s'intéresse qu'aux regroupements (plus d'un objet) avec du contenu
        if len(objets) > 1 and len(attributs) > 0:
            
            # Signature unique pour éviter de traiter 2 fois le même groupe
            group_signature = tuple(objets)
            if group_signature in processed_groups: continue
            processed_groups.add(group_signature)

            print(f"\n[CAS DÉTECTÉ] Classes : {objets}")
            print(f"              Partage : {attributs}")
            
            # Appel à l'expert IA
            prompt = construct_consultant_prompt(objets, attributs)
            avis_expert = ask_gemini_architect(prompt)
            
            if avis_expert:
                decision = avis_expert.get('decision')
                nom = avis_expert.get('nom_suggere')
                raison = avis_expert.get('justification')
                
                print(f"   >>> AVIS EXPERT : {decision}")
                print(f"   >>> PROPOSITION : {nom}")
                print(f"   >>> RAISON      : {raison}")
                
                # On ajoute au plan seulement si une amélioration est proposée
                if decision in ["INTERFACE", "HERITAGE"]:
                    improvements_plan.append({
                        "type": decision,
                        "concept_name": nom,
                        "classes_concernees": objets,
                        "elements_remontes": attributs,
                        "raison": raison
                    })
            print("   ------------------------------------------------")

    # 3. Génération du rapport d'amélioration (JSON)
    output_file = 'plan_amelioration.json'
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(improvements_plan, f, indent=4, ensure_ascii=False)
        print(f"\n[TERMINÉ] Le plan d'amélioration a été généré : {output_file}")
        print(f"Nombre d'améliorations proposées : {len(improvements_plan)}")
        json_to_xmi_simple('plan_amelioration.json', 'plan_atl.xmi')
    except Exception as e:
        print(f"Erreur écriture fichier : {e}")

if __name__ == "__main__":
    run_pipeline_improvement()