"use strict";
const $=id=>document.getElementById(id);
const button=$("renderMp4"),status=$("renderStatus"),player=$("renderedVideo"),download=$("downloadMp4");
let ffmpeg=null,loading=false,resultUrl=null,workspaceFiles=[];
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
   const base="https://cdn.jsdelivr.net/npm/@ffmpeg/core@0.12.10/dist/esm";
   await ffmpeg.load({classWorkerURL:new URL("/ffmpeg-worker.js",location.href).href,coreURL:await toBlobURL(base+"/ffmpeg-core.js","text/javascript"),wasmURL:await toBlobURL(base+"/ffmpeg-core.wasm","application/wasm")});
  }
  const video=selected||await fetch(previewSource).then(r=>r.blob());
  const audioResponse=await fetch(wav);
  if(!audioResponse.ok)throw new Error("Could not read the generated dubbed WAV audio.");
  const audioBlob=await audioResponse.blob();
  const maxVideoBytes=250*1024*1024,maxAudioBytes=150*1024*1024,maxCombinedBytes=300*1024*1024;
  if(video.size>maxVideoBytes)throw new Error("Video exceeds the 250 MB phone-safety limit. Use a shorter or more compressed video.");
  if(audioBlob.size>maxAudioBytes)throw new Error("Dubbed WAV exceeds the 150 MB phone-safety limit. Generate a shorter audio part.");
  if(video.size+audioBlob.size>maxCombinedBytes)throw new Error("Video and audio exceed the 300 MB combined phone-safety limit. Use a smaller video.");
  say("Reading files within phone-safety limits into browser memory…");
  const videoBytes=new Uint8Array(await video.arrayBuffer()),audioBytes=new Uint8Array(await audioBlob.arrayBuffer());
  const originalName=selected?.name||"video.mp4";
  const ext=(originalName.split(".").pop()||"mp4").toLowerCase().replace(/[^a-z0-9]/g,"");
  const inputName="source."+ext,outputName="aslam-ai-dubbed.mp4";
  workspaceFiles=[inputName,"dubbed.wav","subtitles.srt",outputName];
  await ffmpeg.writeFile(inputName,videoBytes);await ffmpeg.writeFile("dubbed.wav",audioBytes);
  const embed=$("embedSubtitles").checked&&typeof window.aslamBuildSrt==="function",srt=embed?window.aslamBuildSrt():"";
  if(srt.trim())await ffmpeg.writeFile("subtitles.srt",new TextEncoder().encode(srt));
  const inputs=srt.trim()?["-i",inputName,"-i","dubbed.wav","-i","subtitles.srt"]:["-i",inputName,"-i","dubbed.wav"];
  const subtitleMaps=srt.trim()?["-map","2:s:0","-c:s","mov_text"]:[];
  const mixMode=$("audioMixMode").value;let usedMix=mixMode==="mix";const quality=$("outputQuality")?.value||"original";const dimensions={720:[1280,720],1080:[1920,1080],2160:[3840,2160]}[quality];const scaleFilter=dimensions?"scale=w='min(iw,"+dimensions[0]+")':h='min(ih,"+dimensions[1]+")':force_original_aspect_ratio=decrease":"";const scaleArgs=dimensions?["-vf",scaleFilter]:[];const videoEncode=scaleArgs.length?[...scaleArgs,"-c:v","libx264","-preset","ultrafast","-crf","28"]:["-c:v","copy"];
  const audioMaps=mixMode==="mix"?["-filter_complex","[0:a:0]volume=0.20[bg];[1:a:0]volume=1.0[dub];[bg][dub]amix=inputs=2:duration=longest:dropout_transition=2[aout]","-map","[aout]"]:["-map","1:a:0"];
  say((mixMode==="mix"?"Mixing original sound quietly under dubbing":"Replacing original audio with dubbing")+(srt.trim()?" and embedding selectable subtitles":"")+" in the MP4 locally…");
  let maps=["-map","0:v:0",...audioMaps,...subtitleMaps];
  let args=[...inputs,...maps,...videoEncode,"-c:a","aac","-b:a","192k","-movflags","+faststart","-shortest",outputName];
  await ffmpeg.deleteFile(outputName).catch(()=>{});
  let code=await ffmpeg.exec(args);
  if(code!==0&&mixMode==="mix"){usedMix=false;say("Original audio stream could not be mixed; retrying with dubbed audio replacement…");maps=["-map","0:v:0","-map","1:a:0",...subtitleMaps];args=[...inputs,...maps,...videoEncode,"-c:a","aac","-b:a","192k","-movflags","+faststart","-shortest",outputName];await ffmpeg.deleteFile(outputName).catch(()=>{});code=await ffmpeg.exec(args);}
  if(code!==0){say("Trying H.264 re-encoding for MP4 compatibility…");args=[...inputs,...maps,...scaleArgs,"-c:v","libx264","-preset","ultrafast","-crf","28","-c:a","aac","-b:a","160k","-movflags","+faststart","-shortest",outputName];await ffmpeg.deleteFile(outputName).catch(()=>{});code=await ffmpeg.exec(args);}
  if(code!==0)throw new Error("FFmpeg exited with code "+code);
  const data=await ffmpeg.readFile(outputName),blob=new Blob([data],{type:"video/mp4"});
  if(resultUrl)URL.revokeObjectURL(resultUrl);resultUrl=URL.createObjectURL(blob);player.src=resultUrl;player.hidden=false;download.href=resultUrl;download.download="ASLAM-AI-Dubbed.mp4";download.hidden=false;
  say("MP4 rendered successfully in this browser. Original video track retained; "+(usedMix?"original audio mixed quietly under the dubbing.":"audio replaced by generated dubbing.")+" Review synchronization and sound before publishing.");
 }catch(e){say("MP4 render failed: "+(e?.message||"unknown error")+". This operation needs substantial free RAM/storage; try a shorter or smaller video. The original files remain unchanged.");}
 finally{if(ffmpeg)for(const name of workspaceFiles)await ffmpeg.deleteFile(name).catch(()=>{});workspaceFiles=[];loading=false;button.disabled=false;}
});
