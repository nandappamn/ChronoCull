---
name: scientific-research
description: >-
  Conduct scientific inquiry, literature review, chemical/biological data retrieval,
  and computational analysis. Use this skill when asked to investigate scientific hypotheses,
  query databases like PubMed or arXiv, analyze molecular/genomic data, or generate
  evidence-grounded research summaries.
---

# Scientific Research Skill

Inspired by [`K-Dense-AI/scientific-agent-skills`](https://github.com/K-Dense-AI/scientific-agent-skills) and `scientific-agents`, this skill equips the agent to think and act like a senior research scientist. It establishes rigorous methodological protocols for hypothesis formulation, literature synthesis, and scientific computation.

## When to Use

- When asked to survey biomedical, chemical, genomic, or physical sciences literature.
- When retrieving data from public scientific registries (PubMed, NCBI, ChEMBL, UniProt, arXiv).
- When processing bioinformatics datasets (FASTA, PDB, SAM/BAM) or cheminformatics formats (SMILES, InChI).
- When writing structured scientific reports requiring empirical grounding and DOI citations.

---

## The Scientific Method Workflow

When addressing scientific inquiries, adhere strictly to the 4-stage empirical protocol:

### Phase 1: Problem Formulation & Hypothesis Generation
- State the research question with precise biological/chemical terminology.
- Propose testable hypotheses and identify measurable dependent/independent variables.

### Phase 2: Literature & Database Querying
Use the provided `query_pubmed.py` script or open APIs to gather peer-reviewed evidence:

```bash
# Query PubMed abstracts for a topic
python .agents/skills/scientific-research/scripts/query_pubmed.py --query "CRISPR off-target Cas9 kinetics" --max-results 5
```

### Phase 3: Computational Analysis
Utilize domain-specific Python libraries when data processing is requested:
- **Bioinformatics**: `biopython`, `scanpy`, `pysam`
- **Cheminformatics**: `rdkit`, `pubchempy`
- **Statistical Modeling**: `scipy.stats`, `statsmodels`, `pandas`

### Phase 4: Structured Reporting
Format findings into an evidence matrix:
1. **Background & Objective**
2. **Methodology / Data Sources**
3. **Key Findings & Evidence Summary (with citations)**
4. **Limitations & Open Questions**

---

## Best Practices

- **Distinguish Correlation vs. Causation**: Explicitly flag observational vs. experimental data.
- **Reference Standard Identifiers**: Use Gene Symbols (HGNC), Protein IDs (UniProt), Compound IDs (PubChem CID), and DOIs for literature.
- **No Hallucinated Citations**: Only cite verifiable papers or explicitly state when summarizing general consensus.
