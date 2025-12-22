# Mise en place d'une solution TTS open source Piper TTS avec FastAPI

Ce document décrit la mise en place d'une solution de synthèse vocale (Text-to-Speech \- TTS) basée sur Piper TTS, une solution open source, et exposée via une API FastAPI. Il abordera également les aspects de test, de benchmark et de tests de montée en charge.

## 1. Introduction à Piper TTS et FastAPI

### 1.1. Piper TTS

Piper TTS est un moteur de synthèse vocale open source léger et performant. Il est conçu pour être rapide et efficace, ce qui en fait un excellent choix pour les applications nécessitant une synthèse vocale en temps réel.

### 1.2. FastAPI

FastAPI est un framework web moderne et rapide pour construire des API avec Python 3.7+. Il est basé sur les standards OpenAPI et JSON Schema, offrant une documentation interactive automatique et une excellente performance.

## 2. Architecture de la solution

La solution proposée consiste en une API FastAPI qui servira de passerelle entre les applications clientes et le moteur Piper TTS.

* **Client**: L'application qui envoie le texte à synthétiser.  
* **API FastAPI**: Reçoit le texte du client, l'envoie à Piper TTS et retourne le fichier audio généré.  
* **Piper TTS**: Le moteur de synthèse vocale qui convertit le texte en audio.

## 3. Installation et configuration

### 3.1. Installation de Piper TTS

Build image

```
cat << EOF > Dockerfile
# syntax=docker/dockerfile:1.4
# This file is named 'Containerfile' (or Dockerfile)

# --- STAGE 1: Downloader (Guarantees Extraction to a Single Folder) ---
FROM busybox AS downloader

# Set variables for the version and standard AMD64 architecture
ARG PIPER_RELEASE_TAG="2023.1.14-2"
ARG PIPER_ARCH="x86_64" 
ENV PIPER_FILE="piper_linux_${PIPER_ARCH}.tar.gz"
ENV PIPER_URL="https://github.com/rhasspy/piper/releases/download/${PIPER_RELEASE_TAG}/${PIPER_FILE}"

# Download and extract the official pre-compiled binary package
WORKDIR /tmp

# Download the file
# Busybox includes a basic wget; tar will extract contents to /tmp/extracted_piper
RUN wget ${PIPER_URL} && \
    mkdir -p /tmp/extracted_piper && \
    tar -xzf ${PIPER_FILE} -C /tmp/extracted_piper --strip-components=1

# --- STAGE 2: Runtime (Minimal Debian Slim Base) ---
FROM debian:stable-slim

# 1. Install core runtime dependencies (espeak-ng and libstdc++6 for C++ runtime)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        espeak-ng \
        libstdc++6 \
    && rm -rf /var/lib/apt/lists/*

# 2. Copy the pre-compiled Piper binary
COPY --from=downloader /tmp/extracted_piper/piper /usr/local/bin/piper

# ⚡️ FIX 1: Copy the required shared libraries (Phonemizer) ⚡️
# We explicitly copy the file from the flat extracted folder to /usr/lib.
COPY --from=downloader /tmp/extracted_piper/libpiper_phonemize.so.1 /usr/libpiper_phonemize.so.1

# ⚡️ FIX 2: Copy the required shared libraries (ONNX Runtime) ⚡️
# We explicitly copy the missing ONNX library file. This is crucial as it failed last.
# Note: The exact version number in the filename might vary slightly, but we are trusting the archive.
COPY --from=downloader /tmp/extracted_piper/libonnxruntime.so.1.14.1 /usr/lib/libonnxruntime.so.1.14.1

# 3. Update the dynamic linker cache
# This ensures the system recognizes the newly copied .so files.
RUN ldconfig

# 4. Define the Mount Point
ENV VOICE_DIR="/opt/voices"
RUN mkdir -p ${VOICE_DIR}

# 5. Define the container execution
ENTRYPOINT ["/usr/local/bin/piper"]
CMD ["--help"]
EOF
```

### 3.2. Fichier Containerfile actuel

Voici le fichier Containerfile actuel qui implémente une solution plus avancée :

