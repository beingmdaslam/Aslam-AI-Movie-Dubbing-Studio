"use strict";
const $=id=>document.getElementById(id);
const loadButton=$("loadTts"),generateButton=$("generateDub"),status=$("ttsStatus"),audioPlayer=$("dubPreview"),downloadLink=$("downloadDub");
const mmsModels={hi:"Xenova/mms-tts-hin",ar:"Xenova/mms-tts-ara",en:"Xenova/mms-tts-eng",fr:"Xenova/mms-tts-fra",es:"Xenova/mms-tts-spa",de:"Xenova/mms-tts-deu",pt:"Xenova/mms-tts-por",ru:"Xenova/mms-tts-rus",ur:"payam1394/traxlate-mms-tts-urd"};
const supertonicLanguages=new Set(["en","ko","ja","ar","bg","cs","da","de","el","es","et","fi","fr","hi","hr","hu","id","it","lt","lv","nl","pl","pt","ro","ru","sk","sl","sv","tr","uk","vi"]);
const supertonicRevision="aafc6e32416a594460b32413efc49d7fe4ce6d46";
const supertonicRoot="https://huggingface.co/supertone-oss-archive/supertonic-3/resolve/"+supertonicRevision;
const supertonicOnnx=supertonicRoot+"/onnx";
let synthesizer=null,loadedLanguage=null,loadedEngine=null,busy=false,outputUrl=null;
let supertonic=null,supertonicHelper=null,voiceCache=new Map(),ortScriptPromise=null,supertonicBackend="";
function say(s){status.textContent=s;}
function wavBlob(samples,sampleRate){
 const buffer=new ArrayBuffer(44+samples.length*2),view=new DataView(buffer);
 const write=(offset,value)=>{for(let i=0;i<value.length;i++)view.setUint8(offset+i,value.charCodeAt(0));};
 write(0,"RIFF");view.setUint32(4,36+samples.length*2,true);write(8,"WAVE");write(12,"fmt ");view.setUint32(16,16,true);view.setUint16(20,1,true);view.setUint16(22,1,true);view.setUint32(24,sampleRate,true);view.setUint32(28,sampleRate*2,true);view.setUint16(32,2,true);view.setUint16(34,16,true);write(36,"data");view.setUint32(40,samples.length*2,true);
 for(let i=0;i<samples.length;i++){const x=Math.max(-1,Math.min(1,samples[i]));view.setInt16(44+i*2,x<0?x*32768:x*32767,true);}
 return new Blob([buffer],{type:"audio/wav"});
}
async function loadOrtRuntime(){
 if(window.ort)return window.ort;
 if(!ortScriptPromise)ortScriptPromise=new Promise((resolve,reject)=>{
  const script=document.createElement("script");
  script.src="https://cdn.jsdelivr.net/npm/onnxruntime-web@1.17.0/dist/ort.webgpu.min.js";
  script.crossOrigin="anonymous";
  script.onload=()=>window.ort?resolve(window.ort):reject(new Error("ONNX Runtime Web loaded without its global API."));
  script.onerror=()=>reject(new Error("Could not download ONNX Runtime Web."));
  document.head.append(script);
 });
 const ort=await ortScriptPromise;
 ort.env.wasm.wasmPaths="https://cdn.jsdelivr.net/npm/onnxruntime-web@1.17.0/dist/";
 ort.env.wasm.numThreads=1;
 return ort;
}
async function loadSupertonic(){
 const ort=await loadOrtRuntime();
 const helper=await import("./supertonic-helper.js");
 say("Loading Supertonic 3 multilingual model (~400 MB). WebGPU is tried first; this may take several minutes.");
 let loaded;
 try{
  loaded=await helper.loadTextToSpeech(supertonicOnnx,{executionProviders:["webgpu"],graphOptimizationLevel:"all"},(name,current,total)=>say("Supertonic WebGPU: loading "+name+" ("+current+"/"+total+")"));
  supertonicBackend="WebGPU";
 }catch(webgpuError){
  say("WebGPU is unavailable for this phone/browser. Loading the CPU/WASM model instead…");
  ort.env.wasm.numThreads=1;
  loaded=await helper.loadTextToSpeech(supertonicOnnx,{executionProviders:["wasm"],graphOptimizationLevel:"all"},(name,current,total)=>say("Supertonic WASM: loading "+name+" ("+current+"/"+total+")"));
  supertonicBackend="WASM";
 }
 supertonic=loaded.textToSpeech;supertonicHelper=helper;voiceCache.clear();
}
async function loadVoiceStyle(name){
 if(voiceCache.has(name))return voiceCache.get(name);
 const style=await supertonicHelper.loadVoiceStyle([supertonicRoot+"/voice_styles/"+name+".json"],true);
 voiceCache.set(name,style);return style;
}
async function releaseSupertonic(){
 if(supertonic){
  const sessions=[supertonic.dpOrt,supertonic.textEncOrt,supertonic.vectorEstOrt,supertonic.vocoderOrt];
  await Promise.all(sessions.map(session=>session?.release?.().catch(()=>{})));
 }
 supertonic=null;supertonicHelper=null;voiceCache.clear();supertonicBackend="";
}
async function releaseTTSForOtherStage(){
 if(busy)return false;
 synthesizer=null;loadedLanguage=null;loadedEngine=null;generateButton.disabled=true;
 await releaseSupertonic();
 say("Voice model released to free phone memory for another AI stage. Load it again when needed.");
 return true;
}
window.aslamReleaseTTS=releaseTTSForOtherStage;
window.addEventListener("aslam:release-tts",()=>{releaseTTSForOtherStage().catch(()=>{});});
$("ttsEngine").addEventListener("change",()=>{
 if(busy)return;
 synthesizer=null;loadedLanguage=null;loadedEngine=null;generateButton.disabled=true;
 releaseSupertonic().catch(()=>{});
 say("Voice engine changed. Load the selected local voice engine.");
});
loadButton.addEventListener("click",async()=>{
 if(window.aslamASRBusy||window.aslamASRLoading){say("Finish speech transcription before loading the voice model.");return;}
 if(busy)return;
 const engine=$("ttsEngine").value,lang=$("targetLanguage").value;
 if(loadedEngine===engine&&loadedLanguage&&(engine==="supertonic"?!!supertonic:!!synthesizer)){say("The selected local voice model is already loaded.");return;}
 if(engine==="mms"&&!mmsModels[lang]){say("No MMS voice model is available for "+lang+". Select another language or use Supertonic 3 if it supports your language.");return;}
 if(engine==="supertonic"&&!supertonicLanguages.has(lang)){say("Supertonic 3 does not support "+lang+". Use MMS where available or choose one of its 31 supported languages.");return;}
 if(engine==="supertonic"&&!window.confirm("Supertonic 3 downloads about 400 MB of model files on first use. It runs on this phone and provides 10 preset voice styles. Continue?"))return;
 window.dispatchEvent(new Event("aslam:release-asr"));
 busy=true;window.aslamTTSLoading=true;loadButton.disabled=true;generateButton.disabled=true;
 try{
  if(engine==="supertonic"){
   synthesizer=null;await releaseSupertonic();await loadSupertonic();loadedLanguage=lang;loadedEngine=engine;
   say("Supertonic 3 ready on "+supertonicBackend+". Choose M1–M5 or F1–F5 for each character.");
  }else{
   await releaseSupertonic();
   say("Loading local MMS voice model for "+lang+"… First download may be large. This model is for non-commercial use only.");
   const {pipeline}=await import("https://cdn.jsdelivr.net/npm/@huggingface/transformers@3.8.1");
   synthesizer=await pipeline("text-to-speech",mmsModels[lang],{dtype:"q8",progress_callback:p=>{if(p?.status==="progress"&&Number.isFinite(p.progress))say("Downloading MMS voice model: "+Math.round(p.progress)+"%");}});
   loadedLanguage=lang;loadedEngine=engine;say("Local MMS voice model ready for "+lang+". It uses one voice style for all speakers.");
  }
 }catch(e){synthesizer=null;loadedLanguage=null;loadedEngine=null;await releaseSupertonic();say("Voice model failed to load: "+(e?.message||"unknown error")+". Check connection, free storage and phone memory.");}
 finally{busy=false;window.aslamTTSLoading=false;loadButton.disabled=false;generateButton.disabled=!(synthesizer||supertonic);}
});
$("targetLanguage").addEventListener("change",()=>{
 const lang=$("targetLanguage").value;
 if(loadedEngine==="supertonic"&&supertonicLanguages.has(lang)){loadedLanguage=lang;say("Supertonic 3 is ready for "+lang+".");return;}
 if(loadedLanguage&&loadedLanguage!==lang){synthesizer=null;loadedLanguage=null;loadedEngine=null;generateButton.disabled=true;say("Target language changed. Load the matching voice model.");}
});
generateButton.addEventListener("click",async()=>{
 if(busy)return;
 const engine=$("ttsEngine").value,lang=$("targetLanguage").value;
 if(engine!==loadedEngine||!loadedLanguage||(engine==="mms"&&loadedLanguage!==lang)||!((engine==="mms"&&synthesizer)||(engine==="supertonic"&&supertonic))){say("Load the matching voice model first.");return;}
 const entries=[...$("lines").children].map((card,i)=>({start:window.aslamToMs(card.querySelector(".start").value),end:window.aslamToMs(card.querySelector(".end").value),text:card.querySelector(".translated").value.trim()||card.querySelector(".source").value.trim(),speaker:card.querySelector(".speaker").value.trim()||"Speaker "+(i+1),voice:card.querySelector(".speakerVoice")?.value||"M1",index:i+1})).filter(x=>x.text);
 if(!entries.length){say("No dialogue text to speak. Transcribe or enter dialogue first.");return;}
 const invalid=entries.find(x=>x.start===null||x.end===null||x.end<=x.start);if(invalid){say("Dialogue "+invalid.index+" has invalid timestamps. Set a valid start and an end time after it.");return;}
 if(engine==="supertonic"&&!supertonicLanguages.has(lang)){say("This language is not supported by Supertonic 3. Choose MMS or another supported language.");return;}
 const duration=Number.isFinite($("preview").duration)?$("preview").duration:Math.max(...entries.map(x=>x.end/1000))+10;
 const maxDuration=engine==="supertonic"?300:900;if(duration>maxDuration){say("For phone memory safety, this voice engine is limited to "+(maxDuration/60)+" minutes per pass. Split longer videos into shorter parts.");return;}
 busy=true;window.aslamTTSBusy=true;generateButton.disabled=true;loadButton.disabled=true;
 try{
  const rate=engine==="supertonic"?supertonic.sampleRate:16000,total=Math.ceil(duration*rate),mix=new Float32Array(total);
  for(let i=0;i<entries.length;i++){
   const item=entries[i];say("Generating voice "+(i+1)+" / "+entries.length+" for "+item.speaker+"…");
   let audio,sampleRate;
   if(engine==="supertonic"){
    const style=await loadVoiceStyle(item.voice);
    const result=await supertonic.call(item.text,lang,style,8,1.05,0.12,(step,steps)=>say("Supertonic "+item.speaker+": dialogue "+(i+1)+"/"+entries.length+", quality step "+step+"/"+steps));
    sampleRate=supertonic.sampleRate;audio=result.wav.slice(0,Math.floor(sampleRate*result.duration[0]));
   }else{
    const result=await synthesizer(item.text);
    if(!result?.audio?.length)throw new Error("Voice model returned empty audio for dialogue "+item.index);
    sampleRate=result.sampling_rate;audio=result.audio;
   }
   if(!audio?.length)throw new Error("Voice model returned empty audio for dialogue "+item.index);
   const offset=Math.max(0,Math.round(item.start/1000*rate)),ratio=sampleRate/rate;
   const length=Math.min(Math.ceil(audio.length/ratio),mix.length-offset);
   for(let j=0;j<length;j++){const p=j*ratio,a=Math.floor(p),b=Math.min(a+1,audio.length-1),f=p-a;mix[offset+j]+=audio[a]*(1-f)+audio[b]*f;}
  }
  for(let i=0;i<mix.length;i++)mix[i]=Math.max(-1,Math.min(1,mix[i]));
  const blob=wavBlob(mix,rate);if(outputUrl)URL.revokeObjectURL(outputUrl);outputUrl=URL.createObjectURL(blob);audioPlayer.src=outputUrl;audioPlayer.hidden=false;downloadLink.href=outputUrl;downloadLink.download="ASLAM-AI-dubbed-audio-"+lang+".wav";downloadLink.hidden=false;say("Dubbed audio generated with "+(engine==="supertonic"?"Supertonic 3 ("+supertonicBackend+")":"MMS")+". Review voice assignments, timing and sound before rendering MP4.");
 }catch(e){say("Voice generation failed: "+(e?.message||"unknown error")+". Try shorter dialogue or a device with more memory.");}
 finally{busy=false;window.aslamTTSBusy=false;generateButton.disabled=!(synthesizer||supertonic);loadButton.disabled=false;}
});
