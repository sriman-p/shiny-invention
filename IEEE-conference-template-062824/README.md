# ReqLens IEEE Paper

This folder is self-contained for the paper source. Compile from this directory:

```sh
pdflatex paper.tex
pdflatex paper.tex
```

or:

```sh
latexmk -pdf paper.tex
```

The main manuscript is `paper.tex`. The original template filename,
`IEEE-conference-template-062824.tex`, is kept as a compatibility wrapper that
inputs `paper.tex`.

Local assets required by the paper:

- `IEEEtran.cls`
- `figures/architecture.png`
- `figures/pipeline_flow.png`
- `figures/eval_matrix_traceability.png`
- `figures/strategy_comparison.png`
- `figures/statistical_summary.png`
