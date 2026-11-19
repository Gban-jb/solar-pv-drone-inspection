"""Self-contained drawing viewport embedded in the existing Streamlit page."""

from __future__ import annotations

import base64
import html
import json

from solar_pv.imaging.drawings import DrawingView


def drawing_viewer_html(view: DrawingView, image_bytes: bytes, *, height_px: int = 620) -> str:
    """Render one source-linked raster with local zoom, pan and fit controls."""
    source = "data:image/png;base64," + base64.b64encode(image_bytes).decode("ascii")
    title = html.escape(f"{view.sheet} · {view.title}")
    aria = html.escape(f"Engineering drawing {view.sheet}, PDF page {view.pdf_page}")
    storage_key = json.dumps(f"solar-pv-drawing:{view.sheet}")
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<style>
* {{ box-sizing: border-box; }}
html, body {{ margin: 0; height: 100%; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
.viewer {{ display: flex; flex-direction: column; height: {height_px}px; border: 1px solid #d6ded5; border-radius: 7px; overflow: hidden; background: #f0f1ec; color: #1d3028; }}
.toolbar {{ min-height: 48px; display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 6px 12px; background: #fff; border-bottom: 1px solid #d6ded5; }}
.title {{ font-size: 13px; font-weight: 650; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
.controls {{ display: flex; gap: 4px; align-items: center; flex-shrink: 0; }}
button {{ border: 1px solid #cbd5cc; background: #fff; color: #1d3028; border-radius: 4px; min-width: 32px; height: 32px; padding: 0 9px; font: inherit; font-size: 12px; font-weight: 650; cursor: pointer; }}
button:hover, button:focus-visible {{ border-color: #275f4c; background: #eaf0e9; outline: 2px solid transparent; }}
button:focus-visible {{ outline: 2px solid #275f4c; outline-offset: 1px; }}
.viewport {{ position: relative; flex: 1; overflow: hidden; cursor: grab; touch-action: none; outline: none; }}
.viewport:active {{ cursor: grabbing; }}
.viewport:focus-visible {{ outline: 2px solid #275f4c; outline-offset: -3px; }}
.viewport img {{ position: absolute; left: 0; top: 0; max-width: none; transform-origin: 0 0; user-select: none; pointer-events: none; image-rendering: auto; }}
.foot {{ display: flex; justify-content: space-between; gap: 8px; padding: 6px 12px; background: #fff; border-top: 1px solid #d6ded5; color: #617168; font-size: 11px; }}
@media (max-width: 600px) {{ .toolbar {{ flex-wrap: wrap; }} .title {{ flex-basis: 100%; }} .foot span:first-child {{ display: none; }} }}
</style></head>
<body><div class="viewer">
  <div class="toolbar"><span class="title">{title}</span><div class="controls" role="group" aria-label="Drawing controls">
    <button id="out" type="button" aria-label="Zoom out">−</button>
    <button id="in" type="button" aria-label="Zoom in">+</button>
    <button id="fit" type="button" aria-label="Fit drawing to screen">Fit</button>
    <button id="reset" type="button" aria-label="Reset to original size">100%</button>
  </div></div>
  <div id="viewport" class="viewport" role="img" tabindex="0" aria-label="{aria}. Drag to pan; use mouse wheel or plus and minus keys to zoom.">
    <img id="drawing" src="{source}" alt="{aria}" draggable="false">
  </div>
  <div class="foot"><span>Drag to pan · scroll to zoom · arrow keys to move</span><span id="zoomLabel" aria-live="polite">Fitting…</span></div>
</div>
<script>
(() => {{
  const viewport = document.getElementById('viewport');
  const image = document.getElementById('drawing');
  const label = document.getElementById('zoomLabel');
  const key = {storage_key};
  let scale = 1, fitScale = 1, x = 0, y = 0, dragging = false, lastX = 0, lastY = 0;
  let lastWidth = 0, lastHeight = 0;
  const clamp = (n, lo, hi) => Math.min(hi, Math.max(lo, n));
  function viewState(width = viewport.clientWidth, height = viewport.clientHeight) {{
    return {{
      zoom: scale / fitScale,
      centerX: (width / 2 - x) / (image.naturalWidth * scale),
      centerY: (height / 2 - y) / (image.naturalHeight * scale),
    }};
  }}
  function save() {{
    if (!image.naturalWidth || !Number.isFinite(fitScale) || fitScale <= 0) return;
    try {{ sessionStorage.setItem(key, JSON.stringify(viewState())); }} catch (_) {{}}
  }}
  function restore(saved) {{
    if (!saved || ![saved.zoom, saved.centerX, saved.centerY].every(Number.isFinite)) return;
    scale = clamp(fitScale * saved.zoom, fitScale * 0.5, Math.max(2, fitScale * 12));
    x = viewport.clientWidth / 2 - saved.centerX * image.naturalWidth * scale;
    y = viewport.clientHeight / 2 - saved.centerY * image.naturalHeight * scale;
    paint();
  }}
  function paint() {{
    image.style.transform = `translate(${{x}}px, ${{y}}px) scale(${{scale}})`;
    label.textContent = `${{Math.round(scale / fitScale * 100)}}% of fit`;
    lastWidth = viewport.clientWidth; lastHeight = viewport.clientHeight;
    save();
  }}
  function fit() {{
    if (!image.naturalWidth || !image.naturalHeight) return;
    fitScale = Math.min(viewport.clientWidth / image.naturalWidth, viewport.clientHeight / image.naturalHeight);
    scale = fitScale;
    x = (viewport.clientWidth - image.naturalWidth * scale) / 2;
    y = (viewport.clientHeight - image.naturalHeight * scale) / 2;
    paint();
  }}
  function zoom(factor, clientX, clientY) {{
    const rect = viewport.getBoundingClientRect();
    const px = clientX - rect.left, py = clientY - rect.top;
    const next = clamp(scale * factor, fitScale * 0.5, Math.max(2, fitScale * 12));
    x = px - (px - x) * next / scale;
    y = py - (py - y) * next / scale;
    scale = next;
    paint();
  }}
  function centerZoom(factor) {{
    const rect = viewport.getBoundingClientRect();
    zoom(factor, rect.left + rect.width / 2, rect.top + rect.height / 2);
  }}
  image.addEventListener('load', () => {{
    let saved = null;
    try {{ saved = JSON.parse(sessionStorage.getItem(key) || 'null'); }} catch (_) {{}}
    fit();
    restore(saved);
  }});
  viewport.addEventListener('wheel', event => {{
    event.preventDefault();
    zoom(Math.exp(-event.deltaY * 0.0015), event.clientX, event.clientY);
  }}, {{passive: false}});
  viewport.addEventListener('pointerdown', event => {{
    dragging = true; lastX = event.clientX; lastY = event.clientY;
    viewport.setPointerCapture(event.pointerId); viewport.focus();
  }});
  viewport.addEventListener('pointermove', event => {{
    if (!dragging) return;
    x += event.clientX - lastX; y += event.clientY - lastY;
    lastX = event.clientX; lastY = event.clientY; paint();
  }});
  const endDrag = () => {{ dragging = false; }};
  viewport.addEventListener('pointerup', endDrag);
  viewport.addEventListener('pointercancel', endDrag);
  viewport.addEventListener('keydown', event => {{
    if (event.key === '+' || event.key === '=') {{ centerZoom(1.25); event.preventDefault(); }}
    else if (event.key === '-') {{ centerZoom(0.8); event.preventDefault(); }}
    else if (event.key === '0') {{ fit(); event.preventDefault(); }}
    else if (['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(event.key)) {{
      x += event.key === 'ArrowLeft' ? 40 : event.key === 'ArrowRight' ? -40 : 0;
      y += event.key === 'ArrowUp' ? 40 : event.key === 'ArrowDown' ? -40 : 0;
      paint(); event.preventDefault();
    }}
  }});
  document.getElementById('in').addEventListener('click', () => centerZoom(1.25));
  document.getElementById('out').addEventListener('click', () => centerZoom(0.8));
  document.getElementById('fit').addEventListener('click', fit);
  document.getElementById('reset').addEventListener('click', () => {{
    scale = 1; x = (viewport.clientWidth - image.naturalWidth) / 2;
    y = (viewport.clientHeight - image.naturalHeight) / 2; paint();
  }});
  new ResizeObserver(() => {{
    if (!image.naturalWidth || !viewport.clientWidth || !viewport.clientHeight) return;
    const saved = lastWidth && lastHeight && Number.isFinite(fitScale) && fitScale > 0
      ? viewState(lastWidth, lastHeight) : null;
    const nextFit = Math.min(viewport.clientWidth / image.naturalWidth, viewport.clientHeight / image.naturalHeight);
    if (Math.abs(nextFit - fitScale) < 0.00001) return;
    fitScale = nextFit;
    if (saved) restore(saved);
    else fit();
  }}).observe(viewport);
}})();
</script></body></html>"""
