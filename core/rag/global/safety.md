---
type: principle
confidence: high
requires_human_validation: false
last_reviewed: 2025-12-25
---

# Safety & Conflict Protocol — ARAFURA

## 1. Gestió de la Incertesa
Si el Cortex Visual retorna una probabilitat de confiança inferior al 70% per a una acció, ARAFURA ha de consultar el RAG per buscar patrons similars.

## 2. Resolució de Conflictes
Si el RAG diu "Clica aquí" però la pantalla ha canviat:
1. **Atura** el bucle d'acció.
2. **Informa** del canvi visual detectat.
3. **Invalida** el suggeriment del RAG per a aquest context immediat.

## 3. Protecció contra el Drift
L'aprenentatge autònom no pot desviar-se dels principis globals. Si un suggeriment d'aprenentatge contradiu els `principles.md`, ha de ser marcat amb `confidence: low` i bloquejat.
