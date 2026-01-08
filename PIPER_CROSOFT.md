Absolument. Voici une documentation complète, précise et structurée pour la mise en place et l'utilisation de l'endpoint compatible Microsoft Azure.

---

## Documentation : API TTS avec Compatibilité Microsoft Azure

### 1. Vue d'ensemble

Cette documentation décrit la mise en place et l'utilisation d'un service de synthèse vocale (TTS) qui, tout en utilisant le moteur local **Piper**, expose un endpoint (`/tts/generate_microsoft_like`) compatible avec le format des requêtes de l'API TTS de **Microsoft Azure**.

Cela permet de l'intégrer facilement dans des applications existantes conçues pour Azure, tout en bénéficiant d'une exécution locale, privée et sans coût par requête.

L'API traduit "à la volée" les paramètres de style Microsoft (voix, vitesse) en paramètres compréhensibles par Piper.

---

### 2. Installation et Configuration

Pour déployer le service, vous avez besoin de quatre fichiers principaux : le code de l'API (`main.py`), les dépendances Python (`requirements.txt`), la configuration des voix (`voices_config.json`) et un `Dockerfile` pour construire l'image conteneurisée.

#### 2.1. Structure des Fichiers

Organisez vos fichiers comme suit :

```
tts-api/
├── config/
│   └── voices_config.json      # Fichier de configuration des voix
├── voices/
│   ├── fr_FR-siwis-medium.onnx # Modèles de voix .onnx
│   └── en_GB-alan-medium.onnx
├── main.py                     # Code de l'API
├── requirements.txt            # Dépendances Python
└── Dockerfile                  # Instructions pour construire l'image
```

#### 2.2. Fichier 1 : `voices_config.json` (Configuration des voix)

Ce fichier est la **source de vérité** pour les métadonnées de vos voix. Il est crucial pour faire le lien entre les noms de voix Microsoft et vos modèles Piper locaux.

**Emplacement :** `config/voices_config.json`

**Contenu Exemple :**
```json
{
  "siwis": {
    "gender": "female",
    "language_code": "fr-FR",
    "microsoft_voice_name": "fr-FR-DeniseNeural"
  },
  "alan": {
    "gender": "male",
    "language_code": "en-GB",
    "microsoft_voice_name": "en-GB-RyanNeural"
  },
  "amy": {
    "gender": "female",
    "language_code": "en-US",
    "microsoft_voice_name": "en-US-JennyNeural"
  }
}
```
**Détail des champs :**
*   **`"siwis"` (la clé)** : Le nom de la voix, dérivé du nom de fichier (`...-siwis-...).lower()`).
*   **`gender`** : Le genre de la voix (`"male"` ou `"female"`).
*   **`language_code`** : Le code de langue (`"fr-FR"`, `"en-GB"`, etc.).
*   **`microsoft_voice_name`** : **Le champ le plus important.** C'est l'alias. C'est la valeur que vos applications clientes enverront dans le paramètre `voice` pour appeler ce modèle Piper. Assurez-vous qu'il est **exactement** identique à ce que le client envoie.

#### 2.3. Fichier 2 : `requirements.txt` (Dépendances Python)

Ce fichier liste les paquets Python nécessaires et fige les versions critiques pour garantir des builds reproductibles et éviter les conflits.

**Emplacement :** `requirements.txt`

**Contenu Précis :**
```
fastapi
uvicorn[standard]
soundfile
setuptools
numpy==2.3.5
numba
resampy
```

#### 2.4. Fichier 3 : `Dockerfile` (Construction de l'image)

Ce fichier contient les instructions pour construire une image Podman ou Docker optimisée pour votre service.

**Emplacement :** `Dockerfile`

**Contenu Complet :**
```dockerfile
# Étape 1: Utiliser une image Python légère comme base
FROM python:3.12-slim

# Définir le répertoire de travail dans le conteneur
WORKDIR /app

# Copier le fichier des dépendances
COPY requirements.txt .

# Désinstaller toute version préexistante de numpy pour éviter les conflits
# Puis installer les dépendances depuis le fichier requirements.txt
RUN pip uninstall -y numpy && \
    pip install --no-cache-dir -r requirements.txt

# Copier le reste de l'application dans le répertoire de travail
COPY main.py .

# Exposer le port sur lequel l'API tournera
EXPOSE 8000

# Commande pour lancer l'API au démarrage du conteneur
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

#### 2.5. Construire et Lancer le Conteneur

1.  **Construire l'image :**
    Ouvrez un terminal dans le répertoire `tts-api/` et exécutez :
    ```bash
    podman build -t mon-api-tts:latest .
    ```

2.  **Lancer le conteneur :**
    Exécutez cette commande en l'adaptant à vos chemins. Elle est décomposée pour plus de lisibilité.
    ```bash
    podman run -d \
      --name service-tts \
      -p 8080:8000 \
      -v ./voices:/opt/voices:ro \
      -v ./config/voices_config.json:/config/voices_config.json:ro \
      -e VOICES_CONFIG_FILE_PATH="/config/voices_config.json" \
      -e CONTAINER_VOICES_PATH="/opt/voices" \
      -e MICROSOFT_API_KEY="VOTRE_CLE_SECRETE_PERSONNALISEE_ICI" \
      mon-api-tts:latest
    ```
    **Détail de la commande :**
    *   `-d`: Lance le conteneur en arrière-plan.
    *   `--name service-tts`: Donne un nom facile à retenir au conteneur.
    *   `-p 8080:8000`: Mappe le port 8080 de votre machine au port 8000 du conteneur.
    *   `-v ./voices:/opt/voices:ro`: Monte votre répertoire de voix local en lecture seule (`ro`).
    *   `-v ./config/voices_config.json:/config/voices_config.json:ro`: Monte votre fichier de configuration en lecture seule.
    *   `-e ...`: Définit les variables d'environnement cruciales, notamment votre **clé d'API secrète**.

---

### 3. Utilisation de l'Endpoint Compatible Microsoft

Votre API est maintenant prête à recevoir des requêtes sur l'endpoint `/tts/generate_microsoft_like`.

*   **URL :** `http://localhost:8080/tts/generate_microsoft_like`
*   **Méthode :** `POST`

