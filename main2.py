import os
import time
import asyncio
import json
import io
import soundfile as sf
import resampy
import numpy as np
from typing import Optional, List, Dict, Any
import httpx
from xml.etree import ElementTree

from fastapi import FastAPI, HTTPException, Response, Query
from pydantic import BaseModel, Field

# --- FastAPI Setup ---
app = FastAPI(
    title="IV3US Dynamic & Configurable TTS API",
    description="API for TTS that supports both Piper and Microsoft TTS engines."
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
IV2US_VOICES_CONFIG_FILE_PATH = os.environ.get("IV2US_VOICES_CONFIG_FILE_PATH", "/opt/voices/voices_iv2us.json")
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
    # Microsoft TTS parameters
    api: Optional[str] = "piper"
    url: Optional[str] = None
    language: Optional[str] = "fr-FR"
    voice: Optional[str] = "fr-FR-DeniseNeural"
    key: Optional[str] = None
    ssml: Optional[bool] = True
    checkbreak: Optional[bool] = False
    rate: Optional[float] = 1.0
    pitch: Optional[str] = "+2st"
    style: Optional[str] = "cheerful"
    styledegree: Optional[str] = "1.5"
    format: Optional[str] = "wav"
    
    # Piper TTS parameters (existing)
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
    # Convert Microsoft TTS parameters to Piper TTS parameters and generate using Piper
    return await generate_piper_tts_with_microsoft_params(request)

async def generate_piper_tts_with_microsoft_params(request: TTSRequest):
    if not AVAILABLE_VOICES: raise HTTPException(status_code=503, detail="TTS service is unavailable: no voices loaded.")
    
    # Map Microsoft voice to Piper voice
    # If a Piper voice name is provided, use it; otherwise try to match based on language
    voice_name_to_find = request.name if request.name is not None else DEFAULT_VOICE_NAME
    
    # If voice_name_to_find is not provided or not found, try to match based on Microsoft voice name
    if not voice_name_to_find or voice_name_to_find not in [v["name"] for v in AVAILABLE_VOICES]:
        # Try to find a Piper voice that matches the language
        matching_voices = [v for v in AVAILABLE_VOICES if request.language.split('-')[0] in v["language"].lower()]
        if matching_voices:
            selected_voice = matching_voices[0]
        else:
            selected_voice = next((v for v in AVAILABLE_VOICES if v["name"] == DEFAULT_VOICE_NAME), AVAILABLE_VOICES[0] if AVAILABLE_VOICES else None)
    else:
        selected_voice = next((v for v in AVAILABLE_VOICES if v["name"] == voice_name_to_find), None)
    
    if not selected_voice: raise HTTPException(status_code=400, detail=f"Voice with name '{voice_name_to_find}' not found.")
    
    model_filename = selected_voice["model_filename"]
    model_full_path = os.path.join(CONTAINER_VOICES_PATH, model_filename)
    if not os.path.exists(model_full_path):
        raise HTTPException(status_code=500, detail="Server configuration error: voice model file is missing.")
    
    base_filename = f"ts_{int(time.time())}_{selected_voice['name']}"
    output_filename = f"{base_filename}.wav"
    output_path_container = os.path.join(CONTAINER_OUTPUT_PATH, output_filename)
    
    # Convert Microsoft TTS parameters to Piper TTS parameters
    # The rate parameter affects speed - convert to length_scale (inverse relationship)
    length_scale = 1.0 / request.rate if request.rate != 0 else 1.0
    
    # For now, use default noise parameters but we could adjust based on Microsoft pitch/style if needed
    noise_scale = 0.67  # Default
    noise_w = 0.8      # Default
    
    command = [
        PIPER_EXECUTABLE_PATH, 
        "--model", model_full_path, 
        "--output_file", output_path_container, 
        "--length_scale", str(length_scale),
        "--noise_scale", str(noise_scale),
        "--noise_w", str(noise_w)
    ]
    
    # Piper doesn't have direct equivalents for Microsoft's style and pitch parameters,
    # but we can make some adjustments based on the provided values
    # For pitch: Piper doesn't have direct pitch control, but we could potentially use audio processing
    
    if request.speaker is not None:
        command.extend(["--speaker", str(request.speaker)])
    
    # Sentence silence is similar between both systems
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
            # Debug: Log file info
            file_size = os.path.getsize(output_path_container)
            print(f"DEBUG: Generated audio file size: {file_size} bytes")

            pcm_data, original_sr = sf.read(output_path_container, dtype='float32')
            print(f"DEBUG: Loaded audio - shape: {pcm_data.shape}, sample rate: {original_sr}")

            # Apply additional audio processing based on Microsoft-style parameters
            # Adjust pitch if specified (though Piper doesn't support this directly, we can apply post-processing)
            processed_data = pcm_data

            # Amplification is similar in both systems
            if request.amplification != 1.0:
                processed_data = processed_data * request.amplification

            # Resample to target sample rate
            resampled_data = resampy.resample(processed_data, original_sr, TARGET_SAMPLE_RATE)
            print(f"DEBUG: Resampled audio - shape: {resampled_data.shape}")

            final_data = np.clip(resampled_data, -1.0, 1.0)

            mem_out = io.BytesIO()
            sf.write(mem_out, final_data, TARGET_SAMPLE_RATE, format='WAV', subtype='ALAW')
            audio_content = mem_out.getvalue()
            print(f"DEBUG: Final audio content size: {len(audio_content)} bytes")

            response = Response(content=audio_content, media_type="audio/wav")
            response.headers["Content-Disposition"] = f"attachment; filename={f'{base_filename}_alaw.wav'}"
            return response
        except Exception as e:
            import traceback
            print(f"Audio transcoding error: {e}")
            print("Full traceback:")
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=f"Audio transcoding failed: {e}")
        finally:
            os.remove(output_path_container)
    else:
        raise HTTPException(status_code=500, detail="TTS completed but output file was not found.")

