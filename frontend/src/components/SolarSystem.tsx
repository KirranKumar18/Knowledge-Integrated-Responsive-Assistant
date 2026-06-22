import React, { useEffect, useRef, useState } from 'react';
import { PLANET_MAP, PlanetConfig } from './Planet';
import { StarField } from './StarField';
import { usePlanetOrbit, PlanetPosition } from '../hooks/usePlanetOrbit';

export interface CalendarEvent {
  summary: string;
  start: string;
}

export interface GitHubRepo {
  name: string;
  stars: number;
  url: string;
}

interface SolarSystemProps {
  activePlanetId: string | null;
  focusOnPlanet: (id: string) => void;
  resetToOverview: () => void;
  updateCamera: (targetX: number, targetY: number, targetScale: number, isFirstFrame?: boolean) => { x: number; y: number; scale: number };
  currentX: React.MutableRefObject<number>;
  currentY: React.MutableRefObject<number>;
  currentScale: React.MutableRefObject<number>;
  isRecording: boolean;
  amplitude: number;
  onSunPress: () => void;
  onSunRelease: () => void;
  kiraLoading: boolean;

  // Phase 5 Additions
  productivityTime: number;
  calendarEvents: CalendarEvent[];
  responseTime: number;
  lastGithubRepos: GitHubRepo[];
  githubEmptyResult: boolean;
}