#### 3.1. Corps de la Requête

La requête doit contenir un corps JSON avec les paramètres suivants :

| Paramètre     | Type    | Obligatoire | Description                                                                                                                                                             |
|---------------|---------|-------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `key`         | string  | **Oui**     | Votre clé d'API secrète, doit correspondre à la variable `MICROSOFT_API_KEY`.                                                                                           |
| `voice`       | string  | **Oui**     | Le nom de la voix au format Microsoft. Doit correspondre à une valeur `microsoft_voice_name` dans votre `voices_config.json`.                                              |
| `text`        | string  | **Oui**     | Le texte à synthétiser. Peut contenir du SSML si `ssml` est `true`.                                                                                                     |
| `ssml`        | boolean | Non         | Mettre à `true` si le champ `text` contient du SSML. L'API nettoiera les balises et tentera d'extraire le `rate`. Défaut : `false`.                                       |
| `format`      | string  | Non         | Format de sortie. Mettre à `"wav"` pour obtenir le fichier brut haute qualité. Toute autre valeur renverra le format A-law (téléphonie). Défaut : `"wav"`.                |
| `rate`        | float   | Non         | Vitesse de la parole (1.0 = normal, >1.0 = plus rapide). **Sera ignoré** si un `rate` est trouvé dans une balise `<prosody>` du SSML. Défaut : `1.0`.                      |
| `pitch`       | string  | Non         | **Ignoré.** Accepté pour la compatibilité, mais n'a aucun effet.                                                                                                        |
| `style`       | string  | Non         | **Ignoré.** Accepté pour la compatibilité, mais n'a aucun effet.                                                                                                        |
| `styledegree` | string  | Non         | **Ignoré.** Accepté pour la compatibilité, mais n'a aucun effet.                                                                                                        |

#### 3.2. Exemples `curl`

**Exemple 1 : Requête simple en haute qualité (WAV brut)**
```bash
curl -X POST \
  -H "Content-Type: application/json" \
  -d '{"key": "VOTRE_CLE_SECRETE_PERSONNALISEE_ICI", "voice": "fr-FR-DeniseNeural", "text": "Bonjour, ceci est un test."}' \
  -o test.wav \
  http://localhost:8080/tts/generate_microsoft_like
```

**Exemple 2 : Requête avec SSML pour accélérer la parole**
```bash
curl -X POST \
  -H "Content-Type: application/json" \
  -d '{"key": "VOTRE_CLE_SECRETE_PERSONNALISEE_ICI", "voice": "fr-FR-DeniseNeural", "ssml": true, "text": "<speak version=\"1.0\" xml:lang=\"fr-FR\"><prosody rate=\"1.3\">Ce texte sera lu trente pour cent plus rapidement.</prosody></speak>"}' \
  -o test_rapide.wav \
  http://localhost:8080/tts/generate_microsoft_like
```

**Exemple 3 : Requête pour générer un fichier au format A-law (téléphonie)**
```bash
curl -X POST \
  -H "Content-Type: application/json" \
  -d '{"key": "VOTRE_CLE_SECRETE_PERSONNALISEE_ICI", "voice": "fr-FR-DeniseNeural", "format": "alaw", "text": "Test pour la téléphonie."}' \
  -o test_alaw.wav \
  http://localhost:8080/tts/generate_microsoft_like
```

---

### 4. Dépannage

*   **Erreur `401 Unauthorized` "Invalid API Key"** : Votre `key` dans la requête ne correspond pas à la variable d'environnement `MICROSOFT_API_KEY` du conteneur.
*   **Erreur `400 Bad Request` "Voice '...' not found"** : La valeur `voice` envoyée n'a pas de correspondance `microsoft_voice_name` dans votre `voices_config.json`. Vérifiez l'orthographe et assurez-vous que le fichier de configuration est bien monté et lu par le conteneur.
*   **Erreur `422 Unprocessable Entity`** : Le corps de votre requête n'est pas un JSON valide ou le header `Content-Type: application/json` est manquant.
