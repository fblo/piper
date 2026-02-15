#!/usr/bin/env python3
"""
Script to generate voices_iv2us.json for IV2US TTS API
This script creates a configuration file in the specific IV2US format
"""

import json
import os

def generate_voices_iv2us():
    """Generate voices_iv2us.json with Piper voices in IV2US format"""
    # First, generate the Piper voices config to get the available voices
    import subprocess
    subprocess.run(["python3", "/app/generate_voices_config.py"], check=True)

    # Read the generated Piper config
    with open("/opt/voices/voices_config.json", 'r') as f:
        piper_config = json.load(f)

    # Convert Piper config to IV2US format
    iv2us_config = {}

    for voice_name, voice_info in piper_config.items():
        language_code = voice_info["language_code"]
        gender = voice_info["gender"]

        # Initialize language in IV2US config
        if language_code not in iv2us_config:
            iv2us_config[language_code] = {"male": {}, "female": {}}

        # Add voice to the appropriate gender section
        # Use voice name as ID and pretty name
        voice_id = f"{voice_name}8k"  # Add 8k suffix to match IV2US format
        voice_display_name = voice_name.capitalize()

        iv2us_config[language_code][gender][voice_id] = voice_display_name

    # Write configuration file
    config_path = os.path.join("/opt/voices", "voices_iv2us.json")
    with open(config_path, 'w') as f:
        json.dump(iv2us_config, f, indent=2)

    print(f"Generated IV2US voices config with {len(iv2us_config)} languages")
    total_voices = sum(len(lang['male']) + len(lang['female']) for lang in iv2us_config.values())
    print(f"Total voices: {total_voices}")
    print(f"Male voices: {sum(len(lang['male']) for lang in iv2us_config.values())}")
    print(f"Female voices: {sum(len(lang['female']) for lang in iv2us_config.values())}")

if __name__ == "__main__":
    generate_voices_iv2us()