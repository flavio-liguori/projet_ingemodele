package org.example;

import java.io.BufferedReader;
import java.io.File;
import java.io.InputStreamReader;

public class MainWorkflow {

    // On suppose que la structure est :
    // projet/
    //   src/main/resources/
    //      - llm.py (ou pipeline_rca.py)
    //      - rca_engine.py
    //      - transport.ecore

    static final String PROJECT_ROOT = System.getProperty("user.dir");
    static final String RESOURCES_PATH = PROJECT_ROOT + File.separator + "src" + File.separator + "main" + File.separator + "resources";

    static final String FILE_RCFT     = RESOURCES_PATH + File.separator + "sortie.rcft";
    // ATTENTION : Mets bien le nom de ton script Python principal ici (ex: pipeline_rca.py)
    static final String SCRIPT_PYTHON = "pipeline_rca.py";
    static final String PLAN_JSON     = RESOURCES_PATH + File.separator + "plan_amelioration.json"; // Output du python
    static final String PYTHON_CMD    = "python3"; // ou "python" selon ton système

    public static void main(String[] args) {
        long start = System.currentTimeMillis();

        String inputFileName = (args.length > 0) ? args[0] : "transport.ecore";
        String fullInputPath = RESOURCES_PATH + File.separator + inputFileName;

        File oldJson = new File(PLAN_JSON);
        if (oldJson.exists()) {
            oldJson.delete();
            System.out.println("[INFO] Ancien plan supprimé pour garantir une nouvelle analyse.");
        }

        System.out.println("=== PIPELINE IDM-RCA-LLM ===");

        // 1. Extraction (JAVA)
        // Génère le fichier .rcft avec Contextes + Relations
        ModelExtractor.runExtraction(fullInputPath, FILE_RCFT);

        // 2. Analyse (PYTHON)
        // Lit le .rcft -> Boucle RCA -> Gemini -> JSON
        runPythonScript();

        // 3. Refactoring (JAVA)
        // Lit le JSON -> Modifie le Ecore
        File jsonFile = new File(PLAN_JSON);
        if (jsonFile.exists() && jsonFile.length() > 0) {
            System.out.println("\n[JAVA] Lancement du Refactoring...");
            RefactoringAuto.main(new String[]{ fullInputPath });
        } else {
            System.err.println("\n[ERREUR] Le script Python n'a pas généré de plan JSON.");
        }

        System.out.println("\n=== FIN DU TRAITEMENT (" + (System.currentTimeMillis() - start) + "ms) ===");
    }

    private static void runPythonScript() {
        System.out.println("\n[SYSTEM] Lancement du script Python (" + SCRIPT_PYTHON + ")...");
        try {
            ProcessBuilder pb = new ProcessBuilder(PYTHON_CMD, SCRIPT_PYTHON);
            pb.directory(new File(RESOURCES_PATH));
            pb.redirectErrorStream(true);

            Process process = pb.start();
            try (BufferedReader reader = new BufferedReader(new InputStreamReader(process.getInputStream()))) {
                String line;
                while ((line = reader.readLine()) != null) {
                    System.out.println("   [PY] " + line);
                }
            }
            int exitCode = process.waitFor();
            if (exitCode != 0) System.err.println("   [PY] Erreur : Code de sortie " + exitCode);

        } catch (Exception e) {
            System.err.println("   -> Impossible de lancer Python : " + e.getMessage());
            e.printStackTrace();
        }
    }
}