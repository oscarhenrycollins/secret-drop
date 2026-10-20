"""Release-pinned boxes must get the exact runtime bytes the recipe was reviewed with (wizard-os#27)."""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIGEST = re.compile(r"@sha256:[0-9a-f]{64}$")


class ImagePins(unittest.TestCase):
    def test_every_compose_image_is_digest_pinned(self):
        images = re.findall(r"^\s+image:\s*(\S+)\s*$", (ROOT / "runtipi/docker-compose.yml").read_text(), re.M)
        self.assertTrue(images)
        for image in images:
            self.assertRegex(image, DIGEST, f"{image} is a mutable tag; pin tag@sha256:<multi-arch index digest>")

    def test_dockerfile_base_is_digest_pinned(self):
        for line in (ROOT / "Dockerfile").read_text().splitlines():
            if line.startswith("FROM "):
                self.assertRegex(line.split()[1], DIGEST)


if __name__ == "__main__":
    unittest.main()
