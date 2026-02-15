#!/usr/bin/env python3
"""
Script to generate voices_config.json based on available .onnx files in /opt/voices
This script is designed to run during container startup to automatically
configure Piper TTS with all available voice models.
"""

import os
import json

def generate_voices_config():
    """Generate voices_config.json based on available .onnx files"""
    voices_dir = "/opt/voices"
    config = {}

    # Discover language and gender information dynamically from filenames
    # Pattern: {lang}_{COUNTRY}-{voice_name}-{quality}.onnx
    # Example: fr_FR-siwis-medium.onnx -> French, voice: siwis

    # Common gender patterns in voice names (can be extended)
    female_patterns = {'siwis', 'alba', 'sharvard', 'paola', 'mls'}
    male_patterns = {'upmc', 'alan', 'davefx', 'tom'}

    # Check which voices actually exist in the voices directory
    for filename in os.listdir(voices_dir):
        if filename.endswith(".onnx"):
            try:
                # Extract components from filename (format: lang_COUNTRY-voice-quality.onnx)
                parts = filename.split('-')
                if len(parts) >= 2:
                    # Get voice name (second part)
                    voice_name = parts[1].lower()

                    # Extract language from first part (format: lang_COUNTRY)
                    lang_part = parts[0]
                    if '_' in lang_part:
                        lang_code = lang_part.replace('_', '-')  # e.g., fr_FR -> fr-FR
                    else:
                        # Fallback for simple language codes
                        lang_code = f"{lang_part}-{lang_part.upper()}"

                    # Determine gender based on voice name patterns
                    if voice_name in female_patterns:
                        gender = "female"
                    elif voice_name in male_patterns:
                        gender = "male"
                    else:
                        gender = "unknown"
                        print(f"Warning: Unknown gender for voice '{voice_name}', using 'unknown'")

                    config[voice_name] = {
                        "gender": gender,
                        "language_code": lang_code
                    }
                    print(f"Discovered voice: {voice_name} ({gender}, {lang_code})")
            except Exception as e:
                print(f"Warning: Could not process {filename}: {e}")
                continue

    # Write configuration file
    config_path = os.path.join(voices_dir, "voices_config.json")
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)

    print(f"Generated voices config with {len(config)} voices")

if __name__ == "__main__":
    generate_voices_config()