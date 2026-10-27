"""Render offline SVG flow exports as slide PNGs and an optional didactic GIF.

Run with ephemeral dependencies, without changing Inspector dependencies:
uv run --with playwright --with pillow python tools/inspector/scripts/render-logistics-media.py EXPORT_DIR --gif
"""
import argparse
import json
from io import BytesIO
from pathlib import Path

from playwright.sync_api import sync_playwright


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--chrome', type=Path, default=Path('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'))
    parser.add_argument('--gif', action='store_true')
    args = parser.parse_args()
    directory = args.directory.resolve()
    if not (directory / 'flow.html').is_file():
        parser.error('Exporte o episódio com export-logistics-flow.mjs primeiro.')
    with sync_playwright() as playwright:
        options = {'headless': True}
        if args.chrome.is_file():
            options['executable_path'] = str(args.chrome)
        browser = playwright.chromium.launch(**options)
        page = browser.new_page(viewport={'width': 1800, 'height': 1100}, device_scale_factor=1)
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        for stem in ['overview', 'incident', 'recovery']:
            source = directory / f'{stem}.svg'
            if source.is_file():
                page.goto(source.as_uri())
                page.locator('svg').screenshot(path=str(directory / f'{stem}.png'))
        page.goto((directory / 'flow.html').as_uri())
        page.locator('#flow-canvas svg').wait_for()
        page.locator('#overview').check()
        page.screenshot(path=str(directory / 'offline-player.png'), full_page=True)
        if args.gif:
            from PIL import Image

            page.locator('#overview').uncheck()
            page.add_style_tag(content='.page{max-width:none;padding:0}.grid{display:block}.canvas{width:1600px;height:900px}.steps{display:none}')
            frames = json.loads((directory / 'frames.json').read_text())
            pictures, durations = [], []
            for index, frame in enumerate(frames):
                page.locator('#position').evaluate('(e,i)=>{e.value=i;e.dispatchEvent(new Event("input",{bubbles:true}));}', index)
                picture = Image.open(BytesIO(page.locator('#flow-canvas svg').screenshot())).convert('RGB')
                picture.thumbnail((1280, 720), Image.Resampling.LANCZOS)
                pictures.append(picture.quantize(colors=128))
                highlighted = frame['kind'] == 'incident' or frame['kind'] == 'effect' and frame['text'].startswith('TRANSFER')
                durations.append(2600 if highlighted else 2200 if frame['kind'] == 'finished' else 850)
            pictures[0].save(directory / 'flow.gif', save_all=True, append_images=pictures[1:], duration=durations, loop=0, optimize=True)
        browser.close()
        if errors:
            raise RuntimeError(errors)
    print(json.dumps({'directory': str(directory), 'png': True, 'gif': args.gif, 'browser_errors': errors}))


if __name__ == '__main__':
    main()
