# Modelos LLM Locales

Este directorio contiene modelos `.gguf` para ARAFURA local.

## Descarga de Modelos

### Opcion Ligera (~1.5GB)
```
Phi-2 Q4_K_M
https://huggingface.co/TheBloke/phi-2-GGUF/resolve/main/phi-2.Q4_K_M.gguf
```

### Opcion Balanceada (~4GB)
```
Mistral 7B Instruct v0.2 Q4_K_M
https://huggingface.co/TheBloke/Mistral-7B-Instruct-v0.2-GGUF/resolve/main/mistral-7b-instruct-v0.2.Q4_K_M.gguf
```

## Instalacion

1. Descarga el archivo `.gguf`
2. Colocalo en esta carpeta (`models/`)
3. Ejecuta: `python terminals/cli/arafura_cli.py`

ARAFURA detecta automaticamente el modelo.

## Requisitos

| Modelo | RAM minima |
|--------|------------|
| Phi-2 (1.5GB) | 4GB |
| Mistral 7B (4GB) | 8GB |

---

*Los archivos .gguf NO se suben a Git*
