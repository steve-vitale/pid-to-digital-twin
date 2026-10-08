# I/O lists (input to scripts/map_points.py)

An I/O list is the plant's record of which tag lives at which data address. At a site it comes from the control
system or historian database, or from the instrument index.

`open100_sheet0_demo.csv` is **synthetic**, made up for the demonstration. OPEN100 is a design with no plant behind
it, so it has no real I/O list. The file is shaped like a real export, and it carries the cases a real one
produces:
- tags written differently from the drawing (`TE-14084A`, `TE 14089A` and `te_14091a` all match the drawing's
  `TE 14084A` style);
- points the plant has that the drawing doesn't show (`PT-14094`, `TE-14095A`): in a real archive, the drawing may be
  out of date;
- drawing instruments with no point (relief valves, local items, placeholders): spare, demolished, or a missing row;
- one tag shown twice on the drawing (`FT 1401`), which no tag-only match can resolve. It is reported as ambiguous
  and left for a person.

Its values are served by `scripts/ignition/demo_points_server.py`, which also produces synthetic data.
