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
  const embed=$("embedSubtitles").checked&&typeof window.aslamBuildSrt==="function",srt=embed?window.aslamBuildSrt():"";
  if(srt.trim())await ffmpeg.writeFile("subtitles.srt",new TextEncoder().encode(srt));
  const inputs=srt.trim()?["-i",inputName,"-i","dubbed.wav","-i","subtitles.srt"]:["-i",inputName,"-i","dubbed.wav"];
  const subtitleMaps=srt.trim()?["-map","2:s:0","-c:s","mov_text"]:[];
  const mixMode=$("audioMixMode").value;
  const audioMaps=mixMode==="mix"?["-filter_complex","[0:a:0]volume=0.20[bg];[1:a:0]volume=1.0[dub];[bg][dub]amix=inputs=2:duration=longest:dropout_transition=2[aout]","-map","[aout]"]:["-map","1:a:0"];
  say((mixMode==="mix"?"Mixing original sound quietly under dubbing":"Replacing original audio with dubbing")+(srt.trim()?" and embedding selectable subtitles":"")+" in the MP4 locally…");
  let maps=["-map","0:v:0",...audioMaps,...subtitleMaps];
  let args=[...inputs,...maps,"-c:v","copy","-c:a","aac","-b:a","192k","-movflags","+faststart","-shortest",outputName];
  let code=await ffmpeg.exec(args);
  if(code!==0&&mixMode==="mix"){say("Original audio stream could not be mixed; retrying with dubbed audio replacement…");maps=["-map","0:v:0","-map","1:a:0",...subtitleMaps];args=[...inputs,...maps,"-c:v","copy","-c:a","aac","-b:a","192k","-movflags","+faststart","-shortest",outputName];code=await ffmpeg.exec(args);}
  if(code!==0){say("Trying H.264 re-encoding for MP4 compatibility…");args=[...inputs,...maps,"-c:v","libx264","-preset","ultrafast","-crf","28","-c:a","aac","-b:a","160k","-movflags","+faststart","-shortest",outputName];code=await ffmpeg.exec(args);}
  if(code!==0)throw new Error("FFmpeg exited with code "+code);
  const data=await ffmpeg.readFile(outputName),blob=new Blob([data],{type:"video/mp4"});
  if(resultUrl)URL.revokeObjectURL(resultUrl);resultUrl=URL.createObjectURL(blob);player.src=resultUrl;player.hidden=false;download.href=resultUrl;download.download="ASLAM-AI-Dubbed.mp4";download.hidden=false;
  say("MP4 rendered successfully in this browser. Original video track retained; audio replaced by generated dubbing. Review synchronization and sound before publishing.");
  for(const name of [inputName,"dubbed.wav","subtitles.srt",outputName])await ffmpeg.deleteFile(name).catch(()=>{});
 }catch(e){say("MP4 render failed: "+(e?.message||"unknown error")+". This operation needs substantial free RAM/storage; try a shorter or smaller video. The original files remain unchanged.");}
 finally{loading=false;button.disabled=false;}
});
