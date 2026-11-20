"use strict";
const el=id=>document.getElementById(id);
const load=el("loadAsr"),run=el("transcribeVideo"),status=el("asrStatus"),video=el("preview");
let transcriber=null,loading=false,processing=false,audioContext=null,mediaSource=null;
const languages={en:"english",hi:"hindi",ar:"arabic",ur:"urdu",fr:"french",es:"spanish",de:"german",tr:"turkish",pt:"portuguese",zh:"chinese",ja:"japanese"};
function say(s){status.textContent=s;}
window.addEventListener("aslam:release-asr",()=>{if(loading||processing){say("Finish the current speech task before loading another AI model.");return;}transcriber=null;run.disabled=true;if(audioContext){audioContext.close().catch(()=>{});audioContext=null;mediaSource=null;}say("Whisper model released to free phone memory for another AI stage. Load it again when needed.");});
load.addEventListener("click",async()=>{
 if(window.aslamTTSBusy||window.aslamTTSLoading){say("Finish the current voice task before loading Whisper.");return;}
 window.dispatchEvent(new Event("aslam:release-tts"));
 if(loading||transcriber)return;
 loading=true;window.aslamASRLoading=true;load.disabled=true;say("Loading browser AI runtime…");
 try{
  const {pipeline,env}=await import("https://cdn.jsdelivr.net/npm/@huggingface/transformers@3.7.2");
  env.allowLocalModels=false;env.useBrowserCache=true;
  transcriber=await pipeline("automatic-speech-recognition","Xenova/whisper-tiny",{dtype:"q8",progress_callback:p=>{
   if(p?.status==="progress"&&Number.isFinite(p.progress))say("Downloading Whisper model: "+Math.round(p.progress)+"%. First download may be large.");
   else if(p?.status==="initiate")say("Preparing model: "+(p.file||"model component"));
  }});
  say("Whisper Tiny loaded. Ready to transcribe on this device.");run.disabled=false;
 }catch(e){say("Model load failed: "+(e?.message||"unknown error")+". Check internet, browser storage and retry.");}
 finally{loading=false;window.aslamASRLoading=false;load.disabled=false;}
});
function format(ms){const h=Math.floor(ms/3600000);ms%=3600000;const m=Math.floor(ms/60000);ms%=60000;const s=Math.floor(ms/1000),z=ms%1000;return [h,m,s].map(v=>String(v).padStart(2,"0")).join(":")+","+String(z).padStart(3,"0");}
function resample(input,from,to=16000){
 const n=Math.floor(input.length*to/from),out=new Float32Array(n),step=from/to;
 for(let i=0;i<n;i++){const p=i*step,a=Math.floor(p),b=Math.min(a+1,input.length-1),f=p-a;out[i]=input[a]*(1-f)+input[b]*f;}
 return out;
}
function capture(context,node,start,duration){
 const target=Math.ceil(duration*context.sampleRate);
 return new Promise((resolve,reject)=>{
  let blocks=[],count=0,done=false;
  const finish=()=>{if(done)return;done=true;video.pause();node.onaudioprocess=null;const data=new Float32Array(count);let offset=0;for(const b of blocks){const n=Math.min(b.length,count-offset);data.set(b.subarray(0,n),offset);offset+=n;if(offset===count)break;}resolve(data);};
  node.onaudioprocess=e=>{
   const input=e.inputBuffer,n=Math.min(input.length,target-count),mono=new Float32Array(n);
   for(let ch=0;ch<input.numberOfChannels;ch++){const d=input.getChannelData(ch);for(let i=0;i<n;i++)mono[i]+=d[i]/input.numberOfChannels;}
   if(n){blocks.push(mono);count+=n;}
   for(let ch=0;ch<e.outputBuffer.numberOfChannels;ch++)e.outputBuffer.getChannelData(ch).fill(0);
   if(count>=target||video.ended)finish();
  };
  const begin=()=>video.play().catch(reject);
  video.currentTime=start;
  if(video.readyState>=2)begin();else video.addEventListener("seeked",begin,{once:true});
 });
}
run.addEventListener("click",async()=>{
 if(!transcriber)return say("Load Whisper model first.");
 if(!video.src||!Number.isFinite(video.duration)||video.duration<=0)return say("Select a video with an audio track first.");
 const existing=[...document.querySelectorAll("#lines .line")];if(existing.some(card=>card.querySelector(".source").value.trim()||card.querySelector(".translated").value.trim()))return say("Remove or export existing dialogue lines before transcription to avoid duplicate entries.");existing.forEach(card=>card.remove());
 const AC=window.AudioContext||window.webkitAudioContext;if(!AC)return say("Web Audio is not supported in this browser.");
 run.disabled=true;load.disabled=true;processing=true;window.aslamASRBusy=true;
 let ctx,src,node,gain,oldMuted=video.muted;
 try{
  ctx=audioContext||new AC();audioContext=ctx;await ctx.resume();src=mediaSource||ctx.createMediaElementSource(video);mediaSource=src;node=ctx.createScriptProcessor(4096,2,1);gain=ctx.createGain();gain.gain.value=0;src.connect(node);node.connect(gain);gain.connect(ctx.destination);video.muted=false;
  const total=video.duration,step=25,found=[];let cursor=0;
  while(cursor<total){
   const span=Math.min(step,total-cursor);say("Capturing audio "+format(cursor*1000)+" … "+format((cursor+span)*1000));
   const raw=await capture(ctx,node,cursor,span);if(!raw.length)break;
   const audio=resample(raw,ctx.sampleRate);
   say("Whisper is recognizing "+format(cursor*1000)+" …");
   const language=el("sourceLanguage").value,opts={sampling_rate:16000,return_timestamps:true};
   if(languages[language])opts.language=languages[language];
   const result=await transcriber(audio,opts),chunks=Array.isArray(result?.chunks)?result.chunks:[];
   if(chunks.length){for(const part of chunks){const text=(part.text||"").trim();if(!text)continue;const t=part.timestamp||[0,span],a=cursor+(Number(t[0])||0),b=cursor+(Number(t[1])||span);found.push({start:a,end:Math.max(a+.5,b),text});}}
   else if(result?.text?.trim())found.push({start:cursor,end:cursor+span,text:result.text.trim()});
   cursor+=span;say("Recognized "+Math.min(cursor,total).toFixed(0)+" / "+total.toFixed(0)+" seconds; "+found.length+" segments.");
  }
  video.pause();video.currentTime=0;
  found.sort((a,b)=>a.start-b.start);
  for(const item of found)window.addLine(format(Math.round(item.start*1000)),format(Math.round(item.end*1000)),item.text,"");
  say(found.length?"Transcription complete: "+found.length+" segments added. Review the text/timestamps, then export SRT.":"No speech was detected. Confirm this video has an audio track.");
 }catch(e){video.pause();say("Transcription failed: "+(e?.message||"unknown error")+". Long videos may exceed phone/browser memory.");}
 finally{video.muted=oldMuted;if(node){node.disconnect();node.onaudioprocess=null;}if(src)src.disconnect();if(gain)gain.disconnect();processing=false;window.aslamASRBusy=false;run.disabled=!transcriber;load.disabled=false;}
});
