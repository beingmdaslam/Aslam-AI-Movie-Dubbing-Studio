"use strict";
const $=id=>document.getElementById(id);
const source=$("sourceLanguage"),target=$("targetLanguage"),status=$("translationStatus");
const runAll=$("translateAll"),detect=$("detectSource");
const tags={en:"en",hi:"hi",ar:"ar",ur:"ur",fr:"fr",es:"es",de:"de",tr:"tr",pt:"pt",zh:"zh",ja:"ja",ru:"ru"};
const engines=new Map();
const langName={en:"English",hi:"Hindi",ar:"Arabic",ur:"Urdu",fr:"French",es:"Spanish",de:"German",tr:"Turkish",pt:"Portuguese",zh:"Chinese",ja:"Japanese",ru:"Russian"};
function say(s){status.textContent=s;}
async function getTranslator(src,dst){
 if(!("Translator" in self))throw new Error("This browser does not provide the built-in on-device Translator API. Try a supported Chrome version/device, or enter translations manually.");
 const key=src+":"+dst;if(engines.has(key))return engines.get(key);
 const availability=await Translator.availability({sourceLanguage:src,targetLanguage:dst});
 if(availability==="unavailable")throw new Error("This browser has no translation model for "+src+" → "+dst+".");
 const translator=await Translator.create({sourceLanguage:src,targetLanguage:dst,monitor(m){m.addEventListener("downloadprogress",e=>say("Downloading browser language pack: "+Math.round(e.loaded*100)+"%"));}});
 engines.set(key,translator);return translator;
}
async function detectLanguage(text){
 if(!("LanguageDetector" in self))return null;
 const detector=await LanguageDetector.create({});const results=await detector.detect(text);detector.destroy?.();
 if(!(results?.[0]?.confidence>0.5))return null;
 const detected=String(results[0].detectedLanguage||"").trim();
 const base=detected.split("-")[0].toLowerCase();
 return tags[base]?base:(detected||null);
}
function lineSource(card){return card.querySelector(".source").value.trim()||card.querySelector(".translated").value.trim();}
async function translateCard(card){
 let text=lineSource(card);if(!text)throw new Error("Dialogue "+([...$("lines").children].indexOf(card)+1)+" has no original text.");
 let src=source.value;
 if(src==="auto"){const detected=await detectLanguage(text);if(!detected)throw new Error("Could not detect source language. Select it manually.");src=detected;}
 else src=tags[src]||src;
 const dst=tags[target.value]||target.value;
 if(src===dst){card.querySelector(".translated").value=text;return;}
 const engine=await getTranslator(src,dst);const output=await engine.translate(text);
 if(!output?.trim())throw new Error("No translation returned.");
 card.querySelector(".translated").value=output;card.querySelector(".translated").dispatchEvent(new Event("input",{bubbles:true}));
}
$("lines").addEventListener("click",async e=>{
 const button=e.target.closest("[data-translate-line]");if(!button)return;
 const card=button.closest(".line");button.disabled=true;button.textContent="TRANSLATING…";
 try{await translateCard(card);say("Dialogue translated. Review the result.");}
 catch(err){say(err.message||"Translation failed.");}
 finally{button.disabled=false;button.textContent="TRANSLATE";}
});
runAll.addEventListener("click",async()=>{
 const cards=[...$("lines").children];if(!cards.length){say("Add or transcribe dialogue first.");return;}
 runAll.disabled=true;let done=0;
 try{for(const card of cards){await translateCard(card);done++;say("Translated "+done+" / "+cards.length+" dialogue lines…");}say("Translation complete. Review every line before exporting subtitles.");}
 catch(err){say("Stopped after "+done+" lines. "+(err.message||"Translation failed."));}
 finally{runAll.disabled=false;}
});
detect.addEventListener("click",async()=>{
 const first=[...$("lines").children].map(lineSource).find(Boolean);
 if(!first){say("Transcribe or enter a dialogue line first.");return;}
 try{const detected=await detectLanguage(first);if(!detected)throw new Error("Language detection is not available in this browser.");const match=Object.entries(tags).find(([,v])=>v===detected);if(match)source.value=match[0];say("Detected language: "+(langName[source.value]||detected)+". Check it before translating.");}
 catch(e){say(e.message||"Language detection failed.");}
});
say("Translation uses the browser's built-in on-device language models when supported. Availability varies by browser and language pair; unsupported pairs are not silently sent to a third party.");
