const fs = require('fs');
const path = require('path');

const assetsDir = path.join(__dirname, 'assets');
if (!fs.existsSync(assetsDir)){
    fs.mkdirSync(assetsDir, { recursive: true });
}

const base64Png = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=';
const pngData = Buffer.from(base64Png, 'base64');

const filenames = ['icon.png', 'splash.png', 'adaptive-icon.png', 'favicon.png'];
filenames.forEach(name => {
    const filepath = path.join(assetsDir, name);
    fs.writeFileSync(filepath, pngData);
    console.log(`Created asset: ${filepath}`);
});
