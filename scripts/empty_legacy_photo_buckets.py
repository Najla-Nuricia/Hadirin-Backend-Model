"""One-off cleanup for legacy Supabase Storage buckets (foto-wajah, foto-presensi).

Default is dry-run; pass `--apply` to actually delete objects. A path-only
manifest is written to /tmp/opencode before deletion for traceability.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.db.session import get_supabase_client

LEGACY_BUCKETS = ("foto-wajah", "foto-presensi")
MANIFEST = Path("/tmp/opencode/legacy_photo_buckets_before_empty.json")


def walk(client: Any, bucket: str, prefix: str = "") -> list[str]:
    """Recursively list object keys; Supabase folders have `id: None`."""
    items = client.storage.from_(bucket).list(prefix) or []
    files: list[str] = []
    folders: list[str] = []
    for item in items:
        name = item.get("name")
        if not name:
            continue
        path = f"{prefix}/{name}" if prefix else name
        (folders if item.get("id") is None else files).append(path)
    for folder in folders:
        files.extend(walk(client, bucket, folder))
    return files


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Hapus objek (default: dry-run)")
    args = parser.parse_args()

    client = get_supabase_client(get_settings())
    inventory = {bucket: walk(client, bucket) for bucket in LEGACY_BUCKETS}
    total = sum(len(paths) for paths in inventory.values())
    print("Inventory:", {bucket: len(paths) for bucket, paths in inventory.items()})

    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(inventory, indent=2), encoding="utf-8")
    print(f"Manifest path ditulis ke {MANIFEST}")

    if not args.apply:
        print("DRY RUN — tidak ada objek yang dihapus. Gunakan --apply untuk menghapus.")
        return

    for bucket, paths in inventory.items():
        for start in range(0, len(paths), 100):
            batch = paths[start:start + 100]
            client.storage.from_(bucket).remove(batch)
        print(f"{bucket}: dihapus {len(paths)} objek")

    remaining = {bucket: len(walk(client, bucket)) for bucket in LEGACY_BUCKETS}
    print("Sisa setelah penghapusan:", remaining)
    if any(remaining.values()):
        raise SystemExit("Gagal mengosongkan semua bucket legacy.")


if __name__ == "__main__":
    main()
