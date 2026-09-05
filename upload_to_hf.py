import os
import sys

try:
    from huggingface_hub import HfApi, create_repo
except ImportError:
    print("Installing huggingface_hub package...")
    os.system(f"{sys.executable} -m pip install huggingface_hub")
    from huggingface_hub import HfApi, create_repo

def upload_dataset():
    print("=========================================================")
    print("      NITRIX — HUGGING FACE DATASET UPLOADER            ")
    print("=========================================================\n")

    token = input("Enter your Hugging Face Write Token (hf_...): ").strip()
    if not token:
        print("Error: Hugging Face token is required.")
        return

    repo_id = input("Enter your Hugging Face Dataset Repo Name (e.g., username/nitrix-dataset): ").strip()
    if not repo_id:
        print("Error: Repository ID is required.")
        return

    dataset_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Data_updated")
    if not os.path.exists(dataset_folder):
        print(f"Error: Data_updated folder not found at {dataset_folder}")
        return

    print(f"\n[1/3] Ensuring repository '{repo_id}' exists on Hugging Face...")
    try:
        create_repo(repo_id=repo_id, token=token, repo_type="dataset", exist_ok=True)
        print("✓ Repository ready!")
    except Exception as e:
        print(f"Warning/Notice creating repo: {e}")

    print(f"\n[2/3] Uploading 'Data_updated' folder to Hugging Face dataset '{repo_id}'...")
    print("This may take several minutes depending on your network upload speed.\n")

    api = HfApi()
    try:
        api.upload_folder(
            folder_path=dataset_folder,
            path_in_repo="Data_updated",
            repo_id=repo_id,
            repo_type="dataset",
            token=token,
        )
        print("\n=========================================================")
        print("🎉 SUCCESS! Data_updated has been uploaded to Hugging Face!")
        print(f"🔗 Dataset URL: https://huggingface.co/datasets/{repo_id}")
        print("=========================================================")
    except Exception as e:
        print(f"\n❌ Upload failed: {e}")

if __name__ == "__main__":
    upload_dataset()