# --- IV2US Configuration Functions ---
def load_iv2us_voices_config() -> Dict[str, Dict[str, Dict[str, str]]]:
    """Loads the IV2US voice metadata from the external JSON configuration file."""
    if not os.path.exists(IV2US_VOICES_CONFIG_FILE_PATH):
        print(f"WARNING: IV2US voices config file not found at '{IV2US_VOICES_CONFIG_FILE_PATH}'. No IV2US voices will be loaded.")
        return {}
    try:
        with open(IV2US_VOICES_CONFIG_FILE_PATH, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"ERROR: Failed to read or parse IV2US voices config file '{IV2US_VOICES_CONFIG_FILE_PATH}': {e}")
        return {}

IV2US_AVAILABLE_VOICES: List[Dict[str, Any]] = []

def discover_iv2us_voices():
    """Scans the IV2US config file and updates the IV2US_AVAILABLE_VOICES list."""
    global IV2US_AVAILABLE_VOICES
    print("Refreshing IV2US voice list...")
    iv2us_config = load_iv2us_voices_config()

    if not iv2us_config:
        print("WARNING: No IV2US voices configuration found.")
        IV2US_AVAILABLE_VOICES = []
        return

    discovered = []

    for language_code, gender_voices in iv2us_config.items():
        for gender, voices in gender_voices.items():
            for voice_id, voice_name in voices.items():
                # Remove the "8k" suffix to get the base voice name for Piper
                base_voice_name = voice_id.replace("8k", "").lower()
                discovered.append({
                    "id": voice_id,
                    "name": voice_name,
                    "base_name": base_voice_name,
                    "language": language_code,
                    "gender": gender
                })

    IV2US_AVAILABLE_VOICES = sorted(discovered, key=lambda v: v['name'])
    print(f"IV2US refresh complete. Loaded {len(IV2US_AVAILABLE_VOICES)} IV2US voices.")

@app.on_event("startup")
async def startup_event():
    """On application startup, run initial discovery and start background refresh task."""
    print("Application starting up...")
    discover_voices()
    discover_iv2us_voices()
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
        discover_iv2us_voices()

# --- IV2US API Endpoints ---
@app.get("/tts/voices-iv2us", summary="Get IV2US voices", response_model=VoicesResponse)
async def get_iv2us_voices(language: Optional[str] = None, gender: Optional[str] = None):
    """Get list of available IV2US voices"""
    if not IV2US_AVAILABLE_VOICES: return {"voices": []}
    filtered_voices = IV2US_AVAILABLE_VOICES
    if language: filtered_voices = [v for v in filtered_voices if v["language"] == language]
    if gender: filtered_voices = [v for v in filtered_voices if v["gender"] == gender]
    response_list = [{"id": v["id"], "name": v["name"]} for v in filtered_voices]
    return {"voices": response_list}

@app.post("/tts/generate-iv2us", summary="Generate TTS using IV2US voice", response_class=Response)
async def generate_tts_iv2us(request: TTSRequest):
    """Generate TTS using IV2US voice configuration"""
    if not IV2US_AVAILABLE_VOICES:
        raise HTTPException(status_code=503, detail="IV2US TTS service is unavailable: no IV2US voices loaded.")

    # Find the IV2US voice by ID or name
    voice_id_to_find = request.name if request.name else DEFAULT_VOICE_NAME
    selected_iv2us_voice = None

    # Try to find by ID first
    selected_iv2us_voice = next((v for v in IV2US_AVAILABLE_VOICES if v["id"] == voice_id_to_find), None)

    # If not found by ID, try to find by name
    if not selected_iv2us_voice:
        selected_iv2us_voice = next((v for v in IV2US_AVAILABLE_VOICES if v["name"].lower() == voice_id_to_find.lower()), None)

    # If still not found, try to match based on language
    if not selected_iv2us_voice:
        matching_voices = [v for v in IV2US_AVAILABLE_VOICES if request.language.split('-')[0] in v["language"].lower()]
        if matching_voices:
            selected_iv2us_voice = matching_voices[0]
        else:
            selected_iv2us_voice = IV2US_AVAILABLE_VOICES[0] if IV2US_AVAILABLE_VOICES else None

    if not selected_iv2us_voice:
        raise HTTPException(status_code=400, detail=f"IV2US voice with ID/name '{voice_id_to_find}' not found.")

    # Map IV2US voice to Piper voice
    piper_voice_name = selected_iv2us_voice["base_name"].capitalize()
    selected_piper_voice = next((v for v in AVAILABLE_VOICES if v["name"] == piper_voice_name), None)

    if not selected_piper_voice:
        raise HTTPException(status_code=400, detail=f"Corresponding Piper voice for IV2US voice '{selected_iv2us_voice['name']}' not found.")

    # Use the Piper voice to generate TTS
    return await generate_piper_tts_with_microsoft_params(request)

# Remove the Microsoft TTS function since we're only using Piper with converted parameters
async def generate_microsoft_tts(request: TTSRequest):
    # This function is kept for potential future use but not called by default
    pass
