import { useRef } from 'react';
import { PLANET_MAP, PlanetConfig } from '../components/Planet';

export interface PlanetPosition {
  id: string;
  x: number;
  y: number;
  angle: number;
}

export const usePlanetOrbit = () => {
  // Store the active orbit angles using a ref to prevent triggering React state updates on every frame
  const anglesRef = useRef<Record<string, number>>({
    earth: Math.random() * Math.PI * 2,
    mars: Math.random() * Math.PI * 2,
    europa: Math.random() * Math.PI * 2,
    saturn: Math.random() * Math.PI * 2,
    jupiter: Math.random() * Math.PI * 2,
  });

  const updatePositions = (
    centerX: number,
    centerY: number,
    timeDelta = 1
  ): Record<string, PlanetPosition> => {
    const positions: Record<string, PlanetPosition> = {};

    for (const key of Object.keys(PLANET_MAP)) {
      const config = PLANET_MAP[key];
      // Increment the angle based on the planet's orbit speed
      anglesRef.current[key] += config.orbitSpeed * timeDelta;
      const angle = anglesRef.current[key];

      // Calculate trigonometry position
      const x = centerX + config.orbitRadius * Math.cos(angle);
      const y = centerY + config.orbitRadius * Math.sin(angle);

      positions[key] = {
        id: config.id,
        x,
        y,
        angle,
      };
    }

    return positions;
  };

  return { updatePositions, anglesRef };
};
