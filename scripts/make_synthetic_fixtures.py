"""Render stand-in Korean fixtures so the golden suite runs for anyone who clones.

Her real photos live beside these and are gitignored (they carry her name,
address and ARC number). A clean render is a weak proxy for a phone photo and
proves nothing about robustness — it only keeps the harness honest and runnable.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parents[1] / "tests" / "golden" / "fixtures"

FONT_CANDIDATES = (
    "/System/Library/Fonts/AppleSDGothicNeo.ttc",
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
)

DOCS = {
    "immigration.synthetic.png": [
        "서울출입국·외국인청",
        "체류기간 연장허가 신청 안내",
        "신청인은 아래 기한까지 방문하여",
        "여권과 외국인등록증을 지참하고",
        "신청서를 제출하여야 합니다.",
        "수수료: 60,000원",
        "납부기한: 2026년 10월 5일",
    ],
    "undated_notice.synthetic.png": [
        "한국전력공사",
        "전기요금 안내",
        "청구금액: 34,500원",
        "자동이체 등록을 권장합니다.",
    ],
    "cold_medicine.synthetic.png": [
        "콜드에스 정",
        "성분 및 함량",
        "이부프로펜 200mg",
        "슈도에페드린염산염 30mg",
        "클로르페니라민말레산염 2mg",
        "용법용량: 1일 3회 1정 식후 복용",
    ],
    "unreadable.synthetic.png": ["ㅁ ㅇ"],
}


def _font(size: int) -> ImageFont.FreeTypeFont:
    for path in FONT_CANDIDATES:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    raise SystemExit(
        "No Korean font found. Install one of:\n  " + "\n  ".join(FONT_CANDIDATES)
    )


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    font = _font(34)
    for name, lines in DOCS.items():
        img = Image.new("RGB", (900, 60 * len(lines) + 60), "white")
        draw = ImageDraw.Draw(img)
        for i, line in enumerate(lines):
            draw.text((40, 30 + i * 60), line, fill="black", font=font)
        img.save(OUT / name)
        print(f"wrote {name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
