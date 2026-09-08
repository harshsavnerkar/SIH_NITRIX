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

from python.models.avnet import AVNet
from python.inekf_harness import InEKF
from python.utils.zupt import StationaryDetector

class EdgeEngine:
    def __init__(self, checkpoint_path="experiments/checkpoints/model_avnet_stage1.p", hz=100):
        self.hz = hz
        self.dt = 1.0 / hz
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        
        # Load trained AVNet model
        self.model = AVNet().to(self.device)
        if Path(checkpoint_path).exists():
            ckpt = torch.load(checkpoint_path, map_location=self.device)
            self.model.load_state_dict(ckpt.get("model_state_dict", ckpt))
            print(f"[EdgeEngine] Loaded model checkpoint from {checkpoint_path}")
        self.model.eval()
        
        # Initialize InEKF (21-DOF right-invariant filter)
        self.inekf = InEKF(use_gravity=False)
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
        
        # 100-200Hz InEKF state propagation
        if not still:
            self.inekf.propagate(gyro, acc, self.dt)
            
        self.buffer.append(np.concatenate([acc, gyro]))
        if len(self.buffer) > self.window_size:
            self.buffer.pop(0)
            
        v_pred = 0.0
        sigma_v = 0.3
        if len(self.buffer) == self.window_size and not still:
            inp = torch.tensor(np.array(self.buffer), dtype=torch.float32).unsqueeze(0).to(self.device)
            with torch.no_grad():
                v_out, sigma_out = self.model(inp)
                v_pred = max(float(v_out[0].cpu().numpy()), 0.0)
                sigma_v = float(sigma_out[0].cpu().numpy())
                
            # Velocity measurement update into InEKF
            z_vel = np.array([v_pred, 0.0, 0.0])
            r_vel = np.diag([max(sigma_v**2, 0.09), max(sigma_v**2, 0.09), 25.0])
            self.inekf.update_velocity(z_vel, r_vel)

        pos = self.inekf.position()
        return {
            "timestamp": timestamp,
            "speed": v_pred if not still else 0.0,
            "pos_n": pos[0],
            "pos_e": pos[1],
            "pos_u": pos[2],
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

if __name__ == "__main__":
    main()
