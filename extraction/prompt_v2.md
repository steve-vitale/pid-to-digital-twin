You are reading one sheet of a piping and instrumentation diagram (P&ID) to build an asset model for a digital twin.

Return ONLY a JSON object (no prose, no code fences) with this exact shape:

{
  "symbols": [
    {
      "id": "s1",
      "class": "tank | pump | valve | instrumentation | inlet/outlet | general",
      "tag": "text label printed in or next to the symbol, exactly as written, or null",
      "bbox": {"x_min": 0, "y_min": 0, "x_max": 0, "y_max": 0},
      "confidence": 0.0
    }
  ],
  "connections": [
    { "from": "s1", "to": "s2" }
  ]
}

Definitions:
- tank: vessels, tanks, heat exchangers, columns and other large process equipment.
- pump: pumps, compressors, blowers.
- valve: any valve symbol (manual, control, check, relief, motor-operated) drawn in a line.
- instrumentation: instrument bubbles (circles, circles-in-squares) carrying a tag such as TE, PT, FT, MOV, TCV.
- inlet/outlet: off-page connectors / continuation flags at the edge of the drawing that name another drawing or system.
- general: other in-line symbols (reducers, flanges, strainers, spectacle blinds, etc.).
- Do NOT report line bends, line crossings, flow arrows, the drawing border, the title block, or notes.

Coordinates: "bbox" uses a 0–1000 scale in both directions. x runs left to right (x = 0 is the left edge, 1000 the right edge); y runs top to bottom (y = 0 is the top edge, 1000 the bottom edge), regardless of the image's pixel size.

Connections: list a connection between two symbols when a process line runs from one to the other, possibly through bends, tees, or line crossings drawn without a junction, but not through another reported symbol. Instruments connect to the line or equipment they measure.

"confidence" is your own 0–1 estimate that the symbol exists with that class.
Report every symbol you can see. If you are unsure about a symbol, include it with a lower confidence rather than leaving it out.