```dockerfile
# syntax=docker/dockerfile:1.4

# === STAGE 1: Builder (Builds espeak-ng AND piper-tts wheels) ===
FROM quay.io/centos/centos:stream10 AS builder

# 1. Install Build Dependencies
RUN dnf -y update && \
    dnf install -y --setopt=install_weak_deps=False \
        git \
        cmake \
        gcc-c++ \
        make \
        autoconf \
        automake \
        libtool \
        pkgconfig \
        which \
        python3-devel \
        python3-pip \
    && dnf clean all

# 2. Build and Install espeak-ng from source
# (This provides the -devel headers for the pip install)
WORKDIR /build
RUN git clone https://github.com/espeak-ng/espeak-ng.git
WORKDIR /build/espeak-ng
RUN ./autogen.sh && \
    ./configure --prefix=/usr && \
    make && \
    make install

# 3. Clone Piper
WORKDIR /build
RUN git clone https://github.com/OHF-Voice/piper1-gpl.git
WORKDIR /build/piper1-gpl

# 4. ⚡️ THE FIX: Build all Python dependencies into wheels
# We create a wheelhouse for piper AND all its C++ dependencies
RUN mkdir -p /build/wheelhouse
RUN pip3 wheel . -w /build/wheelhouse


# === STAGE 2: Monolithic Runtime (CentOS Stream 10 Base) ===
FROM quay.io/centos/centos:stream10

# 1. Install System Dependencies (Runtime only)
RUN dnf -y update && \
    # We need EPEL to find the espeak-ng runtime
    dnf install -y epel-release && \
    dnf install -y --setopt=install_weak_deps=False \
        python3 \
        python3-pip \
        espeak-ng \
    && dnf clean all

# 2. Install Python Dependencies from requirements.txt
WORKDIR /app
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# 3. ⚡️ THE FIX: Install Piper from the local wheelhouse
# This is fast, robust, and requires no path guessing.
COPY --from=builder /build/wheelhouse /tmp/wheelhouse
RUN pip3 install --no-index --find-links=/tmp/wheelhouse /tmp/wheelhouse/*.whl
RUN rm -rf /tmp/wheelhouse

# 4. Update the dynamic linker cache
RUN ldconfig

# 5. Define the Voice Mount Point (for external models)
ENV VOICE_DIR="/opt/voices"
RUN mkdir -p ${VOICE_DIR}

# 6. Copy the application code and startup script
COPY main2.py .
COPY start2.sh .
RUN chmod +x /app/start2.sh

# 7. Define the Execution Environment
EXPOSE 5051
CMD ["/app/start2.sh"]
```

### 3.3. API FastAPI (main2.py)

Voici le fichier principal de l'API FastAPI qui gère la synthèse vocale :

