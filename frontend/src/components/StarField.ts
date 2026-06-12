export interface Star {
  x: number;
  y: number;
  size: number;
  opacity: number;
  twinkleSpeed: number;
  color: string;
}

export class StarField {
  private stars: Star[] = [];
  private numStars = 600;

  constructor(width: number, height: number) {
    this.generate(width, height);
  }

  public generate(width: number, height: number) {
    this.stars = [];
    const colors = ['#ffffff', '#e7f5ff', '#fff9db', '#f8f9fa'];
    
    for (let i = 0; i < this.numStars; i++) {
      this.stars.push({
        x: Math.random() * width,
        y: Math.random() * height,
        size: Math.random() * 1.5 + 0.3,
        opacity: Math.random() * 0.7 + 0.3,
        twinkleSpeed: Math.random() * 0.02 + 0.005,
        color: colors[Math.floor(Math.random() * colors.length)],
      });
    }
  }

  public updateAndDraw(ctx: CanvasRenderingContext2D, elapsedFrames: number, parallaxX = 0, parallaxY = 0) {
    ctx.save();
    
    // Draw pre-generated stars with subtle twinkle animation and parallax offset
    for (const star of this.stars) {
      // Apply parallax movement
      let x = star.x + parallaxX * 0.2;
      let y = star.y + parallaxY * 0.2;

      // Handle wrapping of stars when parallax shifts them out of screen bounds
      const canvasWidth = ctx.canvas.width;
      const canvasHeight = ctx.canvas.height;
      if (x < 0) x = canvasWidth + (x % canvasWidth);
      if (x > canvasWidth) x = x % canvasWidth;
      if (y < 0) y = canvasHeight + (y % canvasHeight);
      if (y > canvasHeight) y = y % canvasHeight;

      // Subtle twinkling using sine wave on opacity
      const twinkle = Math.sin(elapsedFrames * star.twinkleSpeed) * 0.15;
      const opacity = Math.max(0.1, Math.min(1, star.opacity + twinkle));

      ctx.fillStyle = star.color;
      ctx.globalAlpha = opacity;
      ctx.beginPath();
      ctx.arc(x, y, star.size, 0, Math.PI * 2);
      ctx.fill();
    }
    
    ctx.restore();
  }
}
