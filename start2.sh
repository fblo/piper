#!/bin/bash
# Script de démarrage pour l'API TTS Piper
# Ce script est utilisé dans le conteneur pour lancer l'application

exec python3 -m uvicorn main2:app --host 0.0.0.0 --port 5051