export const SolarSystem: React.FC<SolarSystemProps> = ({
  activePlanetId,
  focusOnPlanet,
  resetToOverview,
  updateCamera,
  currentX,
  currentY,
  currentScale,
  isRecording,
  amplitude,
  onSunPress,
  onSunRelease,
  kiraLoading,

  productivityTime,
  calendarEvents,
  responseTime,
  lastGithubRepos,
  githubEmptyResult,
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const starFieldRef = useRef<StarField | null>(null);
  const animationFrameId = useRef<number | null>(null);
  const elapsedFrames = useRef<number>(0);
  
  const [hoveredPlanetId, setHoveredPlanetId] = useState<string | null>(null);
  const [isPressingSun, setIsPressingSun] = useState(false);
  const currentPositionsRef = useRef<Record<string, PlanetPosition>>({});
  const isFirstFrameRef = useRef<boolean>(true);

  const { updatePositions } = usePlanetOrbit();

  // Escape listener to zoom out
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        resetToOverview();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [resetToOverview]);

  // Window resize handler
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

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
      const ctx = canvas.getContext('2d');
      if (!ctx) return;

      elapsedFrames.current += 1;
      const width = canvas.width;
      const height = canvas.height;
      const centerX = width / 2;
      const centerY = height / 2;

      // 1. Calculate camera target
      let targetX = centerX;
      let targetY = centerY;
      let targetScale = 0.85;

      if (activePlanetId) {
        const activePlanetPos = currentPositionsRef.current[activePlanetId];
        if (activePlanetPos) {
          targetX = activePlanetPos.x;
          targetY = activePlanetPos.y;
          targetScale = activePlanetId === 'jupiter' ? 2.2 : 3.2;
        }
      }

      // 2. Easing camera updates
      const cam = updateCamera(targetX, targetY, targetScale, isFirstFrameRef.current);
      if (isFirstFrameRef.current) {
        isFirstFrameRef.current = false;
      }

      // 3. Draw background
      ctx.fillStyle = '#030508';
      ctx.fillRect(0, 0, width, height);

      // 4. Draw Parallax Stars
      if (starFieldRef.current) {
        const parallaxX = -cam.x;
        const parallaxY = -cam.y;
        starFieldRef.current.updateAndDraw(ctx, elapsedFrames.current, parallaxX, parallaxY);
      }

      // 5. Apply Camera Matrix
      ctx.save();
      ctx.translate(centerX, centerY);
      ctx.scale(cam.scale, cam.scale);
      ctx.translate(-cam.x, -cam.y);

      // Deep space ambient radial glow
      const spaceGlow = ctx.createRadialGradient(
        centerX, centerY, 0,
        centerX, centerY, Math.max(width, height) * 0.7
      );
      
      if (isRecording) {
        spaceGlow.addColorStop(0, 'rgba(252, 196, 25, 0.25)');
        spaceGlow.addColorStop(0.4, 'rgba(253, 126, 20, 0.08)');
      } else if (kiraLoading) {
        spaceGlow.addColorStop(0, 'rgba(255, 255, 255, 0.2)');
        spaceGlow.addColorStop(0.3, 'rgba(92, 124, 250, 0.08)');
      } else {
        spaceGlow.addColorStop(0, 'rgba(253, 184, 19, 0.12)');
        spaceGlow.addColorStop(0.4, 'rgba(13, 18, 30, 0.15)');
      }
      spaceGlow.addColorStop(1, 'rgba(3, 5, 8, 0)');
      ctx.fillStyle = spaceGlow;
      ctx.fillRect(-width * 2, -height * 2, width * 4, height * 4);

      // 6. Draw Orbit Paths
      ctx.save();
      for (const key of Object.keys(PLANET_MAP)) {
        const config = PLANET_MAP[key];
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.03)';
        ctx.lineWidth = 1 / cam.scale;
        ctx.setLineDash([4, 8]);
        ctx.beginPath();
        ctx.arc(centerX, centerY, config.orbitRadius, 0, Math.PI * 2);
        ctx.stroke();
      }
      ctx.restore();

      const positions = updatePositions(centerX, centerY);
      currentPositionsRef.current = positions;

      // 7. Draw Sun (Core KIRA AI)
      ctx.save();
      
      // Speed up or slow down pulse based on server response time
      const sunSpeedMultiplier = Math.max(0.2, Math.min(5.0, 1000 / responseTime));
      let sunPulse = Math.sin(elapsedFrames.current * 0.02 * sunSpeedMultiplier) * 2.5;
      let sunBaseSize = 42;
      
      if (isRecording) {
        sunPulse = Math.sin(elapsedFrames.current * 0.08) * 3 + amplitude * 18;
      } else if (kiraLoading) {
        const flicker = Math.random() * 4 - 2;
        sunPulse = Math.sin(elapsedFrames.current * 0.15) * 4.5 + flicker;
      }
      
      const sunSize = sunBaseSize + sunPulse;

      // Real-time voice amplitude rings
      if (isRecording && amplitude > 0.05) {
        ctx.save();
        const numRings = 3;
        for (let i = 0; i < numRings; i++) {
          const ringRadius = sunSize + 15 + (i * 22) + (amplitude * 32);
          const ringOpacity = Math.max(0.01, (0.4 - i * 0.12) * (1 - amplitude * 0.3));
          
          ctx.strokeStyle = 'rgba(252, 196, 25, 1)';
          ctx.globalAlpha = ringOpacity;
          ctx.lineWidth = 2 / cam.scale;
          ctx.setLineDash([6, 12]);
          ctx.beginPath();
          ctx.arc(centerX, centerY, ringRadius, elapsedFrames.current * 0.005 + (i * Math.PI / 3), elapsedFrames.current * 0.005 + (i * Math.PI / 3) + Math.PI * 2);
          ctx.stroke();
        }
        ctx.restore();
      }

      // Pulsing Corona Halos
      const numCoronaLayers = 3;
      for (let i = 0; i < numCoronaLayers; i++) {
        let speedCoeff = (0.015 - i * 0.003) * sunSpeedMultiplier;
        let scaleCoeff = 6 - i * 2;
        if (kiraLoading) {
          speedCoeff *= 4;
          scaleCoeff *= 1.4;
        }
        
        const layerPulse = Math.sin(elapsedFrames.current * speedCoeff) * scaleCoeff;
        const radius = sunBaseSize + (i * 12) + layerPulse;
        let opacity = (0.12 - i * 0.035) * (0.8 + Math.sin(elapsedFrames.current * 0.03) * 0.2);
        if (kiraLoading) opacity *= 1.6;
        
        ctx.fillStyle = kiraLoading ? 'rgba(255, 236, 153, 1)' : 'rgba(255, 190, 40, 1)';
        ctx.globalAlpha = Math.max(0.01, Math.min(0.9, opacity));
        ctx.beginPath();
        ctx.arc(centerX, centerY, radius, 0, Math.PI * 2);
        ctx.fill();
      }

      // Sun Core Gradient
      const sunGrad = ctx.createRadialGradient(
        centerX, centerY, 0,
        centerX, centerY, sunSize
      );
      if (kiraLoading) {
        sunGrad.addColorStop(0, '#ffffff');
        sunGrad.addColorStop(0.3, '#fff9db');
        sunGrad.addColorStop(0.8, '#ffd43b');
        sunGrad.addColorStop(1, 'rgba(252, 196, 25, 0.95)');
      } else {
        sunGrad.addColorStop(0, '#ffffff');
        sunGrad.addColorStop(0.25, '#fff9db');
        sunGrad.addColorStop(0.75, '#fcc419');
        sunGrad.addColorStop(1, 'rgba(230, 60, 0, 0.7)');
      }

      ctx.globalAlpha = 1.0;
      ctx.fillStyle = sunGrad;
      ctx.beginPath();
      ctx.arc(centerX, centerY, sunSize, 0, Math.PI * 2);
      ctx.fill();

      // Tech status ring
      ctx.strokeStyle = isRecording ? 'rgba(252, 196, 25, 0.45)' : 'rgba(255, 190, 40, 0.15)';
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
          drawSaturnRings(
            ctx,
            pos.x,
            pos.y,
            config.size,
            elapsedFrames.current,
            true,
            calendarEvents.length,
            calendarEvents,
            cam.scale,
            activePlanetId
          );
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

        if (config.id === 'mars') {
          drawMarsSurface(ctx, pos.x, pos.y, config.size, elapsedFrames.current, productivityTime);
        } else {
          const planetGrad = ctx.createRadialGradient(
            fx, fy, 0,
            pos.x, pos.y, config.size
          );
          planetGrad.addColorStop(0, config.accentColor);
          planetGrad.addColorStop(0.4, config.baseColor);
          planetGrad.addColorStop(1, '#040608');

          ctx.fillStyle = planetGrad;
          ctx.shadowColor = config.accentColor;
          ctx.shadowBlur = 5 / cam.scale;
          ctx.beginPath();
          ctx.arc(pos.x, pos.y, config.size, 0, Math.PI * 2);
          ctx.fill();
          ctx.shadowBlur = 0;
        }

        // Saturn Rings (front)
        if (config.id === 'saturn') {
          drawSaturnRings(
            ctx,
            pos.x,
            pos.y,
            config.size,
            elapsedFrames.current,
            false,
            calendarEvents.length,
            calendarEvents,
            cam.scale,
            activePlanetId
          );
        }

        // Earth Clouds
        if (config.id === 'earth') {
          drawEarthClouds(ctx, pos.x, pos.y, config.size, elapsedFrames.current);
        }

        // Europa Hex cracks & pillars
        if (config.id === 'europa') {
          drawEuropaHexGrid(ctx, pos.x, pos.y, config.size, elapsedFrames.current, githubEmptyResult);
          drawEuropaPillars(ctx, pos.x, pos.y, config.size, lastGithubRepos, cam.scale, activePlanetId);
        }

        // Hover Ring
        if (hoveredPlanetId === config.id && activePlanetId !== config.id) {
          ctx.strokeStyle = config.accentColor;
          ctx.lineWidth = 1.5 / cam.scale;
          ctx.setLineDash([4, 4]);
          ctx.beginPath();
          ctx.arc(pos.x, pos.y, config.size + 6, elapsedFrames.current * 0.01, elapsedFrames.current * 0.01 + Math.PI * 2);
          ctx.stroke();
        }

        // Planet label
        if (activePlanetId !== config.id) {
          ctx.fillStyle = 'rgba(255, 255, 255, 0.4)';
          ctx.font = `${Math.max(10, Math.min(13, 11 / cam.scale))}px "Outfit"`;
          ctx.textAlign = 'center';
          ctx.fillText(config.name, pos.x, pos.y + config.size + 15 / cam.scale);
        }

        ctx.restore();
      }

      // 9. Draw Hologram Connector Line in World Coordinates (Phase 4)
      if (activePlanetId) {
        const hologram = document.getElementById('hologram-overlay');
        if (hologram) {
          const config = PLANET_MAP[activePlanetId];
          const pos = positions[activePlanetId];
          if (pos && config) {
            ctx.save();
            ctx.strokeStyle = config.accentColor;
            ctx.lineWidth = 1.5 / cam.scale;
            ctx.globalAlpha = 0.7;
            ctx.setLineDash([2, 4]); // tech dashed line

            ctx.beginPath();
            // Start at planet edge (not center)
            const dx = pos.x - centerX;
            const dy = pos.y - centerY;
            const dist = Math.sqrt(dx * dx + dy * dy);
            const ux = dx / dist;
            const uy = dy / dist;
            ctx.moveTo(pos.x + ux * config.size, pos.y + uy * config.size);

            // Tech callout angles
            ctx.lineTo(pos.x + 30 / cam.scale, pos.y - 30 / cam.scale);
            ctx.lineTo(pos.x + 50 / cam.scale, pos.y - 40 / cam.scale);
            ctx.stroke();

            // End indicator point
            ctx.fillStyle = config.accentColor;
            ctx.globalAlpha = 0.95;
            ctx.beginPath();
            ctx.arc(pos.x + 50 / cam.scale, pos.y - 40 / cam.scale, 2.5 / cam.scale, 0, Math.PI * 2);
            ctx.fill();
            ctx.restore();
          }
        }
      }

      ctx.restore(); // Revert Camera transform

      // 10. Update Hologram Position directly in DOM for 60fps locking (Phase 4)
      const hologram = document.getElementById('hologram-overlay');
      if (hologram && activePlanetId) {
        const activePlanetPos = currentPositionsRef.current[activePlanetId];
        if (activePlanetPos) {
          const sx = centerX + (activePlanetPos.x - cam.x) * cam.scale;
          const sy = centerY + (activePlanetPos.y - cam.y) * cam.scale;
          
          hologram.style.left = `${sx + 50}px`;
          hologram.style.top = `${sy - 40}px`;
        }
      }

      animationFrameId.current = requestAnimationFrame(render);
    };

    render();

    return () => {
      window.removeEventListener('resize', resizeCanvas);
      if (animationFrameId.current) {
        cancelAnimationFrame(animationFrameId.current);
      }
    };
  }, [updatePositions, activePlanetId, hoveredPlanetId, updateCamera, isRecording, amplitude, kiraLoading]);

  // Screen click hit testing
  const handleCanvasClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (isPressingSun) {
      setIsPressingSun(false);
      return;
    }

    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const sx = e.clientX - rect.left;
    const sy = e.clientY - rect.top;

    const centerX = canvas.width / 2;
    const centerY = canvas.height / 2;

    const wx = currentX.current + (sx - centerX) / currentScale.current;
    const wy = currentY.current + (sy - centerY) / currentScale.current;

    // Check if clicked Europa's pillars
    if (activePlanetId === 'europa' && lastGithubRepos.length > 0) {
      const pos = currentPositionsRef.current['europa'];
      if (pos) {
        let clickedPillarUrl: string | null = null;
        lastGithubRepos.forEach((repo, idx) => {
          const numRepos = lastGithubRepos.length;
          const spacing = 28 / currentScale.current;
          const px = pos.x + (idx - (numRepos - 1) / 2) * spacing;
          
          const stars = repo.stars;
          const minHeight = 12 / currentScale.current;
          const maxHeight = 50 / currentScale.current;
          const height = stars > 0 ? Math.min(maxHeight, minHeight + Math.log10(stars) * (8 / currentScale.current)) : minHeight;
          const width = 8 / currentScale.current;

          const leftBound = px - width/2;
          const rightBound = px + width/2;
          const topBound = pos.y - height;
          const bottomBound = pos.y;

          if (wx >= leftBound && wx <= rightBound && wy >= topBound && wy <= bottomBound) {
            clickedPillarUrl = repo.url;
          }
        });

        if (clickedPillarUrl) {
          window.open(clickedPillarUrl, '_blank');
          return;
        }
      }
    }

    const dxSun = wx - centerX;
    const dySun = wy - centerY;
    const sunDist = Math.sqrt(dxSun * dxSun + dySun * dySun);
    if (sunDist <= 50) {
      return;
    }

    let clickedPlanetId: string | null = null;

    for (const key of Object.keys(PLANET_MAP)) {
      const config = PLANET_MAP[key];
      const pos = currentPositionsRef.current[key];
      if (!pos) continue;

      const dx = wx - pos.x;
      const dy = wy - pos.y;
      const dist = Math.sqrt(dx * dx + dy * dy);

      if (dist <= config.size * 1.8) {
        clickedPlanetId = config.id;
        break;
      }
    }

    if (clickedPlanetId) {
      focusOnPlanet(clickedPlanetId);
    }
  };

  // MouseDown listener for Sun press-and-hold
  const handleCanvasMouseDown = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const sx = e.clientX - rect.left;
    const sy = e.clientY - rect.top;

    const centerX = canvas.width / 2;
    const centerY = canvas.height / 2;

    const wx = currentX.current + (sx - centerX) / currentScale.current;
    const wy = currentY.current + (sy - centerY) / currentScale.current;

    const dx = wx - centerX;
    const dy = wy - centerY;
    const dist = Math.sqrt(dx * dx + dy * dy);

    if (dist <= 50) {
      setIsPressingSun(true);
      onSunPress();
    }
  };

  const handleCanvasMouseUp = () => {
    if (isPressingSun) {
      setIsPressingSun(false);
      onSunRelease();
    }
  };

  // Touch handlers for mobile screens
  const handleCanvasTouchStart = (e: React.TouchEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas || e.touches.length === 0) return;
    const rect = canvas.getBoundingClientRect();
    const sx = e.touches[0].clientX - rect.left;
    const sy = e.touches[0].clientY - rect.top;

    const centerX = canvas.width / 2;
    const centerY = canvas.height / 2;

    const wx = currentX.current + (sx - centerX) / currentScale.current;
    const wy = currentY.current + (sy - centerY) / currentScale.current;

    const dx = wx - centerX;
    const dy = wy - centerY;
    const dist = Math.sqrt(dx * dx + dy * dy);

    if (dist <= 50) {
      setIsPressingSun(true);
      onSunPress();
    }
  };

  const handleCanvasTouchEnd = () => {
    if (isPressingSun) {
      setIsPressingSun(false);
      onSunRelease();
    }
  };

  // Saturn rings split drawing
  const drawSaturnRings = (
    ctx: CanvasRenderingContext2D,
    x: number,
    y: number,
    planetSize: number,
    frames: number,
    behind: boolean,
    eventCount: number,
    events: CalendarEvent[],
    camScale: number,
    activePlanetId: string | null
  ) => {
    ctx.save();
    ctx.translate(x, y);
    ctx.rotate(0.3);

    const rx = planetSize * 1.95;
    const ry = planetSize * 0.46;
    const startAngle = behind ? Math.PI : 0;
    const endAngle = behind ? 0 : Math.PI;

    // Ring density/width changes with busier days
    const ringDensityCoeff = 1 + Math.min(2.5, eventCount * 0.25);
    const ringWidth = planetSize * 0.42 * ringDensityCoeff;

    const ringGrad = ctx.createLinearGradient(-rx, 0, rx, 0);
    ringGrad.addColorStop(0, 'rgba(233, 196, 106, 0.2)');
    ringGrad.addColorStop(0.35, 'rgba(244, 162, 97, 0.85)');
    ringGrad.addColorStop(0.5, 'rgba(233, 196, 106, 0.95)');
    ringGrad.addColorStop(0.65, 'rgba(244, 162, 97, 0.85)');
    ringGrad.addColorStop(1, 'rgba(233, 196, 106, 0.2)');

    ctx.strokeStyle = ringGrad;
    ctx.lineWidth = ringWidth;
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

    // Draw Event particles orbiting Saturn
    if (eventCount > 0) {
      events.forEach((evt, idx) => {
        const baseAngle = (idx * (Math.PI * 2) / eventCount);
        const orbitSpeed = 0.0015;
        const currentAngle = baseAngle + frames * orbitSpeed;

        const erx = planetSize * 1.6;
        const ery = planetSize * 0.45;
        const ex = erx * Math.cos(currentAngle);
        const ey_val = ery * Math.sin(currentAngle);

        const rotX = ex * Math.cos(0.3) - ey_val * Math.sin(0.3);
        const rotY = ex * Math.sin(0.3) + ey_val * Math.cos(0.3);

        const px = x + rotX;
        const py = y + rotY;

        const isBehind = Math.sin(currentAngle) < 0;
        if (isBehind !== behind) return;

        ctx.save();
        ctx.fillStyle = '#fff9db';
        ctx.shadowColor = '#fcc419';
        ctx.shadowBlur = 8 / camScale;
        ctx.beginPath();
        ctx.arc(px, py, 2.5 / camScale, 0, Math.PI * 2);
        ctx.fill();
        ctx.shadowBlur = 0;

        if (activePlanetId === 'saturn') {
          ctx.fillStyle = 'rgba(255, 255, 255, 0.85)';
          ctx.font = `${Math.max(6, 8 / camScale)}px "Outfit"`;
          ctx.textAlign = 'left';
          ctx.fillText(evt.summary, px + 5 / camScale, py - 2 / camScale);
        }
        ctx.restore();
      });
    }
  };

  const drawMarsSurface = (
    ctx: CanvasRenderingContext2D,
    x: number,
    y: number,
    size: number,
    frames: number,
    distractionTime: number
  ) => {
    ctx.save();
    ctx.beginPath();
    ctx.arc(x, y, size, 0, Math.PI * 2);
    ctx.clip();

    ctx.fillStyle = '#b23b3b';
    ctx.fillRect(x - size, y - size, size * 2, size * 2);

    ctx.fillStyle = '#7a2222';
    ctx.beginPath();
    ctx.arc(x - size * 0.3, y - size * 0.2, size * 0.4, 0, Math.PI * 2);
    ctx.arc(x + size * 0.4, y + size * 0.3, size * 0.35, 0, Math.PI * 2);
    ctx.fill();

    const stormIntensity = Math.min(1.0, distractionTime / 300);

    if (stormIntensity > 0.05) {
      const numStorms = Math.floor(stormIntensity * 8) + 2;
      ctx.strokeStyle = `rgba(230, 0, 0, ${0.4 + stormIntensity * 0.5})`;
      ctx.lineWidth = 1.5;
      
      for (let i = 0; i < numStorms; i++) {
        const angle = frames * (0.02 + i * 0.01) + (i * Math.PI / 4);
        const rx = size * (0.5 + Math.sin(angle) * 0.3);
        const ry = size * (0.2 + Math.cos(angle) * 0.1);
        
        ctx.beginPath();
        ctx.ellipse(x, y + (i - numStorms/2) * (size * 0.2), rx, ry, 0.1, 0, Math.PI * 2);
        ctx.stroke();
      }
    }

    ctx.restore();

    ctx.save();
    const grad = ctx.createRadialGradient(x, y, size * 0.95, x, y, size * 1.35);
    if (distractionTime > 150) {
      grad.addColorStop(0, 'rgba(120, 10, 10, 0.35)');
      grad.addColorStop(1, 'rgba(0, 0, 0, 0)');
    } else {
      grad.addColorStop(0, 'rgba(40, 200, 100, 0.25)');
      grad.addColorStop(0.5, 'rgba(50, 180, 80, 0.08)');
      grad.addColorStop(1, 'rgba(0, 0, 0, 0)');
    }
    ctx.fillStyle = grad;
    ctx.beginPath();
    ctx.arc(x, y, size * 1.4, 0, Math.PI * 2);
    ctx.fill();
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

  const drawEuropaHexGrid = (ctx: CanvasRenderingContext2D, x: number, y: number, size: number, frames: number, emptyResult: boolean) => {
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
    
    if (emptyResult) {
      ctx.strokeStyle = 'rgba(255, 107, 107, 0.85)';
      ctx.lineWidth = 1.0;
      ctx.beginPath();
      ctx.moveTo(x - size * 0.3, y - size * 0.3);
      ctx.lineTo(x + size * 0.1, y + size * 0.2);
      ctx.lineTo(x + size * 0.4, y + size * 0.4);
      ctx.stroke();
    } else {
      const shimmer = Math.abs(Math.sin(frames * 0.015));
      ctx.strokeStyle = `rgba(231, 245, 255, ${shimmer * 0.45})`;
      ctx.lineWidth = 0.8;
      ctx.beginPath();
      ctx.moveTo(x - size * 0.4, y - size * 0.2);
      ctx.lineTo(x - size * 0.1, y + size * 0.3);
      ctx.lineTo(x + size * 0.4, y + size * 0.1);
      ctx.stroke();
    }
    ctx.restore();
  };

  const drawEuropaPillars = (
    ctx: CanvasRenderingContext2D,
    x: number,
    y: number,
    planetSize: number,
    repos: GitHubRepo[],
    camScale: number,
    activePlanetId: string | null
  ) => {
    if (repos.length === 0) return;

    ctx.save();
    repos.forEach((repo, idx) => {
      const numRepos = repos.length;
      const spacing = 28 / camScale;
      const px = x + (idx - (numRepos - 1) / 2) * spacing;
      
      const stars = repo.stars;
      const minHeight = 12 / camScale;
      const maxHeight = 50 / camScale;
      const height = stars > 0 ? Math.min(maxHeight, minHeight + Math.log10(stars) * (8 / camScale)) : minHeight;
      const width = 8 / camScale;

      const isFocused = activePlanetId === 'europa';
      
      ctx.save();
      if (isFocused) {
        const grad = ctx.createLinearGradient(px - width/2, y, px - width/2, y - height);
        grad.addColorStop(0, 'rgba(102, 217, 232, 0.2)');
        grad.addColorStop(0.7, 'rgba(102, 217, 232, 0.85)');
        grad.addColorStop(1, '#ffffff');
        
        ctx.fillStyle = grad;
        ctx.shadowColor = '#66d9e8';
        ctx.shadowBlur = 10 / camScale;
        
        ctx.beginPath();
        ctx.rect(px - width/2, y - height, width, height);
        ctx.fill();
        ctx.shadowBlur = 0;

        ctx.fillStyle = '#ffffff';
        ctx.beginPath();
        ctx.ellipse(px, y - height, width/2, 2 / camScale, 0, 0, Math.PI * 2);
        ctx.fill();

        ctx.fillStyle = '#e7f5ff';
        ctx.font = `${Math.max(6, 8 / camScale)}px "Share Tech Mono"`;
        ctx.textAlign = 'center';
        
        const cleanName = repo.name.length > 12 ? repo.name.substring(0, 10) + '..' : repo.name;
        ctx.fillText(cleanName, px, y - height - 12 / camScale);
        ctx.fillStyle = '#66d9e8';
        ctx.fillText(`★${stars >= 1000 ? (stars/1000).toFixed(1) + 'k' : stars}`, px, y - height - 4 / camScale);
      } else {
        ctx.strokeStyle = 'rgba(102, 217, 232, 0.35)';
        ctx.lineWidth = 0.5 / camScale;
        ctx.beginPath();
        ctx.rect(px - width/2, y - height * 0.7, width, height * 0.7);
        ctx.stroke();
      }
      ctx.restore();
    });
    ctx.restore();
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

    const dxSun = wx - centerX;
    const dySun = wy - centerY;
    const sunDist = Math.sqrt(dxSun * dxSun + dySun * dySun);
    if (sunDist <= 50) {
      canvas.style.cursor = 'pointer';
      setHoveredPlanetId(null);
      return;
    }

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

  return (
    <canvas
      ref={canvasRef}
      onClick={handleCanvasClick}
      onMouseDown={handleCanvasMouseDown}
      onMouseUp={handleCanvasMouseUp}
      onMouseLeave={handleCanvasMouseUp}
      onTouchStart={handleCanvasTouchStart}
      onTouchEnd={handleCanvasTouchEnd}
      onMouseMove={handleCanvasMouseMove}
      style={{
        display: 'block',
        width: '100%',
        height: '100%',
      }}
    />
  );
};
