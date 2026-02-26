# MOR41 / STO-3G paper artifacts

## Figures

**Fig 1 — Qubit reduction from active-space selection.**  
Full-system qubit counts (dry-run) vs the paper benchmark active space (H2 full; CO/CO2 in a compact active space). The dashed line marks max_qubits=16 used for benchmark gating.

**Fig 2 — Active-space VQE accuracy vs exact.**  
Absolute energy error |E_VQE − E_exact| in kcal/mol on a log scale. The dashed line marks “chemical accuracy” (1 kcal/mol). CO and CO2 are within chemical accuracy in the chosen active space.

**Fig 3 — QM/MM embedding shift consistency (point-charge demo).**  
Scatter of embedding energy shift ΔE = E(QM/MM) − E(QM) computed by exact vs VQE. Points close to the y=x line indicate that VQE tracks the embedding-induced shift.

## Tables

**Table 1 — Benchmark summary (full vs active + accuracy).**  
Per record: full/active qubits, active space parameters, energies, absolute error (kcal/mol), and runtimes.

**Table 2 — QM vs QM/MM point-charge shift.**  
Per record: ΔE_exact and ΔE_VQE (kcal/mol) plus the mismatch (kcal/mol).