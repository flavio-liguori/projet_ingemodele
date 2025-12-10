import os
import json
import time
import google.generativeai as genai

# Import du moteur RCA
try:
    from rca_engine import RCAManager
except ImportError:
    print("[ERREUR] Le fichier 'rca_engine.py' est introuvable.")
    exit(1)

# --- CONFIGURATION ---
API_KEY = os.getenv("GOOGLE_API_KEY")
RCFT_PATH = 'sortie.rcft'
OUTPUT_JSON = 'plan_amelioration.json'

# --- 1. CHARGEMENT DONNÉES ---

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

# --- 2. INTELLIGENCE ARTIFICIELLE (AVEC FALLBACK) ---

def simulate_response(objects):
    """Réponse de secours quand l'IA est hors quota."""
    print(f"   [FALLBACK] Génération d'une réponse simulée pour {objects}...")

    # Logique simple pour simuler une intelligence
    objs_str = " ".join(objects).lower()

    if "moto" in objs_str or "voiture" in objs_str:
        return {"decision": "HERITAGE", "nom_suggere": "Vehicule", "justification": "Partage de propriétés physiques."}

    if "manager" in objs_str or "director" in objs_str or "worker" in objs_str:
        return {"decision": "HERITAGE", "nom_suggere": "Personne", "justification": "Entités humaines avec ID."}

    if "charrue" in objs_str or "tracteur" in objs_str:
        return {"decision": "INTERFACE", "nom_suggere": "MachineAgricole", "justification": "Outils agricoles."}

    # Par défaut
    return {"decision": "HERITAGE", "nom_suggere": "ConceptCommun", "justification": "Regroupement par défaut."}

def ask_gemini(context_name, objects, attributes):
    clean_attrs = [a.replace("rel_", "Relation vers ") for a in attributes]

    # 1. Tentative d'appel API
    if API_KEY:
        try:
            genai.configure(api_key=API_KEY)
            model = genai.GenerativeModel('gemini-2.0-flash')
            prompt = f"Analyse UML pour {objects}. Commun: {clean_attrs}. JSON attendu: decision (HERITAGE/INTERFACE/RIEN), nom_suggere, justification."

            # On tente une fois
            resp = model.generate_content(prompt)
            text = resp.text.replace("```json", "").replace("```", "").strip()
            return json.loads(text)

        except Exception as e:
            # SI ÇA PLANTE (Quota, Erreur 429, Pas de wifi...), on passe en simulation
            print(f"[IA WARNING] L'API Google a échoué ({str(e)}).")
            print("             -> Passage automatique au mode SIMULATION pour continuer le pipeline.")
            return simulate_response(objects)

    # 2. Si pas de clé, simulation directe
    return simulate_response(objects)

# --- 3. EXÉCUTION ---

def run_rca_pipeline():
    # 1. RCA
    manager = load_data_from_rcft(RCFT_PATH)
    if not manager: return
    lattices = manager.run(max_steps=10)

    # 2. Analyse
    improvements = []
    processed = set()

    if "Classes" in lattices:
        for concept in lattices["Classes"]:
            objs = sorted(list(concept.extent))
            attrs = list(concept.intent)

            if len(objs) < 2 or len(attrs) == 0: continue
            if tuple(objs) in processed: continue
            processed.add(tuple(objs))

            print(f"\n[GROUPE] {objs}")

            # Appel sécurisé (renverra toujours quelque chose)
            res = ask_gemini("Classes", objs, attrs)

            if res and res.get('decision') in ["INTERFACE", "HERITAGE"]:
                print(f"   >>> ACTION RETENUE : {res['decision']} {res['nom_suggere']}")
                improvements.append({
                    "type": res['decision'],
                    "concept_name": res['nom_suggere'],
                    "classes_concernees": objs,
                    "elements_remontes": attrs,
                    "raison": res.get('justification', 'Automatique')
                })

    # 3. Écriture JSON
    with open(OUTPUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(improvements, f, indent=4)
    print(f"\n[FIN] Fichier {OUTPUT_JSON} généré avec {len(improvements)} propositions.")

if __name__ == "__main__":
    run_rca_pipeline()