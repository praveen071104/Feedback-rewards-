import { expect, test } from '@playwright/test'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const screenshots = fileURLToPath(new URL('../../docs/screenshots/', import.meta.url))
const appreciation = 'I was really struggling to get the pista cookies for the past few days considering everybody loves it. The stock runs out whenever I visit the store. Thankfully, Mr. Joe helped me with the timings when the product will be restocked and I was finally able to get it today for my niece who loves it.'

test('live reward recommendations and responsive screenshots', async ({ page }) => {
  const exceptions: string[] = []
  page.on('pageerror', error => exceptions.push(error.message))
  await page.goto('/')
  for (const [sample, sentiment, decision] of [
    ['Store improvement', 'Negative', 'Eligible'],
    ['Helpful service', 'Positive', 'Eligible'],
    ['Mixed experience', 'Neutral', 'Eligible'],
    ['Generic praise', 'Positive', 'Not eligible'],
  ]) {
    await page.getByLabel('Sample feedback').selectOption(sample)
    await expect(page.getByRole('heading', { name: 'Awaiting feedback analysis', exact: true })).toBeVisible()
    await page.getByRole('button', { name: 'Analyse feedback', exact: true }).click()
    await expect(page.getByRole('heading', { name: decision, exact: true })).toBeVisible()
    if (sample !== 'Generic praise') await expect(page.locator('.sentiment')).toHaveText(sentiment)
    await expect(page.getByRole('meter')).toHaveCount(2)
    await expect(page.locator('blockquote')).toHaveText(await page.getByLabel('Customer feedback', { exact: true }).inputValue())
  }
  for (const feedback of ['Hi', 'Hello', 'Thank you very much', 'qwerty asdfgh zxcvbn']) {
    await page.getByLabel('Customer feedback', { exact: true }).fill(feedback)
    await page.getByRole('button', { name: 'Analyse feedback', exact: true }).click()
    await expect(page.getByRole('heading', { name: 'Not eligible', exact: true })).toBeVisible()
    await expect(page.locator('.genuine-label')).toHaveText('No')
    await expect(page.locator('.explanation')).toContainText('minimum-detail rule')
  }
  for (const feedback of [appreciation, `Hi! ${appreciation} Thank you!`]) {
    await page.getByLabel('Customer feedback', { exact: true }).fill(feedback)
    await page.getByRole('button', { name: 'Analyse feedback', exact: true }).click()
    await expect(page.getByRole('heading', { name: 'Eligible', exact: true })).toBeVisible()
    await expect(page.locator('.genuine-label')).toHaveText('Yes')
    await expect(page.locator('blockquote')).toHaveText(feedback)
  }
  for (const feedback of [
    'The cakes are really good but always sold out. Would be nice if it can be stocked frequently.',
    'The bakery items are fresh, but most popular products are already sold out by evening. It would help if stock is replenished more frequently.',
    'cakes sold out by 5pm',
    'cakes sold out. please restock before lunch',
    'cakes always soldout pls restock',
  ]) {
    await page.getByLabel('Customer feedback', { exact: true }).fill(feedback)
    await page.getByRole('button', { name: 'Analyse feedback', exact: true }).click()
    await expect(page.getByRole('heading', { name: 'Eligible', exact: true })).toBeVisible()
    await expect(page.locator('.genuine-label')).toHaveText('Yes')
    await expect(page.locator('.explanation')).toContainText('stock-feedback rule')
  }
  for (const feedback of ['cakes sold out', 'nice cakes but no stock', 'The bakery items are sold out.', 'pls restock bread']) {
    await page.getByLabel('Customer feedback', { exact: true }).fill(feedback)
    await page.getByRole('button', { name: 'Analyse feedback', exact: true }).click()
    await expect(page.getByRole('heading', { name: 'Not eligible', exact: true })).toBeVisible()
    await expect(page.locator('.genuine-label')).toHaveText('No')
    await expect(page.locator('.explanation')).toContainText('alone is too generic')
  }
  await page.getByRole('button', { name: 'Clear feedback' }).click()
  await expect(page.getByRole('button', { name: 'Analyse feedback', exact: true })).toBeDisabled()
  await page.getByLabel('Customer feedback', { exact: true }).fill('123!')
  await expect(page.getByRole('button', { name: 'Analyse feedback', exact: true })).toBeDisabled()
  await page.getByLabel('Sample feedback').selectOption('Store improvement')
  await page.getByRole('button', { name: 'Analyse feedback', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Eligible', exact: true })).toBeVisible()
  for (const width of [320, 390, 768, 1440]) {
    await page.setViewportSize({ width, height: 1000 })
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
    const input = await page.locator('.input-section').boundingBox()
    const result = await page.locator('.result-section').boundingBox()
    expect(input).not.toBeNull()
    expect(result).not.toBeNull()
    if (width >= 768) expect(result!.x).toBeGreaterThan(input!.x)
    else expect(result!.y).toBeGreaterThan(input!.y)
  }
  await page.screenshot({ path: path.join(screenshots, 'desktop.png'), fullPage: true })
  await page.setViewportSize({ width: 390, height: 844 })
  await page.screenshot({ path: path.join(screenshots, 'mobile.png'), fullPage: true })
  expect(exceptions).toEqual([])
})

test('loading lock, server error, and successful retry', async ({ page }) => {
  await page.goto('/')
  let releaseRequest!: () => void
  const holdRequest = new Promise<void>(resolve => { releaseRequest = resolve })
  await page.route('**/api/predict', async route => {
    await holdRequest
    await route.fulfill({ status: 503, contentType: 'application/json', body: '{"detail":"Models unavailable"}' })
  })
  await page.getByRole('button', { name: 'Analyse feedback', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Analysing feedback...' })).toBeDisabled()
  await expect(page.getByLabel('Customer feedback', { exact: true })).toBeDisabled()
  releaseRequest()
  await expect(page.getByRole('alert')).toContainText('Models are unavailable')
  await page.unroute('**/api/predict')
  await page.getByRole('button', { name: 'Analyse feedback', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Eligible', exact: true })).toBeVisible()
})