import os
import sys
import json
import subprocess

def upload_kaggle():
    print("=========================================================")
    print("        NITRIX — KAGGLE DATASET UPLOADER                 ")
    print("=========================================================\n")

    # Check for kaggle.json in standard user directory
    user_home = os.path.expanduser("~")
    kaggle_dir = os.path.join(user_home, ".kaggle")
    kaggle_json = os.path.join(kaggle_dir, "kaggle.json")

    if not os.path.exists(kaggle_json):
        print("⚠️ Kaggle API token (kaggle.json) not found!")
        print("Follow these steps to set up your Kaggle API key:")
        print(" 1. Go to https://www.kaggle.com/settings")
        print(" 2. Scroll to 'API' section and click 'Create New Token'")
        print(" 3. Download kaggle.json")
        print(f" 4. Place kaggle.json inside: {kaggle_dir}\n")
        
        kaggle_username = input("Or enter your Kaggle Username: ").strip()
        kaggle_key = input("Enter your Kaggle API Key: ").strip()
        
        if kaggle_username and kaggle_key:
            os.makedirs(kaggle_dir, exist_ok=True)
            with open(kaggle_json, "w") as f:
                json.dump({"username": kaggle_username, "key": kaggle_key}, f)
            print(f"✓ Created Kaggle API configuration at {kaggle_json}")
        else:
            print("Error: Kaggle credentials are required to upload.")
            return

    username = input("\nEnter your Kaggle Username: ").strip()
    if not username:
        print("Error: Kaggle username is required.")
        return

    dataset_slug = input("Enter Dataset Slug Name (default: nitrix-gnss-dataset): ").strip() or "nitrix-gnss-dataset"
    dataset_title = "NITRIX GNSS Denial Navigation Dataset"

    dataset_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Data_updated")
    if not os.path.exists(dataset_folder):
        print(f"Error: Data_updated directory not found at {dataset_folder}")
        return

    # Generate metadata file inside Data_updated
    meta_path = os.path.join(dataset_folder, "dataset-metadata.json")
    metadata = {
        "title": dataset_title,
        "id": f"{username}/{dataset_slug}",
        "licenses": [{"name": "CC0-1.0"}]
    }

    with open(meta_path, "w") as f:
        json.dump(metadata, f, indent=2)

    print(f"\n[1/2] Created dataset-metadata.json for dataset '{username}/{dataset_slug}'")
    print(f"[2/2] Uploading 'Data_updated' to Kaggle...")
    print("This may take several minutes depending on your internet connection...\n")

    try:
        result = subprocess.run(
            ["kaggle", "datasets", "create", "-p", dataset_folder],
            capture_output=True,
            text=True
        )
        print(result.stdout)
        if result.returncode == 0 or "Your private dataset" in result.stdout:
            print("\n=========================================================")
            print("🎉 SUCCESS! Dataset has been created and uploaded to Kaggle!")
            print(f"🔗 Dataset URL: https://www.kaggle.com/datasets/{username}/{dataset_slug}")
            print("=========================================================")
        else:
            print(f"Stderr: {result.stderr}")
    except Exception as e:
        print(f"❌ Upload failed: {e}")

if __name__ == "__main__":
    upload_kaggle()
