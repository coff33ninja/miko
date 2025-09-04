# Live2D Implementation Guide

To properly implement Live2D in this project:

1. Download the official Live2D Cubism SDK for Web:
   - Go to: https://www.live2d.com/download/cubism-sdk/download-web/
   - Extract the downloaded SDK

2. Required files from the SDK (copy to `/static/js/`):
   ```
   /Core/live2dcubismcore.min.js
   /Framework/dist/live2dcubismframework.js
   /Framework/dist/live2dcubismpixi.js
   ```

3. Dependencies:
   ```bash
   npm install pixi.js@5.3.12
   npm install @cubism/framework
   ```

4. Model organization:
   Your model files should be in `/static/models/Poblanc/`:
   - Poblanc.model3.json
   - Poblanc.moc3
   - Poblanc.physics3.json
   - expression1.exp3.json
   - Textures in a subfolder

5. Update model paths:
   The model URL should be: `/static/models/Poblanc/Poblanc.model3.json`

6. The Live2D Cubism SDK requires:
   - WebGL support
   - A valid Live2D Cubism Core license
   - Proper model file structure
   - All related model assets (textures, physics, expressions)

Please download the SDK and follow these steps to properly implement Live2D.
