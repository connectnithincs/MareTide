import React, { useEffect, useRef, useState, useCallback } from "react";
import * as THREE from "three";
import { useTheme } from "../../context/ThemeContext";
import { type DigitalTwinContainer, type SelectedContainerInfo, type SelectedTankInfo, type ViewMode } from "../pages/VesselDigitalTwinView";

export interface Vessel3DCanvasProps {
  containers: DigitalTwinContainer[];
  ballastTanks: Record<string, { name: string; current_volume: number; capacity: number; fill_ratio: number }>;
  roll: number;
  pitch: number;
  viewMode: ViewMode;
  selectedContainerId?: string | null;
  selectedTankId?: string | null;
  recommendedSlot?: { bay: number; side: string; tier: number } | null;
  alternativeSlots?: Array<{ bay: number; side: string; tier: number; score?: number }>;
  onSelectContainer: (container: SelectedContainerInfo | null) => void;
  onSelectTank: (tank: SelectedTankInfo | null) => void;
  className?: string;
}

// 4-Bay Longitudinal Coordinate Mapping (meters)
const BAY_X_COORDS: Record<number, number> = {
  1: 10.5,  // Bay 1: Forward Hold (Bow)
  2: 3.5,   // Bay 2: Mid-Forward Hold
  3: -3.5,  // Bay 3: Mid-Aft Hold
  4: -10.5  // Bay 4: Aft Hold (Stern)
};

const SIDE_Z_COORDS = {
  PORT: -3.0,
  STARBOARD: 3.0
};

const TIER_Y_COORDS = {
  1: 1.85, // Base deck tier
  2: 4.45  // High tier
};

const CONTAINER_DIMS = {
  length: 6.2,
  height: 2.5,
  width: 2.6
};

// Shipping Line Brands & Color Themes
const BRAND_THEMES = [
  { name: "MAERSK", color: 0x1B4965 },
  { name: "EVERGREEN", color: 0x195337 },
  { name: "MSC", color: 0xD4AF37 },
  { name: "ONE", color: 0x9E1B32 },
  { name: "HAPAG-LLOYD", color: 0xC05621 }
];

