# SmartDesktop — Models Directory

Place any custom Porcupine wake word model files (`.ppn`) in this directory.

## Custom Wake Words

Porcupine's free tier includes several built-in wake words (e.g. "jarvis",
"computer", "hey siri"). To train a **custom wake word**:

1. Go to https://console.picovoice.ai/
2. Select **Porcupine** → **Train Wake Word**
3. Download the `.ppn` model file
4. Place it here and reference it in `config.yaml`:

```yaml
wakeword:
  custom_model_path: models/my-wake-word_en_mac.ppn
```
