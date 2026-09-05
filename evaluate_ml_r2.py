import json
import glob
import numpy as np
from sklearn.metrics import r2_score

files = sorted(glob.glob("Nitrix/data/trajectory_scn_*.json"))

print("=========================================================================")
print("          NITRIX — UPDATED R² SCORE EVALUATION (UKF vs PYTORCH LSTM)    ")
print("=========================================================================\n")

for f in files:
    with open(f, 'r') as fp:
        data = json.load(fp)
        
    samples = data['samples']
    meta = data['metadata']
    scenario_id = meta['scenario_id']
    scenario_name = meta['scenario']
    
    gt = np.column_stack([[s['ground_truth']['latitude'] for s in samples], [s['ground_truth']['longitude'] for s in samples]])
    ukf = np.column_stack([[s['ukf_estimate']['latitude'] for s in samples], [s['ukf_estimate']['longitude'] for s in samples]])
    ml = np.column_stack([[s['ml_estimate']['latitude'] for s in samples], [s['ml_estimate']['longitude'] for s in samples]])
    
    outage_mask = np.array([not s['gnss_available'] for s in samples])
    
    # Full track
    r2_full_ukf = r2_score(gt, ukf)
    r2_full_ml = r2_score(gt, ml)
    
    # Outage phase
    r2_outage_ukf = r2_score(gt[outage_mask], ukf[outage_mask])
    r2_outage_ml = r2_score(gt[outage_mask], ml[outage_mask])
    
    print(f"Scenario: {scenario_id} — {scenario_name}")
    print(f"  • Full Trajectory R²:  UKF Baseline = {r2_full_ukf:.4f}  |  PyTorch LSTM = {r2_full_ml:.4f}")
    print(f"  • Outage Phase R²:     UKF Baseline = {r2_outage_ukf:.4f}  |  PyTorch LSTM = {r2_outage_ml:.4f}")
    print("-" * 73)
