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
        default=1.0, ge=0.1, le=10.0,
        description="Phoneme length (speed). 1.0=normal, <1.0=faster, >1.0=slower."
    )
    noise_scale: Optional[float] = Field(
        default=0.67, ge=0.0, le=1.0,
        description="Generator noise (voice quality/variation). Default is 0.67."
    )
    noise_w: Optional[float] = Field(
        default=0.8, ge=0.0, le=1.0,
        description="Phoneme width noise (voice stability). Default is 0.8."
    )
    amplification: Optional[float] = Field(
        default=1.0, ge=0.1, le=5.0,
        description="Linear amplification factor. 1.0=normal, <1.0=quieter, >1.0=louder."
    )
    speaker: Optional[int] = Field(
        default=0, ge=0,
        description="ID of speaker if the model supports multiple speakers."
    )
    sentence_silence: Optional[float] = Field(
        default=0.2, ge=0.0,
        description="Seconds of silence after each sentence. Default is 0.2."
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
        "--length_scale", str(request.length_scale),
        "--noise_scale", str(request.noise_scale),
        "--noise_w", str(request.noise_w)
    ]
    
    if request.speaker is not None:
        command.extend(["--speaker", str(request.speaker)])
    
    if request.sentence_silence is not None:
        command.extend(["--sentence_silence", str(request.sentence_silence)])

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
