import { test, expect } from '@playwright/test'

const target = { id:'22222222-2222-4222-8222-222222222222', public_code:'staff000000000001',
  display_name:'Сотрудник для управления доступом', state:'active', verified:true, created_at:1000 }
const actor = { id:'11111111-1111-4111-8111-111111111111', public_code:'owner00000000001',
  display_name:'Владелец доступа', state:'active', email:'owner@example.invalid', email_verified:true,
  permissions:['users.read_limited','audit.read','access.read','access.manage'] }
const access = { permissions:actor.permissions,
  delegation_ceiling:['access.read','access.manage','plans.read','plans.write','catalog.read'],
  csrf_token:'access-csrf' }

function subject(permissions: {permission:string,expires_at:number|null,managed:boolean}[] = []) {
  return { ...target, permissions }
}

test.beforeEach(async({page})=>{
  await page.route('**/api/v1/foundation',r=>r.fulfill({json:{stage:'foundation',build_sha:'test',capabilities:[]}}))
  await page.route('**/api/v1/auth/me',r=>r.fulfill({json:{account:actor,csrf_token:'auth-csrf'}}))
  await page.route('**/api/v1/admin/access/me',r=>r.fulfill({json:access}))
  await page.route('**/api/v1/admin/users?*',r=>r.fulfill({json:{users:[target],next_after:null}}))
})

test('ACCESS-001 A-28 search, subject card and responsive scope-aware navigation',async({page},info)=>{
  await page.route('**/api/v1/admin/access/subjects/'+target.id,r=>r.fulfill({json:subject()}))
  await page.goto('/admin/access')
  await expect(page.getByRole('heading',{name:'Доступ персонала'})).toBeVisible()
  await expect(page.getByRole('link',{name:'Пользователи'})).toBeVisible()
  await expect(page.getByRole('link',{name:'Журнал действий'})).toBeVisible()
  await page.getByLabel('Имя или публичный код').fill(target.public_code)
  await page.getByRole('button',{name:'Найти'}).click()
  await page.getByRole('button',{name:'Управлять доступом'}).click()
  await expect(page.getByRole('heading',{name:target.display_name})).toBeVisible()
  await expect(page.getByText('scope:')).toBeVisible()
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true)
  await page.screenshot({path:info.outputPath('access-page.png'),fullPage:true})
})


test('ACCESS-001 uncertain grant retries the same operation and clears password',async({page})=>{
  let granted=false; const ids:string[]=[]
  await page.route('**/api/v1/admin/access/subjects/'+target.id,r=>r.fulfill({json:subject(granted ? [
    {permission:'plans.write',expires_at:5000,managed:true}] : [])}))
  let attempts=0
  await page.route('**/api/v1/admin/access/subjects/'+target.id+'/grants',async route=>{
    const body=route.request().postDataJSON(); ids.push(body.operation_id); attempts++
    expect(route.request().headers()['x-csrf-token']).toBe('access-csrf')
    expect(Object.keys(body).sort()).toEqual(['case_reference','current_password','operation_id','permission','scope','ttl_seconds'])
    if(attempts===1) return route.fulfill({status:503,json:{error:{code:'temporary'}}})
    granted=true
    return route.fulfill({json:{operation_id:body.operation_id,target_id:target.id,action:'grant',
      permission:'plans.write',scope:'global',expires_at:5000,case_reference:'ACCESS-42'}})
  })
  await page.goto('/admin/access')
  await page.getByLabel('UUID аккаунта').fill(target.id)
  await page.getByRole('button',{name:'Открыть'}).click()
  await page.getByLabel('Право').selectOption('plans.write')
  await page.getByLabel('Номер заявки').fill('ACCESS-42')
  await page.getByLabel('Текущий пароль').fill('synthetic-password')
  await page.getByRole('button',{name:'Выдать право'}).click()
  await expect(page.getByRole('alert')).toContainText('Результат операции неизвестен')
  await expect(page.getByLabel('Текущий пароль')).toHaveValue('')
  await page.getByLabel('Текущий пароль').fill('synthetic-password')
  await page.getByRole('button',{name:'Выдать право'}).click()
  await expect(page.locator('.admin-receipt')).toContainText('plans.write')
  expect(ids).toHaveLength(2); expect(ids[0]).toBe(ids[1])
  await expect(page.getByLabel('Текущий пароль')).toHaveValue('')
})


test('ACCESS-001 access-only staff navigation does not expose unrelated admin links',async({page})=>{
  const accessOnly={...actor,permissions:['access.read']}
  await page.route('**/api/v1/auth/me',r=>r.fulfill({json:{account:accessOnly,csrf_token:'auth'}}))
  await page.route('**/api/v1/admin/access/me',r=>r.fulfill({json:{permissions:['access.read'],delegation_ceiling:[],csrf_token:'access'}}))
  await page.route('**/api/v1/admin/access/subjects/'+target.id,r=>r.fulfill({json:subject([{permission:'access.read',expires_at:5000,managed:true}])}))
  await page.goto('/admin/access')
  await expect(page.getByRole('link',{name:'Доступ'})).toBeVisible()
  await expect(page.getByRole('link',{name:'Пользователи'})).toHaveCount(0)
  await expect(page.getByRole('link',{name:'Журнал действий'})).toHaveCount(0)
  await expect(page.locator('aside a.staff-link[href="/admin/access"]')).toHaveCount(1)
  await expect(page.locator('input[minlength="3"][maxlength="80"]')).toHaveCount(0)
  await page.locator('form.admin-search input').fill(target.id)
  await page.locator('form.admin-search button').click()
  await expect(page.locator('.admin-form')).toHaveCount(0)
})
