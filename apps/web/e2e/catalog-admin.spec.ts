import { test, expect, type Page } from '@playwright/test'

const actor={id:'11111111-1111-4111-8111-111111111111',public_code:'aaaabbbbccccdddd',display_name:'Catalog operator',state:'active',email:'catalog@example.invalid',email_verified:true,
  permissions:['catalog.read','catalog.write','pricing.write','connections.read','connections.write','secrets.bind']}
const revision=(id:string,n:number,hash:string)=>({id,revision:n,content_hash:hash.repeat(64).slice(0,64),created_at:1789000000})

async function fixture(page:Page, permissions=actor.permissions){
  let model:any={capability_id:'openrouter.image.v1',version:1,draft:revision('11111111-2222-4333-8444-555555555555',1,'a'),published:null,
    content:{name:'OpenRouter image',help:'Тест metadata',adapter_id:'openrouter.images.v1',model_id:'google/gemini-2.5-flash-image',connection_id:'openrouter-primary',resolutions:['512'],price_credits:3},runtime_available:false}
  let connection:any={connection_id:'openrouter-primary',version:2,draft:revision('22222222-2222-4333-8444-555555555555',1,'b'),published:null,
    content:{provider_id:'openrouter',endpoint:'https://openrouter.ai/api/v1/images',account_ref:'test-account',project_ref:'test-project',environment:'test',max_concurrency:1,rate_limit:10,rate_window_seconds:60,spend_cap_minor:100,currency:'USD',timeout_seconds:180,allow_fallbacks:false},runtime_state:'disabled',credential:null}
  let credential:any=null, bindFailures=0
  const requests:{path:string;method:string;body:any}[]=[]
  await page.route('**/api/v1/**',async route=>{
    const req=route.request(),url=new URL(req.url()),path=url.pathname,body=req.postData()?req.postDataJSON():null
    requests.push({path,method:req.method(),body})
    const json=(value:any,status=200)=>route.fulfill({status,json:value})
    const error=(code:string,status=409)=>json({error:{code}},status)
    if(path==='/api/v1/foundation')return json({stage:'foundation',build_sha:'unreleased',capabilities:[]})
    if(path==='/api/v1/auth/me')return json({account:{...actor,permissions},csrf_token:'catalog-csrf'})
    if(req.method()==='POST'){
      expect(req.headers()['x-csrf-token']).toBe('catalog-csrf')
      expect(req.headers()['x-izo-request']).toBe('web')
    }
    if(path==='/api/v1/admin/catalog/providers')return permissions.includes('connections.read')?json({items:[{provider_id:'openrouter',adapter_id:'openrouter.images.v1',endpoint:'https://openrouter.ai/api/v1/images',live_enabled:false}]}):error('forbidden',403)
    if(path==='/api/v1/admin/catalog/models'&&req.method()==='GET')return permissions.includes('catalog.read')?json({items:[model]}):error('forbidden',403)
    if(path==='/api/v1/admin/catalog/models/openrouter.image.v1'&&req.method()==='GET')return json(model)
    if(path==='/api/v1/admin/catalog/connections'&&req.method()==='GET')return permissions.includes('connections.read')?json({items:[connection]}):error('forbidden',403)
    if(path==='/api/v1/admin/catalog/connections/openrouter-primary'&&req.method()==='GET')return json(connection)
    if(path==='/api/v1/admin/catalog/connections/openrouter-primary/credential'&&req.method()==='GET')return credential?json(credential):error('credential_unavailable',404)
    if(path.endsWith('/models/openrouter.image.v1/draft')){model={...model,version:model.version+1,draft:revision('33333333-2222-4333-8444-555555555555',model.version+1,'c'),content:{name:body.name,help:body.help,adapter_id:body.adapter_id,model_id:body.model_id,connection_id:body.connection_id,resolutions:body.resolutions,price_credits:body.price_credits}};return json({operation_id:body.operation_id,action:'capability.draft',target:model.capability_id,result_version:model.version,result_id:model.draft.id})}
    if(path.endsWith('/models/openrouter.image.v1/proof'))return json({proof_id:'44444444-2222-4333-8444-555555555555',capability_id:model.capability_id,connection_id:'openrouter-primary',capability_hash:model.draft.content_hash,connection_hash:connection.draft?.content_hash??connection.published.content_hash,credential_version:1,evidence_hash:'d'.repeat(64),proof_kind:'contract',network_called:false,live_ready:false,created_at:1789000000})
    if(path.endsWith('/connections/openrouter-primary/publish')){connection={...connection,version:connection.version+1,published:connection.draft,draft:null};return json({operation_id:body.operation_id,action:'connection.publish',target:'openrouter-primary',result_version:connection.version,result_id:connection.published.id})}
    if(path.endsWith('/models/openrouter.image.v1/publish')){model={...model,version:model.version+1,published:model.draft,draft:null};return json({operation_id:body.operation_id,action:'capability.publish',target:model.capability_id,result_version:model.version,result_id:model.published.id})}
    if(path.endsWith('/connections/openrouter-primary/draft')){connection={...connection,version:connection.version+1,draft:revision('55555555-2222-4333-8444-555555555555',connection.version+1,'e'),content:{provider_id:'openrouter',endpoint:'https://openrouter.ai/api/v1/images',account_ref:body.account_ref,project_ref:body.project_ref,environment:body.environment,max_concurrency:body.max_concurrency,rate_limit:body.rate_limit,rate_window_seconds:body.rate_window_seconds,spend_cap_minor:body.spend_cap_minor,currency:'USD',timeout_seconds:body.timeout_seconds,allow_fallbacks:body.allow_fallbacks}};return json({operation_id:body.operation_id,action:'connection.draft',target:'openrouter-primary',result_version:connection.version,result_id:connection.draft.id})}
    if(path.endsWith('/connections/openrouter-primary/credentials')&&req.method()==='POST'){
      if(bindFailures++===0)return error('temporary',503)
      connection={...connection,version:connection.version+1};credential={binding_id:'66666666-2222-4333-8444-555555555555',version:1,source_type:body.source_type,reference_fingerprint:'f'.repeat(64),environment:body.environment,account_ref:body.account_ref,project_ref:body.project_ref,state:'active',created_at:1789000000,revoked_at:null};return json(credential)
    }
    if(path.endsWith('/credentials/revoke')){credential=null;connection={...connection,version:connection.version+1};return json({operation_id:body.operation_id,action:'credential.revoke',target:'openrouter-primary',result_version:connection.version,result_id:null})}
    return error('not_found',404)
  })
  return {requests,get model(){return model},get connection(){return connection},get credential(){return credential}}
}

