from concepts import Context

class RCAManager:
    def __init__(self):
        self.contexts = {}
        self.relations = []

    def add_context(self, name, objects, properties, matrix):
        """Ajoute un contexte (ex: Classes ou Types)"""
        # On stocke les données brutes pour pouvoir les modifier (ajouter des colonnes)
        self.contexts[name] = {
            'objects': objects,
            'properties': properties, # Liste de strings
            'matrix': matrix          # Liste de listes de booléens
        }

    def add_relation(self, source_name, target_name, relation_matrix):
        """Ajoute une relation (ex: Classes --appelle--> Methodes)"""
        self.relations.append({
            'source': source_name,
            'target': target_name,
            'matrix': relation_matrix
        })

    def get_lattice(self, name):
        """Génère le treillis actuel pour un contexte"""
        data = self.contexts[name]
        try:
            return Context(data['objects'], data['properties'], data['matrix']).lattice
        except Exception as e:
            print(f"Erreur création treillis {name}: {e}")
            return []

    def _scaling_step(self):
        """Une étape de mise à l'échelle relationnelle (Scaling)"""
        changes = 0

        for rel in self.relations:
            src_name = rel['source']
            tgt_name = rel['target']
            rel_mat = rel['matrix']

            # 1. On récupère le treillis de la cible pour voir les concepts émergents
            tgt_lattice = self.get_lattice(tgt_name)
            src_data = self.contexts[src_name]
            tgt_data = self.contexts[tgt_name]

            # 2. Pour chaque concept cible, on crée un attribut potentiel dans la source
            for concept in tgt_lattice:
                if not concept.extent: continue # On ignore le concept vide

                # Signature du concept cible (ex: "public,static")
                concept_intent = ",".join(sorted(concept.intent))
                if not concept_intent: concept_intent = "Empty"

                # Nom technique de l'attribut relationnel
                # Ex: "rel_Types[public,static]"
                new_attr_name = f"rel_{tgt_name}[{concept_intent}]"

                if new_attr_name in src_data['properties']:
                    continue # Déjà existant

                # 3. On calcule quels objets source sont liés à ce concept cible
                new_col = []
                target_extent = concept.extent # Les objets de la cible qui forment ce concept

                for i, src_obj in enumerate(src_data['objects']):
                    # Est-ce que src_obj est lié à AU MOINS UN objet du target_extent ?
                    is_linked = False
                    for j, is_related in enumerate(rel_mat[i]):
                        if is_related:
                            target_obj_name = tgt_data['objects'][j]
                            if target_obj_name in target_extent:
                                is_linked = True
                                break
                    new_col.append(is_linked)

                # Si au moins un objet source a cette relation, on ajoute la colonne
                if any(new_col):
                    src_data['properties'].append(new_attr_name)
                    for idx, val in enumerate(new_col):
                        src_data['matrix'][idx].append(val)
                    changes += 1

        return changes

    def run(self, max_steps=10):
        """Exécute la boucle RCA jusqu'à stabilité"""
        print(f"--- Démarrage RCA ({len(self.contexts)} contextes, {len(self.relations)} relations) ---")
        for i in range(max_steps):
            print(f"   > Itération {i+1}...")
            changes = self._scaling_step()
            if changes == 0:
                print("   > Convergence atteinte (Stable).")
                break

        # Retourne tous les treillis finaux
        return {name: self.get_lattice(name) for name in self.contexts}