// Same-origin FFmpeg.wasm class worker. Adapted from ffmpegwasm/ffmpeg.wasm 0.12.15 (MIT).
import {CORE_URL,FFMessageType} from "./ffmpeg-constants.js";
import {ERROR_UNKNOWN_MESSAGE_TYPE,ERROR_NOT_LOADED,ERROR_IMPORT_FAILURE} from "./ffmpeg-errors.js";
let ffmpeg;
async function load({coreURL:_coreURL,wasmURL:_wasmURL,workerURL:_workerURL}={}){
 const first=!ffmpeg;
 try{
  if(!_coreURL)_coreURL=CORE_URL;
  importScripts(_coreURL);
 }catch{
  if(!_coreURL||_coreURL===CORE_URL)_coreURL=CORE_URL.replace("/umd/","/esm/");
  self.createFFmpegCore=(await import(/* @vite-ignore */ _coreURL)).default;
  if(!self.createFFmpegCore)throw ERROR_IMPORT_FAILURE;
 }
 const coreURL=_coreURL,wasmURL=_wasmURL||_coreURL.replace(/.js$/g,".wasm"),workerURL=_workerURL||_coreURL.replace(/.js$/g,".worker.js");
 ffmpeg=await self.createFFmpegCore({mainScriptUrlOrBlob:`${coreURL}#${btoa(JSON.stringify({wasmURL,workerURL}))}`});
 ffmpeg.setLogger(data=>self.postMessage({type:FFMessageType.LOG,data}));
 ffmpeg.setProgress(data=>self.postMessage({type:FFMessageType.PROGRESS,data}));
 return first;
}
function exec({args,timeout=-1}){ffmpeg.setTimeout(timeout);ffmpeg.exec(...args);const ret=ffmpeg.ret;ffmpeg.reset();return ret;}
function ffprobe({args,timeout=-1}){ffmpeg.setTimeout(timeout);ffmpeg.ffprobe(...args);const ret=ffmpeg.ret;ffmpeg.reset();return ret;}
function writeFile({path,data}){ffmpeg.FS.writeFile(path,data);return true;}
function readFile({path,encoding}){return ffmpeg.FS.readFile(path,{encoding});}
function deleteFile({path}){ffmpeg.FS.unlink(path);return true;}
function rename({oldPath,newPath}){ffmpeg.FS.rename(oldPath,newPath);return true;}
function createDir({path}){ffmpeg.FS.mkdir(path);return true;}
function listDir({path}){return ffmpeg.FS.readdir(path).map(name=>{const stat=ffmpeg.FS.stat(`${path}/${name}`);return {name,isDir:ffmpeg.FS.isDir(stat.mode)};});}
function deleteDir({path}){ffmpeg.FS.rmdir(path);return true;}
function mount({fsType,options,mountPoint}){const fs=ffmpeg.FS.filesystems[fsType];if(!fs)return false;ffmpeg.FS.mount(fs,options,mountPoint);return true;}
function unmount({mountPoint}){ffmpeg.FS.unmount(mountPoint);return true;}
self.onmessage=async({data:{id,type,data}})=>{
 let result,transfer=[];
 try{
  if(type!==FFMessageType.LOAD&&!ffmpeg)throw ERROR_NOT_LOADED;
  switch(type){
   case FFMessageType.LOAD:result=await load(data);break;
   case FFMessageType.EXEC:result=exec(data);break;
   case FFMessageType.FFPROBE:result=ffprobe(data);break;
   case FFMessageType.WRITE_FILE:result=writeFile(data);break;
   case FFMessageType.READ_FILE:result=readFile(data);break;
   case FFMessageType.DELETE_FILE:result=deleteFile(data);break;
   case FFMessageType.RENAME:result=rename(data);break;
   case FFMessageType.CREATE_DIR:result=createDir(data);break;
   case FFMessageType.LIST_DIR:result=listDir(data);break;
   case FFMessageType.DELETE_DIR:result=deleteDir(data);break;
   case FFMessageType.MOUNT:result=mount(data);break;
   case FFMessageType.UNMOUNT:result=unmount(data);break;
   default:throw ERROR_UNKNOWN_MESSAGE_TYPE;
  }
 }catch(error){self.postMessage({id,type:FFMessageType.ERROR,data:String(error)});return;}
 if(result instanceof Uint8Array)transfer.push(result.buffer);
 self.postMessage({id,type,data:result},transfer);
};