export const Vessel3DCanvas: React.FC<Vessel3DCanvasProps> = ({
  containers,
  ballastTanks,
  roll,
  pitch,
  viewMode,
  selectedContainerId,
  selectedTankId,
  recommendedSlot,
  alternativeSlots = [],
  onSelectContainer,
  onSelectTank,
  className = ""
}) => {
  const { theme } = useTheme();
  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  // Three.js instances ref
  const sceneRef = useRef<THREE.Scene | null>(null);
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null);
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null);
  const vesselGroupRef = useRef<THREE.Group | null>(null);
  const containerMeshesRef = useRef<Map<string, THREE.Group>>(new Map());
  const tankMeshesRef = useRef<Map<string, THREE.Mesh>>(new Map());
  const highlightSlotsGroupRef = useRef<THREE.Group | null>(null);
  const radarMastRef = useRef<THREE.Mesh | null>(null);
  const waterMaterialRef = useRef<THREE.ShaderMaterial | null>(null);

  // Mouse orbit state
  const isDraggingRef = useRef<boolean>(false);
  const previousMousePosRef = useRef<{ x: number; y: number }>({ x: 0, y: 0 });
  const cameraTargetPosRef = useRef<THREE.Vector3>(new THREE.Vector3(32, 22, 32));
  const currentCameraPosRef = useRef<THREE.Vector3>(new THREE.Vector3(32, 22, 32));

  // Raycaster for object clicking
  const raycasterRef = useRef<THREE.Raycaster>(new THREE.Raycaster());
  const mouseCoordsRef = useRef<THREE.Vector2>(new THREE.Vector2());

  // 1. Initialize Scene, Camera, Lights, and Realistic Vessel Geometry
  useEffect(() => {
    if (!containerRef.current || !canvasRef.current) return;

    const width = containerRef.current.clientWidth || 900;
    const height = containerRef.current.clientHeight || 550;

    // A. Create Scene
    const scene = new THREE.Scene();
    const isDark = theme === "dark";
    const bgColor = isDark ? 0x020B18 : 0xEDF2F7;
    scene.background = new THREE.Color(bgColor);
    scene.fog = new THREE.FogExp2(bgColor, isDark ? 0.008 : 0.005);
    sceneRef.current = scene;

    // B. Create Camera
    const camera = new THREE.PerspectiveCamera(42, width / height, 0.1, 1000);
    camera.position.set(32, 22, 32);
    camera.lookAt(0, 2, 0);
    cameraRef.current = camera;

    // C. Create WebGL Renderer
    const renderer = new THREE.WebGLRenderer({
      canvas: canvasRef.current,
      antialias: true,
      powerPreference: "high-performance"
    });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = isDark ? 1.15 : 1.05;
    rendererRef.current = renderer;

    // D. Lighting Setup
    const ambientLight = new THREE.AmbientLight(isDark ? 0xc8e0f8 : 0xffffff, isDark ? 0.85 : 0.95);
    scene.add(ambientLight);

    const hemiLight = new THREE.HemisphereLight(
      isDark ? 0x00D2FF : 0x0284C7, 
      isDark ? 0x06152B : 0x334E68, 
      0.8
    );
    scene.add(hemiLight);

    // Key Sunlight
    const sunLight = new THREE.DirectionalLight(0xfff5e6, isDark ? 1.8 : 1.5);
    sunLight.position.set(35, 55, 30);
    sunLight.castShadow = true;
    sunLight.shadow.mapSize.width = 2048;
    sunLight.shadow.mapSize.height = 2048;
    sunLight.shadow.bias = -0.0001;
    scene.add(sunLight);

    // Fill Ocean Bounce Light
    const oceanFill = new THREE.DirectionalLight(0x00A3FF, 0.6);
    oceanFill.position.set(-35, 20, -30);
    scene.add(oceanFill);

    // E. Dynamic Ocean Water Surface
    const waterVertexShader = `
      varying vec2 vUv;
      varying vec3 vWorldPosition;
      uniform float uTime;
      void main() {
        vUv = uv;
        vec3 pos = position;
        pos.z += sin(pos.x * 0.15 + uTime * 1.2) * 0.15 + cos(pos.y * 0.15 + uTime * 0.9) * 0.12;
        vec4 worldPosition = modelMatrix * vec4(pos, 1.0);
        vWorldPosition = worldPosition.xyz;
        gl_Position = projectionMatrix * viewMatrix * worldPosition;
      }
    `;

    const waterFragmentShader = `
      uniform float uTime;
      uniform float uIsDark;
      varying vec2 vUv;
      varying vec3 vWorldPosition;
      void main() {
        float wave = sin(vWorldPosition.x * 0.3 + uTime * 1.5) * 0.5 + 0.5;
        vec3 deepColor = uIsDark > 0.5 ? vec3(0.01, 0.05, 0.12) : vec3(0.12, 0.28, 0.45);
        vec3 surfaceColor = uIsDark > 0.5 ? vec3(0.03, 0.18, 0.35) : vec3(0.25, 0.52, 0.72);
        vec3 crestColor = vec3(0.0, 0.82, 1.0);
        vec3 color = mix(deepColor, surfaceColor, wave * 0.6);
        // Subtle grid lines
        vec2 grid = abs(fract(vUv * 40.0 - 0.5) - 0.5) / fwidth(vUv * 40.0);
        float line = min(grid.x, grid.y);
        float gridAlpha = 1.0 - min(line, 1.0);
        color = mix(color, crestColor * 0.3, gridAlpha * 0.25);
        gl_FragColor = vec4(color, uIsDark > 0.5 ? 0.92 : 0.85);
      }
    `;

    const waterMat = new THREE.ShaderMaterial({
      vertexShader: waterVertexShader,
      fragmentShader: waterFragmentShader,
      uniforms: {
        uTime: { value: 0 },
        uIsDark: { value: isDark ? 1.0 : 0.0 }
      },
      transparent: true,
      side: THREE.DoubleSide
    });
    waterMaterialRef.current = waterMat;

    const waterGeo = new THREE.PlaneGeometry(160, 160, 64, 64);
    const waterMesh = new THREE.Mesh(waterGeo, waterMat);
    waterMesh.rotation.x = -Math.PI / 2;
    waterMesh.position.y = -0.1;
    scene.add(waterMesh);

    // F. Master Vessel Group (Rotates dynamically with roll/pitch)
    const vesselGroup = new THREE.Group();
    scene.add(vesselGroup);
    vesselGroupRef.current = vesselGroup;

    // G. Highlights Sub-Group
    const highlightsGroup = new THREE.Group();
    vesselGroup.add(highlightsGroup);
    highlightSlotsGroupRef.current = highlightsGroup;

    // Materials Palette
    const antifoulingMat = new THREE.MeshStandardMaterial({
      color: 0x8B1E0F, // Antifouling hull red
      roughness: 0.45,
      metalness: 0.3
    });

    const topsidesNavyMat = new THREE.MeshStandardMaterial({
      color: isDark ? 0x08182B : 0x1E293B, // Naval container ship topsides
      roughness: 0.35,
      metalness: 0.5
    });

    const deckSteelMat = new THREE.MeshStandardMaterial({
      color: isDark ? 0x0C1C2E : 0x334E68, // Weathered industrial deck steel
      roughness: 0.8,
      metalness: 0.25
    });

    const superstructureMat = new THREE.MeshStandardMaterial({
      color: 0xF0F4F8, // Signal white
      roughness: 0.25,
      metalness: 0.2
    });

    const bridgeWindowMat = new THREE.MeshStandardMaterial({
      color: 0x00D2FF,
      roughness: 0.05,
      metalness: 0.95,
      emissive: 0x00D2FF,
      emissiveIntensity: 0.35
    });

    // 1. Lower Keel Antifouling Hull
    const lowerHullShape = new THREE.Shape();
    lowerHullShape.moveTo(-16.5, -1.8);
    lowerHullShape.lineTo(16.0, -1.8);
    lowerHullShape.quadraticCurveTo(19.5, -1.8, 21.0, -0.2); // Bulbous bow taper
    lowerHullShape.lineTo(-17.5, -0.2);
    lowerHullShape.closePath();

    const lowerHullExtrude = new THREE.ExtrudeGeometry(lowerHullShape, {
      steps: 2,
      depth: 9.0,
      bevelEnabled: true,
      bevelThickness: 0.5,
      bevelSize: 0.4,
      bevelSegments: 3
    });
    lowerHullExtrude.center();
    const lowerHull = new THREE.Mesh(lowerHullExtrude, antifoulingMat);
    lowerHull.position.set(0, -0.8, 0);
    lowerHull.castShadow = true;
    lowerHull.receiveShadow = true;
    vesselGroup.add(lowerHull);

    // 2. White Plimsoll Boot-topping Line
    const bootLineGeo = new THREE.BoxGeometry(37.5, 0.18, 9.7);
    const bootLineMat = new THREE.MeshStandardMaterial({ color: 0xFFFFFF, roughness: 0.3 });
    const bootLine = new THREE.Mesh(bootLineGeo, bootLineMat);
    bootLine.position.set(0, 0.02, 0);
    vesselGroup.add(bootLine);

    // 3. Upper Topsides Hull
    const upperHullShape = new THREE.Shape();
    upperHullShape.moveTo(-17.0, 0.0);
    upperHullShape.lineTo(16.5, 0.0);
    upperHullShape.quadraticCurveTo(20.5, 0.2, 23.0, 2.2); // Bow sheer flare
    upperHullShape.lineTo(-17.8, 1.4);
    upperHullShape.closePath();

    const upperHullExtrude = new THREE.ExtrudeGeometry(upperHullShape, {
      steps: 3,
      depth: 9.6,
      bevelEnabled: true,
      bevelThickness: 0.4,
      bevelSize: 0.3,
      bevelSegments: 4
    });
    upperHullExtrude.center();
    const upperHull = new THREE.Mesh(upperHullExtrude, topsidesNavyMat);
    upperHull.position.set(0, 0.9, 0);
    upperHull.castShadow = true;
    upperHull.receiveShadow = true;
    vesselGroup.add(upperHull);

    // 4. Bulbous Bow Teardrop Protrusion
    const bulbGeo = new THREE.SphereGeometry(1.8, 24, 24);
    bulbGeo.scale(2.2, 1.0, 0.9);
    const bulbMesh = new THREE.Mesh(bulbGeo, antifoulingMat);
    bulbMesh.position.set(22.5, -0.8, 0);
    bulbMesh.castShadow = true;
    vesselGroup.add(bulbMesh);

    // 5. Forecastle Deck
    const foreDeckGeo = new THREE.BoxGeometry(7.0, 0.4, 8.8);
    const foreDeck = new THREE.Mesh(foreDeckGeo, deckSteelMat);
    foreDeck.position.set(18.5, 1.6, 0);
    foreDeck.receiveShadow = true;
    vesselGroup.add(foreDeck);

    // 6. Main Cargo Deck Floor
    const deckGeo = new THREE.BoxGeometry(29.0, 0.4, 8.6);
    const deckMesh = new THREE.Mesh(deckGeo, deckSteelMat);
    deckMesh.position.set(0, 0.6, 0);
    deckMesh.receiveShadow = true;
    vesselGroup.add(deckMesh);

    // 7. Raised Cellular Hatch Coamings & Guides for Bays 1, 2, 3, 4
    [1, 2, 3, 4].forEach((bayNum) => {
      const bayX = BAY_X_COORDS[bayNum];

      // Hatch Coaming Box
      const coamingGeo = new THREE.BoxGeometry(6.6, 0.7, 8.4);
      const coamingMat = new THREE.MeshStandardMaterial({ color: isDark ? 0x1A3D68 : 0x475569, metalness: 0.5 });
      const coaming = new THREE.Mesh(coamingGeo, coamingMat);
      coaming.position.set(bayX, 0.95, 0);
      coaming.castShadow = true;
      coaming.receiveShadow = true;
      vesselGroup.add(coaming);

      // Vertical Cell Guide Corner Rails
      const railMat = new THREE.MeshStandardMaterial({ color: isDark ? 0x285D96 : 0x64748B, metalness: 0.8 });
      [-3.3, 3.3].forEach((xOff) => {
        [-4.1, 0, 4.1].forEach((zOff) => {
          const guideGeo = new THREE.BoxGeometry(0.18, 5.8, 0.18);
          const guide = new THREE.Mesh(guideGeo, railMat);
          guide.position.set(bayX + xOff, 3.6, zOff);
          vesselGroup.add(guide);
        });
      });
    });

    // 8. Superstructure & Navigational Bridge (Aft Deckhouse)
    const bridgeBaseGeo = new THREE.BoxGeometry(5.2, 5.5, 8.2);
    const bridgeBase = new THREE.Mesh(bridgeBaseGeo, superstructureMat);
    bridgeBase.position.set(-15.2, 3.8, 0);
    bridgeBase.castShadow = true;
    bridgeBase.receiveShadow = true;
    vesselGroup.add(bridgeBase);

    // Wheelhouse Bridge Wings
    const bridgeTopGeo = new THREE.BoxGeometry(3.6, 1.8, 10.4);
    const bridgeTop = new THREE.Mesh(bridgeTopGeo, superstructureMat);
    bridgeTop.position.set(-15.2, 7.2, 0);
    bridgeTop.castShadow = true;
    vesselGroup.add(bridgeTop);

    // Bridge Windows Panoramic Band
    const windowGeo = new THREE.BoxGeometry(3.7, 0.75, 10.5);
    const bridgeWindows = new THREE.Mesh(windowGeo, bridgeWindowMat);
    bridgeWindows.position.set(-15.2, 7.35, 0);
    vesselGroup.add(bridgeWindows);

    // Engine Exhaust Funnel
    const funnelGeo = new THREE.CylinderGeometry(0.9, 1.1, 3.8, 16);
    const funnelMat = new THREE.MeshStandardMaterial({ color: 0x00E5FF, roughness: 0.2, metalness: 0.6 });
    const funnel = new THREE.Mesh(funnelGeo, funnelMat);
    funnel.position.set(-17.2, 8.2, 0);
    funnel.rotation.z = -0.08;
    vesselGroup.add(funnel);

    // Radar Mast
    const mastGeo = new THREE.CylinderGeometry(0.08, 0.14, 4.2);
    const mast = new THREE.Mesh(mastGeo, superstructureMat);
    mast.position.set(-15.2, 10.2, 0);
    vesselGroup.add(mast);

    // Rotating Radar Scanner
    const scannerGeo = new THREE.BoxGeometry(1.6, 0.15, 0.25);
    const scannerMat = new THREE.MeshStandardMaterial({ color: 0x00E5FF, emissive: 0x00E5FF, emissiveIntensity: 0.5 });
    const scanner = new THREE.Mesh(scannerGeo, scannerMat);
    scanner.position.set(-15.2, 12.3, 0);
    vesselGroup.add(scanner);
    radarMastRef.current = scanner;

    // -------------------------------------------------------------
    // ANIMATION & RENDER LOOP
    // -------------------------------------------------------------
    let animationFrameId: number;
    let clock = new THREE.Clock();

    const animate = () => {
      animationFrameId = requestAnimationFrame(animate);
      const elapsedTime = clock.getElapsedTime();

      // Rotate radar scanner
      if (radarMastRef.current) {
        radarMastRef.current.rotation.y += 0.05;
      }

      // Dynamic water waves shader
      if (waterMaterialRef.current) {
        waterMaterialRef.current.uniforms.uTime.value = elapsedTime;
      }

      // Smooth camera interpolation towards target
      if (cameraRef.current) {
        currentCameraPosRef.current.lerp(cameraTargetPosRef.current, 0.08);
        cameraRef.current.position.copy(currentCameraPosRef.current);
        cameraRef.current.lookAt(0, 2, 0);
      }

      // Dynamic vessel roll/pitch attitude from backend telemetry
      if (vesselGroupRef.current) {
        // Roll: rotation along longitudinal X-axis
        const targetRollRad = THREE.MathUtils.degToRad(-roll);
        // Pitch: rotation along transverse Z-axis
        const targetPitchRad = THREE.MathUtils.degToRad(pitch);

        vesselGroupRef.current.rotation.x = THREE.MathUtils.lerp(vesselGroupRef.current.rotation.x, targetRollRad, 0.1);
        vesselGroupRef.current.rotation.z = THREE.MathUtils.lerp(vesselGroupRef.current.rotation.z, targetPitchRad, 0.1);
      }

      renderer.render(scene, camera);
    };

    animate();

    // Resize Handler
    const handleResize = () => {
      if (!containerRef.current || !rendererRef.current || !cameraRef.current) return;
      const newWidth = containerRef.current.clientWidth;
      const newHeight = containerRef.current.clientHeight;
      cameraRef.current.aspect = newWidth / newHeight;
      cameraRef.current.updateProjectionMatrix();
      rendererRef.current.setSize(newWidth, newHeight);
    };

    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      cancelAnimationFrame(animationFrameId);
      renderer.dispose();
    };
  }, [theme]);

  // 2. Camera View Mode Presets Handler
  useEffect(() => {
    if (!cameraRef.current) return;
    const presets: Record<ViewMode, THREE.Vector3> = {
      ISOMETRIC: new THREE.Vector3(32, 22, 32),
      TOP: new THREE.Vector3(0, 48, 0.1),
      SIDE: new THREE.Vector3(0, 4, 44),
      FRONT: new THREE.Vector3(44, 4, 0)
    };

    const targetPos = presets[viewMode] || presets.ISOMETRIC;
    cameraTargetPosRef.current.copy(targetPos);
  }, [viewMode]);

  // 3. Helper: Create Container Mesh with Ribs and Castings
  const createRealisticContainer = (c: DigitalTwinContainer, idx: number, isSelected: boolean) => {
    const group = new THREE.Group();
    const brand = BRAND_THEMES[idx % BRAND_THEMES.length];
    const baseColor = c.isProjected ? 0x00E5FF : brand.color;

    // Body Box
    const bodyGeo = new THREE.BoxGeometry(
      CONTAINER_DIMS.length,
      CONTAINER_DIMS.height,
      CONTAINER_DIMS.width
    );
    const bodyMat = new THREE.MeshStandardMaterial({
      color: baseColor,
      roughness: 0.35,
      metalness: 0.5,
      transparent: c.isProjected,
      opacity: c.isProjected ? 0.75 : 1.0,
      emissive: c.isProjected ? 0x00E5FF : (isSelected ? 0x00E5FF : 0x000000),
      emissiveIntensity: c.isProjected ? 0.4 : (isSelected ? 0.3 : 0.0)
    });
    const bodyMesh = new THREE.Mesh(bodyGeo, bodyMat);
    bodyMesh.castShadow = true;
    bodyMesh.receiveShadow = true;
    group.add(bodyMesh);

    // Rib Corrugations
    const ribMat = new THREE.MeshStandardMaterial({
      color: baseColor,
      roughness: 0.3,
      metalness: 0.6
    });

    const numRibs = 8;
    for (let r = 0; r < numRibs; r++) {
      const xOffset = -CONTAINER_DIMS.length / 2 + 0.4 + (r * (CONTAINER_DIMS.length - 0.8)) / (numRibs - 1);
      [-CONTAINER_DIMS.width / 2 - 0.02, CONTAINER_DIMS.width / 2 + 0.02].forEach((zSide) => {
        const fluteGeo = new THREE.BoxGeometry(0.18, CONTAINER_DIMS.height * 0.85, 0.04);
        const flute = new THREE.Mesh(fluteGeo, ribMat);
        flute.position.set(xOffset, 0, zSide);
        group.add(flute);
      });
    }

    // Corner Castings
    const castingMat = new THREE.MeshStandardMaterial({ color: 0x1E293B, metalness: 0.9, roughness: 0.2 });
    [-1, 1].forEach((xSign) => {
      [-1, 1].forEach((ySign) => {
        [-1, 1].forEach((zSign) => {
          const cornerGeo = new THREE.BoxGeometry(0.35, 0.35, 0.35);
          const corner = new THREE.Mesh(cornerGeo, castingMat);
          corner.position.set(
            (xSign * CONTAINER_DIMS.length) / 2,
            (ySign * CONTAINER_DIMS.height) / 2,
            (zSign * CONTAINER_DIMS.width) / 2
          );
          group.add(corner);
        });
      });
    });

    // IMDG Dangerous Goods Placard
    if (c.hazardous) {
      const dgGeo = new THREE.PlaneGeometry(0.8, 0.8);
      const dgMat = new THREE.MeshStandardMaterial({
        color: 0xEF4444,
        emissive: 0xEF4444,
        emissiveIntensity: 0.4,
        side: THREE.DoubleSide
      });
      const dgPlacard = new THREE.Mesh(dgGeo, dgMat);
      dgPlacard.rotation.z = Math.PI / 4;
      dgPlacard.position.set(0, 0, CONTAINER_DIMS.width / 2 + 0.06);
      group.add(dgPlacard);
    }

    // Edge Highlight
    const edges = new THREE.EdgesGeometry(bodyGeo);
    const lineMat = new THREE.LineBasicMaterial({
      color: isSelected ? 0x00E5FF : (c.isProjected ? 0x00E5FF : 0xFFFFFF),
      linewidth: isSelected ? 2 : 1
    });
    const wireframe = new THREE.LineSegments(edges, lineMat);
    group.add(wireframe);

    group.userData = { container: c, isContainer: true };
    return group;
  };

  // 4. Update Dynamic 3D Containers
  useEffect(() => {
    if (!vesselGroupRef.current || !sceneRef.current) return;
    const vessel = vesselGroupRef.current;

    // Clear old container groups
    containerMeshesRef.current.forEach((grp) => {
      vessel.remove(grp);
      grp.traverse((child) => {
        if (child instanceof THREE.Mesh) {
          child.geometry.dispose();
          if (Array.isArray(child.material)) child.material.forEach((m) => m.dispose());
          else child.material.dispose();
        }
      });
    });
    containerMeshesRef.current.clear();

    // Render active containers
    containers.forEach((c, idx) => {
      const bayX = BAY_X_COORDS[c.bay] ?? 0;
      const isStarboard = String(c.side).toUpperCase().includes("STARBOARD") || String(c.side).toUpperCase().includes("STBD");
      const sideZ = isStarboard ? SIDE_Z_COORDS.STARBOARD : SIDE_Z_COORDS.PORT;
      const tierY = c.tier === 2 ? TIER_Y_COORDS[2] : TIER_Y_COORDS[1];

      const isSelected = selectedContainerId === c.id;
      const containerGroup = createRealisticContainer(c, idx, isSelected);
      containerGroup.position.set(bayX, tierY, sideZ);

      vessel.add(containerGroup);
      containerMeshesRef.current.set(c.id, containerGroup);
    });
  }, [containers, selectedContainerId]);

  // 5. Update Dynamic 3D Double-Bottom Ballast Tanks
  useEffect(() => {
    if (!vesselGroupRef.current) return;
    const vessel = vesselGroupRef.current;

    // Clear old tank meshes
    tankMeshesRef.current.forEach((mesh) => {
      vessel.remove(mesh);
      mesh.geometry.dispose();
      if (Array.isArray(mesh.material)) mesh.material.forEach((m) => m.dispose());
      else mesh.material.dispose();
    });
    tankMeshesRef.current.clear();

    // Render 8 double-bottom ballast fluid volumes
    [1, 2, 3, 4].forEach((bayNum) => {
      ["port", "starboard"].forEach((sideKey) => {
        const tankKey = `${sideKey}_${bayNum}`;
        const t = ballastTanks[tankKey] || { name: `${sideKey.toUpperCase()} ${bayNum}`, current_volume: 10.5, capacity: 15 };
        const fillRatio = Math.min(Math.max((t.current_volume || 0) / (t.capacity || 15), 0.1), 1.0);

        const bayX = BAY_X_COORDS[bayNum] ?? 0;
        const sideZ = sideKey === "port" ? SIDE_Z_COORDS.PORT : SIDE_Z_COORDS.STARBOARD;
        const tankHeight = 1.1 * fillRatio;
        const isTankSelected = selectedTankId === tankKey;

        const tankGeo = new THREE.BoxGeometry(6.0, tankHeight, 2.7);
        const tankMat = new THREE.MeshStandardMaterial({
          color: 0x00E5FF,
          roughness: 0.1,
          metalness: 0.85,
          transparent: true,
          opacity: isTankSelected ? 0.85 : 0.45,
          emissive: 0x00E5FF,
          emissiveIntensity: isTankSelected ? 0.6 : 0.25
        });

        const tankMesh = new THREE.Mesh(tankGeo, tankMat);
        tankMesh.position.set(bayX, -0.6 + tankHeight / 2, sideZ);
        tankMesh.userData = {
          isTank: true,
          tankId: tankKey,
          tankInfo: {
            id: tankKey,
            name: `${sideKey === "port" ? "Port Tank" : "Starboard Tank"} ${bayNum}`,
            side: sideKey.toUpperCase() as "PORT" | "STARBOARD",
            bay: bayNum,
            location: `Bay 0${bayNum} ${sideKey.toUpperCase()} Double Bottom`,
            current_volume: t.current_volume || 0,
            capacity: t.capacity || 15,
            percentage: fillRatio * 100,
            status: "NORMAL" as const
          }
        };

        vessel.add(tankMesh);
        tankMeshesRef.current.set(tankKey, tankMesh);
      });
    });
  }, [ballastTanks, selectedTankId]);

  // 6. Update Recommended Slot & Alternative Slot Highlighting
  useEffect(() => {
    if (!highlightSlotsGroupRef.current) return;
    const group = highlightSlotsGroupRef.current;

    // Clear previous highlights
    while (group.children.length > 0) {
      const child = group.children[0];
      group.remove(child);
      if (child instanceof THREE.Mesh || child instanceof THREE.LineSegments) {
        child.geometry.dispose();
        if (Array.isArray(child.material)) child.material.forEach((m) => m.dispose());
        else child.material.dispose();
      }
    }

    // A. Recommended Slot (Glowing Cyan Box & Target Ray)
    if (recommendedSlot) {
      const bayX = BAY_X_COORDS[recommendedSlot.bay] ?? 0;
      const isStarboard = String(recommendedSlot.side).toUpperCase().includes("STARBOARD") || String(recommendedSlot.side).toUpperCase().includes("STBD");
      const sideZ = isStarboard ? SIDE_Z_COORDS.STARBOARD : SIDE_Z_COORDS.PORT;
      const tierY = recommendedSlot.tier === 2 ? TIER_Y_COORDS[2] : TIER_Y_COORDS[1];

      const boxGeo = new THREE.BoxGeometry(CONTAINER_DIMS.length + 0.3, CONTAINER_DIMS.height + 0.3, CONTAINER_DIMS.width + 0.3);
      const edges = new THREE.EdgesGeometry(boxGeo);
      const lineMat = new THREE.LineBasicMaterial({ color: 0x00E5FF, linewidth: 2 });
      const wireframe = new THREE.LineSegments(edges, lineMat);
      wireframe.position.set(bayX, tierY, sideZ);
      group.add(wireframe);

      // Semi-transparent target fill
      const fillMat = new THREE.MeshBasicMaterial({
        color: 0x00E5FF,
        transparent: true,
        opacity: 0.2
      });
      const fillMesh = new THREE.Mesh(boxGeo, fillMat);
      fillMesh.position.set(bayX, tierY, sideZ);
      group.add(fillMesh);
    }

    // B. Alternative Candidate Slots (Subtle Amber Wireframes)
    alternativeSlots.forEach((alt) => {
      if (recommendedSlot && alt.bay === recommendedSlot.bay && alt.side === recommendedSlot.side && alt.tier === recommendedSlot.tier) return;
      const bayX = BAY_X_COORDS[alt.bay] ?? 0;
      const isStarboard = String(alt.side).toUpperCase().includes("STARBOARD") || String(alt.side).toUpperCase().includes("STBD");
      const sideZ = isStarboard ? SIDE_Z_COORDS.STARBOARD : SIDE_Z_COORDS.PORT;
      const tierY = alt.tier === 2 ? TIER_Y_COORDS[2] : TIER_Y_COORDS[1];

      const boxGeo = new THREE.BoxGeometry(CONTAINER_DIMS.length + 0.2, CONTAINER_DIMS.height + 0.2, CONTAINER_DIMS.width + 0.2);
      const edges = new THREE.EdgesGeometry(boxGeo);
      const lineMat = new THREE.LineBasicMaterial({ color: 0xF59E0B, linewidth: 1 });
      const wireframe = new THREE.LineSegments(edges, lineMat);
      wireframe.position.set(bayX, tierY, sideZ);
      group.add(wireframe);
    });
  }, [recommendedSlot, alternativeSlots]);

  // 7. Mouse Orbit & Raycasting Click Handlers
  const handlePointerDown = (e: React.PointerEvent<HTMLCanvasElement>) => {
    isDraggingRef.current = true;
    previousMousePosRef.current = { x: e.clientX, y: e.clientY };
  };

  const handlePointerMove = (e: React.PointerEvent<HTMLCanvasElement>) => {
    if (!isDraggingRef.current || !cameraRef.current) return;

    const deltaX = e.clientX - previousMousePosRef.current.x;
    const deltaY = e.clientY - previousMousePosRef.current.y;
    previousMousePosRef.current = { x: e.clientX, y: e.clientY };

    // Orbit calculation around target (0, 2, 0)
    const target = new THREE.Vector3(0, 2, 0);
    const offset = cameraTargetPosRef.current.clone().sub(target);

    const radius = offset.length();
    let theta = Math.atan2(offset.x, offset.z);
    let phi = Math.acos(Math.max(Math.min(offset.y / radius, 1), -1));

    theta -= deltaX * 0.007;
    phi = Math.max(0.12, Math.min(Math.PI / 2.05, phi - deltaY * 0.007));

    offset.x = radius * Math.sin(phi) * Math.sin(theta);
    offset.y = radius * Math.cos(phi);
    offset.z = radius * Math.sin(phi) * Math.cos(theta);

    cameraTargetPosRef.current.copy(target.clone().add(offset));
  };

  const handlePointerUp = () => {
    isDraggingRef.current = false;
  };

  const handleWheel = (e: React.WheelEvent<HTMLCanvasElement>) => {
    e.preventDefault();
    const zoomFactor = e.deltaY > 0 ? 1.08 : 0.92;
    const target = new THREE.Vector3(0, 2, 0);
    const offset = cameraTargetPosRef.current.clone().sub(target);
    const newLen = Math.max(14, Math.min(75, offset.length() * zoomFactor));
    offset.setLength(newLen);
    cameraTargetPosRef.current.copy(target.clone().add(offset));
  };

  const handleClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!canvasRef.current || !cameraRef.current || !sceneRef.current) return;

    const rect = canvasRef.current.getBoundingClientRect();
    mouseCoordsRef.current.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
    mouseCoordsRef.current.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;

    raycasterRef.current.setFromCamera(mouseCoordsRef.current, cameraRef.current);
    const intersects = raycasterRef.current.intersectObjects(
      vesselGroupRef.current?.children || [],
      true
    );

    if (intersects.length > 0) {
      let hitObj: THREE.Object3D | null = intersects[0].object;
      while (hitObj && !hitObj.userData.isContainer && !hitObj.userData.isTank && hitObj.parent) {
        hitObj = hitObj.parent;
      }

      if (hitObj?.userData.isContainer) {
        const c = hitObj.userData.container;
        onSelectContainer({
          id: c.id,
          bay: c.bay,
          side: c.side.toUpperCase() as "PORT" | "STARBOARD",
          tier: c.tier,
          weight: c.weight,
          container_type: c.container_type || "40HC",
          hazardous: c.hazardous
        });
        onSelectTank(null);
        return;
      }

      if (hitObj?.userData.isTank) {
        onSelectTank(hitObj.userData.tankInfo);
        onSelectContainer(null);
        return;
      }
    }
  };

  return (
    <div ref={containerRef} className={`w-full h-full relative cursor-grab active:cursor-grabbing select-none ${className}`}>
      <canvas
        ref={canvasRef}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onWheel={handleWheel}
        onClick={handleClick}
        className="w-full h-full block touch-none"
      />

      {/* 3D Viewport HUD Provenance Tag */}
      <div className="absolute top-3 right-3 pointer-events-none flex items-center gap-1.5 px-2.5 py-1 rounded bg-brand-dark/85 backdrop-blur-md border border-maretide-info/40 text-[9px] font-mono font-black text-maretide-info shadow-lg">
        <span className="w-1.5 h-1.5 rounded-full bg-brand-cyan animate-pulse" />
        <span>HIGH-FIDELITY WEBGL DIGITAL TWIN • ACES FILMIC TONE MAPPING</span>
      </div>

      {/* Orbit Helper Tip */}
      <div className="absolute bottom-3 right-3 pointer-events-none hidden sm:flex items-center gap-2 px-2.5 py-1 rounded bg-brand-dark/85 backdrop-blur-md border border-maretide-border text-[9px] font-mono text-maretide-text-secondary">
        <span>Drag: Orbit</span>
        <span>•</span>
        <span>Scroll: Zoom</span>
        <span>•</span>
        <span>Click: Inspect Container / Tank</span>
      </div>
    </div>
  );
};
