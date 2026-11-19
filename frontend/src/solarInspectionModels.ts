import {
  Box3, Group, Mesh, Quaternion, RingGeometry, MeshBasicMaterial, DoubleSide, Vector3,
  type BufferGeometry, type Material, type MeshStandardMaterial, type Object3D, type Texture,
} from 'three';

const rotorAxis = new Vector3(0, 0, 1);
const rotorSpin = new Quaternion();

export const arrayCenters = [-1.24, 0, 1.24].flatMap(x =>
  [-1.17, 0, 1.17].map(z => ({x, z})),
);

function isolateModel(source: Group, size: number): Group {
  source.updateMatrixWorld(true);
  const box = new Box3();
  source.traverseVisible(object => {
    if (!(object instanceof Mesh)) return;
    object.geometry.computeBoundingBox();
    const bounds = object.geometry.boundingBox;
    if (bounds) box.union(bounds.clone().applyMatrix4(object.matrixWorld));
  });
  const center = box.getCenter(new Vector3());
  const length = box.getSize(new Vector3());
  const scale = size / Math.max(length.x, length.y, length.z);
  if (box.isEmpty() || !Number.isFinite(scale)) throw new Error('Missing hero model geometry.');
  source.scale.multiplyScalar(scale);
  source.position.set(-center.x * scale, -box.min.y * scale, -center.z * scale);
  const normalized = new Group();
  normalized.add(source);
  return normalized;
}

export function createSolarArray(source: Group, anisotropy: number) {
  const floor = source.getObjectByName('Plane_Environment_0');
  if (floor) floor.visible = false;
  let face: MeshStandardMaterial | undefined;
  source.traverseVisible(object => {
    if (!(object instanceof Mesh) || Array.isArray(object.material)) return;
    const material: MeshStandardMaterial = object.material;
    if (material.map) material.map.anisotropy = anisotropy;
    if (object.name === 'Plane_003_Environment.2_0') {
      material.color.set(0xe4ebff);
      material.roughness = .65;
      face = material;
    }
  });
  const normalized = isolateModel(source, 1.04);
  const group = new Group();
  const surfaces: MeshStandardMaterial[] = [];

  for (const {x, z} of arrayCenters) {
    const panel = normalized.clone();
    panel.position.set(x, .012, z);
    if (face) {
      const surface = face.clone();
      panel.traverse(object => {
        if (object instanceof Mesh && object.material === face) object.material = surface;
      });
      surfaces.push(surface);
    }
    group.add(panel);
  }
  return {group, surfaces};
}

export function createDrone(source: Group, anisotropy: number) {
  const wrapper = isolateModel(source, 1.14);
  wrapper.position.y = -.17;
  const drone = new Group();
  drone.add(wrapper);
  source.traverse(object => {
    if (object instanceof Mesh && !Array.isArray(object.material) && object.material.map) {
      object.material.map.anisotropy = anisotropy;
      object.material.emissive.set(0x819ac6);
      object.material.emissiveIntensity = .075;
    }
  });

  const propellers = Array.from({length: 4}, (_, index) => {
    const node = source.getObjectByName('Wing' + (index + 1));
    if (!node) throw new Error('Missing a propeller pivot in the supplied drone.');
    const base = node.quaternion.clone();
    // All four pivots point along local Z. Opposite arms counter-rotate as pairs.
    const direction = index % 2 === 0 ? 1 : -1;

    const radius = index < 2 ? .325 : 1.335;
    const halo = new Mesh(
      new RingGeometry(radius * .78, radius, 28, 1, 0, Math.PI * .9),
      new MeshBasicMaterial({color: 0xd2e9ff, transparent: true, opacity: .29, side: DoubleSide, depthWrite: false}),
    );
    halo.position.z = index < 2 ? .008 : .031;
    node.add(halo);
    return {node, base, direction, halo};
  });

  return {
    drone,
    spin(seconds: number, moving: boolean) {
      for (const [index, blade] of propellers.entries()) {
        rotorSpin.setFromAxisAngle(rotorAxis, (seconds * 24 * blade.direction + index * .63) % (Math.PI * 2));
        blade.node.quaternion.copy(blade.base).multiply(rotorSpin);
        blade.halo.visible = moving;
      }
    },
  };
}

export function disposeHeroResources(root: Object3D) {
  const geometries = new Set<BufferGeometry>();
  const materials = new Set<Material>();
  const textures = new Set<Texture>();
  root.traverse(object => {
    if (!('geometry' in object) || !('material' in object)) return;
    const drawable = object as Mesh;
    geometries.add(drawable.geometry);
    const items = Array.isArray(drawable.material) ? drawable.material : [drawable.material];
    for (const material of items) {
      const map = (material as MeshStandardMaterial).map;
      if (map) textures.add(map);
      materials.add(material);
    }
  });
  for (const geometry of geometries) geometry.dispose();
  for (const material of materials) material.dispose();
  for (const texture of textures) {
    texture.dispose();
    const data = texture.source.data;
    if (typeof ImageBitmap !== 'undefined' && data instanceof ImageBitmap) data.close();
  }
}
