import { expect, type APIRequestContext, type Locator, type Page } from '@playwright/test';

export async function expectIntegratedAppReady(request: APIRequestContext, baseURL?: string): Promise<void> {
  const health = await request.get('/api/health');
  expect(health.ok(), 'GET /api/health should return 2xx').toBeTruthy();

  const root = await request.get('/');
  expect(
    root.status(),
    `GET / should serve the integrated frontend from ${baseURL ?? 'the configured baseURL'}`,
  ).toBeLessThan(400);
}

export function byTestIdOrRole(
  page: Page,
  testId: string,
  role: Parameters<Page['getByRole']>[0],
  name: RegExp | string,
): Locator {
  return page.getByTestId(testId).or(page.getByRole(role, { name }));
}

export function byTestIdOrLabel(page: Page, testId: string, label: RegExp | string): Locator {
  return page.getByTestId(testId).or(page.getByLabel(label));
}

export function watchlist(page: Page): Locator {
  return page.getByTestId('watchlist');
}

export function tickerRow(page: Page, ticker: string): Locator {
  return page.getByTestId(`watchlist-row-${ticker}`);
}

export function positionsTable(page: Page): Locator {
  return page.getByTestId('positions-table');
}

export function positionRow(page: Page, ticker: string): Locator {
  return page.getByTestId(`position-row-${ticker}`);
}

export function cashBalance(page: Page): Locator {
  return page.getByTestId('cash-balance');
}

export function connectionStatus(page: Page): Locator {
  return page.getByTestId('connection-status');
}

export async function gotoApp(page: Page): Promise<void> {
  await page.goto('/');
  await expect(page.getByTestId('app-shell'), 'frontend should be hydrated before UI interactions').toHaveAttribute(
    'data-hydrated',
    'true',
  );
  await expect(watchlist(page), 'watchlist panel should render').toBeVisible();
}

export async function addTicker(page: Page, ticker: string): Promise<void> {
  const input = page.getByTestId('watchlist-symbol-input');
  await input.fill(ticker);
  await input.press('Enter');
}

export async function removeTicker(page: Page, ticker: string): Promise<void> {
  await page.getByTestId(`remove-${ticker}`).press('Enter');
}

export async function submitTrade(page: Page, side: 'buy' | 'sell', ticker: string, quantity: string): Promise<void> {
  await page.getByTestId('trade-symbol-input').fill(ticker);
  await page.getByTestId('trade-quantity-input').fill(quantity);
  await page.getByTestId(`${side}-button`).click();
}

export async function waitForSsePriceEvents(page: Page, minimumEvents = 2): Promise<void> {
  const eventCount = await page.evaluate(
    ({ minimumEvents: needed }) =>
      new Promise<number>((resolve, reject) => {
        const source = new EventSource('/api/stream/prices');
        let count = 0;
        const timeout = window.setTimeout(() => {
          source.close();
          reject(new Error(`Timed out waiting for ${needed} SSE price events; received ${count}`));
        }, 8_000);

        const handlePriceEvent = () => {
          count += 1;
          if (count >= needed) {
            window.clearTimeout(timeout);
            source.close();
            resolve(count);
          }
        };
        source.addEventListener('prices', handlePriceEvent);

        source.onerror = () => {
          if (source.readyState === EventSource.CLOSED) {
            window.clearTimeout(timeout);
            reject(new Error('SSE price stream closed before enough price events arrived'));
          }
        };
      }),
    { minimumEvents },
  );

  expect(eventCount).toBeGreaterThanOrEqual(minimumEvents);
}
