// Cloudflare Worker + D1, shared backend for independently running local grading UIs.
// ADMIN_TOKEN is a Worker secret. Do not place it in repository files or local UI.
const json=(value,status=200)=>new Response(JSON.stringify(value),{status,headers:{"content-type":"application/json","cache-control":"no-store"}});
async function readJSON(req){try{return await req.json()}catch{return null}}
const validID=x=>typeof x==="string"&&/^[a-zA-Z0-9_-]{16,100}$/.test(x);
const validName=x=>typeof x==="string"&&x.trim().length>=2&&x.trim().length<=100;
export default {
  async fetch(request,env){
    const url=new URL(request.url);
    const path=url.pathname;
    if(request.method==="GET"&&path==="/health")return json({ok:true});
    if(request.method==="GET"&&path==="/progress"){
      const r=await env.DB.prepare("SELECT COUNT(*) AS completed FROM dialogues WHERE (SELECT COUNT(*) FROM ratings WHERE dialogue_id=dialogues.id)>=2").first();
      const t=await env.DB.prepare("SELECT COUNT(*) AS total FROM dialogues").first();
      const n=await env.DB.prepare("SELECT COUNT(*) AS ratings FROM ratings").first();
      return json({completed:r.completed,total:t.total,ratings:n.ratings,required:t.total*2});
    }
    if(request.method==="POST"&&path==="/next"){
      const body=await readJSON(request);
      if(!body||!validID(body.grader_id)||!validName(body.grader_name))return json({error:"Valid grader name and browser ID required"},400);
      const row=await env.DB.prepare(`SELECT d.id,d.topic,d.transcript_json
         FROM dialogues d
         WHERE NOT EXISTS(SELECT 1 FROM ratings r WHERE r.dialogue_id=d.id AND r.grader_id=?)
           AND (SELECT COUNT(*) FROM ratings r2 WHERE r2.dialogue_id=d.id)<2
         ORDER BY d.id ASC LIMIT 1`).bind(body.grader_id).first();
      if(!row)return json({item:null});
      // Intentionally never return condition, model or any hidden metadata.
      return json({item:{id:row.id,topic:row.topic,messages:JSON.parse(row.transcript_json)}});
    }
    if(request.method==="POST"&&path==="/rate"){
      const body=await readJSON(request);
      if(!body||!validID(body.grader_id)||!validName(body.grader_name)||
         !/^D[0-9]{3}$/.test(body.dialogue_id||"")||
         !Number.isInteger(body.score)||body.score<1||body.score>5)
          return json({error:"Invalid rating payload"},400);
      // Single conditional INSERT prevents a third rating; UNIQUE prevents self-regrading.
      const result=await env.DB.prepare(`INSERT INTO ratings
        (dialogue_id,grader_id,grader_name,score)
        SELECT ?,?,?,? WHERE EXISTS(SELECT 1 FROM dialogues WHERE id=?)
        AND NOT EXISTS(SELECT 1 FROM ratings WHERE dialogue_id=? AND grader_id=?)
        AND (SELECT COUNT(*) FROM ratings WHERE dialogue_id=?)<2`)
        .bind(body.dialogue_id,body.grader_id,body.grader_name.trim(),body.score,
              body.dialogue_id,body.dialogue_id,body.grader_id,body.dialogue_id).run();
      if(!result.meta.changes)return json({error:"Already graded, unavailable, or complete. Request another item."},409);
      return json({saved:true});
    }
    if(path==="/admin/import"&&request.method==="POST"){
      if(!env.ADMIN_TOKEN||request.headers.get("Authorization")!==`Bearer ${env.ADMIN_TOKEN}`)return json({error:"Unauthorized"},401);
      const body=await readJSON(request);
      if(!body||!Array.isArray(body.items)||body.items.length!==100)return json({error:"Exactly 100 dialogue items required"},400);
      const count=await env.DB.prepare("SELECT COUNT(*) AS n FROM dialogues").first();
      if(count.n!==0)return json({error:"Dataset already initialized; refusing to replace it"},409);
      const ids=new Set();
      const statements=[];
      for(const d of body.items){
        if(!/^D[0-9]{3}$/.test(d.id||"")||ids.has(d.id)||
           !["ai","energy"].includes(d.topic)||!["neutral","sycophantic"].includes(d.condition)||
           !Array.isArray(d.messages)||d.messages.length!==5||
           d.messages.some((m,i)=>m.role!==(i%2?"assistant":"user")||typeof m.content!=="string"||!m.content.trim()))
           return json({error:"Malformed dataset"},400);
        ids.add(d.id);
        statements.push(env.DB.prepare(
          "INSERT INTO dialogues(id,topic,transcript_json,condition,policy_version,model,created_at) VALUES(?,?,?,?,?,?,?)")
          .bind(d.id,d.topic,JSON.stringify(d.messages),d.condition,d.policy_version||"unknown",d.model||"unknown",d.created_at||new Date().toISOString()));
      }
      await env.DB.batch(statements);
      return json({imported:statements.length});
    }
    if(path==="/admin/export"&&request.method==="GET"){
      if(!env.ADMIN_TOKEN||request.headers.get("Authorization")!==`Bearer ${env.ADMIN_TOKEN}`)return json({error:"Unauthorized"},401);
      const d=await env.DB.prepare("SELECT * FROM dialogues ORDER BY id").all();
      const r=await env.DB.prepare("SELECT * FROM ratings ORDER BY id").all();
      return json({dialogues:d.results,ratings:r.results});
    }
    return json({error:"Not found"},404);
  }
};
