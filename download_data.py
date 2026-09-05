import os
import sys

try:
    from huggingface_hub import snapshot_download
except ImportError:
    print("Installing huggingface_hub package...")
    os.system(f"{sys.executable} -m pip install huggingface_hub")
    from huggingface_hub import snapshot_download

# Default repository link (Replace with your actual HuggingFace dataset repo_id)
DATASET_REPO_ID = "YOUR_USERNAME/nitrix-dataset"

def download():
    print("=========================================================")
    print("      NITRIX — DATASET AUTOMATIC DOWNLOADER             ")
    print("=========================================================\n")

    repo_id = DATASET_REPO_ID
    if "YOUR_USERNAME" in repo_id:
        custom_repo = input("Enter your Hugging Face dataset ID (e.g., username/nitrix-dataset): ").strip()
        if custom_repo:
            repo_id = custom_repo

    target_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Data_updated")
    print(f"Downloading dataset from HuggingFace ({repo_id}) into:\n -> {target_dir}\n")

    try:
        snapshot_download(
            repo_id=repo_id,
            repo_type="dataset",
            local_dir=os.path.dirname(target_dir),
            local_dir_use_symlinks=False
        )
        print("\n=========================================================")
        print("🎉 SUCCESS! Dataset downloaded and ready at Data_updated/")
        print("=========================================================")
    except Exception as e:
        print(f"\n❌ Download failed: {e}")

if __name__ == "__main__":
    download()
