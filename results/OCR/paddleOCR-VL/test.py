import sys
from pathlib import Path

from paddleocr import PaddleOCRVL

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[2]
INPUT_ROOT = REPO_ROOT / "data" / "OCR_sample"
OUTPUT_ROOT = SCRIPT_DIR / "output"
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"}

# Optional subset arg: e.g. `python test.py 물류` scans only data/OCR_sample/물류
# while still preserving the full relative path under output/.
scope = INPUT_ROOT / sys.argv[1] if len(sys.argv) > 1 else INPUT_ROOT

pipeline = PaddleOCRVL(device="gpu")

image_paths = sorted(
    p for p in scope.rglob("*") if p.suffix.lower() in IMAGE_EXTS
)
print(f"Found {len(image_paths)} images under {scope}")

for idx, img_path in enumerate(image_paths, start=1):
    rel_dir = img_path.parent.relative_to(INPUT_ROOT)
    save_dir = OUTPUT_ROOT / rel_dir / img_path.stem
    save_dir.mkdir(parents=True, exist_ok=True)

    print(f"[{idx}/{len(image_paths)}] {img_path.relative_to(REPO_ROOT)}")
    output = pipeline.predict(str(img_path))

    for res in output:
        res.save_to_markdown(save_path=str(save_dir))