test('CATALOG UI A-08 list is available to catalog-only staff without user-admin permission',async({page},info)=>{
  await fixture(page,['catalog.read'])
  await page.goto('/admin/models')
  await expect(page.getByRole('heading',{name:'Модели'})).toBeVisible()
  await expect(page.getByText('OpenRouter image')).toBeVisible()
  await expect(page.getByRole('link',{name:'Администрирование'})).toHaveAttribute('href','/admin/models')
  await expect(page.getByRole('link',{name:'Пользователи'})).toHaveCount(0)
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true)
  await page.screenshot({path:info.outputPath('catalog-models.png'),fullPage:true})
})

test('CATALOG UI A-09 proof publishes metadata in order and never claims live readiness',async({page})=>{
  const app=await fixture(page)
  await page.goto('/admin/models/openrouter.image.v1')
  await page.getByLabel('Основание изменения').fill('Проверка публикации metadata')
  await page.getByRole('button',{name:'Проверить контракт без сети'}).click()
  const proof=page.locator('.catalog-receipt')
  await expect(proof).toContainText('Network called')
  await expect(proof).toContainText('Live ready')
  await expect(proof.getByText('Нет', { exact: true })).toHaveCount(2)
  await page.getByRole('button',{name:'Опубликовать metadata подключения'}).click()
  await expect(page.getByText('Connection metadata опубликована; runtime всё равно disabled.')).toBeVisible()
  await page.getByRole('button',{name:'Опубликовать metadata модели'}).click()
  await expect(page.getByText('Опубликована metadata')).toBeVisible()
  expect(app.requests.some(r=>r.path.includes('openrouter.ai'))).toBe(false)
  await expect(page.getByRole('button',{name:/включить live/i})).toHaveCount(0)
})

test('CATALOG UI A-11 connection draft has fixed endpoint and bounded server payload',async({page})=>{
  const app=await fixture(page)
  await page.goto('/admin/providers/openrouter/connections/openrouter-primary')
  await expect(page.getByText('https://openrouter.ai/api/v1/images')).toBeVisible()
  await expect(page.getByLabel(/endpoint/i)).toHaveCount(0)
  await page.getByLabel('Max concurrency').fill('2')
  await page.getByLabel('Основание изменения').fill('Изменение лимита тестового подключения')
  await page.getByRole('button',{name:'Сохранить новую draft revision'}).click()
  const sent=app.requests.filter(r=>r.path.endsWith('/connections/openrouter-primary/draft')&&r.method==='POST').at(-1)!.body
  expect(sent.max_concurrency).toBe(2)
  expect(sent.endpoint).toBeUndefined();expect(sent.runtime_state).toBeUndefined();expect(sent.api_key).toBeUndefined()
})

test('CATALOG UI A-12 never accepts raw key and uncertain bind retries same operation',async({page})=>{
  const app=await fixture(page)
  await page.goto('/admin/credentials/openrouter-primary')
  await expect(page.getByText(/Значение API-ключа не вводится/)).toBeVisible()
  await expect(page.getByLabel(/api.?ключ/i)).toHaveCount(0)
  await page.getByLabel('Основание привязки').fill('Привязка test source')
  await page.getByLabel('Текущий пароль для привязки').fill('synthetic-password')
  await page.getByRole('button',{name:'Создать привязку'}).click()
  await expect(page.getByRole('alert')).toContainText('Ответ сервера неизвестен')
  await expect(page.getByLabel('Текущий пароль для привязки')).toHaveValue('')
  await page.getByLabel('Текущий пароль для привязки').fill('synthetic-password')
  await page.getByRole('button',{name:'Создать привязку'}).click()
  await expect(page.getByTestId('credential-fingerprint')).toContainText('ffffffffffffffff')
  const calls=app.requests.filter(r=>r.path.endsWith('/connections/openrouter-primary/credentials')&&r.method==='POST')
  expect(calls).toHaveLength(2);expect(calls[0].body.operation_id).toBe(calls[1].body.operation_id)
  for(const call of calls){expect(call.body.api_key).toBeUndefined();expect(call.body.secret).toBeUndefined();expect(call.body.secret_ref).toBe('IZO_OPENROUTER_API_KEY')}
})

test('CATALOG UI credential page fails closed without secrets.bind and performs no metadata read',async({page})=>{
  const app=await fixture(page,['connections.read','connections.write'])
  await page.goto('/admin/credentials/openrouter-primary')
  await expect(page.getByRole('alert')).toContainText('Нужны отдельные')
  expect(app.requests.filter(r=>r.path.endsWith('/credential'))).toHaveLength(0)
  await expect(page.getByText(/Reference fingerprint/)).toHaveCount(0)
})
