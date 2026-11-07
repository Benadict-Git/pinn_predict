# Physics-Informed Neural Network (PINN) for Regional Groundwater Forecasting
### Multi-Decadal Groundwater Level Prediction & Parameter Inversion across Tamil Nadu, India

[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/)
[![PyTorch 2.x](https://img.shields.io/badge/PyTorch-2.x-ee4c2c.svg)](https://pytorch.org/)
[![Dataset: 4.58M Rows](https://img.shields.io/badge/Dataset-4.58M%20Rows-green.svg)](data/processed/DATA_DICTIONARY.md)
[![Model Size: 14k Params](https://img.shields.io/badge/Model%20Size-14k%20Params%20(56KB)-purple.svg)](notebooks/pinn_train.ipynb)
[![Status: Record Benchmark Wins](https://img.shields.io/badge/Benchmark-Beats%20Both%20Baselines-brightgreen.svg)](STATUS.md)

---

## 📌 Executive Summary

Groundwater level forecasting across semi-arid fractured hard-rock aquifers is one of the most critical challenges in regional hydrogeology. In peninsular India (Tamil Nadu), groundwater dynamics are governed by erratic monsoonal precipitation, deep topographical variation, and intensive agricultural pumping across millions of unmetered borewells.

This repository implements an **Anchored Residual Neural Network with Physical Decoupling** to predict water table depth $h(x, y, t)$ across all 38 districts of Tamil Nadu. Integrating **54 years of hydro-meteorological data (1972–2026, 4.58 million records)** from 3,391 monitoring wells, the model resolves long-standing baseline stagnation in regional hydrological machine learning:

* **Primary Forecast Benchmark (1.2-Year Horizon):** Achieves **5.057 m RMSE** vs. the **5.500 m Persistence Baseline** (**-0.443 m margin of victory**; beats persistence on **75.6% of individual monitoring wells**).
* **Secondary Spatial Benchmark (Held-Out Wells):** Achieves **10.668 m RMSE** vs. the **11.573 m 5-kNN Baseline** (**-0.905 m margin of victory** across 3 out of 3 random seeds).
* **Core Scientific Discovery:** Physical PDE loss regularizers ($W_{\text{PDE}}$) parameterized with uncalibrated empirical proxy fluxes ($R, Q$) introduce synthetic gradient conflict during joint training. **Decoupling physics ($W_{\text{PDE}} = 0.0$)** yields superior predictive accuracy while reducing training runtime by 68%.

---

## 📑 Table of Contents
1. [What is This Project?](#1-what-is-this-project)
2. [The Governing Hydrogeological Physics](#2-the-governing-hydrogeological-physics)
3. [What Was Used (Data, Hardware, Software)](#3-what-was-used)
4. [Neural Network Architecture Specification](#4-neural-network-architecture-specification)
5. [Key Challenges Faced & How They Were Resolved](#5-key-challenges-faced--how-they-were-resolved)
6. [Complete Glossary & Acronyms](#6-complete-glossary--acronyms)
7. [Hyperparameters & Configuration Reference](#7-hyperparameters--configuration-reference)
8. [Benchmark Results & Visualizations](#8-benchmark-results--visualizations)
9. [Repository Layout](#9-repository-layout)
10. [Quick Start & Reproduction](#10-quick-start--reproduction)

---

## 1. What is This Project?

Traditional regional groundwater prediction relies on either:
1. **Numerical Differential Solvers (e.g., MODFLOW):** Highly rigorous, but require boundary conditions, hydraulic conductivity rasters, and pumping logs that do not exist at state-wide scales.
2. **Pure Data-Driven Black-Box Models (LSTMs, Gradient Boosting):** Overfit local well noise, fail to extrapolate across drought years, and lack spatial physical coherence.

This project investigates the deployment of **Physics-Informed Neural Networks (PINNs)** to bridge this divide. The system predicts water table depth $h$ across Tamil Nadu and explores the inverse-problem identification of district-level storativity ($S$) and transmissivity ($T$). Across 44 empirical research runs, we identify the exact failure modes of joint PINN training on uncalibrated empirical data and establish a winning **decoupled residual architecture** suitable for operational water resource management.

---

## 2. The Governing Hydrogeological Physics

Groundwater dynamics in a two-dimensional horizontal unconfined aquifer are governed by the **Boussinesq equation**:

$$S(x, y) \frac{\partial h}{\partial t} = \nabla \cdot \big(T(x, y) \nabla h\big) + R(x, y, t) - Q(x, y, t)$$

Rearranged as a partial differential equation (PDE) residual:

$$\mathcal{R}_{\text{PDE}} = S_d \left(-\frac{\partial h}{\partial t}\right) - \kappa_{\text{scale}} T_d \left(\frac{\partial^2 h}{\partial x^2} + \frac{\partial^2 h}{\partial y^2}\right) - R + Q = 0$$

### Physical Variables:
* $h(x, y, t)$: Depth to water table below ground surface (meters; positive = deeper). Absolute hydraulic head is $H(x, y, t) = z_{\text{surf}}(x, y) - h(x, y, t)$.
* $S(x, y)$: Dimensionless aquifer storativity (specific yield), parameterized per district as $S_d = \text{softplus}(S_{\text{raw}}[d]) > 0$.
* $T(x, y)$: Aquifer transmissivity ($\text{m}^2/\text{day}$), parameterized per district as $T_d = \text{softplus}(T_{\text{raw}}[d]) > 0$.
* $R(x, y, t)$: Diffuse net recharge ($\text{mm}/\text{day}$ proxy), derived from daily rainfall and relative humidity deficit.
* $Q(x, y, t)$: Extraction sink (relative $[0, 1]$ index), derived from agricultural tube-well and irrigated area censuses.
* $\kappa_{\text{scale}} = 10^{10}$: Empirical Laplacian magnification factor required to overcome the spatial coordinate scale shrinkage across Tamil Nadu's 700 km territorial width.

---

## 3. What Was Used

### 3.1 Data Inventory (4,578,824 Cleaned Observations)
| Dataset Source | Temporal Coverage | Raw Records | Stations | Physical Role & Extraction Method |
|---|---|---|---|---|
| **NWIC Manual GWL** | 1972 – 2020 | 1,093,251 rows | 2,527 wells | Historical quarterly tape measurements of water depth ($h$). |
| **NWIC Telemetry GWL** | 2000 – 2026 | 3,485,573 rows | 849 piezometers | High-frequency 6-hourly pressure transducer readings (sign-inverted). |
| **IMD / NWIC Rainfall** | 1972 – 2026 | Daily / Hourly | 145 telemetry | Surface precipitation rate ($P$) feeding recharge proxy ($R$). |
| **NWIC Humidity (RH)** | 2021 – 2026 | Hourly | 45 stations | Relative humidity used to estimate atmospheric evapotranspiration deficit. |
| **Rajya Sabha / CGWB** | 2018 – 2019 Snapshot | 38 districts | Census snapshot | Irrigated acreage and energized well counts feeding pumping proxy ($Q$). |
| **SRTM 30m Global DEM** | Static | 4,023 coords | OpenTopoData API | Ground surface elevation ($z_{\text{surf}}$) for depth-to-head mapping. |

### 3.2 Dataset Storage Footprint
* **Raw Downloaded Archives (`data/raw/`):** **1.3 GB** (36 raw CSV files from NWIC, IMD, and data.gov.in).
* **Processed Outputs (`data/processed/`):** **759 MB** (Cleaned tables, including `observations.csv` at 368 MB and `groundwater_level.csv` at 375 MB).
* **Total Storage on Disk:** **~2.1 GB**.

### 3.3 Hardware & Software Stack
* **Software:** Python 3.11, PyTorch 2.x, Pandas 3.x, NumPy 2.x, Matplotlib 3.x, Requests.
* **Compute Infrastructure:** 
  * **Kaggle GPU (Tesla P100 / T4):** Production multi-seed benchmark batteries (~13 minutes per 3-seed run).
  * **Local Workstation CPU:** Fast plumbing integration tests and ablation harnesses (`scripts/run_smoke_test.py`, ~6 minutes for 5,000 epochs).

---

## 4. Neural Network Architecture Specification

The network is a specialized, compact **Residual Multi-Layer Perceptron (MLP)** with entity embeddings and learnable output scaling.

```
                                  INPUT VECTOR (17 Features)
  ┌────────────────────────────────────────────────────────────────────────────────────────┐
  │ 1. Coordinates:            [ x_norm, y_norm, t_norm ]                         (3 dims) │
  │ 2. Harmonic Seasonality:   [ sin(2πt/365.25), cos(2πt/365.25) ]               (2 dims) │
  │ 3. Hydrological Covariates:[ elev_norm, R_norm, Q_norm ]                      (3 dims) │
  │ 4. Pre-Cutoff Anchor:      [ h0_norm ] (90-day rolling mean well water level) (1 dim)  │
  │ 5. District Representation:[ e_d ] (Entity Embedding for 38 districts)       (8 dims) │
  └───────────────────────────────────────────┬────────────────────────────────────────────┘
                                              │
                                              ▼
                               ┌─────────────────────────────┐
                               │ Linear(17 → 64)  +  SiLU()  │
                               │ Linear(64 → 64)  +  SiLU()  │
                               │ Linear(64 → 64)  +  SiLU()  │
                               │ Linear(64 → 64)  +  SiLU()  │
                               │ Linear(64 → 1)              │
                               └──────────────┬──────────────┘
                                              │
                                              ▼
                                 Raw Residual Deviation (Δ)
                                              │
                                              ▼
                                 Trainable Delta Shrinkage:
                                   α = softplus(log_alpha)
                                              │
                                              ▼
                         Final Prediction:  h_pred = h0 + α · Δ
```

### 4.1 Parameter Accounting (14,078 Total Parameters)
* **District Embeddings:** 38 districts $\times$ 8 dimensions = **304** parameters.
* **Input Layer:** $17 \times 64 + 64$ = **1,152** parameters.
* **Hidden Layers (3):** $3 \times (64 \times 64 + 64)$ = **12,480** parameters.
* **Output Projection:** $64 \times 1 + 1$ = **65** parameters.
* **Physical & Scaling Scalars:** $S_{\text{raw}}$ (38) + $T_{\text{raw}}$ (38) + $\log \alpha$ (1) = **77** parameters.
* **Total Model Weight Footprint:** **~56 KB** on disk.

### 4.2 Key Architectural Mechanisms
1. **Residual-from-Anchor Formulation ($h = h_0 + \alpha \Delta$):** Rather than predicting absolute depth from scratch, the network predicts the seasonal deviation from each well's 90-day pre-cutoff rolling mean $h_0$. At step zero ($\text{MLP} \approx 0$), the model naturally matches persistence ($5.48\text{ m}$ RMSE), dedicating its entire gradient budget to learning dynamic trends.
2. **Trainable Delta Shrinkage ($\alpha \approx 0.35$):** Multiplies the raw MLP deviation by a bounded positive scalar $\alpha = \text{softplus}(\log \alpha)$. Corrects the neural network's empirical tendency to overshoot seasonal amplitudes.
3. **Anchor Dropout ($p_{\text{drop}} = 0.30$):** Randomly zeroes $h_0$ during training on 30% of rows. Enables dual operational inference: anchored forecasting when historical well data exists, and absolute spatial interpolation when evaluating ungauged coordinates.
4. **SiLU Activation Function:** Replaced $\tanh$. Because $\tanh''(0) = 0$, $L_2$ weight decay caused the autograd Laplacian to vanish. $\text{SiLU}''(0) = 0.5 \neq 0$, preserving second-order curvature gradients.

---

## 5. Key Challenges Faced & How They Were Resolved

```
========================================================================================================================
CHALLENGE ENCOUNTERED                    ROOT CAUSE IDENTIFIED                     ENGINEERING RESOLUTION
========================================================================================================================
1. The Head Target Failure               Ground elevation variance (std=204m)      Switched network target to normalized
   (Runs 1–6)                            was 373x larger than depth (std=10.5m),   depth h. Elevation is provided as an input
                                         blinding loss gradients to depth error.   covariate, restoring gradient sensitivity.

2. Frozen Transmissivity T               Chain-rule spatial shrinkage across       Swapped Tanh for SiLU (SiLU''(0) != 0) and
   (Runs 7–11)                           700 km domain compressed Laplacian        calibrated an empirical Laplacian multiplier
                                         to ~1e-11, yielding zero gradients.       (kappa_scale = 10^10).

3. Telemetry Sign Inversion              Digital piezometers measure hydrostatic   Applied exact sign negation (-raw) to all
   (Data Cleaning)                       pressure; manual logs measure depth       telemetry records, reconciling distribution
                                         below ground.                             medians with historical manual series.

4. 181 Station Name Collisions           Identical village names recur across      Constructed composite unique primary keys:
   (Data Cleaning)                       completely unrelated districts.           (Station_Name, LGD_District_Code).

5. The Persistence Baseline Barrier      MLP learned the correct oscillation       Implemented Delta Shrinkage (alpha ~ 0.35)
   (Runs 12–30)                          direction but overshot magnitude by 3x    and a 90-day pre-cutoff rolling anchor.
                                         (RMS delta ~ 6m vs 2m true shifts).       Forecast RMSE dropped from 6.12m to 5.057m.

6. Gradient Waste under Year-Weights     Weighting by inverse rows per year        Adopted uniform random batch sampling, shifting
   (Runs 21–25)                          gave modern telemetry (69% of data)       69% of gradient to modern telemetry and
                                         only 7.5% of training gradient.           improving spatial RMSE by 0.88m.

7. Runaway Temporal Extrapolation        Without periodic boundaries, MLPs         Engineered Fourier harmonic features:
   (Runs 39–41)                          extrapolate time linearly, predicting     [sin(2πt/365.25), cos(2πt/365.25)]. Prevented
                                         100m+ drawdowns in future windows.        extrapolation blowups (11.07m -> 5.80m).

8. Uncalibrated Proxy PDE Conflict       R and Q lack true volumetric units;       Decoupled physics: trained predictive model
   (Runs 36–38)                          PDE acted as synthetic gradient noise     with W_PDE = 0.0; preserved S and T estimation
                                         that corrupted observational fitting.     as a post-hoc diagnostic inversion stage.
========================================================================================================================
```

---

## 6. Complete Glossary & Acronyms

* **PINN (Physics-Informed Neural Network):** A neural network trained with a composite loss function penalizing both observational data error and differential equation residuals.
* **PDE (Partial Differential Equation):** A mathematical equation describing relationships between multivariable functions and their partial derivatives (e.g., groundwater flow in space and time).
* **$h$ (Water Table Depth):** Distance in meters from the ground surface down to the water table. Positive values indicate deeper water.
* **$H$ (Hydraulic Head):** Mechanical energy per unit weight of fluid ($H = z_{\text{surf}} - h$), measuring potential energy above mean sea level.
* **$S$ (Storativity / Storage Coefficient):** The volume of water an unconfined aquifer releases from storage per unit surface area per unit decline in head.
* **$T$ (Transmissivity):** The rate at which groundwater flows horizontally through a unit width of aquifer under a unit hydraulic gradient ($m^2/\text{day}$).
* **$R$ (Recharge Proxy):** Net downward infiltration reaching the water table after accounting for evapotranspiration losses.
* **$Q$ (Pumping Proxy):** Net abstraction rate representing groundwater extracted for agriculture, industry, and domestic consumption.
* **NWIC (National Water Informatics Centre):** Apex Indian government repository for automated telemetry and hydrological data.
* **CGWB (Central Ground Water Board):** National authority responsible for groundwater monitoring and aquifer mapping in India.
* **IMD (India Meteorological Department):** National agency providing official daily precipitation and climatological datasets.
* **LGD Code (Local Government Directory):** Standardized census code assigned to administrative districts in India, resolving spelling and reorganization ambiguities.
* **DEM / SRTM (Digital Elevation Model / Shuttle Radar Topography Mission):** High-resolution global satellite elevation raster providing ground surface elevation ($z_{\text{surf}}$).
* **SiLU (Sigmoid Linear Unit / Swish):** Activation function $f(z) = z / (1 + e^{-z})$ possessing smooth non-zero second derivatives.
* **Persistence Baseline:** The baseline prediction assuming future water level equals the well's last recorded measurement before the forecast cutoff.
* **kNN (k-Nearest Neighbors):** Baseline spatial interpolation estimating depth at an unknown location via inverse-distance weighted averaging of known well means.
* **Autograd:** PyTorch's automatic differentiation engine computing exact partial derivatives ($\partial h / \partial t$, $\nabla^2 h$) via backpropagation.

---

## 7. Hyperparameters & Configuration Reference

Every parameter in `notebooks/pinn_train.ipynb` was calibrated through empirical ablation:

| Parameter Name | Settled Value | Engineering Rationale & Justification |
|---|---|---|
| `W_DATA` | `1.0` | Primary objective weight penalizing mean squared error against observed well readings. |
| `W_DELTA` | `1e-2` | Regularization penalty shrinking the learned deviation $\Delta$ toward zero unless justified by data. |
| `W_IC` | `1.0` | Initial condition loss ensuring temporal consistency at the earliest training boundaries. |
| `W_PDE` | `0.0` | **Winning ablation.** Setting to $0.0$ decouples uncalibrated proxy PDE noise, unlocking record accuracy. |
| `USE_ALPHA_SCALE` | `True` | Learnable shrinkage parameter $\alpha = \text{softplus}(\log \alpha)$, initialized at $\log(0.30)$. |
| `H0_ANCHOR_DAYS` | `90` | Replaced single last-observation anchor with 90-day pre-cutoff rolling mean, smoothing measurement noise. |
| `USE_SEASONAL` | `True` | Annual harmonic encodings $[\sin, \cos]$. Disabling doubles forecast error from 5.80 m to 11.07 m. |
| `USE_API` | `False` | Antecedent Precipitation Index. Coarse district aggregations added noise (+0.696 m error); omitted. |
| `USE_TEMPORAL_WEIGHTS` | `False` | Uniform batch sampling. Overcame calendar-year weighting that starved modern telemetry of gradient. |
| `H0_DROPOUT_P` | `0.30` | 30% anchor dropout rate forcing the network to maintain unanchored spatial interpolation capabilities. |
| `LAPLACIAN_SCALE` | `1e10` | Magnification multiplier overcoming spatial coordinate shrinkage to allow transmissivity $T$ to learn. |
| `N_EPOCHS_ADAM` | `10000` | Halved from 20,000 based on loss diagnostics proving data loss reaches an asymptotic floor by epoch 8,500. |
| `ADAM_LR` | `1e-3` | Initial learning rate; decays by factor of 0.5 at epoch 5,000 via StepLR. |
| `WEIGHT_DECAY` | `3e-4` | $L_2$ regularization on MLP weights preventing memorization of individual station coordinates. |
| `BATCH_SIZE_DATA` | `4096` | Mini-batch draw per epoch from observation tensors. |
| `BATCH_SIZE_COLLOC` | `4096` | Mini-batch draw per epoch from synthetic spatial-temporal collocation grid. |
| `SPLIT_SEED` | `0` | **Permanently pinned.** Random seed drawing the held-out spatial well benchmark. |

---

## 8. Benchmark Results & Visualizations

### 8.1 3-Seed Comparison Table (Winning Run 36–38 Battery)
All reported values represent mean $\pm$ range over three independent optimization seeds (`SEED = 0, 1, 2`):

```
========================================================================================================================
BENCHMARK TASK          OPERATIONAL BASELINE       COUPLED PINN (W_PDE=1e-4)   WINNING DECOUPLED (W_PDE=0.0)    MARGIN
========================================================================================================================
Spatial Task (RMSE)     11.573 m (5-kNN)           11.552 ± 0.412 m            10.668 ± 0.608 m                 -0.905 m (Wins)
Spatial Task (MAE)       6.352 m (5-kNN)            6.410 ± 0.220 m             6.053 ± 0.298 m                 -0.299 m (Wins)
Forecast Task (RMSE)     5.500 m (Persistence)      5.803 ± 0.320 m             5.057 ± 0.070 m                 -0.443 m (Wins)
Forecast Task (MAE)      2.473 m (Persistence)      3.076 ± 0.180 m             2.391 ± 0.040 m                 -0.082 m (Wins)
Well Win Rate            0.0% vs Persistence       44.2% ± 3.1%                75.6% ± 1.3%                    +31.4% (527/699)
Training Runtime         --                         19.2 min                    6.1 min                         -68.2% (Faster)
========================================================================================================================
```

### 8.2 Visual Diagnostics (Generated from Winning Run 36)

#### Training Convergence (Loss Curves)
![Loss Curves](kaggle/results/run36_local_wpde0_ablation/loss_curves.png)
*Figure 1: Adam optimization convergence across 5,000 epochs showing stable minimization of data loss across anchored and dropped regimes.*

#### Parity Plots (Predicted vs. Actual)
![Parity Plots](kaggle/results/run36_local_wpde0_ablation/pred_vs_actual.png)
*Figure 2: Parity plots of predicted vs. true water table depth (meters) for the Primary Forecast Task (left, RMSE 5.09 m) and Secondary Spatial Task (right, RMSE 10.45 m).*

#### Continuous Spatial Groundwater Contours
![Spatial Maps](kaggle/results/run36_local_wpde0_ablation/spatial_maps.png)
*Figure 3: Spatially continuous depth contours predicted across Tamil Nadu at different time quantiles, correctly capturing deep water tables inland and shallow water tables in the coastal Cauvery delta.*

---

## 9. Repository Layout

```
pinn_predict/
├── README.md                  # Comprehensive technical documentation (this file)
├── AGENTS.md                  # Critical project conventions, gotchas, and execution orders
├── STATUS.md                  # Single source of truth: 44-run chronological research log
│
├── data/
│   ├── raw/                   # Original 36 downloaded CSV datasets (1.3 GB)
│   └── processed/             # Cleaned harmonized datasets (759 MB)
│       ├── observations.csv   # Master training dataset (4.58M rows, 368 MB)
│       ├── collocation.csv    # 51,300-point synthetic spatiotemporal PDE grid
│       ├── district_name_mapping.csv # 38 canonical districts mapped via LGD codes
│       ├── station_table.csv  # 3,391 unique stations keyed on (Station, District)
│       └── DATA_DICTIONARY.md # Column-by-column definitions, units, and limitations
│
├── notebooks/
│   └── pinn_train.ipynb       # Self-contained Phase 2 training notebook (Kaggle/Colab)
│
├── scripts/
│   ├── clean_*.py, build_*.py # Standalone Phase 1 data engineering scripts
│   ├── merge_datasets.py      # Pipeline script producing observations.csv
│   ├── run_local_train.py     # Local execution harness for pinn_train.ipynb
│   ├── run_seed_battery.py    # Remote Kaggle push, polling, and metric extraction
│   ├── run_smoke_test.py      # Rapid 5-epoch plumbing and gradient verification harness
│   └── generate_documentary_pdf.py # Automated PDF/Word documentation compiler
│
├── docs/
│   ├── PINN_Groundwater_Neural_Network_Documentary.pdf  # 8-page formatted PDF report
│   └── PINN_Groundwater_Neural_Network_Documentary.docx # Formatted Word source
│
├── paper/
│   ├── conference_paper.md    # Full academic conference paper manuscript
│   └── main.tex               # IEEEtran conference LaTeX template source
│
└── kaggle/
    └── results/               # Archived metrics, weights, and plots for Runs 1 to 44
```

---

## 10. Quick Start & Reproduction

### 1. Environment Setup
```bash
# Clone the repository
git clone https://github.com/your-username/pinn_predict.git
cd pinn_predict

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install required dependencies
pip install torch pandas numpy matplotlib requests
```

### 2. Verify Pipeline Plumbing (5-Epoch CPU Smoke Test)
```bash
source .venv/bin/activate
python scripts/run_smoke_test.py
```

### 3. Run Local Training
```bash
# Execute winning decoupled model (W_PDE = 0.0, Seed 0)
python scripts/run_local_train.py --run-name run36_reproduced --w-pde 0.0 --epochs 5000 --seed 0
```

### 4. Push 3-Seed Production Battery to Kaggle GPU
```bash
# Automated stage, push, monitor, and pull results
python scripts/run_seed_battery.py --run-name run36_kaggle_battery --w-pde 0.0 --seeds 0 1 2
```

---

## 📄 License & Citation
This project is open-source under the MIT License. If referencing this work in academic research, please cite:
```bibtex
@article{infanta2026decoupled,
  title={Decoupled Physics-Informed Residual Networks for Regional Groundwater Forecasting: When Does Physical Regularization Help?},
  author={Infanta, Benadict and Hydroinformatics Research Group},
  journal={Tamil Nadu Groundwater Modeling Technical Reference},
  year={2026}
}
```
