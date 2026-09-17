# grand-paxos

The art direction for *Distributed Algorithms of Ancient Greece*, a nine-volume illustrated series set on **one island, Paxos**. The island is pre-visualised in Blender, and each panel is then drawn as a 1970s halftone comic.

This is a standalone project. Don't reference or pull material from any other repo.

**Read `STATUS.md` before doing anything.** It has the current stage, the decisions, and what to do next.

## Layout
- `art-direction-grand-island-shape.html` is the main document: the reading order, the map, the measured checks, the 23-site gazetteer, the places each volume builds, the canon, the decisions and the Blender spec. Open it in a browser.
- `ERAS.md` is the story timeline: five phases in one generation, walked from the north-west.
- `tools/blender_panels.py` renders panel layouts from `volumes/<vol>-shots.json` (cameras, posed mannequins from `tools/blender_mannequin.py` coloured per character, stand-in props) into `renders/panels/` with Cycles. `tools/panel_images.py` turns a layout into the comic panel with the Gemini API, and accepted panels go to `volumes/images/`. The comic style is 1970s halftone.
- `volumes/` holds the volume pages: `V-part-time-parliament.html` (the Paxos paper) with `volume.css`. Its image panels are placeholders rendered from `volumes/V-panels.json` by `python3 tools/volume_panels.py V` between `<!-- PANEL id -->` markers (never hand-edit between them), which also writes the briefs to `prompts/volume-V-panels.md`.
- `tools/island_maps.py` generates the island and writes the map, measured checks and reading-order table into the page between `<!-- MAP -->`, `<!-- STATS -->` and `<!-- ORDER -->` markers. Never hand-edit the content between those markers.
- `maps/island.svg`, `maps/island-height.png` and `maps/island-sites.json` are generator outputs. Commit them, because they are the spec.
- `prompts/painted-map.md` is the stage 2 image prompt. The painting it produced is kept only as a record and isn't used downstream. Image generation is done by the user in the Gemini web UI; don't call image APIs. `tools/painted_map.py` makes the upload (`reference`) and registers the result (`register <file>`).
- `references/` holds the image reference sheets (JPEG, named by volume in walking order), indexed in its `README.md` with where they disagree with the canon. They stand in for the small props, which aren't modelled.
- `temp/` holds the user's downloads, such as raw Gemini images (gitignored). Registered results go in `maps/`.
- `tools/blender_buildings.py` is the full scene build: terrain (via `blender_terrain.build()`), the key buildings, every other site through `tools/blender_sites.py`, and vegetation, fields and tracks through `tools/blender_nature.py`. Shared helpers live in `tools/blender_kit.py`. The Great Round is detailed in `tools/blender_round.py`, and the architectural components for the other hero buildings (columns, openings, temple, crenellation) live in `tools/blender_arch.py`. The large props (ships, the Raft, carts, the market, amphorae) are built in `tools/blender_props.py`, and every sightline check casts its rays through them. The full build with renders takes about 2 minutes. Run `~/.local/bin/blender -b -P tools/blender_buildings.py [-- --render]`. `blender/*-checks.json` are committed.
- `tools/blender_terrain.py` builds the terrain-only Blender scene, `blender/paxos.blend` (gitignored), from the heightmap and site list. Run `~/.local/bin/blender -b -P tools/blender_terrain.py [-- --render]`; renders go to `renders/` (gitignored). `blender/terrain-checks.json` is committed.
- `sources/` holds the papers as PDFs (gitignored). Its `README.md` indexes them by volume.

## Commands
- `python3 tools/island_maps.py` regenerates the map, heightmap, site JSON and page blocks (a few seconds). It prints the site elevations and the checks.
- To render the SVG or the page for a visual check: `"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new --hide-scrollbars --window-size=2200,1600 --screenshot=<out.png> file://<path>`. Very tall windows (over about 13000 px) can hang, so wrap them in `timeout`.

## Environment
- The system `python3` has only `numpy` and `Pillow` (no scipy, skimage or matplotlib), so contouring, flood fills and pathfinding are hand-written.
- Blender: `/Applications/Blender.app`, with the CLI at `~/.local/bin/blender`.
- The env has `GEMINI_API_KEY`, `TRIPO_API_KEY` and `MESHY_API_KEY`.

## Conventions
- House palette and type, inlined in the HTML: ink `#1c1512`, paper `#f2e7cd`, paper-hi `#faf3e0`, aegean `#136f9e`, terra `#bf4a26`, olive `#66722c`, gold `#c1912b`, caption `#ffe36e`. Headings use Optima/Gill Sans; body text uses Georgia.
- The art-direction page has no `<!doctype>`, `<html>`, `<head>` or `<body>` tags and no viewport meta, and `<title>` comes first. Volume pages are ordinary full documents.
- Volumes are numbered I–IX in walking order from the north-west, which is also dependency and story order.
- World coordinates are metres on an 11000 × 8000 m world, with x pointing east and y pointing south. One SVG unit is 5 m. The heightmap maps −120 m to 0 and +480 m to 65535.