```python
import os
import time
import asyncio
import json
import io
import soundfile as sf
import resampy
import numpy as np
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel, Field

# --- FastAPI Setup ---
app = FastAPI(
    title="IV3US Dynamic & Configurable TTS API",
    description="API for TTS that discovers voices and uses a rich external configuration file."
)

# --- Infrastructure Configuration ---
PIPER_EXECUTABLE_PATH = "/usr/local/bin/piper"
CONTAINER_VOICES_PATH = "/opt/voices"
CONTAINER_OUTPUT_PATH = "/tmp"
MAX_CONCURRENT_REQUESTS = int(os.environ.get("MAX_PIPER_FORKS", 4))
PIPER_THREADS_PER_FORK = os.environ.get("PIPER_THREADS_PER_FORK", "1")

# --- Audio Pre-processing Configuration ---
TARGET_SAMPLE_RATE = 8000  # A-law/G.711 is 8kHz

# --- Dynamic Configuration ---
VOICES_CONFIG_FILE_PATH = os.environ.get("VOICES_CONFIG_FILE_PATH", "/opt/voices/voices_config.json")
VOICE_REFRESH_INTERVAL_SECONDS = int(os.environ.get("VOICE_REFRESH_INTERVAL_SECONDS", 300))

# --- Global State ---
AVAILABLE_VOICES: List[Dict[str, Any]] = []
DEFAULT_VOICE_NAME = "Siwis"

def load_voices_config() -> Dict[str, Dict[str, str]]:
    """Loads the voice metadata from the external JSON configuration file."""
    if not os.path.exists(VOICES_CONFIG_FILE_PATH):
        print(f"WARNING: Voices config file not found at '{VOICES_CONFIG_FILE_PATH}'. No voices will be loaded.")
        return {}
    try:
        with open(VOICES_CONFIG_FILE_PATH, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"ERROR: Failed to read or parse voices config file '{VOICES_CONFIG_FILE_PATH}': {e}")
        return {}

def discover_voices():
    """Scans the voice directory, reads the config file, and updates the AVAILABLE_VOICES list."""
    global AVAILABLE_VOICES
    print("Refreshing voice list...")
    voices_config = load_voices_config()
    
    if not os.path.isdir(CONTAINER_VOICES_PATH):
        print(f"WARNING: Voices directory not found at '{CONTAINER_VOICES_PATH}'.")
        AVAILABLE_VOICES = []
        return

    discovered = []
    configured_voice_names = set(voices_config.keys())

    for filename in os.listdir(CONTAINER_VOICES_PATH):
        if filename.endswith(".onnx"):
            try:
                voice_name_lower = filename.split('-')[1].lower()
                if voice_name_lower in voices_config:
                    config_entry = voices_config[voice_name_lower]
                    language_code = config_entry.get("language_code", "xx-XX")
                    discovered.append({
                        "id": f"{language_code.split('-')[0]}-{voice_name_lower}",
                        "name": voice_name_lower.capitalize(),
                        "model_filename": filename,
                        "language": language_code,
                        "gender": config_entry.get("gender", "unknown")
                    })
                    configured_voice_names.discard(voice_name_lower)
                else:
                    print(f"INFO: Voice file '{filename}' found but not defined in config. Skipping.")
            except IndexError:
                print(f"WARNING: Could not parse voice filename '{filename}'. Skipping.")
    
    if configured_voice_names:
        print(f"WARNING: Configured voices without matching .onnx file: {list(configured_voice_names)}")
        
    AVAILABLE_VOICES = sorted(discovered, key=lambda v: v['name'])
    print(f"Refresh complete. Loaded {len(AVAILABLE_VOICES)} voices.")

@app.on_event("startup")
async def startup_event():
    """On application startup, run initial discovery and start background refresh task."""
    print("Application starting up...")
    discover_voices()
    if VOICE_REFRESH_INTERVAL_SECONDS > 0:
        print(f"Starting background task for voice discovery every {VOICE_REFRESH_INTERVAL_SECONDS} seconds.")
        asyncio.create_task(periodic_voice_discovery())
    else:
        print("Periodic voice discovery is disabled.")

async def periodic_voice_discovery():
    """Background task to periodically refresh the list of available voices."""
    while True:
        await asyncio.sleep(VOICE_REFRESH_INTERVAL_SECONDS)
        discover_voices()

# --- Concurrency and Environment Setup ---
PIPER_SEMAPHORE = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
SUBPROCESS_ENV = os.environ.copy()
SUBPROCESS_ENV["OMP_NUM_THREADS"] = PIPER_THREADS_PER_FORK
SUBPROCESS_ENV["MKL_NUM_THREADS"] = PIPER_THREADS_PER_FORK
SUBPROCESS_ENV["ORT_GLOBAL_INTRA_OP_NUM_THREADS"] = PIPER_THREADS_PER_FORK
SUBPROCESS_ENV["ORT_GLOBAL_INTER_OP_NUM_THREADS"] = PIPER_THREADS_PER_FORK
SUBPROCESS_ENV["NUMEXPR_NUM_THREADS"] = PIPER_THREADS_PER_FORK
SUBPROCESS_ENV["OPENBLAS_NUM_THREADS"] = PIPER_THREADS_PER_FORK
SUBPROCESS_ENV["VECLIB_MAXIMUM_THREADS"] = PIPER_THREADS_PER_FORK

# --- Pydantic Models ---
class TTSRequest(BaseModel):
    text: str
    name: Optional[str] = None
    length_scale: Optional[float] = Field(
        default=1.0, ge=0.5, le=2.0,
        description="Speech speed. 1.0=normal, <1.0=faster, >1.0=slower."
    )
    amplification: Optional[float] = Field(
        default=1.0, ge=0.1, le=5.0,
        description="Linear amplification factor. 1.0=normal, <1.0=quieter, >1.0=louder."
    )

class Voice(BaseModel):
    id: str
    name: str

class VoicesResponse(BaseModel):
    voices: List[Voice]

# --- API Endpoints ---
@app.get("/tts/voices", summary="Get voices", response_model=VoicesResponse)
async def get_voices(language: Optional[str] = None, gender: Optional[str] = None):
    if not AVAILABLE_VOICES: return {"voices": []}
    filtered_voices = AVAILABLE_VOICES
    if language: filtered_voices = [v for v in filtered_voices if v["language"] == language]
    if gender: filtered_voices = [v for v in filtered_voices if v["gender"] == gender]
    response_list = [{"id": v["id"], "name": v["name"]} for v in filtered_voices]
    return {"voices": response_list}

@app.post("/tts/generate", summary="Generate TTS", response_class=Response)
async def generate_tts(request: TTSRequest):
    if not AVAILABLE_VOICES: raise HTTPException(status_code=503, detail="TTS service is unavailable: no voices loaded.")
    
    voice_name_to_find = request.name if request.name is not None else DEFAULT_VOICE_NAME
    selected_voice = next((v for v in AVAILABLE_VOICES if v["name"] == voice_name_to_find), None)
    if not selected_voice: raise HTTPException(status_code=400, detail=f"Voice with name '{voice_name_to_find}' not found.")
    
    model_filename = selected_voice["model_filename"]
    model_full_path = os.path.join(CONTAINER_VOICES_PATH, model_filename)
    if not os.path.exists(model_full_path):
        raise HTTPException(status_code=500, detail="Server configuration error: voice model file is missing.")
    
    base_filename = f"tts_{int(time.time())}_{selected_voice['name']}"
    output_filename = f"{base_filename}.wav"
    output_path_container = os.path.join(CONTAINER_OUTPUT_PATH, output_filename)
    
    command = [
        PIPER_EXECUTABLE_PATH, 
        "--model", model_full_path, 
        "--output_file", output_path_container, 
        "--length_scale", str(request.length_scale)
    ]

    async with PIPER_SEMAPHORE:
        try:
            proc = await asyncio.create_subprocess_exec(*command, stdin=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, env=SUBPROCESS_ENV)
            (_, stderr_data) = await proc.communicate(input=request.text.encode('utf-8'))
            await proc.wait()
            if proc.returncode != 0: 
                raise HTTPException(status_code=500, detail=f"TTS generation failed: {stderr_data.decode()}")
        except Exception as e: 
            raise HTTPException(status_code=500, detail=f"Internal server error during TTS generation: {e}")
        
    if os.path.exists(output_path_container):
        try:
            pcm_data, original_sr = sf.read(output_path_container, dtype='float32')
            resampled_data = resampy.resample(pcm_data, original_sr, TARGET_SAMPLE_RATE)
            
            amplified_data = resampled_data
            if request.amplification != 1.0:
                amplified_data = resampled_data * request.amplification
            
            final_data = np.clip(amplified_data, -1.0, 1.0)
            
            mem_out = io.BytesIO()
            sf.write(mem_out, final_data, TARGET_SAMPLE_RATE, format='WAV', subtype='ALAW')
            audio_content = mem_out.getvalue()
            
            response = Response(content=audio_content, media_type="audio/wav")
            response.headers["Content-Disposition"] = f"attachment; filename={f'{base_filename}_alaw.wav'}"
            return response
        except Exception as e:
            print(f"Audio transcoding error: {e}")
            raise HTTPException(status_code=500, detail=f"Audio transcoding failed: {e}")
        finally:
            os.remove(output_path_container)
    else:
        raise HTTPException(status_code=500, detail="TTS completed but output file was not found.")
```

