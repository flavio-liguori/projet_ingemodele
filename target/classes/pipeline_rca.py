import os
import json
import time
import requests # On utilise requests pour appeler Mistral simplement

# Import du moteur RCA
try:
    from rca_engine import RCAManager
except ImportError:
    print("[ERREUR] Le fichier 'rca_engine.py' est introuvable.")
    exit(1)

# --- CONFIGURATION ---
# Remplace os.getenv par ta clé "dur" si besoin pour les tests
API_KEY = os.getenv("MISTRAL_API_KEY")
RCFT_PATH = 'sortie.rcft'
OUTPUT_JSON = 'plan_amelioration.json'
MISTRAL_MODEL = "mistral-large-latest" # ou "open-mistral-7b" (moins cher/gratuit)

# --- 1. CHARGEMENT DONNÉES (Identique) ---

def parse_grid(lines):
    col_names = []
    row_names = []
    matrix = []
    header_index = -1
    for i, line in enumerate(lines):
        if line.strip().startswith('|'):
            parts = [p.strip() for p in line.split('|')]
            col_names = [c for c in parts[2:] if c]
            header_index = i
            break
    if header_index == -1: return None, None, None
    for line in lines[header_index + 1:]:
        if not line.strip().startswith('|'): continue
        parts = line.split('|')
        if len(parts) < 2: continue
        obj_name = parts[1].strip()
        if not obj_name: continue
        row_names.append(obj_name)
        row_bools = []
        values = parts[2:]
        for i in range(len(col_names)):
            is_present = False
            if i < len(values) and values[i].strip().lower() == 'x': is_present = True
            row_bools.append(is_present)
        matrix.append(row_bools)
    return row_names, col_names, matrix

def load_data_from_rcft(filepath):
    print(f"--- Lecture du fichier {filepath} ---")
    rca = RCAManager()
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except FileNotFoundError:
        print(f"[ERREUR] Fichier {filepath} introuvable.")
        return None
    blocks = []
    current_block = []
    for line in lines:
        if any(line.strip().startswith(k) for k in ["FormalContext", "RelationalContext"]) and current_block:
            blocks.append(current_block)
            current_block = []
        current_block.append(line)
    if current_block: blocks.append(current_block)
    for block in blocks:
        header = block[0].strip()
        if header.startswith("FormalContext"):
            ctx_name = header.split(" ")[1].strip()
            r, c, m = parse_grid(block)
            if r: rca.add_context(ctx_name, r, c, m)
        elif header.startswith("RelationalContext"):
            src, tgt = None, None
            for l in block:
                if "source" in l: src = l.split("source")[1].strip()
                if "target" in l: tgt = l.split("target")[1].strip()
            if src and tgt:
                r, c, m = parse_grid(block)
                if r: rca.add_relation(src, tgt, m)
    return rca

# --- 2. INTELLIGENCE ARTIFICIELLE (MISTRAL + FALLBACK) ---

def simulate_response(objects):
    """Réponse de secours quand l'IA est hors quota ou plante."""
    print(f"   [FALLBACK] Génération d'une réponse simulée pour {objects}...")
    objs_str = " ".join(objects).lower()

    if "moto" in objs_str or "voiture" in objs_str:
        return {"decision": "HERITAGE", "nom_suggere": "Vehicule", "justification": "Partage de propriétés physiques (simulation)."}
    if "manager" in objs_str or "director" in objs_str or "developer" in objs_str:
        return {"decision": "HERITAGE", "nom_suggere": "Employee", "justification": "Membres du personnel (simulation)."}
    if "charrue" in objs_str or "tracteur" in objs_str:
        return {"decision": "INTERFACE", "nom_suggere": "MachineAgricole", "justification": "Outils agricoles (simulation)."}

    return {"decision": "HERITAGE", "nom_suggere": "ConceptCommun", "justification": "Regroupement par défaut."}

