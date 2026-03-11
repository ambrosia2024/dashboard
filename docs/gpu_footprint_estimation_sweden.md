# GPU Footprint Estimation (Sweden, A40)

This note documents a practical **GPU-only** estimation method for Ambrosia chatbot inference on NVIDIA A40.

## Scope

- Includes: GPU electricity use during inference.
- Excludes: CPU, RAM, networking, storage, datacenter overhead (PUE), embodied emissions.
- Cooling water is estimated using WUE assumptions.

## Inputs used (current)

- GPU: NVIDIA A40
- Observed power draw sample: `106 W` (`nvidia-smi`)
- Response latency range: `5–10 s/query`
- Datacenter country: Sweden (`SE`)

## Environment snapshot (observed)

Captured on `2026-03-05` from runtime host:

This is the host where the **Ambrosia platform is running** (application/runtime VM):

- Hostname: `vmi2758566`
- Virtualization: `KVM`
- OS: `Ubuntu 24.04.3 LTS`
- Kernel: `Linux 6.8.0-87-generic`
- CPU: `3 vCPU` (`AMD EPYC Processor`, `nproc=3`)
- RAM: `7.8 GiB total` (`~5.8 GiB available` at sample time)
- Swap: `0`
- Storage (HDD/SSD): not included in this snapshot block yet because `lsblk/df` outputs were not provided in the same sample.

GPU snapshot details:

- Driver/CUDA: `570.195.03 / CUDA 12.8`
- A40 board power at sample: `106W`
- Power cap: `300W`
- Memory usage at sample: `39014 MiB / 46068 MiB`
- Sample showed a shared GPU workload (`VLLM::EngineCore` + another Python process).
- GPU location context: Sweden (`SE`) is used for carbon-intensity assumptions.

## Formulas

### 1) Energy per query

`kWh/query = (Power_W * Latency_s) / 3,600,000`

### 2) Carbon per query

`gCO2e/query = kWh/query * CarbonIntensity_gCO2e_per_kWh`

### 3) Water per query

`L/query = kWh/query * WUE_L_per_kWh`

## Assumptions (current defaults)

### Carbon intensity (Sweden)

- Central estimate: `30 gCO2e/kWh`
- Suggested range: `18–50 gCO2e/kWh`

### Water intensity (WUE)

- Central estimate: `1.8 L/kWh`
- Suggested range: `0.5–3.0 L/kWh`

## WUE vs PUE (clarification)

These metrics are different and should be reported separately.

### WUE (Water Usage Effectiveness)

- Unit: `L/kWh`
- Meaning: liters of water used by the datacenter per kWh of IT energy.
- In this report: used for cooling-water estimation.
- Current assumption in this report: `1.8 L/kWh` (range `0.5–3.0`).

### PUE (Power Usage Effectiveness)

- Unit: ratio (e.g., `1.2`, `1.4`), not liters.
- Meaning: total facility energy divided by IT energy.
- In this report: currently **not applied**, because scope is GPU-only IT energy.
- If you later want facility-inclusive accounting:
  - `FacilityEnergy = ITEnergy * PUE`
  - Then calculate carbon/water on facility energy as needed.

## Calculated results (current)

Using `106 W` and `5–10 s`:

### Energy

- 5 s: `0.000147 kWh` (0.147 Wh)
- 10 s: `0.000294 kWh` (0.294 Wh)

### Carbon (Sweden central: 30 gCO2e/kWh)

- 5 s: `0.0044 gCO2e/query`
- 10 s: `0.0088 gCO2e/query`

Carbon range with `18–50 gCO2e/kWh`:

- 5 s: `0.0026–0.0074 gCO2e/query`
- 10 s: `0.0053–0.0147 gCO2e/query`

### Water (central WUE: 1.8 L/kWh)

- 5 s: `0.265 mL/query`
- 10 s: `0.529 mL/query`

Water range with `0.5–3.0 L/kWh`:

- 5 s: `0.074–0.441 mL/query`
- 10 s: `0.147–0.882 mL/query`

## Real-world equivalents (to interpret the numbers)

These are rough intuition aids, not exact physical equivalences.

### Energy equivalents

Per query energy (`0.147–0.294 Wh`) is approximately:

- **About 1–2% of a typical smartphone full charge** (assuming ~15 Wh battery).
- **A 1500W hair dryer running for ~0.35–0.71 seconds**.
- **A 10W LED bulb running for ~53–106 seconds**.
- **A 50W laptop running for ~11–21 seconds**.

### Carbon equivalents (Sweden central factor)

Per query carbon (`0.0044–0.0088 gCO2e`) is:

- Extremely low in absolute terms because Sweden grid intensity is low.
- Best reported as **mg CO2e/query**:
  - `4.4–8.8 mg CO2e/query` (central)
  - `2.6–14.7 mg CO2e/query` (low/high range)

### Water equivalents

Per query water (`0.265–0.529 mL`, central WUE) is approximately:

- **About 5–11 drops of water** (assuming ~0.05 mL per drop).
- Range (`0.074–0.882 mL`) is roughly **1.5–18 drops**.

## Notes on uncertainty

- Power value (`106W`) is a single observed point, not yet a per-query integrated average.
- Shared GPU means attribution is approximate unless we separate chatbot incremental load.
- WUE is assumed (`1.8 L/kWh`) until provider-specific value is available.

## Shared vs dedicated GPU accounting

Because GPU can be shared, two accounting styles are possible:

1. Marginal (recommended for shared):
   - Use incremental power attributable to chatbot load.
   - `Energy = (P_active - P_baseline_share) * time`

2. Allocated (for dedicated/cost accounting):
   - Total GPU energy in period divided by total queries.
   - Includes idle overhead.

Current numbers above are **instantaneous power-based estimates**, not full-period allocated accounting.

## Recommended reporting format

Report all three:

1. Central estimate (SE + central WUE)
2. Low/high range (carbon + WUE bands)
3. Method note (GPU-only, operational inference energy)

## Optional next step

Automate per-query sampling:

- Log query start/end timestamps.
- Sample `nvidia-smi --query-gpu=power.draw --format=csv,noheader,nounits` during each query window.
- Integrate power over time for better per-query energy estimates.
