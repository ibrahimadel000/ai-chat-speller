import os
from PIL import Image, ImageDraw, ImageFont

def create_icon():
    sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    images = []
    
    for size in sizes:
        w, h = size
        img = Image.new("RGBA", size, (255, 255, 255, 0))
        draw = ImageDraw.Draw(img)
        
        # Calculate scaling based on size
        radius = int(w * 0.15)
        margin = int(w * 0.08)
        
        # Draw background (a nice vibrant blue/purple gradient or solid color)
        bg_color = (79, 140, 255, 255) # Match ACCENT color
        draw.rounded_rectangle((margin, margin, w - margin, h - margin), radius=radius, fill=bg_color)
        
        # Draw "AI" text
        # Since we don't have guaranteed fonts, we'll draw simple geometry or rely on default
        # Let's draw an 'A' and 'I' using polygons/lines to ensure it looks crisp at all sizes without relying on system fonts
        
        stroke_width = max(1, int(w * 0.08))
        text_color = (255, 255, 255, 255)
        
        # 'A'
        a_left = int(w * 0.25)
        a_right = int(w * 0.45)
        a_top = int(h * 0.3)
        a_bottom = int(h * 0.7)
        a_mid = (a_left + a_right) // 2
        
        draw.line((a_mid, a_top, a_left, a_bottom), fill=text_color, width=stroke_width)
        draw.line((a_mid, a_top, a_right, a_bottom), fill=text_color, width=stroke_width)
        draw.line((int(a_left + (a_right-a_left)*0.25), int(h*0.55), int(a_right - (a_right-a_left)*0.25), int(h*0.55)), fill=text_color, width=stroke_width)
        
        # 'I'
        i_x = int(w * 0.55)
        draw.line((i_x, a_top, i_x, a_bottom), fill=text_color, width=stroke_width)
        
        # Sparkle / Spell marker
        sparkle_x = int(w * 0.75)
        sparkle_y = int(h * 0.35)
        sparkle_size = int(w * 0.1)
        
        draw.line((sparkle_x, sparkle_y - sparkle_size, sparkle_x, sparkle_y + sparkle_size), fill=(255, 215, 0, 255), width=max(1, stroke_width//2))
        draw.line((sparkle_x - sparkle_size, sparkle_y, sparkle_x + sparkle_size, sparkle_y), fill=(255, 215, 0, 255), width=max(1, stroke_width//2))
        
        # Underline to signify spell checking
        underline_y = int(h * 0.8)
        draw.line((a_left, underline_y, i_x, underline_y), fill=(255, 92, 122, 255), width=stroke_width) # Match BAD color
        
        images.append(img)
        
    images[0].save('assets/app_icon.ico', format='ICO', sizes=[img.size for img in images], append_images=images[1:])
    print("Icon generated successfully at assets/app_icon.ico")

if __name__ == "__main__":
    create_icon()
