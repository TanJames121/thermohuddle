import * as T from './vendor/three/three.module.min.js';

// All geometry is in centimetres. The dashboard and Pi retain their existing
// -50..50 tracking plane; only the renderer converts it to the marker rectangle.
const L = 100, W = 80, H = 21;
const tagX = L / 2 - 5, tagZ = W / 2 - 5;
const clamp = T.MathUtils.clamp;
const canvas = document.getElementById('p5canvas');
const viewport = document.getElementById('viewport');
const orbitButton = document.getElementById('view-orbit');
const planButton = document.getElementById('view-plan');
const measureButton = document.getElementById('view-measure');

function texture(width, height, paint) {
  const sheet = document.createElement('canvas');
  sheet.width = width;
  sheet.height = height;
  paint(sheet.getContext('2d'), width, height);
  const map = new T.CanvasTexture(sheet);
  map.colorSpace = T.SRGBColorSpace;
  map.anisotropy = 4;
  return map;
}

function makeScene() {
  const renderer = new T.WebGLRenderer({ canvas, antialias: true, alpha: false });
  renderer.setPixelRatio(Math.min(devicePixelRatio || 1, 2));
  renderer.setClearColor(0x142530);
  const scene = new T.Scene();
  const camera = new T.OrthographicCamera(-80, 80, 60, -60, 1, 850);
  scene.add(new T.HemisphereLight(0xfff5df, 0x809aaa, 1.95));
  const daylight = new T.DirectionalLight(0xffedce, 2.25);
  daylight.position.set(-80, 130, 80);
  scene.add(daylight);
  const rim = new T.DirectionalLight(0xb6dbef, 1.55);
  rim.position.set(60, 55, -75);
  scene.add(rim);

  const box = new T.BoxGeometry(1, 1, 1);
  const ball = new T.SphereGeometry(1, 16, 12);
  const material = (color, options = {}) => new T.MeshStandardMaterial({ color, roughness: .72, ...options });
  const frame = material(0x304348, { metalness: .42 });
  const trim = material(0x607679, { metalness: .48 });
  const screw = material(0xbac3bf, { metalness: .67, roughness: .33 });
  const copper = material(0xb56032, { metalness: .54, roughness: .35, side:T.DoubleSide });
  const kick = material(0xb88853);
  const meshMat = new T.LineBasicMaterial({ color:0x91a3a4, transparent:true, opacity:.50 });
  const lamp = new T.Group();
  scene.add(lamp);
  let seed = 3812;
  const rand = () => ((seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0) / 4294967296);

  function mesh(geometry, mat, x, y, z, parent = scene) {
    const obj = new T.Mesh(geometry, mat);
    obj.position.set(x, y, z);
    parent.add(obj);
    return obj;
  }
  function block(x,y,z,w,h,d,mat,parent) {
    const obj = mesh(box,mat,x,y,z,parent);
    obj.scale.set(w,h,d);
    return obj;
  }
  function cylinder(x,y,z,top,bottom,height,mat,parent) {
    return mesh(new T.CylinderGeometry(top,bottom,height,28),mat,x,y,z,parent);
  }
  function linework(values, mat, parent = scene) {
    const geo = new T.BufferGeometry();
    geo.setAttribute('position',new T.Float32BufferAttribute(values,3));
    const obj = new T.LineSegments(geo,mat);
    parent.add(obj);
    return obj;
  }
  function hoop(x,y,z,r,t,mat,parent) {
    const ring = mesh(new T.TorusGeometry(r,t,7,48),mat,x,y,z,parent);
    ring.rotation.x = Math.PI/2;
  }
  function card(w,h,map,x,y,z,parent = scene) {
    return mesh(new T.PlaneGeometry(w,h),new T.MeshBasicMaterial({map,transparent:true,depthWrite:false}),x,y,z,parent);
  }

  const wood = texture(768,128,(c,w,h) => {
    c.fillStyle='#ba9064'; c.fillRect(0,0,w,h);
    for (let i=0;i<350;i++) {
      const x=rand()*w,y=rand()*h;
      c.strokeStyle=rand()<.5?'rgba(85,53,30,.17)':'rgba(253,222,167,.26)';
      c.lineWidth=.4+rand()*1.3; c.beginPath(); c.moveTo(x-60,y);
      c.bezierCurveTo(x+20,y-1,x+28,y+3,x+100+rand()*280,y+rand()*4); c.stroke();
    }
  });
  const oak=material(0xffffff,{map:wood});
  const litter = texture(800,640,(c,w,h) => {
    c.fillStyle='#c9ac81'; c.fillRect(0,0,w,h);
    const chips=['#dfc99f','#bea47b','#e4cea2','#ad9169','#c6a679','#d7be96'];
    for(let i=0;i<27000;i++){
      const x=rand()*w,y=rand()*h,a=rand()*Math.PI,l=1+rand()*6;
      c.fillStyle=chips[Math.floor(rand()*chips.length)];
      c.beginPath(); c.moveTo(x,y); c.lineTo(x+Math.cos(a)*l,y+Math.sin(a)*l);
      c.lineTo(x+Math.cos(a+1.5)*2,y+Math.sin(a+1.5)*2); c.fill();
    }
    // Four-by-four spatial bins, aligned to the same corner fiducials as detections.
    c.lineWidth=1.6; c.strokeStyle='rgba(84,67,45,.27)'; c.setLineDash([7,6]);
    const insetX=(w*(1-2*tagX/(L-2)))/2, insetY=(h*(1-2*tagZ/(W-2)))/2;
    for(let i=1;i<4;i++){
      const x=insetX+i*(w-2*insetX)/4, y=insetY+i*(h-2*insetY)/4;
      c.beginPath();c.moveTo(x,insetY);c.lineTo(x,h-insetY);c.moveTo(insetX,y);c.lineTo(w-insetX,y);c.stroke();
    }
    const shade=c.createRadialGradient(w/2,h/2,h*.24,w/2,h/2,w*.67);
    shade.addColorStop(0,'rgba(59,39,19,0)'); shade.addColorStop(1,'rgba(59,39,19,.35)');
    c.fillStyle=shade; c.fillRect(0,0,w,h);
  });
  const base=block(0,.8,0,L,1.6,W,frame);
  base.name='100 × 80 cm base';
  const bed=mesh(new T.PlaneGeometry(L-2,W-2),material(0xffffff,{map:litter}),0,1.68,0);
  bed.rotation.x=-Math.PI/2;

  const deck=material(0x1b303d);
  block(0,-1.12,0,1200,.7,1200,deck);
  const backdropGrid=new T.GridHelper(420,42,0x607784,0x607784);
  backdropGrid.position.y=-.73; backdropGrid.material.transparent=true; backdropGrid.material.opacity=.22; scene.add(backdropGrid);
  const shadowMap=texture(256,256,(c,w,h)=>{
    for(let i=22;i>=1;i--){c.fillStyle='rgba(10,16,18,.065)';c.beginPath();
      c.roundRect(24-i,25-i,w-48+2*i,h-50+2*i,12+i);c.fill();}
  });
  const shadow=card(120,97,shadowMap,1,-.62,2);shadow.rotation.x=-Math.PI/2;

  // A plywood kickboard retains the litter; the upper screen leaves the floor visible.
  const screen=[];
  for(const side of [-1,1]) {
    const z=side*(W/2-1), x=side*(L/2-1);
    block(0,4.5,z,L-3,6,1.7,oak);
    const endBoard=block(x,4.5,0,W-3,6,1.7,oak); endBoard.rotation.y=Math.PI/2;
    block(0,7.75,z,L-2,.55,1.95,kick);
    block(x,7.75,0,1.95,.55,W-2,kick);
    block(0,H-.85,z,L-2,1.7,2,frame);
    block(x,H-.85,0,2,1.7,W-2,frame);
    block(0,H-.16,z,L-2,.32,1.25,trim);
    block(x,H-.16,0,1.25,.32,W-2,trim);
    for(let gx=-47;gx<=47;gx+=2.5) screen.push(gx,8,z,gx,H-1.5,z);
    for(let gz=-37;gz<=37;gz+=2.5) screen.push(x,8,gz,x,H-1.5,gz);
    for(let y=8.5;y<H-1;y+=2.5) screen.push(-49,y,z,49,y,z,x,y,-39,x,y,39);
    for(const end of [-1,1]){
      const cx=end*(L/2-1.3);
      block(cx,H/2,z,2.6,H,2,frame);
      for(const y of [4.3,H-1.15]){
        const bolt=mesh(ball,screw,cx,y,side*(W/2+.015));
        bolt.scale.set(.47,.47,.14);
      }
    }
  }
  linework(screen,meshMat);
  const badge=texture(512,96,(c,w,h)=>{
    c.fillStyle='#243b3f';c.fillRect(0,0,w,h);c.fillStyle='#ecb17d';c.fillRect(14,19,7,58);
    c.fillStyle='#f2eee1';c.font='bold 51px Arial';c.fillText('ThermoHuddle',39,66);
  });
  card(23,4.3,badge,-27,4.6,W/2+.05);

  // Clamp-mounted cantilever, spun reflector, ceramic socket and wire bulb guard.
  const armZ=-W/2+2.4;
  block(0,15,armZ,6,10,4.8,frame,lamp);
  block(0,30,armZ,2.4,31,2.4,trim,lamp);
  block(0,45,armZ/2,2.4,2.2,-armZ+2.4,frame,lamp);
  linework([-1,37,armZ,-1,44,armZ+9,1,37,armZ,1,44,armZ+9],new T.LineBasicMaterial({color:0xc9d1cc}),lamp);
  cylinder(0,42.25,0,.45,.45,3.9,frame,lamp);
  cylinder(0,39.2,0,2.1,2.4,3.2,frame,lamp);
  for (const y of [38.2,39.2,40.2]) hoop(0,y,0,2.15,.16,trim,lamp);
  const profile=[[1.9,37.8],[3,37.7],[3.7,36.9],[5.2,36.0],[7.4,34.6],[9.3,32.9],[10.6,31.1],[10.9,30.4]];
  mesh(new T.LatheGeometry(profile.map(([r,y])=>new T.Vector2(r,y)),56),copper,0,0,0,lamp);
  hoop(0,30.45,0,10.86,.35,copper,lamp);
  hoop(0,36.6,0,4.15,.18,copper,lamp);
  const bulbMat=material(0xf5e8cc,{emissive:0xff9438,emissiveIntensity:0});
  const bulb=mesh(ball,bulbMat,0,30.5,0,lamp);bulb.scale.set(2.65,3.3,2.65);
  const guard=[];
  for(let i=0;i<10;i++){
    const a=i*Math.PI/5, co=Math.cos(a),si=Math.sin(a);
    guard.push(10.6*co,30.4,10.6*si,7.3*co,27.5,7.3*si,7.3*co,27.5,7.3*si,2.3*co,26.5,2.3*si);
  }
  linework(guard,new T.LineBasicMaterial({color:0x5b4941}),lamp);
  hoop(0,27.5,0,7.3,.16,frame,lamp);

  const glowMap=texture(128,128,(c,w,h)=>{
    const g=c.createRadialGradient(w/2,h/2,0,w/2,h/2,w/2);
    g.addColorStop(0,'rgba(255,174,69,.9)'); g.addColorStop(.55,'rgba(255,135,48,.48)');g.addColorStop(1,'rgba(255,118,46,0)');
    c.fillStyle=g;c.fillRect(0,0,w,h);
  });
  const heat=card(66,66,glowMap,0,1.76,0);heat.rotation.x=-Math.PI/2;
  const markerMats=[];
  const markerTexture = bits => texture(56,56,c=>{
    c.fillStyle='#f0ebdf';c.fillRect(0,0,56,56);c.fillStyle='#243133';c.fillRect(7,7,42,42);
    c.fillStyle='#f6f5e9';Array.from(bits).forEach((v,i)=>{if(v==='1')c.fillRect(14+(i%4)*7,14+Math.floor(i/4)*7,7,7);});
  });
  // DICT_4X4_50 markers 0 through 3, in camera corner order.
  ['1011010100110010','0000111110011010','0011001100101101','1001100101000110'].forEach((bits,id)=>{
    const x=id%2?tagX:-tagX, z=id>=2?tagZ:-tagZ;
    const mat=material(0xc1ba9f);markerMats.push(mat);
    block(x,1.88,z,5.9,.32,5.9,mat);
    const tag=card(4.8,4.8,markerTexture(bits),x,2.06,z);tag.rotation.x=-Math.PI/2;
  });
  const corners=[[-tagX,-tagZ],[tagX,-tagZ],[tagX,tagZ],[-tagX,tagZ]];
  const border=linework(corners.flatMap(([x,z],i)=>[x,1.89,z,corners[(i+1)%4][0],1.89,corners[(i+1)%4][1]]),new T.LineBasicMaterial({color:0x32836e}));

  const guides=new T.Group();scene.add(guides);guides.visible=false;
  const guideMat=new T.LineBasicMaterial({color:0xf3c18e});
  function dimension(start,end,tick,label,position){
    const lines=[...start,...end];
    for(const p of [start,end]) lines.push(...p.map((v,i)=>v-tick[i]),...p.map((v,i)=>v+tick[i]));
    linework(lines,guideMat,guides);
    const map=texture(220,62,(c,w,h)=>{
      c.fillStyle='#1a2e37';c.fillRect(0,0,w,h);c.strokeStyle='#b79a77';c.lineWidth=3;c.strokeRect(1,1,w-2,h-2);
      c.font='bold 38px monospace';c.fillStyle='#ffdbb7';c.textAlign='center';c.textBaseline='middle';c.fillText(label,w/2,h/2);
    });
    const text=new T.Sprite(new T.SpriteMaterial({map,depthTest:false}));
    text.position.set(...position);text.scale.set(15,4.22,1);text.renderOrder=5;guides.add(text);
  }
  dimension([-50,1,47],[50,1,47],[0,0,1.8],'100 cm',[0,1,47]);
  dimension([57,1,-40],[57,1,40],[1.8,0,0],'80 cm',[57,1,-3]);
  dimension([-54,0,-37],[-54,H,-37],[1.6,0,0],'21 cm',[-55,12,-37]);
  const heightGuide=guides.children.slice(-2);

  const dummy=new T.Object3D();
  const components=[];
  function instanced(geometry,mat){
    const inst=new T.InstancedMesh(geometry,mat,Math.max(64,CONFIG.nChicks));
    inst.count=0;inst.frustumCulled=false;scene.add(inst);components.push(inst);return inst;
  }
  const body=instanced(ball,material(0xffde92));
  const head=instanced(ball,material(0xffeab7));
  const beak=instanced(new T.ConeGeometry(1,1,8),material(0xb56831));
  function stamp(inst,i,x,y,z,sx,sy,sz,yaw=0,tilt=0){
    dummy.position.set(x,y,z);dummy.scale.set(sx,sy,sz);dummy.rotation.set(0,yaw,tilt,'YXZ');dummy.updateMatrix();
    inst.setMatrixAt(i,dummy.matrix);
  }
  const dotGeo=new T.RingGeometry(1.2,2.15,24);dotGeo.rotateX(-Math.PI/2);
  const dotMat=new T.MeshBasicMaterial({color:0xffffff});
  let dots=new T.InstancedMesh(dotGeo,dotMat,64);dots.count=0;dots.frustumCulled=false;scene.add(dots);
  const calm=new T.Color(0x238172),clustered=new T.Color(0xc45623);
  const linkMat=new T.LineBasicMaterial({color:0xd36e38});
  let links=linework([],linkMat);
  const pulse=mesh(new T.RingGeometry(.94,1,48),new T.MeshBasicMaterial({color:0xda5346}),0,1.94,0);
  pulse.rotation.x=-Math.PI/2;
  let lastPoints=null;
  function detections(pts){
    if(pts===lastPoints)return;
    lastPoints=pts;
    if(pts.length>dots.instanceMatrix.count){
      scene.remove(dots);dots.dispose();dots=new T.InstancedMesh(dotGeo,dotMat,pts.length);
      scene.add(dots);dots.frustumCulled=false;
    }
    const grouped=new Set(), segments=[];
    for(let i=0;i<pts.length;i++) for(let j=i+1;j<pts.length;j++){
      const a=pts[i],b=pts[j];
      if(Math.hypot(a.x-b.x,a.z-b.z)<14){
        grouped.add(i);grouped.add(j);
        segments.push(a.x*tagX/50,2.1,a.z*tagZ/50,b.x*tagX/50,2.1,b.z*tagZ/50);
      }
    }
    pts.forEach((p,i)=>{
      stamp(dots,i,p.x*tagX/50,2.16,p.z*tagZ/50,1,1,1);
      dots.setColorAt(i,grouped.has(i)?clustered:calm);
    });
    dots.count=pts.length;dots.instanceMatrix.needsUpdate=true;
    if(dots.instanceColor)dots.instanceColor.needsUpdate=true;
    scene.remove(links);links.geometry.dispose();links=linework(segments,linkMat);
  }

  const homeAngle=.50,homeElevation=.58;
  let angle=homeAngle,elevation=homeElevation,zoom=1,plan=false;
  function render(){
    const w=viewport.clientWidth,h=viewport.clientHeight;
    if(!w||!h)return;
    const aspect=w/h;
    const span=(plan?Math.max(109,143/aspect):Math.max(105,159/aspect))*(guides.visible?1.12:1)/zoom;
    camera.left=-span*aspect/2;camera.right=-camera.left;camera.top=span/2;camera.bottom=-span/2;
    const target=plan?0:16;
    if(plan){camera.up.set(0,0,-1);camera.position.set(0,220,0);}
    else {
      const d=210*Math.cos(elevation);camera.up.set(0,1,0);
      camera.position.set(Math.sin(angle)*d,target+210*Math.sin(elevation),Math.cos(angle)*d);
    }
    camera.lookAt(0,target,0);camera.updateProjectionMatrix();renderer.render(scene,camera);
  }
  function resize(){renderer.setSize(viewport.clientWidth,viewport.clientHeight,false);render();}
  const observer=new ResizeObserver(resize);observer.observe(viewport);
  function setView(top){
    plan=top;angle=homeAngle;elevation=homeElevation;zoom=1;lamp.visible=!plan;
    heightGuide.forEach(obj=>obj.visible=!plan);
    orbitButton.setAttribute('aria-pressed',String(!plan));planButton.setAttribute('aria-pressed',String(plan));render();
  }
  orbitButton.onclick=()=>setView(false);planButton.onclick=()=>setView(true);
  measureButton.onclick=()=>{guides.visible=!guides.visible;measureButton.setAttribute('aria-pressed',String(guides.visible));viewport.classList.toggle('measuring',guides.visible);render();};
  const fingers=new Map();
  const distance=()=>{const [a,b]=fingers.values();return Math.hypot(a.x-b.x,a.y-b.y);};
  const setZoom=value=>{zoom=clamp(value,.68,2.7);render();};
  canvas.onpointerdown=e=>{canvas.setPointerCapture(e.pointerId);fingers.set(e.pointerId,{x:e.clientX,y:e.clientY});};
  canvas.onpointermove=e=>{
    const p=fingers.get(e.pointerId);if(!p)return;
    const old=fingers.size===2?distance():0;
    fingers.set(e.pointerId,{x:e.clientX,y:e.clientY});
    if(old>0){setZoom(zoom*distance()/old);}
    else if(!plan&&fingers.size===1){angle-=(e.clientX-p.x)*.008;elevation=clamp(elevation+(e.clientY-p.y)*.006,.16,1.45);render();}
  };
  canvas.onlostpointercapture=e=>fingers.delete(e.pointerId);
  canvas.addEventListener('wheel',e=>{e.preventDefault();setZoom(zoom*Math.exp(-clamp(e.deltaY,-180,180)*.0014));},{passive:false});
  canvas.onkeydown=e=>{
    if(e.key==='Home')setView(false);
    else if(e.key==='+'||e.key==='=')setZoom(zoom*1.12);
    else if(e.key==='-')setZoom(zoom/1.12);
    else if(!plan&&['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(e.key)){
      angle+=({'ArrowLeft':-.12,'ArrowRight':.12}[e.key]||0);
      elevation=clamp(elevation+({'ArrowUp':.10,'ArrowDown':-.10}[e.key]||0),.16,1.45);render();
    }else return;
    e.preventDefault();
  };
  const empty=[];
  let prevMarkers='',prevMapped=null,wasDemo=true;
  function update({isLive,pilot,points,chicks,sim}){
    if(viewport.classList.contains('feeding')||document.hidden)return;
    const ids=pilot?.arucoMarkers||empty, mapped=Boolean(pilot?.arucoMapped), demo=!isLive;
    const signature=ids.join(',');
    const visiblePoints=isLive&&points.length?points:empty;
    if(!demo&&!wasDemo&&prevMarkers===signature&&prevMapped===mapped&&lastPoints===visiblePoints)return;
    prevMarkers=signature;prevMapped=mapped;wasDemo=demo;
    markerMats.forEach((m,i)=>m.color.setHex(ids.includes(i)?0x42ad85:0xc1ba9f));
    border.visible=mapped; detections(visiblePoints);
    components.forEach(inst=>{inst.count=demo?chicks.length:0;});
    heat.visible=demo;bulbMat.emissiveIntensity=demo?sim.lampPWM*.9:0;
    pulse.visible=demo&&sim.crowdActive;
    if(demo){
      heat.material.opacity=.12+.65*sim.lampPWM;
      let cx=0,cz=0;
      chicks.forEach((c,i)=>{
        const x=c.pos.x*tagX/50,z=c.pos.z*tagZ/50;
        const yaw=Math.atan2(-c.vel.z,c.vel.x);
        const dx=Math.cos(yaw),dz=-Math.sin(yaw);
        stamp(body,i,x,3.48,z,2.05,1.6,1.45,yaw);
        stamp(head,i,x+dx*1.45,4.9,z+dz*1.45,1.27,1.35,1.22,yaw);
        stamp(beak,i,x+dx*2.82,4.7,z+dz*2.82,.52,.95,.52,yaw,-Math.PI/2);
        cx+=x;cz+=z;
      });
      components.forEach(inst=>inst.instanceMatrix.needsUpdate=true);
      if(pulse.visible&&chicks.length){pulse.position.set(cx/chicks.length,1.94,cz/chicks.length);pulse.scale.setScalar(9+3*Math.sin(sim.t*.12));}
    }
    render();
  }
  function snapshot(){
    render();canvas.toBlob(blob=>{
      if(!blob)return;
      const url=URL.createObjectURL(blob),a=document.createElement('a');
      a.href=url;a.download='ThermoHuddle-brooder.png';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
    },'image/png');
  }
  heat.visible=pulse.visible=border.visible=false;
  resize();
  return {update,snapshot};
}

try {
  window.brooderScene=makeScene();
} catch(error) {
  console.error('Brooder renderer:',error);
  document.getElementById('scene-error').hidden=false;
  [orbitButton,planButton,measureButton,document.getElementById('btnsnap')].forEach(b=>b.disabled=true);
}
