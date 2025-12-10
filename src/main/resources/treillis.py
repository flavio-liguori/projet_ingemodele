from concepts import Context
import copy

class RCAManager:
    def __init__(self):
        self.contexts = {}   # Dict de noms -> Objets Context
        self.relations = []  # Liste de tuples (source_name, target_name, matrix_relation)
        self.lattices = {}   # Stockage des treillis générés

    def add_context(self, name, objects, properties, matrix):
        """Ajoute un contexte formel standard (FCA)"""
        self.contexts[name] = {
            'objects': objects,
            'properties': properties,
            'matrix': matrix,
            'base_width': len(properties) # Pour se souvenir des props originales
        }

    def add_relation(self, source_ctx, target_ctx, relation_matrix):
        """
        Ajoute une relation binaire entre deux contextes.
        relation_matrix[i][j] est True si source_objs[i] est lié à target_objs[j]
        """
        self.relations.append({
            'source': source_ctx,
            'target': target_ctx,
            'matrix': relation_matrix
        })

    def get_concept_lattice(self, ctx_name):
        """Génère le treillis pour un contexte donné via la lib concepts"""
        data = self.contexts[ctx_name]
        return Context(data['objects'], data['properties'], data['matrix']).lattice

    def _existential_scaling(self):
        """
        Cœur du RCA : Opérateur 'Existe'.
        Pour chaque relation (Source -> Cible), on regarde les concepts du treillis Cible.
        On ajoute un attribut à Source : "Est en relation avec le Concept C du Cible".
        """
        changes = 0

        for rel in self.relations:
            source_name = rel['source']
            target_name = rel['target']
            rel_matrix = rel['matrix']

            # 1. On récupère le treillis ACTUEL de la cible
            target_lattice = self.get_concept_lattice(target_name)

            source_data = self.contexts[source_name]
            target_data = self.contexts[target_name]

            # 2. Pour chaque concept du treillis cible (sauf le concept vide si désiré)
            for concept in target_lattice:
                # On ignore le concept racine si son extent couvre tout (souvent peu informatif) ou vide
                if not concept.extent:
                    continue

                # Nom du nouvel attribut relationnel
                # Ex: "achete_exist(Concept_1)"
                # Pour faire simple, on utilise une signature basée sur les attributs du concept
                concept_intent_str = ",".join(sorted(concept.intent))
                if not concept_intent_str: concept_intent_str = "Empty"
                new_attr = f"exist_{target_name}[{concept_intent_str}]"

                # Vérifier si cet attribut existe déjà pour ne pas le dupliquer
                if new_attr in source_data['properties']:
                    continue

                # 3. Calcul de la colonne pour ce nouvel attribut
                # Un objet Source a cet attribut s'il est lié à AU MOINS un objet de l'extent du concept Cible
                new_col = []
                target_extent = concept.extent # Les objets de la cible dans ce concept

                for i, src_obj in enumerate(source_data['objects']):
                    has_relation = False
                    # On parcourt les objets cibles liés à cet objet source
                    # rel_matrix[i] est la ligne des relations pour src_obj
                    for j, is_related in enumerate(rel_matrix[i]):
                        if is_related:
                            target_obj_name = target_data['objects'][j]
                            if target_obj_name in target_extent:
                                has_relation = True
                                break
                    new_col.append(has_relation)

                # Si la colonne n'est pas vide (optimisation), on l'ajoute
                if any(new_col):
                    source_data['properties'].append(new_attr)
                    for idx, val in enumerate(new_col):
                        source_data['matrix'][idx].append(val)
                    changes += 1
                    print(f"   [+] Ajout attribut relationnel dans '{source_name}' : {new_attr}")

        return changes

    def run_rca(self, max_steps=10):
        print("--- Démarrage RCA ---")
        for step in range(max_steps):
            print(f"--- Étape {step + 1} ---")
            changes = self._existential_scaling()

            if changes == 0:
                print(">>> Convergence atteinte (Stable).")
                break

        print("\n--- Génération des Treillis Finaux ---")
        results = {}
        for name in self.contexts:
            results[name] = self.get_concept_lattice(name)
        return results

# ==========================================
# EXEMPLE D'UTILISATION
# ==========================================

if __name__ == "__main__":
    rca = RCAManager()

    # --- 1. Contexte : PIZZAS (Cible) ---
    # Propriétés intrinsèques
    pizzas = ["Margherita", "Reine", "4Fromages", "Vegetarienne"]
    props_pizza = ["tomate", "fromage", "viande", "legume"]
    mat_pizza = [
        [True,  True,  False, False], # Margherita
        [True,  True,  True,  False], # Reine
        [False, True,  False, False], # 4Fromages (Base crème, disons pas tomate pour l'exemple)
        [True,  True,  False, True]   # Vegetarienne
    ]
    rca.add_context("Pizzas", pizzas, props_pizza, mat_pizza)

    # --- 2. Contexte : CLIENTS (Source) ---
    # Propriétés intrinsèques
    clients = ["Alice", "Bob", "Charlie"]
    props_client = ["homme", "femme", "jeune"]
    mat_client = [
        [False, True,  True],  # Alice
        [True,  False, True],  # Bob
        [True,  False, False]  # Charlie
    ]
    rca.add_context("Clients", clients, props_client, mat_client)

    # --- 3. Relation : ACHÈTE (Client -> Pizza) ---
    # Alice achète Margherita et Végétarienne
    # Bob achète Reine
    # Charlie achète 4Fromages
    relation_achete = [
        # Margh, Reine, 4From, Vege
        [True,   False, False, True],  # Alice
        [False,  True,  False, False], # Bob
        [False,  False, True,  False]  # Charlie
    ]
    rca.add_relation("Clients", "Pizzas", relation_achete)

    # --- 4. Lancement RCA ---
    lattices = rca.run_rca()

    # --- 5. Affichage ---
    print("\n=== RÉSULTATS RCA ===")

    # On regarde le treillis Clients enrichi
    print(f"\nTreillis CLIENTS (Enrichi par les relations) :")
    for concept in lattices["Clients"]:
        # On ne garde que les attributs intéressants pour l'affichage
        intents = list(concept.intent)
        print(f"Concept : {list(concept.extent)}")
        for attr in intents:
            if "exist_Pizzas" in attr:
                print(f"   -> Lié au concept Pizza : {attr}")
            else:
                print(f"   - {attr}")
        print("-" * 20)