import os
import sys
import subprocess

# Pre-configured dataset ID for NITRIX project on Kaggle
KAGGLE_DATASET_ID = "harshsavnerkar/nitrix-gnss-dataset"

def download_kaggle():
    print("=========================================================")
    print("      NITRIX — KAGGLE DATASET DOWNLOADER                ")
    print("=========================================================\n")

    dataset_id = KAGGLE_DATASET_ID
    target_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Data_updated")
    os.makedirs(target_dir, exist_ok=True)

    print(f"Downloading dataset '{dataset_id}' from Kaggle into:\n -> {target_dir}\n")

    try:
        cmd = ["kaggle", "datasets", "download", "-d", dataset_id, "-p", target_dir, "--unzip"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        print(result.stdout)
        if result.returncode == 0:
            print("\n=========================================================")
            print("🎉 SUCCESS! Dataset downloaded and extracted into Data_updated/")
            print("=========================================================")
        else:
            print(f"Stderr: {result.stderr}")
    except Exception as e:
        print(f"❌ Download failed: {e}")

if __name__ == "__main__":
    download_kaggle()
