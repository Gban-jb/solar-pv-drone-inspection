import {
  AdditiveBlending, BoxGeometry, BufferGeometry, CatmullRomCurve3, Color, DoubleSide,
  Float32BufferAttribute, Group, LineBasicMaterial, LineSegments, MathUtils, Matrix4, Mesh,
  MeshBasicMaterial, PlaneGeometry, ShaderMaterial, SphereGeometry, Vector3, type MeshStandardMaterial,
} from 'three';
import {arrayCenters} from './solarInspectionModels';

const aqua = 0x7deee5;
const amber = 0xffb469;

export const flightPath = new CatmullRomCurve3([
  [-1.9, 1.88, -1.17], [-.65, 1.82, -1.17], [.85, 1.84, -1.17], [1.94, 1.91, -1.10],
  [2.17, 2.0, -.55], [1.84, 1.89, 0], [.66, 1.78, 0], [-.7, 1.83, 0],
  [-1.89, 1.87, .05], [-2.11, 1.96, .69], [-1.84, 1.84, 1.17], [-.64, 1.78, 1.17],
  [.86, 1.83, 1.17], [1.92, 1.93, 1.12], [2.35, 2.08, .47], [2.43, 2.16, -.86],
  [1.8, 2.06, -1.83], [.02, 1.98, -1.93], [-1.51, 1.99, -1.77], [-2.16, 1.96, -1.50],
].map(([x,y,z]) => new Vector3(x,y,z)), true, 'centripetal');

function lineGeometry(points: number[]) {
  return new BufferGeometry().setAttribute('position', new Float32BufferAttribute(points, 3));
}

function plane(width: number, depth: number, color: number, opacity: number) {
  const mesh = new Mesh(new PlaneGeometry(width, depth), new MeshBasicMaterial({
    color, opacity, transparent: true, depthWrite: false, side: DoubleSide,
  }));
  mesh.rotation.x = -Math.PI / 2;
  return mesh;
}

export function createArrayDeck() {
  const deck = new Group();
  const base = new Mesh(new BoxGeometry(4.48, .105, 4.18), new MeshBasicMaterial({color: 0x2c2438}));
  base.position.y = -.072;
  deck.add(base);
  const mat = new MeshBasicMaterial({color: 0x6e6385, opacity: .14, transparent: true});
  const grid: number[] = [];
  for (let x = -2.16; x <= 2.161; x += .24) grid.push(x, .001, -2.02, x, .001, 2.02);
  for (let z = -1.92; z <= 1.921; z += .24) grid.push(-2.19, .001, z, 2.19, .001, z);
  deck.add(new LineSegments(lineGeometry(grid), new LineBasicMaterial({color: 0x82779e, transparent: true, opacity: .27})));
  const surface = new Mesh(new PlaneGeometry(4.47, 4.17), mat);
  surface.rotation.x = -Math.PI / 2;
  surface.position.y = -.013;
  deck.add(surface);
  const edge = [
    -2.24,0,-2.09, 2.24,0,-2.09, 2.24,0,-2.09, 2.24,0,2.09,
    2.24,0,2.09, -2.24,0,2.09, -2.24,0,2.09, -2.24,0,-2.09,
  ];
  deck.add(new LineSegments(lineGeometry(edge), new LineBasicMaterial({color: 0xa395b6, opacity: .48, transparent: true})));
  return deck;
}

function brackets(sizeX: number, sizeZ: number, color: number) {
  const points: number[] = [];
  for (const side of [-1,1]) for (const row of [-1,1]) {
    const x = side * sizeX / 2;
    const z = row * sizeZ / 2;
    points.push(x, 0, z - row * .18, x, 0, z, x, 0, z, x - side * .18, 0, z);
  }
  return new LineSegments(lineGeometry(points), new LineBasicMaterial({
    color, opacity: 0, transparent: true, depthWrite: false,
  }));
}

function scanVolume() {
  const points: number[] = [];
  const weights: number[] = [];
  const halfX = .53;
  const halfZ = .59;
  const corners = [[-halfX,-halfZ],[halfX,-halfZ],[halfX,halfZ],[-halfX,halfZ]];
  for (const [i, a] of corners.entries()) {
    const b = corners[(i + 1) % corners.length];
    points.push(a[0],0,a[1], b[0],0,b[1], b[0]*.07,1,b[1]*.07);
    points.push(a[0],0,a[1], b[0]*.07,1,b[1]*.07, a[0]*.07,1,a[1]*.07);
    weights.push(0,0,1,0,1,1);
  }
  const geometry = lineGeometry(points).setAttribute('heightRatio',new Float32BufferAttribute(weights,1));
  const material = new ShaderMaterial({
    uniforms: { tint:{value:new Color(aqua)}, strength:{value: .65} },
    vertexShader: `
      attribute float heightRatio;
      varying float beamHeight;
      void main() {
        beamHeight = heightRatio;
        gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
      }
    `,
    fragmentShader: `
      uniform vec3 tint;
      uniform float strength;
      varying float beamHeight;
      void main() {
        float glow = mix(0.105, 0.22, smoothstep(0.05, 1.0, beamHeight));
        gl_FragColor = vec4(tint, glow * strength);
        #include <colorspace_fragment>
      }
    `,
    side: DoubleSide, transparent: true, blending: AdditiveBlending, depthWrite: false,
  });
  const beam = new Mesh(geometry, material);
  beam.renderOrder = 2;
  return beam;
}