### 3.4. Script de démarrage (start2.sh)

Le script de démarrage est actuellement vide dans le dépôt, mais pourrait contenir les commandes pour lancer l'API :

```bash
#!/bin/bash
# Script de démarrage pour l'API TTS Piper
# Ce script est utilisé dans le conteneur pour lancer l'application

exec python3 -m uvicorn main2:app --host 0.0.0 --port 5051
```

### 3.5. Fichier de configuration du conteneur (tts-piper-5051.container)

Voici le fichier de configuration pour Podman qui permet de lancer le conteneur une fois celui-ci buildé :

```ini
[Container]
Image=vs-inf-prd-for-fr-501.hostics.fr/connectics/ia/tts_iv3us:latest
ContainerName=tts-piper-iv3us
PublishPort=5051:5051
Volume=/mnt/ia/piper/voices:/opt/voices:ro
Volume=/tmp:/tmp:rw
Volume=/mnt/ia/tts/main2.py:/app/main.py:ro
Environment=VOICES_CONFIG_FILE_PATH=/opt/voices/voices_config.json

[Service]
TimeoutStopSec=70
RestartPolicy=Always

[Install]
WantedBy=default.target
```

## 4. Fonctionnalités avancées

### 4.1. Découverte dynamique des voix

Le système implémente une découverte dynamique des voix disponibles dans le répertoire `/opt/voices`. L'API peut automatiquement détecter les nouveaux modèles vocaux et les rendre disponibles sans redémarrage.

