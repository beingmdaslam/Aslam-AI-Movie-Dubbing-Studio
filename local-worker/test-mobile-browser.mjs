import { chromium } from "playwright";
import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import { extname, resolve } from "node:path";

const root=process.cwd();
const inputPath=process.argv[2];
if(!inputPath)throw new Error("Usage: node local-worker/test-mobile-browser.mjs <test-video.mp4>");
const types={".html":"text/html; charset=utf-8",".js":"text/javascript; charset=utf-8",".mjs":"text/javascript; charset=utf-8",".css":"text/css; charset=utf-8",".svg":"image/svg+xml",".webmanifest":"application/manifest+json"};
const server=createServer(async(req,res)=>{
 try{
  const pathname=decodeURIComponent(new URL(req.url,"http://127.0.0.1").pathname);
  const file=resolve(root,"."+pathname);
  if(!file.startsWith(root))throw new Error("Invalid path");
  const body=await readFile(file);
  res.writeHead(200,{"content-type":types[extname(file)]||"application/octet-stream","cache-control":"no-store"});
  res.end(body);
 }catch{res.writeHead(404);res.end("Not found");}
});
await new Promise(resolve=>server.listen(4173,"127.0.0.1",resolve));
const browser=await chromium.launch({headless:true,args:["--no-sandbox","--disable-dev-shm-usage"]});
try{
 const page=await browser.newPage();
 const errors=[];
 page.on("pageerror",e=>errors.push(e.message));
 page.on("console",msg=>{if(msg.type()==="error")errors.push("console: "+msg.text());});
 await page.goto("http://127.0.0.1:4173/mobile-studio.html",{waitUntil:"domcontentloaded"});
 await page.locator("#videoFile").setInputFiles(inputPath);
 await page.waitForFunction(()=>document.querySelector("#videoFile").files.length===1,null,{timeout:10000});
 await page.evaluate(()=>{
  const rate=16000,count=rate,buffer=new ArrayBuffer(44+count*2),view=new DataView(buffer);
  const put=(o,t)=>{for(let i=0;i<t.length;i++)view.setUint8(o+i,t.charCodeAt(i));};
  put(0,"RIFF");view.setUint32(4,36+count*2,true);put(8,"WAVE");put(12,"fmt ");view.setUint32(16,16,true);view.setUint16(20,1,true);view.setUint16(22,1,true);view.setUint32(24,rate,true);view.setUint32(28,rate*2,true);view.setUint16(32,2,true);view.setUint16(34,16,true);put(36,"data");view.setUint32(40,count*2,true);
  for(let i=0;i<count;i++)view.setInt16(44+i*2,Math.round(Math.sin(2*Math.PI*440*i/rate)*5000),true);
  const url=URL.createObjectURL(new Blob([buffer],{type:"audio/wav"}));
  const link=document.querySelector("#downloadDub");link.href=url;link.hidden=false;
  document.querySelector("#audioMixMode").value="replace";
  document.querySelector("#embedSubtitles").checked=false;
  document.querySelector("#outputQuality").value="720";
 });
 await page.locator("#renderMp4").click();
 await page.waitForFunction(()=>{
  const text=document.querySelector("#renderStatus").textContent;
  return text.includes("MP4 rendered successfully")||text.includes("MP4 render failed");
 },null,{timeout:240000});
 const result=await page.evaluate(async()=>{
  const link=document.querySelector("#downloadMp4");
  if(link.hidden||!link.href)return {size:0,type:""};
  const blob=await (await fetch(link.href)).blob();
  return {size:blob.size,type:blob.type};
 });
 const status=await page.locator("#renderStatus").textContent();
 if(!status.includes("MP4 rendered successfully"))throw new Error("Browser MP4 render failed: "+status+"; page errors: "+errors.join(" | "));
 if(result.size<1000||result.type!=="video/mp4")throw new Error("Rendered MP4 output is invalid: "+JSON.stringify(result));
 if(errors.length)throw new Error("Browser JavaScript errors: "+errors.join(" | "));
 console.log("Mobile browser render passed:",JSON.stringify(result),status);
}finally{
 await browser.close();
 await new Promise(resolve=>server.close(resolve));
}
