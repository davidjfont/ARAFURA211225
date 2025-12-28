---
company: FDFONT Global Design Labs
type: workflow
domain: innovation_systems
confidence: high
requires_human_validation: true
last_reviewed: 2025-01-02
---

# Gestió d’Errors — FDFONT Global Design Labs

## Principis generals
- Els errors són **fonts d’aprenentatge**, no fallades del sistema.
- Cap error crític s’ha de repetir sense documentació prèvia.
- La traçabilitat és obligatòria.

## Tipus d’errors
1. **Errors tècnics**
   - Bugs de codi
   - Fallades de pipeline
   - Problemes de rendiment

2. **Errors conceptuals**
   - Disseny incorrecte del sistema
   - Supòsits erronis
   - Arquitectura mal alineada amb l’objectiu

3. **Errors humans**
   - Decisions precipitades
   - Manca de validació
   - Excés de confiança

## Procediment estàndard
1. Detectar l’error
2. Classificar-lo (tècnic / conceptual / humà)
3. Documentar-lo en format MD dins `experiences/`
4. Proposar millora, **no acció automàtica**
5. Validació humana abans de canvis estructurals

## Regla d’or
Cap correcció estructural s’executa sense revisió humana explícita.