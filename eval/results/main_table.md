# Tabla principal — split evaluation (50 interacciones × 3 runs)

| framework | runs | arts | cov% | KCS% | ev% | simK | lat_med | lat_p90 | cost$ | tools | fail% | LOC |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| baseline_heuristic | 3 | 50.0 | 100.0 | 100 | 100 | 37 | 116.7 | 119.9 | 0.000 | 0 | 0 | 282 |
| baseline_prompt | 3 | 50.0 | 100.0 | 100 | 100 | 43 | 826.6 | 827.2 | 0.917 | 0 | 0 | 340 |
| langgraph | 3 | 52.7 | 86.7 | 100 | 100 | 41 | 17398.0 | 17724.3 | 28.098 | 1964 | 0 | 831 |
| crewai | 3 | 52.3 | 98.7 | 100 | 96 | 42 | 15742.2 | 16507.1 | 27.060 | 687 | 0 | 932 |
| openai_agents | 3 | 57.0 | 99.3 | 100 | 100 | 40 | 14863.2 | 15382.1 | 27.169 | 1206 | 0 | 803 |
