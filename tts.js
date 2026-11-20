"use strict";
const $=id=>document.getElementById(id);
const loadButton=$("loadTts"),generateButton=$("generateDub"),status=$("ttsStatus"),audioPlayer=$("dubPreview"),downloadLink=$("downloadDub");
const models={hi:"Xenova/mms-tts-hin",ar:"Xenova/mms-tts-ara",en:"Xenova/mms-tts-eng",fr:"Xenova/mms-tts-fra",es:"Xenova/mms-tts-spa",de:"Xenova/mms-tts-deu",pt:"Xenova/mms-tts-por",ru:"Xenova/mms-tts-rus"};
let synthesizer=null,loadedLanguage=null,busy=false,outputUrl=null;
function say(s){status.textContent=s;}
window.addEventListener("aslam:release-tts",()=>{synthesizer=null;loadedLanguage=null;generateButton.disabled=true;say("Voice model released to free phone memory for another AI stage. Load it again when needed.");});
function wavBlob(samples,sampleRate){
 const buffer=new ArrayBuffer(44+samples.length*2),view=new DataView(buffer);
 const write=(offset,value)=>{for(let i=0;i<value.length;i++)view.setUint8(offset+i,value.charCodeAt(i));};
 write(0,"RIFF");view.setUint32(4,36+samples.length*2,true);write(8,"WAVE");write(12,"fmt ");view.setUint32(16,16,true);view.setUint16(20,1,true);view.setUint16(22,1,true);view.setUint32(24,sampleRate,true);view.setUint32(28,sampleRate*2,true);view.setUint16(32,2,true);view.setUint16(34,16,true);write(36,"data");view.setUint32(40,samples.length*2,true);
 for(let i=0;i<samples.length;i++){const x=Math.max(-1,Math.min(1,samples[i]));view.setInt16(44+i*2,x<0?x*32768:x*32767,true);}
 return new Blob([buffer],{type:"audio/wav"});
}
loadButton.addEventListener("click",async()=>{
 if(window.aslamASRBusy||window.aslamASRLoading){say("Finish speech transcription before loading the voice model.");return;}
 window.dispatchEvent(new Event("aslam:release-asr"));
 const lang=$("targetLanguage").value,model=models[lang];
 if(!model){say("No bundled local TTS model for "+lang+". Choose Hindi, Arabic, English, French, Spanish, German, Portuguese or Russian.");return;}
 if(busy)return;busy=true;window.aslamTTSLoading=true;loadButton.disabled=true;generateButton.disabled=true;
 try{
  say("Loading local voice model for "+lang+"… First download may be large. The model runs on this phone.");
  const {pipeline}=await import("https://cdn.jsdelivr.net/npm/@huggingface/transformers@3.7.2");
  synthesizer=await pipeline("text-to-speech",model,{dtype:"q8",progress_callback:p=>{if(p?.status==="progress"&&Number.isFinite(p.progress))say("Downloading voice model: "+Math.round(p.progress)+"%");}});
  loadedLanguage=lang;say("Local voice model ready for "+lang+".");
 }catch(e){synthesizer=null;loadedLanguage=null;say("Voice model failed to load: "+(e?.message||"unknown error")+". Check connection, free storage and phone memory.");}
 finally{busy=false;window.aslamTTSLoading=false;loadButton.disabled=false;generateButton.disabled=!synthesizer;}
});
$("targetLanguage").addEventListener("change",()=>{if(loadedLanguage&&loadedLanguage!==$("targetLanguage").value){synthesizer=null;loadedLanguage=null;generateButton.disabled=true;say("Target language changed. Load the matching voice model.");}});
generateButton.addEventListener("click",async()=>{
 if(!synthesizer||loadedLanguage!==$("targetLanguage").value){say("Load the matching voice model first.");return;}
 const entries=[...$("lines").children].map((card,i)=>({start:window.aslamToMs(card.querySelector(".start").value),end:window.aslamToMs(card.querySelector(".end").value),text:card.querySelector(".translated").value.trim()||card.querySelector(".source").value.trim(),index:i+1})).filter(x=>x.text);
 if(!entries.length){say("No dialogue text to speak. Transcribe or enter dialogue first.");return;}
 const invalid=entries.find(x=>x.start===null||x.end===null||x.end<=x.start);if(invalid){say("Dialogue "+invalid.index+" has invalid timestamps. Set a valid start and an end time after it.");return;}
 const duration=Number.isFinite($("preview").duration)?$("preview").duration:Math.max(...entries.map(x=>x.start/1000))+120;
 if(duration>900){say("For phone memory safety, dubbed audio export is limited to 15 minutes per pass.");return;}
 busy=true;window.aslamTTSBusy=true;generateButton.disabled=true;loadButton.disabled=true;
 try{
  const rate=16000,total=Math.ceil(duration*rate),mix=new Float32Array(total);
  for(let i=0;i<entries.length;i++){
   const item=entries[i];say("Generating voice "+(i+1)+" / "+entries.length+"…");
   const result=await synthesizer(item.text);
   if(!result?.audio?.length)throw new Error("Voice model returned empty audio for dialogue "+item.index);
   const offset=Math.max(0,Math.round(item.start/1000*rate));
   const ratio=result.sampling_rate/rate;
   const length=Math.min(Math.ceil(result.audio.length/ratio),mix.length-offset);
   for(let j=0;j<length;j++){const p=j*ratio,a=Math.floor(p),b=Math.min(a+1,result.audio.length-1),f=p-a;mix[offset+j]+=result.audio[a]*(1-f)+result.audio[b]*f;}
  }
  for(let i=0;i<mix.length;i++)mix[i]=Math.max(-1,Math.min(1,mix[i]));
  const blob=wavBlob(mix,rate);if(outputUrl)URL.revokeObjectURL(outputUrl);outputUrl=URL.createObjectURL(blob);audioPlayer.src=outputUrl;audioPlayer.hidden=false;downloadLink.href=outputUrl;downloadLink.download="ASLAM-AI-dubbed-audio-"+loadedLanguage+".wav";downloadLink.hidden=false;say("Dubbed audio generated. Listen and review sync/voice quality before using it with the video.");
 }catch(e){say("Voice generation failed: "+(e?.message||"unknown error")+". Try shorter dialogue or a device with more memory.");}
 finally{busy=false;window.aslamTTSBusy=false;generateButton.disabled=!synthesizer;loadButton.disabled=false;}
});
