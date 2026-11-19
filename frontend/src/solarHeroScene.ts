import {
  DirectionalLight, Group, HemisphereLight, MathUtils, NeutralToneMapping,
  OrthographicCamera, Scene, SRGBColorSpace, Vector2, WebGLRenderer,
} from 'three';
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';
import {createDrone, createSolarArray, disposeHeroResources} from './solarInspectionModels';
import {createArrayDeck, createInspectionScan, flightPath} from './solarInspectionScan';

const models = import.meta.env.BASE_URL + 'models/';
const surveyStart = .59;

export function mountSolarHero(host: HTMLElement, onReady: (ready: boolean) => void) {
  const renderer = new WebGLRenderer({alpha:true, antialias:true, powerPreference:'low-power'});
  renderer.outputColorSpace = SRGBColorSpace;
  renderer.toneMapping = NeutralToneMapping;
  renderer.toneMappingExposure = 1.05;
  renderer.domElement.setAttribute('aria-hidden', 'true');
  host.append(renderer.domElement);

  const scene = new Scene();
  const gallery = new Group();
  scene.add(gallery);
  const camera = new OrthographicCamera(-3.6, 3.6, 3, -3, .1, 45);
  camera.position.set(-6.1, 5.1, 8.2);
  camera.lookAt(0, .54, 0);
  scene.add(new HemisphereLight(0xdee7ff, 0x63516f, 1.45));

  const key = new DirectionalLight(0xffdfc9, 1.9);
  key.position.set(-4, 7, 4);
  scene.add(key);
  const rim = new DirectionalLight(0x89bbff, 1.4);
  rim.position.set(2.2, 4.8, -4.1);
  scene.add(rim);
  const fill = new DirectionalLight(0xd8a9c1, .55);
  fill.position.set(5, 1.6, 1);
  scene.add(fill);

  const motion = matchMedia('(prefers-reduced-motion: reduce)');
  const pointer = new Vector2();
  const position = flightPath.getPointAt(surveyStart);
  const heading = flightPath.getTangentAt(surveyStart);
  let drone: ReturnType<typeof createDrone> | undefined;
  let scan: ReturnType<typeof createInspectionScan> | undefined;
  let active = true;
  let visible = false;
  let contextReady = true;
  let paused = false;
  let frame = 0;
  let last = 0;
  let elapsed = 0;

  function draw(dt: number, moving: boolean) {
    if (!drone || !scan || !active || !contextReady) return false;
    const progress = (surveyStart + elapsed / 18.5) % 1;
    flightPath.getPointAt(progress, position);
    flightPath.getTangentAt(progress, heading);
    position.y += .034 * Math.sin(elapsed * 2.4);
    drone.drone.position.copy(position);
    const yaw = Math.atan2(heading.x, heading.z);
    const yawDelta = Math.atan2(Math.sin(yaw - drone.drone.rotation.y), Math.cos(yaw - drone.drone.rotation.y));
    drone.drone.rotation.y += dt ? yawDelta * (1 - Math.exp(-9 * dt)) : yawDelta;
    drone.drone.rotation.x = moving ? -.105 : 0;
    drone.drone.rotation.z = moving ? MathUtils.clamp(yawDelta * -.32, -.18, .18) : 0;
    drone.spin(elapsed, moving);
    scan.move(position, elapsed);
    const rotate = motion.matches ? 0 : pointer.x * .065;
    gallery.rotation.y = dt ? MathUtils.damp(gallery.rotation.y, rotate, 3, dt) : rotate;
    renderer.render(scene, camera);
    return true;
  }

  function animate(now: number) {
    frame = 0;
    if (!active || !visible || !contextReady || document.hidden || motion.matches || paused || !drone) return;
    const delta = last ? Math.min(.05, (now - last) / 1000) : 0;
    last = now;
    elapsed += delta;
    draw(delta, true);
    frame = requestAnimationFrame(animate);
  }

  function reconcileMotion() {
    cancelAnimationFrame(frame);
    frame = 0;
    last = 0;
    if (!active || !visible || !contextReady || document.hidden || !drone) return;
    if (motion.matches) draw(0, false);
    else if (!paused) frame = requestAnimationFrame(animate);
  }

  function resize() {
    const {clientWidth:width, clientHeight:height} = host;
    if (!width || !height || !contextReady) return;
    const aspect = width / height;
    const halfHeight = Math.max(2.86, 3.48 / aspect);
    camera.left = -halfHeight * aspect;
    camera.right = halfHeight * aspect;
    camera.top = halfHeight;
    camera.bottom = -halfHeight;
    camera.updateProjectionMatrix();
    renderer.setPixelRatio(Math.min(devicePixelRatio, 1.65));
    renderer.setSize(width, height, false);
    if (paused && drone && scan) {
      renderer.render(scene, camera);
      onReady(true);
    } else if (draw(0, !motion.matches)) {
      onReady(true);
    }
  }

  function move(event: PointerEvent) {
    if (event.pointerType !== 'mouse' || motion.matches || paused) return;
    const bounds = host.getBoundingClientRect();
    pointer.setX(MathUtils.clamp(2 * (event.clientX - bounds.left) / bounds.width - 1, -1, 1));
  }

  function neutral() { pointer.setX(0); }

  function loseContext(event: Event) {
    event.preventDefault();
    contextReady = false;
    cancelAnimationFrame(frame);
    frame = 0;
    last = 0;
    onReady(false);
  }

  function restoreContext() {
    contextReady = true;
    resize();
    reconcileMotion();
  }

  const sizeObserver = new ResizeObserver(resize);
  const visibilityObserver = new IntersectionObserver(([entry]) => {
    visible = entry.isIntersecting;
    reconcileMotion();
  });
  sizeObserver.observe(host);
  visibilityObserver.observe(host);
  motion.addEventListener('change', reconcileMotion);
  document.addEventListener('visibilitychange', reconcileMotion);
  host.addEventListener('pointermove', move);
  host.addEventListener('pointerleave', neutral);
  renderer.domElement.addEventListener('webglcontextlost', loseContext);
  renderer.domElement.addEventListener('webglcontextrestored', restoreContext);

  const loader = new GLTFLoader();
  void Promise.allSettled([
    loader.loadAsync(models + 'solar-panel.glb'),
    loader.loadAsync(models + 'drone-low-poly.glb'),
  ]).then(([panel, aircraft]) => {
    if (!active || panel.status !== 'fulfilled' || aircraft.status !== 'fulfilled') {
      if (panel.status === 'fulfilled') disposeHeroResources(panel.value.scene);
      if (aircraft.status === 'fulfilled') disposeHeroResources(aircraft.value.scene);
      return;
    }
    const anisotropy = Math.min(8, renderer.capabilities.getMaxAnisotropy());
    const array = createSolarArray(panel.value.scene, anisotropy);
    gallery.add(createArrayDeck(), array.group);
    drone = createDrone(aircraft.value.scene, anisotropy);
    scan = createInspectionScan(array.surfaces);
    gallery.add(drone.drone, scan.scene);
    resize();
    reconcileMotion();
  }).catch(() => { if (active) onReady(false); });

  return {
    setPaused(value: boolean) {
      paused = value;
      reconcileMotion();
    },
    dispose() {
      active = false;
      cancelAnimationFrame(frame);
      sizeObserver.disconnect();
      visibilityObserver.disconnect();
      motion.removeEventListener('change', reconcileMotion);
      document.removeEventListener('visibilitychange', reconcileMotion);
      host.removeEventListener('pointermove', move);
      host.removeEventListener('pointerleave', neutral);
      renderer.domElement.removeEventListener('webglcontextlost', loseContext);
      renderer.domElement.removeEventListener('webglcontextrestored', restoreContext);
      disposeHeroResources(gallery);
      renderer.dispose();
      renderer.forceContextLoss();
      renderer.domElement.remove();
    },
  };
}
