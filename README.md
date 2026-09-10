# SIH26168 — Intelligent Dead Reckoning for GNSS-Denied Navigation

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**ISRO • Software • SIH26168**

## Clone and Use (30 seconds)

**Just want the app? No build needed:**

```bash
git clone https://github.com/harshsavnerkar/SIH_NITRIX.git
cd SIH_NITRIX
adb install releases/sih26168-debug.apk   # or drag the APK to your phone
# Open NitrixNav on phone → grant Location → map centers on you
```

The APK (`releases/sih26168-debug.apk` 66M, also at `android/app/build/`) already contains the trained `model.tflite` + `scaler.json`. No Python, no training needed to try it.

**Build from source:**

```bash
git clone https://github.com/harshsavnerkar/SIH_NITRIX.git
cd SIH_NITRIX
# Android: open android/ in Android Studio Hedgehog (JDK 17) → Run
# Python (optional, to retrain): see "Run it" below
```

## What this is

An app that keeps telling you where you are when GPS stops working.

When you drive through a tunnel, an underpass, or into a basement parking lot, GPS drops out. A regular phone's motion sensors are too noisy to fill the gap on their own — position drifts hundreds of meters within a minute.

This project uses the phone's motion sensors plus an AI model to predict how fast you're going, then fuses that with a map so the position error stays under 5% over 1 km. No car hardware, no OBD-II — just the phone.

## How it works & Key Features

1. **High-Hz Sensor Pipeline**: Streams motion sensors (accel + gyro at 100 Hz; mag at 50 Hz).
2. **Uncertainty-Aware AI Model**: **AVNetLite** (460k parameters, <1 MB) reads 2s windows and predicts forward speed $v_{ai}$ alongside learned uncertainty $\sigma_v$.
3. **Exact Lie-Group Filter**: 21-DOF right-invariant filter on $SE_2(3)$ with exact $\Phi(F\Delta t)$ matrix exponential propagation:
   - **Adaptive Lean & NHC**: Calculates roll angle $\phi$ for 2-wheelers ($v_{lat} = v_{fwd}\sin\phi$) and clamps lateral slide.
   - **ZUPT Error Reset**: Zero-velocity detection ($\sigma_{acc} < 0.05 \text{ m/s}^2$) clamps velocity to 0 and resets bias accumulation.
   - **Magnetic Anomaly Rejection**: Rejects local iron spikes outside Earth's $25\text{–}65\ \mu\text{T}$ field.
4. **Map-Matching & Visualization**: Snaps poses to road geometries via HMM map matching on offline OpenStreetMap tiles.
5. **Interactive Android UI & Reporting**:
   - **Dual-Color Path**: Blue path (`#0B57D0`) for active GNSS track; Red path (`#E53935`) for Dead Reckoning outage path.
   - **Red Outage Pins**: Automatic pin markers labeled `"Dead Reckoning path"` at GNSS blackout entry points.
   - **Trip Recording & Export**: Tap `[Record]` to log 100 Hz sensor/pose streams; tap `[Download trip details]` to save directly into **`Downloads/NitrixNav/`** on phone via MediaStore; tap `[Share]` for system chooser.
   - **Settings & Permissions Modal**: Inspect live magnetic field norm ($\mu\text{T}$), $SE_2(3)$ math specs, asset SHA-256 hashes, and open system permissions settings.
6. **Standalone 200 Hz Edge Engine (CLI)**: Process external FOG/MEMS IMU CSV streams on embedded hardware:
   ```bash
   python python/edge_engine.py --imu data/sample_imu.csv --hz 200 --out reports/edge_engine_poses.csv
   ```

Covers all 6 mandatory ISRO capabilities: sensor auto-alignment, AI speed filter, map matching + NHC, GNSS+INS fusion, seamless deficit handling, and UI.

## Results

Tested with GPS blocked for 60 seconds (simulated tunnel):

| Test segment | Naive (no AI) | Ours | Ours + map |
|--------------|---------------|------|------------|
| 138 m | 16.3 m off (11.8%) | **4.6 m (3.35%)** | **2.8 m (2.01%)** |
| 188 m (validation) | 16.3 m off (8.7%) | **1.87 m (0.99%)** | **1.12 m (0.59%)** |

Both pass the ISRO requirement (<10%) and our own target (<5%).

Training: 50 epochs on a Colab T4 GPU, ~7 minutes, on the [IO-VNBD dataset](https://github.com/onyekpeu/IO-VNBD) (40h vehicle + 58h phone data).

The plot judges need for screening: `reports/drift_plot.png`.

## Run it

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install pandas scipy onnx onnxruntime loguru matplotlib scikit-learn

python python/download_iovnbd.py --subset Sync                # download data
python python/preprocess.py --subset 1h --window 200 --stride 10  # prepare windows

# train (5 epochs demo; use Colab notebook for the full 50-epoch run)
PYTHONPATH=. python python/train_avnet.py --epochs 5 --batch 128 --augment-yaw --lambda-nll 0.1

# evaluate + generate drift_plot.png
PYTHONPATH=. python python/eval_drift.py --model experiments/checkpoints/model_avnet_stage1.p --plot reports/drift_plot.png

# export for the phone app
PYTHONPATH=. python python/export_tflite.py --model experiments/checkpoints/model_avnet_stage1.p --out model.tflite
```

Full 50-epoch GPU training: open `sih26168_colab.ipynb` in Colab (T4 GPU) — takes ~7 minutes and produces `screening.zip`.

## Repository layout

```
sih26168/
├── python/               # all code: training, preprocessing, evaluation, export
│   ├── models/           # AVNetLite model, lean estimator, uncertainty adapter
│   ├── utils/            # ZUPT, lie group math, metrics
│   └── datasets/         # IO-VNBD dataset loader
├── docs/
│   ├── ARCHITECTURE.md   # system design, diagrams, data flow
│   ├── DATA_INSPECTION.md    # dataset analysis
│   └── IMPROVEMENTS_FROM_COMPETITORS.md  # 13 fixes learned from other teams
├── ref/competitors/      # other teams' code, kept for reference only
├── experiments/checkpoints/  # trained model (model_avnet_stage1.p, 1.8 MB)
├── reports/drift_plot.png    # the screening deliverable
└── sih26168_colab.ipynb  # one-click GPU training
```

## References

- [Problem statement SIH26168](https://sih.gov.in)
- [AVNet paper](https://doi.org/10.1186/s43020-025-00168-7) — Qian et al., Satellite Navigation 2025 (baseline architecture)
- [IO-VNBD dataset](https://github.com/onyekpeu/IO-VNBD) — Data in Brief 35:106885 (official ISRO benchmark dataset)
- Reference implementation: `QDeepOdo` + `QAIIMUDeadReckoning` (AVNet/InEKF architecture) under `ref/`
