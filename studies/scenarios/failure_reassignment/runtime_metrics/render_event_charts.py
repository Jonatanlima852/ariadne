"""Renderiza métricas que dependem do events.jsonl já agregado."""

import csv
import sys
from pathlib import Path


def main():
    summary_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])
    rows = list(csv.DictReader(summary_path.open(encoding="utf-8")))
    recovered = next(
        (row for row in rows if int(row["reassignment_count"] or 0) > 0), None
    )
    recovery = float(recovered["recovery_ms"]) if recovered else 0.0
    total = float(recovered["total_latency_ms"]) if recovered else 0.0
    scale = 480 / max(total, recovery, 1)
    output_path.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="680" height="240" viewBox="0 0 680 240">\n'
        '<rect width="100%" height="100%" fill="white"/>\n'
        '<text x="24" y="28" font-family="sans-serif" font-size="16">Falha e recuperação (ms)</text>\n'
        f'<text x="24" y="85" font-family="sans-serif" font-size="12">recovery</text><rect x="150" y="65" width="{recovery*scale:.1f}" height="26" fill="#20a464"/><text x="{160+recovery*scale:.1f}" y="83" font-family="sans-serif" font-size="11">{recovery:.1f}</text>\n'
        f'<text x="24" y="145" font-family="sans-serif" font-size="12">latência total</text><rect x="150" y="125" width="{total*scale:.1f}" height="26" fill="#367bf5"/><text x="{160+total*scale:.1f}" y="143" font-family="sans-serif" font-size="11">{total:.1f}</text>\n'
        '</svg>\n',
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
