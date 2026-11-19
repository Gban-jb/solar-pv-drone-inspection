import {useEffect,useRef,useState} from 'react';
import {Circle,Group,Image as CanvasImage,Layer,Rect,Stage,Text,Transformer} from 'react-konva';
import Konva from 'konva';
import {Maximize,Minus,Plus,Scan} from 'lucide-react';
import type {Box} from './inspectionApi';

export type Mark = {id:string;box:Box;label?:string;active?:boolean;candidate?:boolean;color?:string};
type Point = {x:number;y:number};
type Props = {
  src:string;
  alt:string;
  width:number;
  height:number;
  marks:Mark[];
  draw?:boolean;
  onDraw?:(box:Box)=>void;
  onSelect?:(id:string)=>void;
  editable?:Box;
  onEdit?:(box:Box)=>void;
};

const clamp=(value:number,min:number,max:number)=>Math.max(min,Math.min(max,value));

export default function ImageViewer({src,alt,width,height,marks,draw,onDraw,onSelect,editable,onEdit}:Props) {
  const shell=useRef<HTMLDivElement>(null);
  const holder=useRef<HTMLDivElement>(null);
  const layer=useRef<Konva.Group>(null);
  const editor=useRef<Konva.Rect>(null);
  const transformer=useRef<Konva.Transformer>(null);
  const gesture=useRef<Point|null>(null);
  const previewRef=useRef<Box>();
  const [size,setSize]=useState({width:0,height:0});
  const [bitmap,setBitmap]=useState<{src:string;image:HTMLImageElement}>();
  const [imageError,setImageError]=useState('');
  const [fullError,setFullError]=useState('');
  const [view,setView]=useState({zoom:1,x:0,y:0});
  const [preview,setPreview]=useState<Box>();
  const [zooming,setZooming]=useState(false);
  const fit=Math.min(size.width/width,size.height/height);
  const scale=fit*view.zoom;
  const x=(size.width-width*scale)/2+view.x;
  const y=(size.height-height*scale)/2+view.y;
  const image=bitmap?.src===src?bitmap.image:undefined;

  useEffect(()=>{
    const element=holder.current;
    if(!element) return;
    const resize=new ResizeObserver(([entry])=>setSize({width:entry.contentRect.width,height:entry.contentRect.height}));
    resize.observe(element);
    return ()=>resize.disconnect();
  },[]);
  useEffect(()=>{
    const loading=new window.Image();
    setImageError('');
    loading.onload=()=>setBitmap({src,image:loading});
    loading.onerror=()=>setImageError('This image could not be displayed.');
    loading.src=src;
    return ()=>{loading.onload=null;loading.onerror=null;};
  },[src]);
  useEffect(()=>{
    if (editor.current && transformer.current) transformer.current.nodes([editor.current]);
  },[!!editable,!!image]);
  useEffect(()=>{
    if(!zooming) return;
    const timer=window.setTimeout(()=>setZooming(false),180);
    return ()=>window.clearTimeout(timer);
  },[zooming]);

  function zoom(next:number, focus={x:size.width/2,y:size.height/2}) {
    if (!fit) return;
    next=clamp(next,1,12);
    if(next===1){setView({zoom:1,x:0,y:0});return;}
    const ratio=next/view.zoom;
    const imageX=focus.x-(focus.x-x)*ratio;
    const imageY=focus.y-(focus.y-y)*ratio;
    setView({zoom:next,x:imageX-(size.width-width*fit*next)/2,y:imageY-(size.height-height*fit*next)/2});
  }

  function point():Point|null {
    const position=layer.current?.getRelativePointerPosition();
    if(!position) return null;
    return {x:clamp(position.x/width,0,1),y:clamp(position.y/height,0,1)};
  }

  function setDraft(next?:Box) {
    previewRef.current=next;setPreview(next);
  }

  function start() {
    if (!draw || !image) return;
    gesture.current=point();setDraft(undefined);
  }

  function move() {
    const origin=gesture.current;
    const end=point();
    if (!origin || !end) return;
    setDraft([Math.min(origin.x,end.x),Math.min(origin.y,end.y),Math.max(origin.x,end.x),Math.max(origin.y,end.y)]);
  }

  function finish() {
    const result=previewRef.current;
    gesture.current=null;setDraft(undefined);
    if (result && (result[2]-result[0])*scale*width>6 && (result[3]-result[1])*scale*height>6) onDraw?.(result);
  }

  function updateEdited() {
    const rect=editor.current;
    if(!rect || !editable) return;
    const next:Box=[
      clamp(rect.x()/width,0,1),clamp(rect.y()/height,0,1),
      clamp((rect.x()+rect.width()*rect.scaleX())/width,0,1),
      clamp((rect.y()+rect.height()*rect.scaleY())/height,0,1),
    ];
    const valid=(next[2]-next[0])*width>=8&&(next[3]-next[1])*height>=8;
    const result=valid?next:editable;
    rect.setAttrs({scaleX:1,scaleY:1,x:result[0]*width,y:result[1]*height,width:(result[2]-result[0])*width,height:(result[3]-result[1])*height});
    if(valid) onEdit?.(next);
  }

  async function fullscreen() {
    setFullError('');
    try {
      if(document.fullscreenElement===shell.current) await document.exitFullscreen();
      else if(shell.current?.requestFullscreen) await shell.current.requestFullscreen();
      else setFullError('Fullscreen is unavailable in this browser.');
    } catch {setFullError('Fullscreen is unavailable in this browser.');}
  }

  function rect(box:Box) {
    return {x:box[0]*width,y:box[1]*height,width:(box[2]-box[0])*width,height:(box[3]-box[1])*height};
  }

  return <div className="image-viewer" ref={shell}>
    <div className={'canvas-area'+(draw?' drawing':'')} ref={holder} aria-label={alt} tabIndex={0}
      onKeyDown={event=>{
        if (['+','=','-','0','ArrowLeft','ArrowUp','ArrowRight','ArrowDown'].includes(event.key)) event.preventDefault();
        if(event.key==='+'||event.key==='=') zoom(view.zoom*1.2);
        if(event.key==='-') zoom(view.zoom/1.2);
        if(event.key==='0') setView({zoom:1,x:0,y:0});
        if(view.zoom>1 && event.key.startsWith('Arrow')) setView(previous=>({...previous,x:previous.x+(event.key==='ArrowLeft'?40:event.key==='ArrowRight'?-40:0),y:previous.y+(event.key==='ArrowUp'?40:event.key==='ArrowDown'?-40:0)}));
      }}>
      {!image&&<div className="viewer-status" role={imageError?'alert':'status'}>{imageError||'Loading image…'}</div>}
      {size.width>0&&size.height>0&&image&&<Stage width={size.width} height={size.height}
        onWheel={event=>{
          if(!event.evt.ctrlKey&&!event.evt.metaKey) return;
          event.evt.preventDefault();
          const pointer=event.target.getStage()?.getPointerPosition();
          zoom(view.zoom*Math.exp(-event.evt.deltaY*.012),pointer??undefined);setZooming(true);
        }}
        onMouseDown={start} onMouseMove={move} onMouseUp={finish} onMouseLeave={()=>{gesture.current=null;setDraft(undefined);}}
        onTouchStart={start} onTouchMove={move} onTouchEnd={finish}>
        <Layer>
          <Group ref={layer} x={x} y={y} scaleX={scale} scaleY={scale}
            draggable={!draw&&view.zoom>1&&!editable}
            onDragEnd={event=>{if(event.target===layer.current)setView({...view,x:event.target.x()-(size.width-width*scale)/2,y:event.target.y()-(size.height-height*scale)/2});}}>
            <CanvasImage image={image} width={width} height={height} listening={false}/>
            {marks.map(mark=>{
              const color=mark.color??(mark.candidate?'#ffb35b':mark.active?'#fff0ce':'#8de9d1');
              const bounds=rect(mark.box);
              return <Group key={mark.id} listening={!draw&&!!onSelect} onClick={()=>onSelect?.(mark.id)} onTap={()=>onSelect?.(mark.id)}>
                <Rect {...bounds} stroke={color} strokeWidth={(mark.active?2.5:1.5)/scale} fill="rgba(0,0,0,0.08)"/>
                {mark.candidate&&<Circle x={bounds.x+bounds.width} y={bounds.y} radius={5/scale} fill={color} stroke="#201a20" strokeWidth={1.5/scale}/>}
                {mark.label&&<Text text={mark.label} x={bounds.x+5/scale} y={bounds.y+5/scale} fontSize={12/scale} fontStyle="bold" fill={color} shadowColor="#171317" shadowBlur={5/scale}/>}
              </Group>;
            })}
            {preview&&<Rect {...rect(preview)} stroke="#fff0ce" strokeWidth={2/scale} dash={[5/scale,4/scale]} listening={false}/>}
            {editable&&<><Rect ref={editor} {...rect(editable)} draggable fill="#ffffff12" stroke="#fff0ce" strokeWidth={2/scale}
              onDragEnd={updateEdited} onTransformEnd={updateEdited}/>
              <Transformer ref={transformer} rotateEnabled={false} flipEnabled={false} keepRatio={false} anchorSize={9/scale} borderStroke="#fff0ce"/></>}
          </Group>
        </Layer>
      </Stage>}
    </div>
    <div className={'viewer-controls'+(zooming?' changing':'')}>
      <span>{alt}</span>
      <div><button className="icon-button" aria-label={'Zoom out '+alt} disabled={view.zoom<=1} onClick={()=>zoom(view.zoom/1.25)}><Minus size={16}/></button>
        <span className="zoom-label">{Math.round(view.zoom*100)}%</span>
        <button className="icon-button" aria-label={'Zoom in '+alt} disabled={view.zoom>=12} onClick={()=>zoom(view.zoom*1.25)}><Plus size={16}/></button>
        <button className="icon-button" aria-label={'Fit '+alt} title="Fit image" onClick={()=>setView({zoom:1,x:0,y:0})}><Scan size={16}/></button>
        <button className="icon-button" title="Fullscreen" aria-label={'Fullscreen '+alt} onClick={()=>void fullscreen()}><Maximize size={16}/></button></div>
    </div>
    {fullError&&<div className="viewer-error" role="alert">{fullError}</div>}
  </div>;
}
