package org.example;

import org.eclipse.emf.common.util.URI;
import org.eclipse.emf.ecore.*;
import org.eclipse.emf.ecore.resource.Resource;
import org.eclipse.emf.ecore.resource.ResourceSet;
import org.eclipse.emf.ecore.resource.impl.ResourceSetImpl;
import org.eclipse.emf.ecore.xmi.impl.XMIResourceFactoryImpl;

import java.io.BufferedReader;
import java.io.File;
import java.io.FileReader;
import java.io.IOException;
import java.util.*;

public class RefactoringAuto {

    public static void main(String[] args) {
        Resource.Factory.Registry.INSTANCE.getExtensionToFactoryMap()
                .put("ecore", new XMIResourceFactoryImpl());
        ResourceSet rs = new ResourceSetImpl();

        String inputModelPath;
        if (args.length > 0) {
            inputModelPath = args[0];
        } else {
            String projectRoot = System.getProperty("user.dir");
            inputModelPath = projectRoot + File.separator + "src" + File.separator + "main" + File.separator + "resources" + File.separator + "transport.ecore";
        }

        Resource resource;
        try {
            resource = rs.getResource(URI.createFileURI(inputModelPath), true);
        } catch (Exception e) {
            System.err.println("[ERREUR] Impossible de lire le fichier Ecore : " + inputModelPath);
            return;
        }

        EPackage rootPackage = (EPackage) resource.getContents().get(0);

        // Chargement du JSON
        String projectRoot = System.getProperty("user.dir");
        String jsonPath = projectRoot + File.separator + "src" + File.separator + "main" + File.separator + "resources" + File.separator + "plan_amelioration.json";

        List<RefactoringAction> actions = loadImprovementPlan(jsonPath);

        if (actions.isEmpty()) {
            System.out.println("[INFO] Aucune action à effectuer.");
            return;
        }

        for (RefactoringAction action : actions) {
            applyRefactoring(rootPackage, action);
        }

        String outputModelPath = inputModelPath.replace(".ecore", "_refactore.ecore");
        resource.setURI(URI.createFileURI(outputModelPath));
        try {
            resource.save(Collections.emptyMap());
            System.out.println("\n[SUCCÈS] Modèle sauvegardé : " + outputModelPath);
        } catch (IOException e) {
            e.printStackTrace();
        }
    }

    private static void applyRefactoring(EPackage pkg, RefactoringAction action) {
        System.out.println("\n--- Application : " + action.type + " -> " + action.conceptName + " ---");

        if (action.concernedClasses.isEmpty()) return;

        EClassifier classifier = pkg.getEClassifier(action.concernedClasses.get(0));
        if (classifier == null || !(classifier instanceof EClass)) return;
        EClass firstChild = (EClass) classifier;

        // 1. Création du concept
        EClass newConcept = EcoreFactory.eINSTANCE.createEClass();
        newConcept.setName(action.conceptName);
        newConcept.setAbstract(true);
        newConcept.setInterface("INTERFACE".equals(action.type));

        pkg.getEClassifiers().add(newConcept);

        // 2. Déplacement des éléments
        for (String featureName : action.elementsToMove) {
            // [IMPORTANT] Filtre RCA : On ignore les attributs générés par l'analyse relationnelle
            if (featureName.startsWith("rel_") || featureName.contains("=>") || featureName.startsWith("R(")) {
                // Ce n'est pas un vrai attribut de code, c'est une info sémantique. On ignore.
                continue;
            }

            String cleanName = featureName.split(":")[0].replace("()", "").trim();

            EStructuralFeature attr = firstChild.getEStructuralFeature(cleanName);
            EOperation op = findOperation(firstChild, cleanName);

            if (op != null) {
                newConcept.getEOperations().add(op);
                System.out.println("   ^ Opération déplacée : " + cleanName);
            } else if (attr != null && !newConcept.isInterface()) {
                newConcept.getEStructuralFeatures().add(attr);
                System.out.println("   ^ Attribut déplacé : " + cleanName);
            } else {
                // Optionnel : Log si on ne trouve pas (utile pour le debug)
            }
        }

        // 3. Liaison aux enfants
        for (String childName : action.concernedClasses) {
            EClass childClass = (EClass) pkg.getEClassifier(childName);
            if (childClass == null) continue;

            childClass.getESuperTypes().add(newConcept);

            // Suppression doublons
            if (!childClass.getName().equals(firstChild.getName())) {
                for (String featureName : action.elementsToMove) {
                    if (featureName.startsWith("rel_") || featureName.contains("=>")) continue;

                    String cleanName = featureName.split(":")[0].replace("()", "").trim();

                    if (!newConcept.isInterface()) {
                        EStructuralFeature a = childClass.getEStructuralFeature(cleanName);
                        if (a != null) childClass.getEStructuralFeatures().remove(a);
                    }
                    EOperation o = findOperation(childClass, cleanName);
                    if (o != null) childClass.getEOperations().remove(o);
                }
            }
        }
    }

    private static EOperation findOperation(EClass cls, String name) {
        for (EOperation op : cls.getEOperations()) {
            if (op.getName().equals(name)) return op;
        }
        return null;
    }

    // --- Parser JSON identique ---
    static class RefactoringAction {
        String type;
        String conceptName;
        List<String> concernedClasses = new ArrayList<>();
        List<String> elementsToMove = new ArrayList<>();
    }

    private static List<RefactoringAction> loadImprovementPlan(String path) {
        List<RefactoringAction> actions = new ArrayList<>();
        File file = new File(path);
        if (!file.exists()) return actions;

        try (BufferedReader br = new BufferedReader(new FileReader(file))) {
            StringBuilder sb = new StringBuilder();
            String line;
            while ((line = br.readLine()) != null) sb.append(line);

            // Parsing très basique "manuel" pour éviter dépendance Jackson/Gson
            String json = sb.toString().trim();
            if (json.startsWith("[") && json.endsWith("]")) json = json.substring(1, json.length() - 1);

            // On splitte grossièrement par objet
            String[] objects = json.split("(?<=\\}),\\s*(?=\\{)");

            for (String obj : objects) {
                RefactoringAction a = new RefactoringAction();
                a.type = extractValue(obj, "\"type\"");
                a.conceptName = extractValue(obj, "\"concept_name\"");
                if (a.conceptName == null) a.conceptName = extractValue(obj, "\"new_name\""); // Support ancien format

                a.concernedClasses = extractArray(obj, "\"classes_concernees\"");
                if (a.concernedClasses.isEmpty()) a.concernedClasses = extractArray(obj, "\"classes\"");

                a.elementsToMove = extractArray(obj, "\"elements_remontes\"");
                if (a.elementsToMove.isEmpty()) a.elementsToMove = extractArray(obj, "\"features\"");

                if (a.type != null && a.conceptName != null) actions.add(a);
            }
        } catch (Exception e) { e.printStackTrace(); }
        return actions;
    }

    private static String extractValue(String s, String key) {
        int i = s.indexOf(key);
        if (i == -1) return null;
        int start = s.indexOf("\"", i + key.length() + 1) + 1;
        int end = s.indexOf("\"", start);
        return s.substring(start, end);
    }

    private static List<String> extractArray(String s, String key) {
        List<String> res = new ArrayList<>();
        int i = s.indexOf(key);
        if (i == -1) return res;
        int start = s.indexOf("[", i);
        int end = s.indexOf("]", start);
        String inner = s.substring(start + 1, end);
        for(String p : inner.split(",")) {
            String clean = p.trim().replace("\"", "");
            if(!clean.isEmpty()) res.add(clean);
        }
        return res;
    }
}