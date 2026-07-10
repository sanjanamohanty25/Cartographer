import os
import json
import base64
import urllib.request
import logging
from typing import Any, Dict, List, Union
from neuro_san.interfaces.coded_tool import CodedTool

try:
    from _paths import request_dir
except ImportError:
    from coded_tools.migration_intelligence._paths import request_dir

logger = logging.getLogger(__name__)

# note -> (service-icon color, zone, provider-specific short code + icon abbrev)
_STYLE = {
    "database":         {"color": "#4aa3ff", "zone": "subnet", "codes": {"aws": "RDS", "azure": "SQL", "gcp": "SQL"}},
    "compute":          {"color": "#ff9d3c", "zone": "subnet", "codes": {"aws": "EC2", "azure": "VM", "gcp": "GCE"}},
    "storage":          {"color": "#4fd68a", "zone": "subnet", "codes": {"aws": "EBS", "azure": "DSK", "gcp": "PD"}},
    "network / security": {"color": "#a884ff", "zone": "subnet", "codes": {"aws": "SG", "azure": "NSG", "gcp": "FW"}},
    "resilience":       {"color": "#ff5ca8", "zone": "region", "codes": {"aws": "BAK", "azure": "BAK", "gcp": "BAK"}},
}
_REGION_NAME = {"aws": "AWS REGION", "azure": "AZURE REGION", "gcp": "GCP REGION"}
_VNET_NAME = {"aws": "VPC · 10.0.0.0/16", "azure": "VNet · 10.0.0.0/16", "gcp": "VPC network"}


