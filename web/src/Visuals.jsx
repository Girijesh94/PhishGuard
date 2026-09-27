import { useEffect, useMemo, useRef } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { ShaderGradientCanvas, ShaderGradient } from "@shadergradient/react";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";
import { Shape, Path, PMREMGenerator, CatmullRomCurve3, Vector3 } from "three";
import { ShieldCheck } from "lucide-react";
import GlassSurface from "./GlassSurface";

function shieldPath(path, scale = 1) {
  path.moveTo(-0.94 * scale, 0.93 * scale);
  path.lineTo(0, 1.3 * scale);
  path.lineTo(0.94 * scale, 0.93 * scale);
  path.lineTo(0.84 * scale, -0.17 * scale);
  path.quadraticCurveTo(0.72 * scale, -0.85 * scale, 0, -1.28 * scale);
  path.quadraticCurveTo(
    -0.72 * scale,
    -0.85 * scale,
    -0.84 * scale,
    -0.17 * scale,
  );
  path.closePath();
  return path;
}
function Studio() {
  const { gl, scene } = useThree();
  useEffect(() => {
    const generator = new PMREMGenerator(gl);
    const room = new RoomEnvironment();
    const target = generator.fromScene(room, 0.04);
    const old = scene.environment;
    scene.environment = target.texture;
    return () => {
      scene.environment = old;
      target.dispose();
      room.dispose();
      generator.dispose();
    };
  }, [gl, scene]);
  return null;
}
function Shield({ motion }) {
  const group = useRef();
  const orbit = useRef();
  const outer = useMemo(() => {
    const shape = shieldPath(new Shape());
    shape.holes.push(shieldPath(new Path(), 0.79));
    return shape;
  }, []);
  const inner = useMemo(() => shieldPath(new Shape(), 0.8), []);
  const tick = useMemo(
    () =>
      new CatmullRomCurve3(
        [
          new Vector3(-0.38, 0.01, 0.25),
          new Vector3(-0.09, -0.27, 0.25),
          new Vector3(0.43, 0.35, 0.25),
        ],
        false,
        "catmullrom",
        0.02,
      ),
    [],
  );
  useFrame(({ clock, pointer }) => {
    if (!motion) return;
    const t = clock.getElapsedTime();
    group.current.rotation.y =
      -0.37 + Math.sin(t * 0.32) * 0.12 + pointer.x * 0.12;
    group.current.rotation.x = 0.12 + pointer.y * 0.08;
    group.current.position.y = Math.sin(t * 0.65) * 0.06;
    orbit.current.rotation.z = t * 0.08;
  });
  return (
    <group>
      <group ref={group} rotation={[0.12, -0.37, 0.07]}>
        <mesh position={[0, 0, -0.15]}>
          <extrudeGeometry
            args={[
              outer,
              {
                depth: 0.22,
                bevelEnabled: true,
                bevelSegments: 5,
                steps: 1,
                bevelSize: 0.085,
                bevelThickness: 0.09,
                curveSegments: 36,
              },
            ]}
          />
          <meshPhysicalMaterial
            color="#c0d0ff"
            metalness={0.35}
            roughness={0.13}
            transmission={0.45}
            thickness={1.2}
            clearcoat={1}
            envMapIntensity={2.8}
            iridescence={0.4}
          />
        </mesh>
        <mesh position={[0, 0, -0.13]}>
          <extrudeGeometry
            args={[
              inner,
              {
                depth: 0.12,
                bevelEnabled: true,
                bevelSegments: 3,
                bevelSize: 0.035,
                bevelThickness: 0.05,
                curveSegments: 36,
              },
            ]}
          />
          <meshPhysicalMaterial
            color="#b8c5f5"
            roughness={0.08}
            metalness={0.08}
            transmission={0.76}
            thickness={0.55}
            envMapIntensity={1.8}
            clearcoat={1}
          />
        </mesh>
        <mesh>
          <tubeGeometry args={[tick, 24, 0.065, 12, false]} />
          <meshStandardMaterial
            color="#f4f9ff"
            metalness={0.4}
            roughness={0.16}
            envMapIntensity={3}
          />
        </mesh>
      </group>
      <group ref={orbit} rotation={[1.24, 0.3, -0.25]}>
        <mesh>
          <torusGeometry args={[1.82, 0.009, 8, 128]} />
          <meshStandardMaterial
            color="#99a7d7"
            metalness={0.5}
            roughness={0.3}
          />
        </mesh>
        <mesh position={[1.82, 0, 0]}>
          <sphereGeometry args={[0.075, 20, 20]} />
          <meshStandardMaterial
            color="#a3befd"
            metalness={0.8}
            roughness={0.15}
          />
        </mesh>
      </group>
      {[
        [1.55, 1.15, -0.4],
        [-1.6, -0.62, 0.3],
        [1.3, -1.1, 0.4],
        [-1.45, 1.08, -0.4],
      ].map((position, i) => (
        <mesh key={i} position={position} rotation={[0.4, 0.4, 0.8]}>
          <boxGeometry args={[0.11, 0.11, 0.11]} />
          <meshPhysicalMaterial
            color={i % 2 ? "#acbdf4" : "#e2e8ff"}
            roughness={0.12}
            metalness={0.4}
            transmission={0.3}
          />
        </mesh>
      ))}
    </group>
  );
}
export default function Visuals({ motion }) {
  return (
    <>
      <div className="gradient-backdrop" aria-hidden="true">
        <ShaderGradientCanvas
          pixelDensity={1}
          fov={45}
          style={{ position: "absolute", inset: 0 }}
          gl={{ preserveDrawingBuffer: true, powerPreference: "low-power" }}
        >
          <ShaderGradient
            control="props"
            type="plane"
            animate={motion ? "on" : "off"}
            color1="#b5c3f4"
            color2="#d6e9f5"
            color3="#8798d4"
            uSpeed={0.12}
            uStrength={2.2}
            uDensity={1.2}
            uFrequency={4}
            cDistance={3.5}
            cPolarAngle={85}
            rotationX={0}
            rotationY={0}
            rotationZ={45}
            lightType="3d"
            brightness={1.1}
            grain="off"
          />
        </ShaderGradientCanvas>
      </div>
      <div
        className="shield-scene"
        aria-label="Floating translucent shield illustration"
      >
        <Canvas
          camera={{ position: [0, 0, 5.5], fov: 40 }}
          dpr={[1, 1.5]}
          frameloop={motion ? "always" : "demand"}
          gl={{ alpha: true, antialias: true, preserveDrawingBuffer: true }}
        >
          <Studio />
          <ambientLight intensity={0.8} />
          <directionalLight
            position={[3, 4, 5]}
            intensity={3}
            color="#edf3ff"
          />
          <pointLight position={[-3, 1, 2]} intensity={12} color="#9caeff" />
          <Shield motion={motion} />
        </Canvas>
      </div>
      <div className="floating-panel">
        <GlassSurface />
        <div className="floating-icon">
          <ShieldCheck size={19} />
        </div>
        <div>
          <strong>Look beyond the link.</strong>
          <span>Two models. One more perspective.</span>
        </div>
      </div>
    </>
  );
}
