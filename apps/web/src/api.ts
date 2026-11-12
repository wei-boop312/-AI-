export class ApiError extends Error { constructor(public status:number,public code:string){super(code)} }
export const csrf=()=>document.cookie.split('; ').find(x=>x.startsWith('visual_csrf='))?.split('=').slice(1).join('=')||'';
let refreshing:Promise<boolean>|null=null;
async function refresh(){
 if(!refreshing) refreshing=fetch('/api/v1/auth/refresh',{method:'POST',credentials:'same-origin',headers:{'X-CSRF-Token':csrf()}}).then(r=>r.ok).finally(()=>{refreshing=null});
 return refreshing;
}
export async function api<T>(path:string,options:RequestInit={},retry=true):Promise<T>{
 const unsafe=options.method && !['GET','HEAD'].includes(options.method);
 const response=await fetch('/api/v1'+path,{...options,credentials:'same-origin',headers:{...(options.body?{'Content-Type':'application/json'}:{}),...(unsafe?{'X-CSRF-Token':csrf()}:{}),...options.headers}});
 if(response.status===401 && retry && !['/auth/login','/auth/refresh','/auth/logout'].includes(path) && await refresh()) return api<T>(path,options,false);
 if(!response.ok){let code='request_failed';try{code=(await response.json()).error?.code||code}catch{};throw new ApiError(response.status,code)}
 return response.status===204?undefined as T:response.json();
}
export const post=<T>(path:string,body?:unknown,headers?:Record<string,string>)=>api<T>(path,{method:'POST',body:body===undefined?undefined:JSON.stringify(body),headers});
export const errors:Record<string,string>={invalid_credentials:'账号或密码不正确',authentication_required:'登录已过期，请重新登录',login_rate_limited:'尝试次数较多，请稍后再试',insufficient_credits:'可用积分不足',quote_expired:'报价已过期，请重新确认',quote_input_mismatch:'配置已变化，请重新获取报价',idempotency_conflict:'提交配置冲突，请重新确认',already_started:'任务已开始，暂不支持取消',decoder_capacity:'图片校验繁忙，请稍后重试',invalid_image:'图片格式、大小或内容不符合要求',validation_temporarily_unavailable:'图片校验暂不可用，可重新完成上传',revision_conflict:'内容已更新，请刷新后重试',dependency_unavailable:'服务暂不可用，请稍后重试',not_found:'内容不存在或没有访问权限',source_unavailable:'原图版本不可用',pixel_exact_size_mismatch:'精确保护需要与原图尺寸一致',csrf_rejected:'登录状态已变化，请刷新页面',origin_rejected:'访问地址与服务配置不一致'};
export function errorText(error:unknown){return error instanceof ApiError?(errors[error.code]||'操作未完成，请重试（'+error.code+'）'):error instanceof Error?error.message:'操作未完成，请重试'}
export type User={id:string,email:string,display_name:string};
export type Product={id:string,name:string,category:string,revision:number,archived_at:string|null};
export type AssetVersion={version_id:string,asset_id:string,width:number,height:number,sha256:string,canonical:boolean};
export type Task={id:string,product_id:string,source:{asset_id:string,version_id:string},status:'queued'|'processing'|'succeeded'|'failed'|'cancelled'|'uncertain',phase:string,revision:number,credits:{status:string,amount:number},created_at:string,error_code:string|null,result:null|{asset_version_id:string,sha256:string,width:number,height:number,download_endpoint:string,report_id:string},compliance:null|{auto_overall:string,report_id:string}};
export type Page<T>={items:T[],next_cursor:string|null};
export type Balance={available:number,reserved:number,funded_total:number,spent_total:number};
export type Region={source_x:number,source_y:number,width:number,height:number,target_x:number,target_y:number};
export type Generation={type:'white_background'|'scene'|'lifestyle',prompt:string,output:{width:number,height:number,format:'png'},protection_mode:'pixel_exact'|'none',regions:Region[]};
export type Business={product_id:string,source_asset_version_id:string,appearance_profile_id?:string,generation:Generation,targets:{platform:string,marketplace:string,category:string,image_type:string}[]};