export function createInspectionScan(surfaces: MeshStandardMaterial[]) {
  const scene = new Group();
  const footprint = new Group();
  const beam = scanVolume();
  const emitter = new Mesh(new SphereGeometry(.024, 10, 8), new MeshBasicMaterial({color: 0xaafbf4}));
  scene.add(footprint, beam, emitter);
  const tile = plane(1.06,1.18,aqua,.1);
  const tick = brackets(1.06,1.18,aqua);
  tick.material.opacity = .94;
  const sweep = plane(1.03,.035,aqua,.78);
  sweep.position.y = .018;
  footprint.add(tile, tick, sweep);

  const tiles = arrayCenters.map(({x, z}, index) => {
    const warm = index === 5;
    const face = new Group();
    // Match the supplied panel's 45-degree face in the normalized model.
    const uphill = new Vector3(1, 1, 0).normalize();
    const across = new Vector3(0, 0, 1);
    const outward = new Vector3().crossVectors(across, uphill);
    face.setRotationFromMatrix(new Matrix4().makeBasis(across, uphill, outward));
    face.position.set(x - .014, .563, z);
    const cornerMarkers = brackets(.97,.92,warm ? amber : aqua);
    cornerMarkers.rotation.x = Math.PI / 2;
    const overlay = new Mesh(new PlaneGeometry(.96,.9), new MeshBasicMaterial({
      color: warm ? amber : aqua, opacity: 0, transparent: true, depthWrite: false,
    }));
    const stripe = new Mesh(new PlaneGeometry(.945,.023), new MeshBasicMaterial({
      color: warm ? amber : aqua, opacity: 0, transparent: true, depthWrite: false,
    }));
    stripe.position.z = .003;
    face.add(overlay, cornerMarkers, stripe);
    scene.add(face);
    const surface = surfaces[index];
    if (surface) surface.emissive.set(warm ? amber : aqua);
    return {x, z, cornerMarkers, warm, overlay, stripe, surface};
  });

  return {
    scene,
    move(point: Vector3, seconds: number) {
      const {x, y, z} = point;
      const edge = Math.max(Math.abs(x) - 1.87, Math.abs(z) - 1.8, 0);
      const active = 1 - MathUtils.smoothstep(edge, 0, .65);
      footprint.position.set(x,.02,z);
      footprint.visible = active > .01;
      beam.position.copy(footprint.position);
      beam.scale.y = Math.max(.7, y - .18);
      beam.material.uniforms.strength.value = .71 * active;
      beam.visible = footprint.visible;
      emitter.position.set(x, y - .155, z);
      emitter.visible = footprint.visible;
      const closest = Math.min(...tiles.map(tile => Math.hypot(x - tile.x, z - tile.z)));
      const deckOpacity = active * (.27 + .73 * MathUtils.smoothstep(closest, .30, .70));
      tick.material.opacity = .88 * deckOpacity;
      tile.material.opacity = .12 * deckOpacity;
      sweep.material.opacity = .88 * deckOpacity;
      sweep.position.z = Math.sin(seconds * 3.9) * .51;
      for (const {x: px, z: pz, cornerMarkers, warm, overlay, stripe, surface} of tiles) {
        const distance = Math.hypot((x - px) * 1.16, z - pz);
        const proximity = (1 - MathUtils.smoothstep(distance, .27, 1.12)) * active;
        const hotspot = warm ? (.13 + .07 * Math.sin(seconds * 2.1)) * Math.max(0, 1 - distance / 2.3) : 0;
        const highlight = Math.max(proximity,hotspot);
        cornerMarkers.material.opacity = highlight * .95;
        overlay.material.opacity = highlight * (warm ? .15 : .10);
        stripe.material.opacity = proximity * .92;
        stripe.position.y = Math.sin(seconds * 3.9) * .41;
        if (surface) surface.emissiveIntensity = highlight * (warm ? .28 : .16);
      }
    },
  };
}
