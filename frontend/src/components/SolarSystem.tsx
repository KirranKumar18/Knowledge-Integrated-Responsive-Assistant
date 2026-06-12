import React, { useEffect, useRef, useState } from 'react';
import { PLANET_MAP, PlanetConfig } from './Planet';
import { StarField } from './StarField';
import { usePlanetOrbit, PlanetPosition } from '../hooks/usePlanetOrbit';

interface SolarSystemProps {
  activePlanetId: string | null;
  focusOnPlanet: (id: string) => void;
  resetToOverview: () => void;
  updateCamera: (targetX: number, targetY: number, targetScale: number, isFirstFrame?: boolean) => { x: number; y: number; scale: number };
  currentX: React.MutableRefObject<number>;
  currentY: React.MutableRefObject<number>;
  currentScale: React.MutableRefObject<number>;
}

export const SolarSystem: React.FC<SolarSystemProps> = ({
  activePlanetId,
  focusOnPlanet,
  resetToOverview,
  updateCamera,
  currentX,
  currentY,
  currentScale,
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const starFieldRef = useRef<StarField | null>(null);
  const animationFrameId = useRef<number | null>(null);
  const elapsedFrames = useRef<number>(0);
  
  const [hoveredPlanetId, setHoveredPlanetId] = useState<string | null>(null);
  const currentPositionsRef = useRef<Record<string, PlanetPosition>>({});
  const isFirstFrameRef = useRef<boolean>(true);

  const { updatePositions } = usePlanetOrbit();

  // Handle keypresses (Escape to return to overview)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        resetToOverview();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [resetToOverview]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const resizeCanvas = () => {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
      
      if (!starFieldRef.current) {
        starFieldRef.current = new StarField(canvas.width, canvas.height);
      } else {
        starFieldRef.current.generate(canvas.width, canvas.height);
      }
    };

    window.addEventListener('resize', resizeCanvas);
    resizeCanvas();

    const render = () => {
      elapsedFrames.current += 1;
      const width = canvas.width;
      const height = canvas.height;
      const centerX = width / 2;
      const centerY = height / 2;

      // 1. Calculate target coordinates for the camera
      let targetX = centerX;
      let targetY = centerY;
      let targetScale = 0.85; // Default overview scale (slightly zoomed out to fit saturn/jupiter)

      // If we are focused on a planet, follow its coordinates in real time
      if (activePlanetId) {
        const activePlanetPos = currentPositionsRef.current[activePlanetId];
        if (activePlanetPos) {
          targetX = activePlanetPos.x;
          targetY = activePlanetPos.y;
          
          // Jupiter is massive, zoom out slightly more compared to smaller planets
          targetScale = activePlanetId === 'jupiter' ? 2.2 : 3.2;
        }
      }

      // 2. Interpolate camera position
      const cam = updateCamera(targetX, targetY, targetScale, isFirstFrameRef.current);
      if (isFirstFrameRef.current) {
        isFirstFrameRef.current = false;
      }

      // 3. Clear and draw space background
      ctx.fillStyle = '#030508';
      ctx.fillRect(0, 0, width, height);

      // 4. Draw Parallax Starfield (move stars inversely to camera coordinates)
      if (starFieldRef.current) {
        // Offset starts slightly to create movement depth
        const parallaxX = -cam.x;
        const parallaxY = -cam.y;
        starFieldRef.current.updateAndDraw(ctx, elapsedFrames.current, parallaxX, parallaxY);
      }

      // 5. Apply Camera Transform
      ctx.save();
      // Apply translation to keep focus target in screen center
      ctx.translate(centerX, centerY);
      ctx.scale(cam.scale, cam.scale);
      ctx.translate(-cam.x, -cam.y);

      // Draw ambient glow from Sun in world coordinates
      const spaceGlow = ctx.createRadialGradient(
        centerX, centerY, 0,
        centerX, centerY, Math.max(width, height) * 0.7
      );
      spaceGlow.addColorStop(0, 'rgba(253, 184, 19, 0.12)');
      spaceGlow.addColorStop(0.4, 'rgba(13, 18, 30, 0.15)');
      spaceGlow.addColorStop(1, 'rgba(3, 5, 8, 0)');
      ctx.fillStyle = spaceGlow;
      ctx.fillRect(-width * 2, -height * 2, width * 4, height * 4);

      // 6. Draw Orbit Paths in World Space
      ctx.save();
      for (const key of Object.keys(PLANET_MAP)) {
        const config = PLANET_MAP[key];
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.03)';
        ctx.lineWidth = 1 / cam.scale; // Maintain thin lines during zoom
        ctx.setLineDash([4, 8]);
        ctx.beginPath();
        ctx.arc(centerX, centerY, config.orbitRadius, 0, Math.PI * 2);
        ctx.stroke();
      }
      ctx.restore();

      // Update positions for this frame
      const positions = updatePositions(centerX, centerY);
      currentPositionsRef.current = positions;

      // 7. Draw Sun (Core AI)
      ctx.save();
      const sunPulse = Math.sin(elapsedFrames.current * 0.02) * 2.5;
      const sunBaseSize = 42;
      const sunSize = sunBaseSize + sunPulse;

      // Outer Corona
      const numCoronaLayers = 3;
      for (let i = 0; i < numCoronaLayers; i++) {
        const layerPulse = Math.sin(elapsedFrames.current * (0.015 - i * 0.003)) * (6 - i * 2);
        const radius = sunBaseSize + (i * 12) + layerPulse;
        const opacity = (0.12 - i * 0.035) * (0.8 + Math.sin(elapsedFrames.current * 0.03) * 0.2);
        
        ctx.fillStyle = 'rgba(255, 190, 40, 1)';
        ctx.globalAlpha = Math.max(0.01, opacity);
        ctx.beginPath();
        ctx.arc(centerX, centerY, radius, 0, Math.PI * 2);
        ctx.fill();
      }

      // Core Gradient
      const sunGrad = ctx.createRadialGradient(
        centerX, centerY, 0,
        centerX, centerY, sunSize
      );
      sunGrad.addColorStop(0, '#ffffff');
      sunGrad.addColorStop(0.25, '#fff9db');
      sunGrad.addColorStop(0.75, '#fcc419');
      sunGrad.addColorStop(1, 'rgba(230, 60, 0, 0.7)');

      ctx.globalAlpha = 1.0;
      ctx.fillStyle = sunGrad;
      ctx.beginPath();
      ctx.arc(centerX, centerY, sunSize, 0, Math.PI * 2);
      ctx.fill();

      // Tech Ring
      ctx.strokeStyle = 'rgba(255, 190, 40, 0.15)';
      ctx.lineWidth = 1.2 / cam.scale;
      ctx.setLineDash([3, 12]);
      ctx.beginPath();
      ctx.arc(centerX, centerY, sunBaseSize + 22, elapsedFrames.current * 0.002, elapsedFrames.current * 0.002 + Math.PI * 2);
      ctx.stroke();
      ctx.restore();

      // 8. Draw Planets
      for (const key of Object.keys(PLANET_MAP)) {
        const config = PLANET_MAP[key];
        const pos = positions[key];
        if (!pos) continue;

        ctx.save();

        // Saturn Rings (behind)
        if (config.id === 'saturn') {
          drawSaturnRings(ctx, pos.x, pos.y, config.size, elapsedFrames.current, true);
        }

        // Planet Body 3D Shading
        const dx = pos.x - centerX;
        const dy = pos.y - centerY;
        const dist = Math.sqrt(dx * dx + dy * dy);
        const ux = dx / dist;
        const uy = dy / dist;

        const lightShift = config.size * 0.45;
        const fx = pos.x - ux * lightShift;
        const fy = pos.y - uy * lightShift;

        const planetGrad = ctx.createRadialGradient(
          fx, fy, 0,
          pos.x, pos.y, config.size
        );
        planetGrad.addColorStop(0, config.accentColor);
        planetGrad.addColorStop(0.4, config.baseColor);
        planetGrad.addColorStop(1, '#040608');

        ctx.fillStyle = planetGrad;
        ctx.shadowColor = config.accentColor;
        ctx.shadowBlur = 5 / cam.scale; // Scale shadow size with zoom
        ctx.beginPath();
        ctx.arc(pos.x, pos.y, config.size, 0, Math.PI * 2);
        ctx.fill();

        ctx.shadowBlur = 0;

        // Saturn Rings (front)
        if (config.id === 'saturn') {
          drawSaturnRings(ctx, pos.x, pos.y, config.size, elapsedFrames.current, false);
        }

        // Earth Clouds
        if (config.id === 'earth') {
          drawEarthClouds(ctx, pos.x, pos.y, config.size, elapsedFrames.current);
        }

        // Europa Hex cracks
        if (config.id === 'europa') {
          drawEuropaHexGrid(ctx, pos.x, pos.y, config.size, elapsedFrames.current);
        }

        // Render Hover ring indicator (Phase 2 dynamic UI)
        if (hoveredPlanetId === config.id && activePlanetId !== config.id) {
          ctx.strokeStyle = config.accentColor;
          ctx.lineWidth = 1.5 / cam.scale;
          ctx.setLineDash([4, 4]);
          ctx.beginPath();
          ctx.arc(pos.x, pos.y, config.size + 6, elapsedFrames.current * 0.01, elapsedFrames.current * 0.01 + Math.PI * 2);
          ctx.stroke();
        }

        // Planet labels - render cleaner and hide when closely zoomed in
        if (activePlanetId !== config.id) {
          ctx.fillStyle = 'rgba(255, 255, 255, 0.4)';
          ctx.font = `${Math.max(10, Math.min(13, 11 / cam.scale))}px "Outfit"`;
          ctx.textAlign = 'center';
          ctx.fillText(config.name, pos.x, pos.y + config.size + 15 / cam.scale);
        }

        ctx.restore();
      }

      ctx.restore(); // Revert Camera transform

      animationFrameId.current = requestAnimationFrame(render);
    };

    render();

    return () => {
      window.removeEventListener('resize', resizeCanvas);
      if (animationFrameId.current) {
        cancelAnimationFrame(animationFrameId.current);
      }
    };
  }, [updatePositions, activePlanetId, hoveredPlanetId, updateCamera]);

  // Screen click hit testing
  const handleCanvasClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const sx = e.clientX - rect.left;
    const sy = e.clientY - rect.top;

    const centerX = canvas.width / 2;
    const centerY = canvas.height / 2;

    // Inverse transform camera coordinates (s -> w)
    const wx = currentX.current + (sx - centerX) / currentScale.current;
    const wy = currentY.current + (sy - centerY) / currentScale.current;

    let clickedPlanetId: string | null = null;

    for (const key of Object.keys(PLANET_MAP)) {
      const config = PLANET_MAP[key];
      const pos = currentPositionsRef.current[key];
      if (!pos) continue;

      const dx = wx - pos.x;
      const dy = wy - pos.y;
      const dist = Math.sqrt(dx * dx + dy * dy);

      // Hitbox padding for comfort
      if (dist <= config.size * 1.8) {
        clickedPlanetId = config.id;
        break;
      }
    }

    if (clickedPlanetId) {
      focusOnPlanet(clickedPlanetId);
    }
  };

  // Screen mousemove hover test
  const handleCanvasMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const sx = e.clientX - rect.left;
    const sy = e.clientY - rect.top;

    const centerX = canvas.width / 2;
    const centerY = canvas.height / 2;

    const wx = currentX.current + (sx - centerX) / currentScale.current;
    const wy = currentY.current + (sy - centerY) / currentScale.current;

    let hoveringPlanetId: string | null = null;

    for (const key of Object.keys(PLANET_MAP)) {
      const config = PLANET_MAP[key];
      const pos = currentPositionsRef.current[key];
      if (!pos) continue;

      const dx = wx - pos.x;
      const dy = wy - pos.y;
      const dist = Math.sqrt(dx * dx + dy * dy);

      if (dist <= config.size * 1.8) {
        hoveringPlanetId = config.id;
        break;
      }
    }

    if (hoveringPlanetId) {
      canvas.style.cursor = 'pointer';
      setHoveredPlanetId(hoveringPlanetId);
    } else {
      canvas.style.cursor = 'default';
      setHoveredPlanetId(null);
    }
  };

  // Saturn rings split drawing
  const drawSaturnRings = (
    ctx: CanvasRenderingContext2D,
    x: number,
    y: number,
    planetSize: number,
    frames: number,
    behind: boolean
  ) => {
    ctx.save();
    ctx.translate(x, y);
    ctx.rotate(0.3);

    const rx = planetSize * 1.95;
    const ry = planetSize * 0.46;
    const startAngle = behind ? Math.PI : 0;
    const endAngle = behind ? 0 : Math.PI;

    const ringGrad = ctx.createLinearGradient(-rx, 0, rx, 0);
    ringGrad.addColorStop(0, 'rgba(233, 196, 106, 0.2)');
    ringGrad.addColorStop(0.35, 'rgba(244, 162, 97, 0.85)');
    ringGrad.addColorStop(0.5, 'rgba(233, 196, 106, 0.95)');
    ringGrad.addColorStop(0.65, 'rgba(244, 162, 97, 0.85)');
    ringGrad.addColorStop(1, 'rgba(233, 196, 106, 0.2)');

    ctx.strokeStyle = ringGrad;
    ctx.lineWidth = planetSize * 0.42;
    ctx.lineCap = 'round';

    ctx.beginPath();
    ctx.ellipse(0, 0, rx - ctx.lineWidth/2, ry - ctx.lineWidth/2 * (ry/rx), 0, startAngle, endAngle, false);
    ctx.stroke();

    ctx.strokeStyle = 'rgba(10, 15, 25, 0.9)';
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.ellipse(0, 0, rx * 0.8, ry * 0.8, 0, startAngle, endAngle, false);
    ctx.stroke();

    ctx.restore();
  };

  const drawEarthClouds = (ctx: CanvasRenderingContext2D, x: number, y: number, size: number, frames: number) => {
    ctx.save();
    ctx.beginPath();
    ctx.arc(x, y, size, 0, Math.PI * 2);
    ctx.clip();
    ctx.fillStyle = 'rgba(255, 255, 255, 0.32)';
    const speed = frames * 0.003;
    ctx.beginPath();
    ctx.arc(x - size * 0.5 + Math.sin(speed) * 4, y - size * 0.3, size * 0.4, 0, Math.PI * 2);
    ctx.arc(x + size * 0.3 + Math.cos(speed * 0.8) * 3, y + size * 0.2, size * 0.35, 0, Math.PI * 2);
    ctx.arc(x - size * 0.1 + Math.sin(speed * 1.2) * 5, y + size * 0.5, size * 0.25, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();
  };

  const drawEuropaHexGrid = (ctx: CanvasRenderingContext2D, x: number, y: number, size: number, frames: number) => {
    ctx.save();
    ctx.beginPath();
    ctx.arc(x, y, size, 0, Math.PI * 2);
    ctx.clip();
    ctx.strokeStyle = 'rgba(102, 217, 232, 0.16)';
    ctx.lineWidth = 0.5;
    const spacing = size / 2.5;
    ctx.beginPath();
    for (let i = -size; i < size; i += spacing) {
      ctx.moveTo(x + i, y - size);
      ctx.lineTo(x + i + size, y + size);
      ctx.moveTo(x + i, y + size);
      ctx.lineTo(x + i - size, y - size);
    }
    ctx.stroke();
    const shimmer = Math.abs(Math.sin(frames * 0.015));
    ctx.strokeStyle = `rgba(231, 245, 255, ${shimmer * 0.45})`;
    ctx.lineWidth = 0.8;
    ctx.beginPath();
    ctx.moveTo(x - size * 0.4, y - size * 0.2);
    ctx.lineTo(x - size * 0.1, y + size * 0.3);
    ctx.lineTo(x + size * 0.4, y + size * 0.1);
    ctx.stroke();
    ctx.restore();
  };

  return (
    <canvas
      ref={canvasRef}
      onClick={handleCanvasClick}
      onMouseMove={handleCanvasMouseMove}
      style={{
        display: 'block',
        width: '100%',
        height: '100%',
      }}
    />
  );
};
