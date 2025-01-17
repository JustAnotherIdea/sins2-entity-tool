import cairosvg
from pathlib import Path

def convert_icons():
    icons_dir = Path(__file__).parent / "icons"
    icons_dir.mkdir(exist_ok=True)
    
    for svg_file in icons_dir.glob("*.svg"):
        png_file = svg_file.with_suffix(".png")
        cairosvg.svg2png(url=str(svg_file), write_to=str(png_file), output_width=32, output_height=32)
        print(f"Converted {svg_file.name} to {png_file.name}")

if __name__ == "__main__":
    convert_icons() 