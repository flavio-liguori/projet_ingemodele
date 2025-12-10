package org.example;

import org.eclipse.emf.common.util.URI;
import org.eclipse.emf.ecore.*;
import org.eclipse.emf.ecore.resource.Resource;
import org.eclipse.emf.ecore.resource.ResourceSet;
import org.eclipse.emf.ecore.resource.impl.ResourceSetImpl;
import org.eclipse.emf.ecore.xmi.impl.XMIResourceFactoryImpl;
import java.io.FileWriter;
import java.util.*;

public class ModelExtractor {

    public static void runExtraction(String inputEcorePath, String outputRcftPath) {
        System.out.println("[JAVA] 1. Extraction des données vers RCFT (Mode RCA)...");

        // Init EMF
        Resource.Factory.Registry.INSTANCE.getExtensionToFactoryMap().put("ecore", new XMIResourceFactoryImpl());
        ResourceSet rs = new ResourceSetImpl();

        try {
            Resource resource = rs.getResource(URI.createFileURI(inputEcorePath), true);
            EPackage rootPackage = (EPackage) resource.getContents().get(0);

            // 1. Collecte des données
            List<EClass> classes = new ArrayList<>();
            Set<String> properties = new LinkedHashSet<>();
            Set<String> typesFound = new LinkedHashSet<>();

            // On parcourt tout pour lister les classes et les types utilisés
            for (EClassifier classifier : rootPackage.getEClassifiers()) {
                if (classifier instanceof EClass) {
                    EClass eClass = (EClass) classifier;
                    classes.add(eClass);

                    // Propriétés intrinsèques (Attributs et Opérations)
                    for (EAttribute attr : eClass.getEAttributes()) {
                        properties.add(getSig(attr));
                        if (attr.getEType() != null) typesFound.add(attr.getEType().getName());
                    }
                    for (EOperation op : eClass.getEOperations()) {
                        properties.add(getSig(op));
                        if (op.getEType() != null) typesFound.add(op.getEType().getName());
                    }
                }
            }

            // 2. Écriture du fichier RCFT
            try (FileWriter writer = new FileWriter(outputRcftPath)) {

                // --- CONTEXTE 1 : Les Classes (Objets principaux) ---
                writer.write("FormalContext Classes\n| |");
                for (String p : properties) writer.write(" " + p + " |");
                writer.write("\n");

                for (EClass c : classes) {
                    writer.write("| " + c.getName() + " |");
                    for (String p : properties) {
                        writer.write(hasProp(c, p) ? " x |" : " |");
                    }
                    writer.write("\n");
                }
                writer.write("\n"); // Séparateur de bloc

                // --- CONTEXTE 2 : Les Types (Pour le RCA) ---
                // On crée un contexte simple pour les types (String, int, List...)
                writer.write("FormalContext Types\n| | is_primitive | is_object |\n");
                for (String t : typesFound) {
                    boolean isPrim = isPrimitive(t);
                    writer.write("| " + t + " | " + (isPrim ? "x |" : " |") + (isPrim ? " |" : "x |") + "\n");
                }
                writer.write("\n");

                // --- RELATION : Classes --dependsOn--> Types ---
                // C'est ici que la magie RCA opère : qui utilise quel type ?
                writer.write("RelationalContext dependencies\n");
                writer.write("source Classes\n");
                writer.write("target Types\n");
                writer.write("scaling exist\n");

                // En-tête de la matrice relationnelle
                writer.write("| |");
                List<String> typesList = new ArrayList<>(typesFound);
                for (String t : typesList) writer.write(" " + t + " |");
                writer.write("\n");

                // Remplissage de la matrice
                for (EClass c : classes) {
                    writer.write("| " + c.getName() + " |");
                    for (String t : typesList) {
                        writer.write(usesType(c, t) ? " x |" : " |");
                    }
                    writer.write("\n");
                }

            }
            System.out.println("   -> Fichier RCFT généré avec succès : " + outputRcftPath);

        } catch (Exception e) {
            e.printStackTrace();
        }
    }

    // --- Helpers ---

    private static String getSig(ENamedElement e) {
        if (e instanceof EAttribute) return e.getName(); // On simplifie pour l'extraction
        if (e instanceof EOperation) return e.getName() + "()";
        return e.getName();
    }

    private static boolean hasProp(EClass c, String sig) {
        for (EAttribute a : c.getEAttributes()) if (getSig(a).equals(sig)) return true;
        for (EOperation o : c.getEOperations()) if (getSig(o).equals(sig)) return true;
        return false;
    }

    private static boolean usesType(EClass c, String typeName) {
        // Vérifie si la classe C utilise ce type dans un attribut ou un retour de méthode
        for (EAttribute a : c.getEAttributes()) {
            if (a.getEType() != null && a.getEType().getName().equals(typeName)) return true;
        }
        for (EOperation o : c.getEOperations()) {
            if (o.getEType() != null && o.getEType().getName().equals(typeName)) return true;
        }
        return false;
    }

    private static boolean isPrimitive(String typeName) {
        return Arrays.asList("EInt", "EString", "EBoolean", "EDouble", "int", "boolean", "String").contains(typeName);
    }
}