# Piper TTS API with Microsoft-Compatible Parameters

This API accepts Microsoft TTS parameters and converts them to Piper TTS parameters for local voice generation.

## Endpoints

### POST /tts/generate

Generate speech from text using Piper TTS with Microsoft-style parameters.

#### Parameters

The API accepts Microsoft TTS parameters and converts them for use with Piper TTS:

**Microsoft TTS Parameters (converted for Piper):**
- `api`: Engine to use (default: "piper", only "piper" is supported in this version)
- `url`: Microsoft TTS endpoint URL (not used in Piper mode)
- `language`: Language code for voice selection (default: "fr-FR")
- `voice`: Voice name for language matching (default: "fr-FR-DeniseNeural")
- `key`: Microsoft API key (not used in Piper mode)
- `ssml`: Whether to use SSML (not directly used by Piper but can be processed)
- `checkbreak`: Check break parameter (not used by Piper)
- `rate`: Speech rate (converted to Piper's length_scale: 1/rate)
- `pitch`: Pitch adjustment (not directly supported by Piper)
- `style`: Voice style (not directly supported by Piper)
- `styledegree`: Style degree (not directly supported by Piper)
- `format`: Output format (default: "wav")

**Piper TTS Parameters (passed through):**
- `text`: Text to convert to speech (required)
- `name`: Voice name (optional, defaults to "Siwis")
- `length_scale`: Phoneme length (speed) (default: 1.0)
- `noise_scale`: Generator noise (default: 0.67)
- `noise_w`: Phoneme width noise (default: 0.8)
- `amplification`: Linear amplification (default: 1.0)
- `speaker`: Speaker ID for multi-speaker models (default: 0)
- `sentence_silence`: Seconds of silence after each sentence (default: 0.2)

#### Parameter Conversion

The API automatically converts Microsoft TTS parameters to their Piper equivalents:
- `rate` → `length_scale` (rate of 1.2 becomes length_scale of 1/1.2 ≈ 0.83 for faster speech)
- `language` and `voice` → voice selection based on language matching
- `amplification`, `text`, and other parameters are passed through directly

#### Examples

**Microsoft-Compatible TTS Request (converted to Piper):**
```json
{
  "api": "piper",
  "language": "fr-FR",
  "voice": "fr-FR-DeniseNeural",
  "rate": 1.0,
  "pitch": "+2st",
  "style": "cheerful",
  "styledegree": "1.5",
  "format": "wav",
  "text": "Bonjour, ceci est un test de conversion des paramètres.",
  "name": "Siwis",
  "amplification": 1.2
}
```

### GET /tts/voices

Get available Piper voices.

## Supported Output Formats

- **Piper TTS**: Outputs wav format (with a-law encoding at 8kHz)

## Voice Matching

When a specific voice name (`name`) is not provided, the system will attempt to match based on:
1. The `language` parameter (e.g., "fr-FR" will look for French voices)
2. The `voice` parameter (e.g., "fr-FR-DeniseNeural" will look for French voices)
