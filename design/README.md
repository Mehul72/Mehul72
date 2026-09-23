# Artwork generator

`build.py` regenerates every static SVG in `../assets` and the three small font
subsets used by `scripts/activity.py`.

## Rebuild

Python 3.10 or newer is recommended. The first build downloads the pinned Inter,
JetBrains Mono and Simple Icons sources into the ignored `.cache` directory.

```bash
cd design
python3 -m venv .venv
.venv/bin/pip install --requirement requirements.txt
.venv/bin/python build.py
```

To rebuild one family while editing:

```bash
.venv/bin/python build.py header
.venv/bin/python build.py about card
```

The supported targets are `fonts`, `header`, `about`, `stack`, `footer`, `card`,
`section` and `contact`.

## Preview

Serve the repository root:

```bash
cd ..
python3 -m http.server 8765
```

Then open:

- `http://127.0.0.1:8765/design/preview/readme.html`
- add `?theme=light` for the light theme
- add `&t=14.5` to freeze animated SVGs at 14.5 seconds

`preview/frame.html` isolates one SVG. For example:

```text
http://127.0.0.1:8765/design/preview/frame.html?src=../../assets/header-dark.svg&t=14.5&w=1280
```

If Chrome or Playwright's Chromium shell is installed, `shoot.py` can save any
preview URL as a PNG without installing the generator dependencies:

```bash
python3 shoot.py "http://127.0.0.1:8765/design/preview/readme.html?theme=dark&t=14.5" preview/shots/readme.png 960 4200
```

The generated SVGs embed their own subsetted fonts and have no external runtime
dependencies. Font notices and licenses are in `licenses/`.
