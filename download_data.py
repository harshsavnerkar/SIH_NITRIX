import os
import zipfile
import urllib.request

RELEASE_ZIP_URL = "https://github.com/harshsavnerkar/SIH_NITRIX/releases/download/v1.0.0/Data_updated.zip"

def download_and_extract():
    print("=========================================================")
    print("      NITRIX — DATASET AUTOMATIC DOWNLOADER             ")
    print("=========================================================\n")

    base_dir = os.path.dirname(os.path.abspath(__file__))
    zip_path = os.path.join(base_dir, "Data_updated.zip")
    target_dir = os.path.join(base_dir, "Data_updated")

    if not os.path.exists(zip_path):
        print(f"[1/2] Downloading Data_updated.zip from GitHub Release...")
        print(f"URL: {RELEASE_ZIP_URL}\n")
        try:
            urllib.request.urlretrieve(RELEASE_ZIP_URL, zip_path)
            print("✓ Download complete!")
        except Exception as e:
            print(f"❌ Download failed: {e}")
            return

    print(f"\n[2/2] Extracting dataset into: {target_dir}...")
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(target_dir)
        print("\n=========================================================")
        print("🎉 SUCCESS! Dataset extracted and ready at Data_updated/")
        print("=========================================================")
    except Exception as e:
        print(f"❌ Extraction failed: {e}")

if __name__ == "__main__":
    download_and_extract()
