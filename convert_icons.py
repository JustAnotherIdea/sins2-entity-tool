import cairosvg
from pathlib import Path

def convert_icons():
    icons_dir = Path(__file__).parent / "icons"
    icons_dir.mkdir(exist_ok=True)
    
    for svg_file in icons_dir.glob("*.svg"):
        png_file = svg_file.with_suffix(".png")
        # Special case for specific icons
        if svg_file.stem == "add_delete":
            output_size = 20
        elif svg_file.stem == "refresh":
            output_size = 18
        else:
            output_size = 32
        cairosvg.svg2png(url=str(svg_file), write_to=str(png_file), output_width=output_size, output_height=output_size)
        print(f"Converted {svg_file.name} to {png_file.name}")

if __name__ == "__main__":
    convert_icons() 