### 4.2. Gestion de la concurrence

L'API limite le nombre de requêtes concurrentes pour éviter la saturation du système. La limite peut être configurée via la variable d'environnement `MAX_PIPER_FORKS`.

### 4.3. Traitement audio

L'API effectue un traitement audio pour adapter le taux d'échantillonnage à 8000 Hz (format A-law/G.711) et permet d'ajuster le volume et la vitesse de la parole.

## 5. Tests

### 5.1. Tests unitaires et d'intégration

Des tests unitaires peuvent être écrits pour vérifier les fonctions individuelles de l'API (par exemple, la gestion des erreurs, la lecture des fichiers). Les tests d'intégration vérifieront la communication entre FastAPI et Piper TTS.

### 5.2. Tests fonctionnels

Ces tests consistent à envoyer du texte à l'API et à écouter le fichier audio retourné pour s'assurer que la synthèse vocale est correcte.

## 6. Benchmarks

### 6.1. Métriques à mesurer

* **Latence**: Temps nécessaire pour obtenir la réponse audio après avoir envoyé la requête texte.  
* **Débit**: Nombre de requêtes traitées par seconde.  
* **Utilisation des ressources**: Consommation CPU, mémoire et disque.

### 6.2. Outils de benchmarking

Des outils comme `ApacheBench` (ab), `JMeter`, `Locust` ou des scripts Python personnalisés peuvent être utilisés pour simuler des charges et mesurer les performances.

```
# Exemple avec ApacheBench pour tester la latence d'une seule requête
ab -n 1 -p data.txt -T application/x-www-form-urlencoded "http://localhost:5051/synthesize/?text=Ceci%20est%20un%20test"
```

Le fichier `data.txt` pourrait contenir `text=Ceci est un test`.

## 7. Tests de montée en charge

### 7.1. Scénarios de test

* **Charge croissante**: Augmenter progressivement le nombre d'utilisateurs simultanés ou de requêtes par seconde.  
* **Charge constante sur une longue durée**: Maintenir une charge élevée pendant une période prolongée pour vérifier la stabilité.  
* **Pic de charge**: Simuler une augmentation soudaine de la demande.

### 7.2. Analyse des résultats

* **Temps de réponse**: Comment il évolue avec la charge.  
* **Taux d'erreur**: Si des erreurs apparaissent sous une forte charge.  
* **Utilisation des ressources**: Identifier les composants qui saturent.

### 7.3. Optimisations possibles

* **Mise en cache**: Cacher les phrases fréquemment synthétisées.  
* **Mise à l'échelle horizontale**: Exécuter plusieurs instances de l'API et de Piper TTS derrière un équilibreur de charge.  
* **Optimisation de Piper TTS**: Utiliser des modèles plus petits ou optimiser la configuration.

## 8. Déploiement

Pour déployer cette solution, vous pouvez utiliser Docker ou Podman avec le Containerfile fourni. Assurez-vous d'avoir un dossier contenant les modèles vocaux (fichiers .onnx) monté dans le conteneur au chemin `/opt/voices`.

## 9. Conclusion

La mise en place de Piper TTS avec FastAPI offre une solution de synthèse vocale puissante et flexible. Les tests rigoureux, les benchmarks et les tests de montée en charge sont essentiels pour garantir la robustesse et la performance de l'API en production. Des optimisations continues basées sur ces analyses permettront d'offrir une expérience utilisateur optimale.
