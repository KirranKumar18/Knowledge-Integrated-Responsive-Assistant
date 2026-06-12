import os
import base64

assets_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'assets')
os.makedirs(assets_dir, exist_ok=True)

# A small 1x1 solid dark-blue PNG file to prevent Expo asset loading crashes
base64_png = (
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII='
)
png_data = base64.b64decode(base64_png)

filenames = ['icon.png', 'splash.png', 'adaptive-icon.png', 'favicon.png']
for name in filenames:
    filepath = os.path.join(assets_dir, name)
    with open(filepath, 'wb') as f:
        f.write(png_data)
    print(f"Created asset: {filepath}")
