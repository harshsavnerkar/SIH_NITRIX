import os
import json

kaggle_dir = os.path.expanduser("~/.kaggle")
os.makedirs(kaggle_dir, exist_ok=True)

token = "KGAT_0ddb8d92f39c1e692e49d9c60e42690a"
username = "harshsavnerkar"

with open(os.path.join(kaggle_dir, "access_token"), "w") as f:
    f.write(token)

with open(os.path.join(kaggle_dir, "kaggle.json"), "w") as f:
    json.dump({"username": username, "key": token}, f)

print(f"Configured Kaggle access_token and kaggle.json in {kaggle_dir}")
