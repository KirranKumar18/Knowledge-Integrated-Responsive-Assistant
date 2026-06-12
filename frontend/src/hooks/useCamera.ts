import { useRef, useState } from 'react';

export type CameraState = 'OVERVIEW' | 'APPROACH' | 'ORBIT' | 'SURFACE';

export const useCamera = () => {
  const [activePlanetId, setActivePlanetId] = useState<string | null>(null);
  const [cameraState, setCameraState] = useState<CameraState>('OVERVIEW');

  // We keep the interpolated camera coordinates in refs to update at 60fps without React re-render overhead
  const currentX = useRef<number>(0);
  const currentY = useRef<number>(0);
  const currentScale = useRef<number>(1);

  // Easing/spring properties
  const lerpFactor = 0.06; // Easing speed. Lower = smoother/heavier travel, higher = snappier

  const focusOnPlanet = (planetId: string) => {
    setActivePlanetId(planetId);
    setCameraState('APPROACH');
    // transition state updates can be timed
    setTimeout(() => {
      setCameraState('ORBIT');
    }, 1200); // Orbit state triggers after arrival
  };

  const resetToOverview = () => {
    setActivePlanetId(null);
    setCameraState('OVERVIEW');
  };

  // Interpolates current camera towards target coordinates
  const updateCamera = (
    targetX: number,
    targetY: number,
    targetScale: number,
    isFirstFrame: boolean = false
  ) => {
    if (isFirstFrame) {
      currentX.current = targetX;
      currentY.current = targetY;
      currentScale.current = targetScale;
      return { x: targetX, y: targetY, scale: targetScale };
    }

    // Standard LERP interpolation
    currentX.current += (targetX - currentX.current) * lerpFactor;
    currentY.current += (targetY - currentY.current) * lerpFactor;
    currentScale.current += (targetScale - currentScale.current) * lerpFactor;

    return {
      x: currentX.current,
      y: currentY.current,
      scale: currentScale.current,
    };
  };

  return {
    activePlanetId,
    cameraState,
    focusOnPlanet,
    resetToOverview,
    updateCamera,
    currentX,
    currentY,
    currentScale,
  };
};
