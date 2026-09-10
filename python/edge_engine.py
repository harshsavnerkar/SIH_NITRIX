#!/usr/bin/env python3
"""
edge_engine.py — Standalone Edge-Deployable Dead Reckoning & Sensor Fusion Engine
SIH26168 Requirement: Standalone engine for edge hardware (Raspberry Pi/Jetson/Linux)
supporting external FOG/MEMS IMUs up to 200 Hz.

Usage:
  python python/edge_engine.py --imu data/sample_imu.csv --hz 100 --out output_pose.csv
"""

import sys
import time
import argparse
import numpy as np
import torch
from pathlib import Path

# Add project root to sys.path for standalone invocation
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from python.models.avnet import AVNet, AVNetLite
from python.inekf_harness import InEKF
from python.utils.zupt import StationaryDetector

class EdgeEngine:
    def __init__(self, checkpoint_path="experiments/checkpoints/model_avnet_stage1.p", hz=100):
        self.hz = hz
        self.dt = 1.0 / hz
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        
        # Load trained AVNetLite model
        self.model = AVNetLite().to(self.device)
        if Path(checkpoint_path).exists():
            ckpt = torch.load(checkpoint_path, map_location=self.device)
            self.model.load_state_dict(ckpt.get("model_state_dict", ckpt))
            print(f"[EdgeEngine] Loaded model checkpoint from {checkpoint_path}")
        self.model.eval()
        
        # Initialize InEKF (21-DOF right-invariant filter)
        R0_init = torch.eye(3, dtype=torch.float64)
        self.inekf = InEKF(R0=R0_init, use_gravity=False)
        self.zupt = StationaryDetector(rate_hz=float(hz))
        self.sample_idx = 0
        
        self.buffer = []
        self.window_size = 200  # 2s window @100Hz
        self.lat = 0.0
        self.lon = 0.0
        self.ref_set = False

    def process_imu_sample(self, acc, gyro, timestamp):
        """
        Process a single 3-axis acc (m/s²) and 3-axis gyro (rad/s) sample @100-200Hz.
        """
        self.sample_idx += 1
        t_ns = int(self.sample_idx * (1e9 / self.hz))
        still = self.zupt.update(acc, gyro, t_ns)
        
        t_acc = torch.tensor(acc, dtype=torch.float64)
        t_gyro = torch.tensor(gyro, dtype=torch.float64)

        # 100-200Hz InEKF state propagation
        if not still:
            self.inekf.propagate(t_gyro, t_acc, self.dt)
            
        self.buffer.append(np.concatenate([acc, gyro]))
        if len(self.buffer) > self.window_size:
            self.buffer.pop(0)
            
        v_pred = 0.0
        sigma_v = 0.3
        if len(self.buffer) == self.window_size and not still:
            inp = torch.tensor(np.array(self.buffer), dtype=torch.float32).unsqueeze(0).to(self.device)
            with torch.no_grad():
                v_out, ls_v_out, _, _, _ = self.model(inp)
                v_pred = max(float(v_out[0].detach().cpu().item()), 0.0)
                sigma_v = float(torch.exp(ls_v_out[0]).detach().cpu().item())
                
            # Velocity measurement update into InEKF
            z_vel = torch.tensor([v_pred, 0.0, 0.0], dtype=torch.float64)
            r_vel = torch.diag(torch.tensor([max(sigma_v**2, 0.09), max(sigma_v**2, 0.09), 25.0], dtype=torch.float64))
            self.inekf.update_velocity(z_vel, r_vel)

        pos = self.inekf.p.cpu().numpy()
        return {
            "timestamp": timestamp,
            "speed": v_pred if not still else 0.0,
            "pos_n": float(pos[0]),
            "pos_e": float(pos[1]),
            "pos_u": float(pos[2]),
            "still": still
        }

def main():
    parser = argparse.ArgumentParser(description="SIH26168 Standalone Edge Engine")
    parser.add_argument("--imu", required=True, help="Input IMU CSV file (timestamp, ax, ay, az, gx, gy, gz)")
    parser.add_argument("--hz", type=int, default=100, help="Sampling frequency (Hz)")
    parser.add_argument("--ckpt", default="experiments/checkpoints/model_avnet_stage1.p", help="Model checkpoint")
    parser.add_argument("--out", default="output_edge_poses.csv", help="Output pose CSV")
    args = parser.parse_args()

    engine = EdgeEngine(checkpoint_path=args.ckpt, hz=args.hz)
    print(f"[EdgeEngine] Initialized standalone engine @ {args.hz} Hz")

    imu_path = Path(args.imu)
    if not imu_path.exists():
        print(f"[EdgeEngine] Creating synthetic test IMU stream: {imu_path}")
        imu_path.parent.mkdir(parents=True, exist_ok=True)
        # Create 10-second synthetic IMU stream @ 100-200Hz
        num_samples = args.hz * 10
        timestamps = np.linspace(0, 10, num_samples)
        acc = np.random.normal(0.0, 0.2, (num_samples, 3)) + np.array([0.5, 0.0, 9.81])
        gyro = np.random.normal(0.0, 0.02, (num_samples, 3))
        data = np.column_stack([timestamps, acc, gyro])
        np.savetxt(imu_path, data, delimiter=",", header="timestamp,ax,ay,az,gx,gy,gz", comments="")

    print(f"[EdgeEngine] Ingesting telemetry stream: {imu_path}")
    raw_data = np.genfromtxt(imu_path, delimiter=",", skip_header=1)
    results = []

    start_t = time.time()
    for row in raw_data:
        ts = row[0]
        acc = row[1:4]
        gyro = row[4:7]
        res = engine.process_imu_sample(acc, gyro, ts)
        results.append([res["timestamp"], res["speed"], res["pos_n"], res["pos_e"], res["pos_u"], 1 if res["still"] else 0])

    elapsed = time.time() - start_t
    print(f"[EdgeEngine] Processed {len(raw_data)} samples @ {args.hz} Hz in {elapsed:.3f}s (Effective rate: {len(raw_data)/elapsed:.1f} Hz)")

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    np.savetxt(out_path, results, delimiter=",", header="timestamp,speed,pos_north,pos_east,pos_up,is_still", comments="")
    print(f"[EdgeEngine] Trajectory poses saved to {out_path}")

if __name__ == "__main__":
    main()