class DiagramRenderTool(CodedTool):
    """Renders a zoned, AWS-reference-style migration architecture diagram (ADR-6).

    Input `resource_mappings` JSON: {"provider":"aws","pairs":[{"source","target","note"}...]}.
    Draws an On-Premises data-center zone and a cloud Region zone containing a VPC/subnet
    cluster with numbered service tiles, plus a labeled migration-flow arrow — so it reads
    like a real cloud architecture diagram rather than a table. Dark SVG, local (no network).
    """

    def invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> Union[Dict[str, Any], str]:
        logger.info("********** DiagramRenderTool started **********")
        request_id = args.get("request_id")
        raw = args.get("resource_mappings", "") or ""
        if not request_id:
            return {"error": "Missing request_id"}

        provider, region, pairs = self._parse(raw)
        svg_path = os.path.join(request_dir(request_id), "diagram.svg")

        engine = os.environ.get("DIAGRAM_RENDER_ENGINE", "builtin").lower()
        rendered = False
        if engine == "mermaid_ink":
            rendered = self._render_mermaid_ink(provider, pairs, svg_path)
        if not rendered:
            self._render_svg(provider, region, pairs, svg_path)

        logger.info("********** DiagramRenderTool completed **********")
        return {"status": "success", "file_path": svg_path, "provider": provider, "pairs": pairs}

    def _parse(self, raw: str):
        try:
            data = json.loads(raw)
            if isinstance(data, dict) and "pairs" in data:
                return data.get("provider", "cloud"), data.get("region", "us-east-1"), data["pairs"]
        except (json.JSONDecodeError, TypeError):
            pass
        return "cloud", "us-east-1", [
            {"source": "Legacy Source Server", "target": "Managed Database", "note": "database"},
            {"source": "On-prem storage", "target": "Block storage", "note": "storage"},
            {"source": "On-prem network", "target": "Virtual network", "note": "network / security"},
        ]

    # ---- zoned architecture SVG ---------------------------------------
    def _render_svg(self, provider: str, region: str, pairs: List[dict], svg_path: str) -> None:
        prov = provider if provider in _REGION_NAME else "aws"
        BG, TXT, MUT = "#0b1220", "#e6edf7", "#8aa0bd"
        SRC_C = "#e0607a"       # on-prem accent
        REGION_C = "#ff9d3c"    # region (aws orange)
        VPC_C = "#a884ff"       # vpc purple
        SUBNET_C = "#4aa3ff"    # subnet blue

        # order: subnet-zone tiles first, then region-level
        def zone_of(p):
            return _STYLE.get(p.get("note", ""), {}).get("zone", "region")
        ordered = sorted(pairs, key=lambda p: 0 if zone_of(p) == "subnet" else 1)
        subnet = [p for p in ordered if zone_of(p) == "subnet"]
        k = len(subnet)

        TW, TH = 232, 66            # tile size
        row_h, gap = TH, 26
        # explicit vertical bands so region/VPC/subnet labels never overlap
        region_top, vpc_top, subnet_top = 104, 140, 172
        top = 196                    # first tile y
        src_x = 60
        tgt_x = 700
        n = len(ordered)
        rows_y = [top + i * (row_h + gap) for i in range(n)]

        subnet_bottom = (rows_y[k - 1] + TH + 16) if k else subnet_top + 30
        vpc_bottom = subnet_bottom + 16
        last_tile_bottom = (rows_y[-1] + TH) if rows_y else top
        region_bottom = max(vpc_bottom, last_tile_bottom + 16) + 6
        H = region_bottom + 34
        W = 1080

        p_parts: List[str] = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
            f'font-family="Segoe UI, Helvetica, Arial, sans-serif">',
            f'<rect width="100%" height="100%" rx="16" fill="{BG}"/>',
            '<defs>'
            f'<marker id="ar" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7.5" markerHeight="7.5" orient="auto-start-reverse">'
            f'<path d="M0 0 L10 5 L0 10 z" fill="{SUBNET_C}"/></marker>'
            f'<linearGradient id="mig" x1="0" x2="1"><stop offset="0" stop-color="{SRC_C}"/><stop offset="1" stop-color="{SUBNET_C}"/></linearGradient>'
            '</defs>',
            f'<text x="38" y="46" fill="{TXT}" font-size="21" font-weight="700">Migration Architecture</text>',
            f'<text x="38" y="70" fill="{MUT}" font-size="12.5">Proposed target topology · on-premises &#8594; {prov.upper()} cloud</text>',
        ]

        reg_x, reg_w = tgt_x - 44, TW + 120
        # on-premises zone (left) — aligned to region band
        p_parts.append(self._zone(src_x - 20, region_top, TW + 40, region_bottom - region_top,
                                   "ON-PREMISES DATA CENTER", SRC_C))
        # region zone (right, outer)
        p_parts.append(self._zone(reg_x, region_top, reg_w, region_bottom - region_top,
                                   f"{_REGION_NAME[prov]} · {region}", REGION_C))
        # VPC + subnet wrap only the subnet tiles
        if k:
            p_parts.append(self._zone(reg_x + 16, vpc_top, reg_w - 32, vpc_bottom - vpc_top,
                                       _VNET_NAME[prov], VPC_C))
            p_parts.append(self._zone(reg_x + 30, subnet_top, reg_w - 60, subnet_bottom - subnet_top,
                                       "PRIVATE SUBNET", SUBNET_C, dash="4 5"))

        # ---- tiles + connectors ----
        for i, p in enumerate(ordered):
            y = rows_y[i]
            cy = y + TH / 2
            style = _STYLE.get(p.get("note", ""), {"color": MUT, "codes": {}})
            code = style.get("codes", {}).get(prov, "SVC")
            # on-prem source tile (numbered)
            p_parts.append(self._tile(src_x, y, TW, TH, p.get("source", ""), "#33415c", "#9db0cc", "SRC", i + 1))
            # cloud target tile (numbered, service-colored)
            p_parts.append(self._tile(tgt_x, y, TW, TH, p.get("target", ""), style["color"], style["color"], code, i + 1))
            # connector
            x1, x2 = src_x + TW, tgt_x
            p_parts.append(f'<path d="M {x1} {cy} C {(x1 + x2) / 2} {cy}, {(x1 + x2) / 2} {cy}, {x2} {cy}" '
                           f'fill="none" stroke="url(#mig)" stroke-width="2.2" marker-end="url(#ar)"/>')
            note = p.get("note", "")
            if note:
                mid = (x1 + x2) / 2
                p_parts.append(f'<rect x="{mid - 62}" y="{cy - 12}" width="124" height="22" rx="11" '
                               f'fill="#0f1729" stroke="#2a3a5c"/>')
                p_parts.append(f'<text x="{mid}" y="{cy + 3}" fill="{MUT}" font-size="10.5" text-anchor="middle">{self._esc(note)}</text>')

        # migration pipeline label on the first connector
        if rows_y:
            p_parts.append(f'<text x="{(src_x + TW + tgt_x) / 2}" y="{rows_y[0] - 6}" fill="{SRC_C}" '
                           f'font-size="11" font-weight="700" text-anchor="middle">MIGRATION PIPELINE &#8594;</text>')

        p_parts.append("</svg>")
        with open(svg_path, "w", encoding="utf-8") as f:
            f.write("\n".join(p_parts))
        logger.info(f"Rendered zoned architecture SVG ({n} components) to {svg_path}")

    def _zone(self, x, y, w, h, label, color, dash="7 6"):
        return (
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" fill="none" '
            f'stroke="{color}" stroke-width="1.4" stroke-dasharray="{dash}" opacity="0.85"/>'
            f'<rect x="{x + 12}" y="{y - 11}" width="{max(150, len(label) * 7.4)}" height="22" rx="6" fill="#0b1220"/>'
            f'<text x="{x + 20}" y="{y + 4}" fill="{color}" font-size="11.5" font-weight="700" '
            f'letter-spacing="0.06em">{self._esc(label)}</text>'
        )

    def _tile(self, x, y, w, h, text, border, icon_color, code, num):
        lines = str(text).split("\n")[:2]
        title = self._esc(lines[0])
        sub = self._esc(lines[1]) if len(lines) > 1 else ""
        icon = 44
        # icon square
        s = [
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" fill="#131d33" stroke="{border}" stroke-width="1.6"/>',
            f'<rect x="{x + 12}" y="{y + (h - icon) / 2}" width="{icon}" height="{icon}" rx="9" fill="{icon_color}" opacity="0.16"/>',
            f'<rect x="{x + 12}" y="{y + (h - icon) / 2}" width="{icon}" height="{icon}" rx="9" fill="none" stroke="{icon_color}" stroke-width="1.4"/>',
            f'<text x="{x + 12 + icon / 2}" y="{y + h / 2 + 4}" fill="{icon_color}" font-size="12" font-weight="700" '
            f'font-family="JetBrains Mono, monospace" text-anchor="middle">{self._esc(code)}</text>',
            f'<text x="{x + 68}" y="{y + (h / 2 - 4 if sub else h / 2 + 4)}" fill="#e6edf7" font-size="13" font-weight="700">{title}</text>',
        ]
        if sub:
            s.append(f'<text x="{x + 68}" y="{y + h / 2 + 14}" fill="#8aa0bd" font-size="10.5" '
                     f'font-family="JetBrains Mono, monospace">{sub}</text>')
        # number badge
        s.append(f'<circle cx="{x + w - 16}" cy="{y + 16}" r="10" fill="{icon_color}"/>')
        s.append(f'<text x="{x + w - 16}" y="{y + 20}" fill="#0b1220" font-size="11" font-weight="800" text-anchor="middle">{num}</text>')
        return "".join(s)

    @staticmethod
    def _esc(s: str) -> str:
        return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    # ---- optional mermaid.ink ------------------------------------------
    def _render_mermaid_ink(self, provider: str, pairs: List[dict], svg_path: str) -> bool:
        try:
            lines = ["flowchart LR"]
            for i, p in enumerate(pairs):
                s = p.get("source", "").replace("\n", " ")
                t = p.get("target", "").replace("\n", " ")
                lines.append(f'  S{i}["{s}"] -->|{p.get("note","")}| T{i}["{t}"]')
            code = "\n".join(lines)
            encoded = base64.b64encode(code.encode("utf-8")).decode("ascii")
            req = urllib.request.Request(f"https://mermaid.ink/svg/{encoded}", headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                with open(svg_path, "wb") as f:
                    f.write(resp.read())
            return True
        except Exception as e:
            logger.warning(f"mermaid.ink failed ({e}); using builtin SVG.")
            return False
