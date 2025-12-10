import re
# Assure-toi d'avoir importé ta classe RCAManager définie précédemment
from rca_engine import RCAManager

def parse_grid(lines):
    """
    Transforme les lignes de texte d'une table ASCII type RCFT en objets/colonnes/matrice.
    Format attendu :
    | | col1 | col2 |
    | obj1 | x | |
    | obj2 | | x |
    """
    col_names = []
    row_names = []
    matrix = []

    # 1. Trouver l'en-tête
    header_index = -1
    for i, line in enumerate(lines):
        if line.strip().startswith('|'):
            parts = [p.strip() for p in line.split('|')]
            # parts[0] est vide (avant le 1er pipe), parts[1] est vide (coin haut-gauche)
            # Les vraies colonnes commencent à parts[2]
            raw_cols = parts[2:]
            # On filtre les colonnes vides (le dernier pipe laisse souvent une string vide)
            col_names = [c for c in raw_cols if c]
            header_index = i
            break

    if header_index == -1:
        return None, None, None

    # 2. Lire les lignes
    for line in lines[header_index + 1:]:
        if not line.strip().startswith('|'): continue

        parts = line.split('|')
        if len(parts) < 2: continue

        obj_name = parts[1].strip()
        if not obj_name: continue # Ligne séparatrice

        row_names.append(obj_name)

        # Lecture des booléens (X ou x = True)
        row_bools = []
        values = parts[2:]

        for i in range(len(col_names)):
            is_present = False
            if i < len(values):
                val = values[i].strip().lower()
                if val == 'x':
                    is_present = True
            row_bools.append(is_present)

        matrix.append(row_bools)

    return row_names, col_names, matrix

def load_data_from_rcft(filepath):
    """
    Lit un fichier RCFT complet et peuple le RCAManager.
    Gère les 'FormalContext' et 'RelationalContext'.
    """
    print(f"--- Lecture du fichier {filepath} ---")
    rca = RCAManager()

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except FileNotFoundError:
        print(f"Erreur : Fichier {filepath} introuvable.")
        return None

    # Stockage temporaire des blocs de texte
    blocks = []
    current_block = []

    # Découpage du fichier en blocs (séparés par des lignes vides ou des keywords)
    # On détecte le début d'un nouveau bloc par les mots clés
    keywords = ["FormalContext", "RelationalContext"]

    for line in lines:
        stripped = line.strip()
        # Si la ligne commence par un mot clé, on sauvegarde le bloc précédent
        is_new_block = any(stripped.startswith(k) for k in keywords)

        if is_new_block and current_block:
            blocks.append(current_block)
            current_block = []

        current_block.append(line)

    if current_block:
        blocks.append(current_block)

    # Analyse de chaque bloc
    for block in blocks:
        header = block[0].strip()

        # --- CAS 1 : CONTEXTE (FormalContext) ---
        if header.startswith("FormalContext"):
            # Format: FormalContext NomDuContexte
            ctx_name = header.split(" ")[1].strip()
            rows, cols, matrix = parse_grid(block)

            if rows and cols and matrix:
                print(f" [LOAD] Contexte trouvé : '{ctx_name}' ({len(rows)} objets, {len(cols)} attributs)")
                rca.add_context(ctx_name, rows, cols, matrix)

        # --- CAS 2 : RELATION (RelationalContext) ---
        elif header.startswith("RelationalContext"):
            # Format: RelationalContext NomDeLaRelation
            rel_name = header.split(" ")[1].strip()

            # Recherche de la source et cible dans les métadonnées (lignes avant le tableau)
            source_name = None
            target_name = None

            for line in block:
                clean = line.strip()
                if clean.startswith("source"):
                    source_name = clean.split("source")[1].strip()
                elif clean.startswith("target"):
                    target_name = clean.split("target")[1].strip()

            if not source_name or not target_name:
                print(f" [WARN] Relation '{rel_name}' ignorée : Source ou Target introuvable.")
                continue

            rows, cols, matrix = parse_grid(block)

            if rows and cols and matrix:
                print(f" [LOAD] Relation trouvée : '{rel_name}' ({source_name} -> {target_name})")
                rca.add_relation(source_name, target_name, matrix)

    return rca

# --- TEST LOCAL ---
if __name__ == "__main__":
    # Pour tester, assure-toi que 'sortie.rcft' existe
    manager = load_data_from_rcft("sortie.rcft")
    if manager:
        print("\nDonnées chargées avec succès.")
        # Tu peux lancer manager.run() ici