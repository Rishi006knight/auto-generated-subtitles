"""
Generate standard PNG icons for Subtitle AI Chrome Extension
"""
import os
import struct
import zlib

def create_sub_icon(size: int, filename: str):
    # Create simple clean RGBA PNG
    width = size
    height = size
    
    # We will draw a dark slate blue rounded background with white CC box
    raw_data = bytearray()
    for y in range(height):
        raw_data.append(0) # filter byte
        for x in range(width):
            nx = (x / width) * 2.0 - 1.0
            ny = (y / height) * 2.0 - 1.0
            dist = max(abs(nx), abs(ny))
            
            # Rounded rect mask
            if dist > 0.95:
                raw_data.extend([0, 0, 0, 0])
            else:
                # Inside icon
                # Draw CC inner badge
                is_badge = (abs(nx) < 0.65 and abs(ny) < 0.45)
                is_inner_cut = (abs(nx) < 0.50 and abs(ny) < 0.30)
                
                # Check for "C C" letter pixels
                in_c1 = (-0.45 <= nx <= -0.1) and (-0.25 <= ny <= 0.25) and not (-0.35 <= nx <= 0.0 and -0.12 <= ny <= 0.12)
                in_c2 = (0.1 <= nx <= 0.45) and (-0.25 <= ny <= 0.25) and not (0.2 <= nx <= 0.55 and -0.12 <= ny <= 0.12)
                
                if in_c1 or in_c2:
                    raw_data.extend([255, 255, 255, 255]) # White letters
                elif is_badge and not is_inner_cut:
                    raw_data.extend([37, 99, 235, 240]) # Blue badge border
                else:
                    # Gradient background from royal blue to dark slate
                    r = int(15 + (1.0 - ny) * 15)
                    g = int(23 + (1.0 - ny) * 25)
                    b = int(42 + (1.0 - ny) * 70)
                    raw_data.extend([r, g, b, 255])

    # PNG Signature
    png = bytearray(b"\x89PNG\r\n\x1a\n")
    
    # IHDR
    ihdr_data = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    ihdr_crc = zlib.crc32(b"IHDR" + ihdr_data)
    png.extend(struct.pack(">I", 13) + b"IHDR" + ihdr_data + struct.pack(">I", ihdr_crc))
    
    # IDAT
    compressed = zlib.compress(bytes(raw_data), level=9)
    idat_crc = zlib.crc32(b"IDAT" + compressed)
    png.extend(struct.pack(">I", len(compressed)) + b"IDAT" + compressed + struct.pack(">I", idat_crc))
    
    # IEND
    iend_crc = zlib.crc32(b"IEND")
    png.extend(struct.pack(">I", 0) + b"IEND" + struct.pack(">I", iend_crc))
    
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    with open(filename, "wb") as f:
        f.write(png)
    print(f"Generated {filename}")

if __name__ == "__main__":
    base_dir = os.path.join(os.path.dirname(__file__), "extension", "icons")
    create_sub_icon(16, os.path.join(base_dir, "icon16.png"))
    create_sub_icon(48, os.path.join(base_dir, "icon48.png"))
    create_sub_icon(128, os.path.join(base_dir, "icon128.png"))
