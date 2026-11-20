"use strict";
const $=id=>document.getElementById(id);
const button=$("renderMp4"),status=$("renderStatus"),player=$("renderedVideo"),download=$("downloadMp4");
let ffmpeg=null,loading=false,resultUrl=null;
function say(s){status.textContent=s;}
button.addEventListener("click",async()=>{
 const selected=$("videoFile").files?.[0],previewSource=$("preview").src,wav=$("downloadDub").href;
 if(!selected&&!previewSource){say("Choose the original video file first.");return;}
 if(!$("downloadDub").href||$("downloadDub").hidden){say("Generate dubbed WAV audio first.");return;}
 if(loading)return;loading=true;button.disabled=true;
 try{
  if(!ffmpeg){
   say("Loading free FFmpeg WebAssembly engine… First use downloads the engine files.");
   const {FFmpeg}=await import("https://cdn.jsdelivr.net/npm/@ffmpeg/ffmpeg@0.12.15/dist/esm/index.js");
   const {toBlobURL}=await import("https://cdn.jsdelivr.net/npm/@ffmpeg/util@0.12.2/dist/esm/index.js");
   ffmpeg=new FFmpeg();
   ffmpeg.on("log",({message})=>{if(message)say("Rendering: "+message.slice(-180));});
   const base="https://cdn.jsdelivr.net/npm/@ffmpeg/core@0.12.10/dist/umd";
   await ffmpeg.load({coreURL:await toBlobURL(base+"/ffmpeg-core.js","text/javascript"),wasmURL:await toBlobURL(base+"/ffmpeg-core.wasm","application/wasm")});
  }
  say("Reading original video and dubbed WAV into browser memory…");
  const video=selected||await fetch(previewSource).then(r=>r.blob());
  const videoBytes=new Uint8Array(await video.arrayBuffer()),audioResponse=await fetch(wav),audioBytes=new Uint8Array(await audioResponse.arrayBuffer());
  const originalName=selected?.name||"video.mp4";
  const ext=(originalName.split(".").pop()||"mp4").toLowerCase().replace(/[^a-z0-9]/g,"");
  const inputName="source."+ext,outputName="aslam-ai-dubbed.mp4";
  await ffmpeg.writeFile(inputName,videoBytes);await ffmpeg.writeFile("dubbed.wav",audioBytes);
  say("Replacing original audio with the generated dubbed WAV. Video is processed on this device…");
  let code=await ffmpeg.exec(["-i",inputName,"-i","dubbed.wav","-map","0:v:0","-map","1:a:0","-c:v","copy","-c:a","aac","-b:a","192k","-movflags","+faststart","-shortest",outputName]);
  if(code!==0){say("Copying the original video codec did not work. Trying H.264 re-encoding…");code=await ffmpeg.exec(["-i",inputName,"-i","dubbed.wav","-map","0:v:0","-map","1:a:0","-c:v","libx264","-preset","ultrafast","-crf","28","-c:a","aac","-b:a","160k","-movflags","+faststart","-shortest",outputName]);}
  if(code!==0)throw new Error("FFmpeg exited with code "+code);
  const data=await ffmpeg.readFile(outputName),blob=new Blob([data],{type:"video/mp4"});
  if(resultUrl)URL.revokeObjectURL(resultUrl);resultUrl=URL.createObjectURL(blob);player.src=resultUrl;player.hidden=false;download.href=resultUrl;download.download="ASLAM-AI-Dubbed.mp4";download.hidden=false;
  say("MP4 rendered successfully in this browser. Original video track retained; audio replaced by generated dubbing. Review synchronization and sound before publishing.");
  for(const name of [inputName,"dubbed.wav",outputName])await ffmpeg.deleteFile(name).catch(()=>{});
 }catch(e){say("MP4 render failed: "+(e?.message||"unknown error")+". This operation needs substantial free RAM/storage; try a shorter or smaller video. The original files remain unchanged.");}
 finally{loading=false;button.disabled=false;}
});