def ask_mistral(context_name, objects, attributes):
    """Interroge l'API Mistral via une requête HTTP standard."""
    clean_attrs = [a.replace("rel_", "Relation vers ") for a in attributes]

    # 1. Si pas de clé, simulation directe
    if not API_KEY:
        print("[WARN] Pas de MISTRAL_API_KEY trouvée.")
        return simulate_response(objects)

    # 2. Préparation de la requête Mistral
    url = "https://api.mistral.ai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    # Prompt système strict pour forcer le JSON
    system_prompt = """
    Tu es un Architecte Logiciel Senior expert en Refactoring UML.
    Ta mission : Analyser des regroupements de classes et décider si une abstraction est nécessaire.
    Format de réponse OBLIGATOIRE : JSON valide uniquement.
    Champs du JSON :
    - "decision": "INTERFACE" (si comportement commun), "HERITAGE" (si nature commune), ou "RIEN".
    - "nom_suggere": Le nom du nouveau concept (CamelCase).
    - "justification": Courte phrase explicative.
    """

    user_message = f"""
    Groupe de classes : {", ".join(objects)}
    Attributs/Méthodes partagés : {json.dumps(clean_attrs, ensure_ascii=False)}

    Quelle est ta décision architecturale ?
    """

    payload = {
        "model": MISTRAL_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ],
        "response_format": {"type": "json_object"}, # Force le mode JSON de Mistral
        "temperature": 0.2
    }

    # 3. Appel API avec gestion d'erreurs
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=20)

        if response.status_code == 200:
            result = response.json()
            content = result['choices'][0]['message']['content']
            # Nettoyage au cas où le modèle ajoute du markdown ```json ... ```
            clean_content = content.replace("```json", "").replace("```", "").strip()
            return json.loads(clean_content)
        elif response.status_code == 429:
            print("[IA ERROR] Quota Mistral dépassé (429).")
            return simulate_response(objects)
        else:
            print(f"[IA ERROR] Erreur API Mistral : {response.status_code} - {response.text}")
            return simulate_response(objects)

    except Exception as e:
        print(f"[IA CRITICAL] Exception lors de l'appel Mistral : {e}")
        return simulate_response(objects)

# --- 3. EXÉCUTION ---

def run_rca_pipeline():
    # 1. RCA
    manager = load_data_from_rcft(RCFT_PATH)
    if not manager: return

    print("\n--- Lancement RCA (Treillis de Galois) ---")
    lattices = manager.run(max_steps=10)

    # 2. Analyse
    improvements = []
    processed = set()

    if "Classes" in lattices:
        for concept in lattices["Classes"]:
            objs = sorted(list(concept.extent))
            attrs = list(concept.intent)

            # Filtre : Il faut au moins 2 objets et des attributs communs
            if len(objs) < 2 or len(attrs) == 0: continue

            # Évite les doublons
            if tuple(objs) in processed: continue
            processed.add(tuple(objs))

            print(f"\n[GROUPE IDENTIFIÉ] {objs}")
            print(f"   -> Attributs : {attrs}")

            # Appel à Mistral (ou fallback)
            res = ask_mistral("Classes", objs, attrs)

            if res and res.get('decision') in ["INTERFACE", "HERITAGE"]:
                print(f"   >>> DÉCISION IA : {res['decision']} {res['nom_suggere']}")
                improvements.append({
                    "type": res['decision'],
                    "concept_name": res['nom_suggere'],
                    "classes_concernees": objs,
                    "elements_remontes": attrs,
                    "raison": res.get('justification', 'Raison IA')
                })
            else:
                 print("   >>> DÉCISION IA : Pas de refactoring.")

    # 3. Écriture JSON
    with open(OUTPUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(improvements, f, indent=4, ensure_ascii=False)
    print(f"\n[FIN] Fichier {OUTPUT_JSON} généré avec {len(improvements)} propositions.")

if __name__ == "__main__":
    run_rca_pipeline()