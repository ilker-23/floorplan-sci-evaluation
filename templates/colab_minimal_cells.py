# Paste these cells into Colab after uploading/copying SASA-GAN_Buildings to Drive.

# Cell 1
from google.colab import drive
drive.mount("/content/drive")

# Cell 2
from pathlib import Path
DRIVE_ROOT = Path("/content/drive/MyDrive")
PROJECT_DIR = DRIVE_ROOT / "SASA-GAN_Buildings"
RPLAN_DIR = DRIVE_ROOT / "RPLAN"  # TODO: change this
SCI = PROJECT_DIR / "sci_system"
for p in [PROJECT_DIR / "metadata", PROJECT_DIR / "outputs", SCI / "reports"]:
    p.mkdir(parents=True, exist_ok=True)

# Cell 3
!python "/content/drive/MyDrive/SASA-GAN_Buildings/sci_system/colab/inspect_drive_dataset.py" \
  --root "/content/drive/MyDrive/RPLAN" \
  --output-json "/content/drive/MyDrive/SASA-GAN_Buildings/sci_system/reports/rplan_drive_inventory.json"

# Cell 4 - after editing converter for your actual RPLAN structure
!python "/content/drive/MyDrive/SASA-GAN_Buildings/sci_system/colab/rplan_to_sci_jsonl_template.py" \
  --source "/content/drive/MyDrive/RPLAN/YOUR_SOURCE_FILE.pkl" \
  --output "/content/drive/MyDrive/SASA-GAN_Buildings/metadata/plans.jsonl"

# Cell 5
!python "/content/drive/MyDrive/SASA-GAN_Buildings/sci_system/scripts/make_splits.py" \
  --input "/content/drive/MyDrive/SASA-GAN_Buildings/metadata/plans.jsonl" \
  --output-dir "/content/drive/MyDrive/SASA-GAN_Buildings/sci_system/reports/splits" \
  --group-key family_id \
  --seed 20260610
